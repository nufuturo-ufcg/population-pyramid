#!/usr/bin/env python
"""Gera as figuras e os números da pirâmide por linguagem, para revisão humana.

    GHAPI_DIR=data/ghapi .venv/bin/python scripts/figuras_linguagem.py

Roda o pipeline com `analysis.unit: language` num `config/` e num `output/` de
rascunho, e copia o que sai para `docs/linguagem/`, que é versionado. O objetivo
é alguém olhar a figura e conferir o número sem precisar rodar nada.

O `settings.yaml` publicado descreve a replicação MSR14, que acaba em 2013. Aqui
a janela vem da própria coleta, arredondada para fim de trimestre civil, que é a
âncora da série (`docs/replicacao/discrepancias.md`, seção 8).

Não altera `config/` nem `output/`.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DESTINO = ROOT / "docs" / "linguagem"


def _janela(raiz_coleta: Path) -> dict:
    """Série trimestral que cobre a coleta, ancorada em fim de trimestre civil."""
    import pandas as pd

    datas = []
    for nome in ("commits.jsonl", "issues.jsonl"):
        arquivo = next(raiz_coleta.rglob(nome), None)
        if arquivo is None:
            continue
        with arquivo.open(encoding="utf-8") as f:
            for linha in f:
                if not linha.strip():
                    continue
                item = json.loads(linha)
                quando = item.get("created_at") or (item.get("commit") or {}).get("author", {}).get(
                    "date"
                )
                if quando:
                    datas.append(pd.Timestamp(quando).tz_localize(None))
    if not datas:
        raise SystemExit(f"nenhuma data encontrada em {raiz_coleta}")
    inicio = (min(datas) + pd.offsets.QuarterEnd(0)).normalize()
    fim = (max(datas) - pd.offsets.QuarterEnd(1)).normalize()
    serie = pd.date_range(inicio, fim, freq="QE")
    if len(serie) < 4:
        raise SystemExit(f"a coleta cobre {len(serie)} trimestres, pouco para uma série")
    return {
        "start": str(serie[0].date()),
        "end": str(serie[-1].date()),
        "classification_snapshot": str(serie[-1].date()),
        "projection_base": [str(serie[-3].date()), str(serie[-2].date())],
        "projection_target": str(serie[-1].date()),
    }


def _scratch(raiz_coleta: Path) -> Path:
    scratch = Path(tempfile.mkdtemp(prefix="pyr_lang_fig_"))
    shutil.copytree(ROOT / "config", scratch / "config")
    alvo = scratch / "config" / "settings.yaml"
    cfg = yaml.safe_load(alvo.read_text(encoding="utf-8"))
    cfg["input"]["adapter"] = "ghapi"
    cfg["analysis"]["unit"] = "language"
    cfg["snapshots"].update(_janela(raiz_coleta))
    alvo.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return scratch


def gera(raiz_coleta: Path) -> dict:
    """Roda o pipeline e devolve os números. Dentro do subprocesso."""
    scratch = _scratch(raiz_coleta)

    from pyramid import config

    config.CONFIG_DIR = scratch / "config"
    config.OUTPUT_DIR = scratch / "output"
    config.LOG_DIR = scratch / "logs"
    config.settings.cache_clear()
    config.checkpoints.cache_clear()

    from pyramid import logging_config

    logging_config.LOG_DIR = config.LOG_DIR

    import pandas as pd

    from pyramid import classify, extract, metrics, plots, snapshots

    for estagio in (extract, classify, snapshots, metrics):
        res = estagio.run(None, force=True, fail_fast=True)
        if res.get("failed"):
            raise SystemExit(f"{estagio.STAGE} falhou: {res['failed']}")

    DESTINO.mkdir(parents=True, exist_ok=True)
    figuras = DESTINO / "figuras"
    if figuras.exists():
        shutil.rmtree(figuras)
    figuras.mkdir()

    t = snapshots.classification_snapshot()
    meta = extract.scope_meta()
    saida: dict = {
        "janela": config.settings()["snapshots"],
        "coleta": json.loads((raiz_coleta / "_coleta.json").read_text(encoding="utf-8"))
        if (raiz_coleta / "_coleta.json").exists()
        else {},
        "escopos": {},
        "serie": {},
    }

    tabela = metrics.table(t)
    for sid, m in sorted(meta.items(), key=lambda kv: -int(kv[1].get("membros", 1))):
        linha = tabela[tabela["scope_id"] == sid]
        eventos = extract.load_events(sid)
        spans = classify.load(sid)
        saida["escopos"][m["label"]] = {
            "scope_id": sid,
            "repositorios": m.get("membros", 1),
            "eventos": len(eventos),
            "contribuidores": int(eventos["contributor_id"].nunique()),
            "primeiro_evento": str(eventos["timestamp"].min()),
            "ultimo_evento": str(eventos["timestamp"].max()),
            "por_tipo": eventos["event_type"].value_counts().to_dict(),
            "plotavel": bool(m.get("plotavel", True)),
            "no_snapshot": {}
            if linha.empty
            else {
                "coding": int(linha["coding"].iloc[0]),
                "non_coding": int(linha["non_coding"].iloc[0]),
                "new": int(linha["new"].iloc[0]),
                "experienced": int(linha["experienced"].iloc[0]),
                "ccr": round(float(linha["ccr"].iloc[0]), 4),
                "ncr": round(float(linha["ncr"].iloc[0]), 4),
                "tipo": None if pd.isna(linha["type"].iloc[0]) else str(linha["type"].iloc[0]),
                "spans": len(spans),
            },
        }
        if m.get("plotavel", True):
            png = plots.figure_pyramid(sid, t)
            shutil.copy(png, figuras / f"piramide_{m['label'].replace(' ', '_')}.png")
            # A figura desenha a população de `plots.pyramid_window_months` (12
            # meses), e o CCR/NCR usa `periods.inactivity_months` (3). São duas
            # janelas diferentes de propósito, fixadas pela medição em pixel da
            # Fig.2 do ESEM14 (seção 19 e seção 40 das discrepâncias). Quem olha
            # a figura e a tabela lado a lado precisa dos dois números.
            frame = plots.pyramid_frame(snapshots.load(sid), t)
            saida["escopos"][m["label"]]["na_figura"] = {
                "janela_meses": float(config.settings()["plots"]["pyramid_window_months"]),
                "non_coding": int(frame["non_coding"].sum()) if not frame.empty else 0,
                "coding": int((frame["coding"] + frame["moved"]).sum()) if not frame.empty else 0,
                "bandas": len(frame),
            }

    # A série completa de CCR e NCR, para ver a população mudar no tempo.
    todos = metrics.load_all()
    for sid, g in todos.groupby("scope_id"):
        rotulo = extract.label_of(int(sid))
        saida["serie"][rotulo] = [
            {
                "snapshot": str(pd.Timestamp(r["snapshot"]).date()),
                "coding": int(r["coding"]),
                "non_coding": int(r["non_coding"]),
                "new": int(r["new"]),
                "experienced": int(r["experienced"]),
                "ccr": None if pd.isna(r["ccr"]) else round(float(r["ccr"]), 4),
                "ncr": None if pd.isna(r["ncr"]) else round(float(r["ncr"]), 4),
                "tipo": None if pd.isna(r["type"]) else str(r["type"]),
            }
            for _, r in g.sort_values("snapshot").iterrows()
        ]

    shutil.rmtree(scratch, ignore_errors=True)
    return saida


def main() -> int:
    import os

    raiz = Path(os.getenv("GHAPI_DIR", "data/ghapi"))
    if not raiz.is_absolute():
        raiz = ROOT / raiz
    if "--gera" in sys.argv:
        print(json.dumps(gera(raiz), ensure_ascii=False, default=str))
        return 0

    r = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--gera"],
        capture_output=True,
        text=True,
        cwd=ROOT,
        env={**os.environ, "GHAPI_DIR": str(raiz)},
        check=False,
    )
    if r.returncode != 0:
        raise SystemExit(f"falhou:\n{r.stderr[-3000:]}")
    dados = json.loads(r.stdout.strip().splitlines()[-1])
    (DESTINO / "numeros.json").write_text(
        json.dumps(dados, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"figuras em {DESTINO / 'figuras'}")
    print(f"números em {DESTINO / 'numeros.json'}")
    for rotulo, e in dados["escopos"].items():
        s = e["no_snapshot"]
        print(
            f"  {rotulo:14} {e['repositorios']} repo(s)  {e['eventos']:6} eventos  "
            f"{e['contribuidores']:4} pessoas  "
            + (f"CCR {s['ccr']:+.3f}  NCR {s['ncr']:+.3f}  tipo {s['tipo']}" if s else "sem ativo")
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
