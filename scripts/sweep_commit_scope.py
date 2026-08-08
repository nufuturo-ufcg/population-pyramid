#!/usr/bin/env python
"""Varre `commit_scope` e mede a distância entre a Fig.2 da réplica e a do artigo.

Motivação (docs/discrepancias.md §21, §22): o `commit_scope=root` conta só os
commits registrados NO projeto raiz. Fork tem cópia do histórico da mãe em
`project_commits`, então há duas outras leituras plausíveis do que é "commit do
projeto" — e o homebrew, que é o painel onde mais sobra gente, é justamente um
projeto com muito fork. A pergunta é se algum dos três escopos aproxima a
réplica da figura publicada, e EM QUANTO.

O que a varredura faz, por escopo:

  1. copia `config/` para um scratch, troca só `commit_scope`;
  2. roda extract -> classify -> snapshots num `output/` de scratch, com os
     4 projetos da Fig.2 e `--force` (o cache do repo não é tocado);
  3. monta o `pyramid_frame` no snapshot da figura;
  4. compara banda a banda com `esem14_fig2.bars_read_px` do
     `checkpoints.yaml` (leitura em pixel do artigo, §20).

Cada escopo roda num SUBPROCESSO próprio. Os estágios têm cache em disco e
`settings()` é `@cache`: trocar o escopo dentro do mesmo processo já deu
resultado contaminado antes, e o subprocesso é a garantia barata de que não
volta a dar.

DISTÂNCIA. Por painel, L1 = soma sobre as bandas de |réplica - artigo|, dos
dois lados somados (esquerda = `non_coding`; direita = `moved + coding`, ver a
nota de `bars_read_px` sobre por que não separamos os dois segmentos da
direita). Bandas que só existem de um lado entram com zero do outro — banda
sobrando é diferença de verdade (§30), não detalhe de alinhamento.

O L1 absoluto é dominado pelo homebrew (milhares de pessoas contra dezenas nos
outros três), então o resumo também traz o L1 relativo (L1 / população lida no
artigo, por painel) e a média dos quatro. Nenhum dos dois é teste estatístico:
o alvo é leitura em pixel com ±1 pessoa por barra. Diferença de poucos por
cento entre escopos é empate, e está escrito assim no relatório.

Uso:
    python scripts/sweep_commit_scope.py
    python scripts/sweep_commit_scope.py --scopes root,family_project_id
    python scripts/sweep_commit_scope.py --json out.json

Precisa do banco de pé (`docker start msr14`), como qualquer coisa que passe
pelo `extract`.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

ESCOPOS = ["root", "family_project_commits", "family_project_id"]
SNAPSHOT_PADRAO = "2011-12-31"


# --- um escopo, dentro do subprocesso -----------------------------------------


def _prepara_scratch(escopo: str) -> Path:
    """Config + output isolados. Só `commit_scope` muda em relação ao repo."""
    scratch = Path(tempfile.mkdtemp(prefix=f"pyr_scope_{escopo}_"))
    shutil.copytree(ROOT / "config", scratch / "config")

    alvo = scratch / "config" / "settings.yaml"
    linhas = alvo.read_text().splitlines(keepends=True)
    achou = 0
    for i, ln in enumerate(linhas):
        if ln.startswith("commit_scope:"):
            linhas[i] = f"commit_scope: {escopo}\n"
            achou += 1
    if achou != 1:
        raise SystemExit(
            f"esperava exatamente 1 linha `commit_scope:` em settings.yaml, achei {achou}. "
            "Edição cega de config é como se troca um parâmetro por acidente — abortando."
        )
    alvo.write_text("".join(linhas))
    return scratch


def _frames(escopo: str, projetos: list[int], snapshot: str) -> dict:
    import pandas as pd

    scratch = _prepara_scratch(escopo)

    # Redireciona ANTES de importar os estágios. `stage_dir()` lê o global no
    # momento da chamada, então basta trocar em `config`; `logging_config` é a
    # exceção, que faz `from .config import LOG_DIR` e prende o nome.
    import pyramid.config as config

    config.CONFIG_DIR = scratch / "config"
    config.OUTPUT_DIR = scratch / "output"
    config.LOG_DIR = scratch / "logs"
    config.settings.cache_clear()
    config.checkpoints.cache_clear()

    import pyramid.logging_config as logging_config

    logging_config.LOG_DIR = config.LOG_DIR

    from pyramid import classify, extract, plots, snapshots

    conferido = config.settings()["commit_scope"]
    if conferido != escopo:
        raise SystemExit(f"scratch não pegou: commit_scope={conferido!r}, esperava {escopo!r}")

    for estagio in (extract, classify, snapshots):
        res = estagio.run(projetos, force=True, fail_fast=True)
        if res.get("failed"):
            raise SystemExit(f"{estagio.STAGE} falhou em {escopo}: {res['failed']}")

    t = pd.Timestamp(snapshot)
    out = {}
    for sid in projetos:
        fr = plots.pyramid_frame(snapshots.load(sid), t)
        out[str(sid)] = {
            "non_coding": [float(v) for v in fr["non_coding"]],
            "coding": [float(v) for v in (fr["moved"] + fr["coding"])],
        }
    shutil.rmtree(scratch, ignore_errors=True)
    return out


# --- comparação ---------------------------------------------------------------


def _l1(replica: list[float], artigo: list[float]) -> tuple[float, int]:
    n = max(len(replica), len(artigo))
    r = list(replica) + [0.0] * (n - len(replica))
    a = list(artigo) + [0.0] * (n - len(artigo))
    return sum(abs(x - y) for x, y in zip(r, a)), n


def compara(frames: dict, snapshot: str) -> dict:
    from pyramid.config import checkpoints

    lido = checkpoints()["figures"]["esem14_fig2"]["bars_read_px"]
    saida = {}
    for sid_str, fr in frames.items():
        alvo = lido[int(sid_str)]
        art_dir = [a + b for a, b in zip(alvo["right_light"], alvo["right_dark"])]
        l1_esq, n_esq = _l1(fr["non_coding"], alvo["non_coding"])
        l1_dir, n_dir = _l1(fr["coding"], art_dir)
        pop_artigo = sum(alvo["non_coding"]) + sum(art_dir)
        pop_replica = sum(fr["non_coding"]) + sum(fr["coding"])
        saida[sid_str] = {
            "l1": l1_esq + l1_dir,
            "l1_non_coding": l1_esq,
            "l1_coding": l1_dir,
            "l1_rel": (l1_esq + l1_dir) / pop_artigo if pop_artigo else float("nan"),
            "pop_artigo": pop_artigo,
            "pop_replica": pop_replica,
            "bandas_artigo": len(alvo["non_coding"]),
            "bandas_replica": len(fr["non_coding"]),
            "bandas_comparadas": max(n_esq, n_dir),
        }
    return saida


# --- relatório ----------------------------------------------------------------


def _rotulos(projetos: list[int]) -> dict[int, str]:
    """Nome do projeto pelo manifesto do `extract` DO REPO (só para ler a tabela).

    Se não houver manifesto, o id serve: rótulo é enfeite, o escopo é sempre por
    `project.id` (dois projetos se chamam `symfony` nos 90).
    """
    man = ROOT / "output" / "extract" / "_manifest.json"
    rotulo = {}
    if man.exists():
        ok = json.loads(man.read_text()).get("ok", {})
        rotulo = {int(k): v.get("label", k) for k, v in ok.items()}
    return {sid: str(rotulo.get(sid, sid)).split("/")[-1] for sid in projetos}


def relatorio(res: dict, projetos: list[int], snapshot: str) -> str:
    nomes = _rotulos(projetos)
    escopos = list(res)
    ls = []
    ls.append(f"Fig.2 @ {snapshot} — réplica x leitura em pixel do artigo (bars_read_px)")
    ls.append("L1 = soma de |réplica - artigo| banda a banda, dois lados; rel = L1 / população lida.")
    ls.append("")
    cab = f"{'projeto':<16}" + "".join(f"{e:>26}" for e in escopos)
    ls.append(cab)
    ls.append("-" * len(cab))
    for sid in projetos:
        k = str(sid)
        linha = f"{nomes[sid][:15]:<16}"
        for e in escopos:
            m = res[e][k]
            linha += f"{m['l1']:>15.1f} ({m['l1_rel']:>5.1%})"
        ls.append(linha)
    ls.append("-" * len(cab))
    linha = f"{'média rel':<16}"
    for e in escopos:
        med = sum(res[e][str(s)]["l1_rel"] for s in projetos) / len(projetos)
        linha += f"{'':>15} ({med:>5.1%})"
    ls.append(linha)
    ls.append("")
    ls.append("População (réplica / artigo), por painel:")
    for sid in projetos:
        k = str(sid)
        peca = "  ".join(
            f"{e.split('_')[0] if e == 'root' else e[7:]}: "
            f"{res[e][k]['pop_replica']:.0f}/{res[e][k]['pop_artigo']:.0f}"
            for e in escopos
        )
        ls.append(f"  {nomes[sid][:15]:<16} {peca}")
    ls.append("")
    ls.append("Bandas (réplica / artigo):")
    for sid in projetos:
        k = str(sid)
        peca = "  ".join(
            f"{res[e][k]['bandas_replica']}/{res[e][k]['bandas_artigo']}" for e in escopos
        )
        ls.append(f"  {nomes[sid][:15]:<16} {peca}")
    ls.append("")
    ls.append(
        "Lembrete: o alvo tem ±1 pessoa de erro por barra. Diferença de poucos "
        "por cento entre escopos é empate, não vitória."
    )
    return "\n".join(ls)


# --- main ---------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--scopes", default=",".join(ESCOPOS))
    ap.add_argument("--snapshot", default=SNAPSHOT_PADRAO)
    ap.add_argument("--projects", default="")
    ap.add_argument("--json", default="")
    ap.add_argument("--_run-one", default="", help=argparse.SUPPRESS)
    a = ap.parse_args()

    if a.projects:
        projetos = [int(x) for x in a.projects.split(",")]
    else:
        from pyramid.config import checkpoints

        projetos = list(checkpoints()["figures"]["esem14_fig2"]["bars_read_px"])

    if a._run_one:
        print(json.dumps(_frames(a._run_one, projetos, a.snapshot)))
        return 0

    escopos = [e.strip() for e in a.scopes.split(",") if e.strip()]
    desconhecido = [e for e in escopos if e not in ESCOPOS]
    if desconhecido:
        raise SystemExit(f"escopo inválido: {desconhecido}. Conhecidos: {ESCOPOS}")

    res = {}
    for e in escopos:
        print(f"[{e}] extract/classify/snapshots nos {len(projetos)} projetos...", file=sys.stderr)
        cmd = [
            sys.executable, str(Path(__file__).resolve()),
            "--_run-one", e,
            "--snapshot", a.snapshot,
            "--projects", ",".join(str(p) for p in projetos),
        ]
        p = subprocess.run(cmd, capture_output=True, text=True, env=os.environ.copy())
        if p.returncode != 0:
            sys.stderr.write(p.stderr)
            raise SystemExit(f"escopo {e} falhou (rc={p.returncode})")
        res[e] = compara(json.loads(p.stdout), a.snapshot)

    print(relatorio(res, projetos, a.snapshot))
    if a.json:
        Path(a.json).write_text(json.dumps(res, indent=2))
        print(f"\njson: {a.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
