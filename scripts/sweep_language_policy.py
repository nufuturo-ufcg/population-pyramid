#!/usr/bin/env python
"""Mede quanto cada chave de `language:` move a pirâmide por linguagem.

A pergunta que motiva: o evento sem arquivo herda a linguagem do repositório, e
esses eventos são quase todo o lado NÃO-CÓDIGO da pirâmide (abertura de issue,
comentário de issue, issue event, e o commit que só toca prosa). Se a herança
inflar esse lado, o CCR da linguagem sai enviesado, e o tamanho do viés precisa
ser um número, e não uma suspeita.

    GHAPI_DIR=data/ghapi .venv/bin/python scripts/sweep_language_policy.py
    GHAPI_DIR=data/ghapi .venv/bin/python scripts/sweep_language_policy.py --json

Não escreve nada no repositório. Cada variante roda num `config/` e num
`output/` de rascunho, e some no fim.

Cada variante roda em SUBPROCESSO próprio. `settings()` e `checkpoints()` são
`@cache`: trocar o YAML dentro do mesmo processo devolve o valor velho, e isso
já contaminou resultado antes (ver `scripts/sweep_commit_scope.py`).
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]

# A janela do `settings.yaml` publicado é a do dump MSR14, que acaba em 2013. A
# coleta da API é de agora, então a série precisa cobrir o período dela, senão
# nenhum snapshot casa e toda pirâmide sai vazia.
JANELA = {
    "start": "2019-03-31",
    "end": "2026-06-30",
    "classification_snapshot": "2026-06-30",
    "projection_base": ["2025-12-31", "2026-03-31"],
    "projection_target": "2026-06-30",
}

# (nome, o que muda em `language:`). O primeiro é o default publicado, e serve
# de base para as diferenças.
VARIANTES: list[tuple[str, dict]] = [
    ("base", {}),
    ("fallback=unknown", {"fallback": "unknown"}),
    ("fallback=drop", {"fallback": "drop"}),
    ("attribution=repo_languages", {"attribution": "repo_languages"}),
    ("min_share=0.1", {"repo_languages": {"policy": "min_share", "min_share": 0.1}}),
    ("outside_eligible=drop", {"outside_eligible": "drop"}),
    ("drop_bots=false", {"drop_bots": False}),
]


def _scratch(mudanca: dict) -> Path:
    """`config/` isolado, com `language:` e a janela trocadas."""
    scratch = Path(tempfile.mkdtemp(prefix="pyr_lang_"))
    shutil.copytree(ROOT / "config", scratch / "config")
    alvo = scratch / "config" / "settings.yaml"
    cfg = yaml.safe_load(alvo.read_text(encoding="utf-8"))
    cfg["input"]["adapter"] = "ghapi"
    cfg["analysis"]["unit"] = "language"
    cfg["snapshots"].update(JANELA)
    lang = dict(cfg.get("language") or {})
    for chave, valor in mudanca.items():
        lang[chave] = valor
    cfg["language"] = lang
    alvo.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return scratch


def _uma(nome: str) -> dict:
    """Roda uma variante e devolve a tabela por linguagem. Dentro do subprocesso."""
    mudanca = dict(VARIANTES)[nome]
    scratch = _scratch(mudanca)

    # Redireciona ANTES de importar os estágios. `stage_dir()` lê o global na
    # hora da chamada; `logging_config` faz `from .config import LOG_DIR` e
    # prende o nome, então precisa da troca própria.
    from pyramid import config

    config.CONFIG_DIR = scratch / "config"
    config.OUTPUT_DIR = scratch / "output"
    config.LOG_DIR = scratch / "logs"
    config.settings.cache_clear()
    config.checkpoints.cache_clear()

    from pyramid import logging_config

    logging_config.LOG_DIR = config.LOG_DIR

    from pyramid import classify, extract, metrics, snapshots

    for estagio in (extract, classify, snapshots, metrics):
        res = estagio.run(None, force=True, fail_fast=True)
        if res.get("failed"):
            raise SystemExit(f"{estagio.STAGE} falhou em {nome}: {res['failed']}")

    tab = metrics.table(snapshots.classification_snapshot())
    saida = {
        str(linha["project"]): {
            "coding": int(linha["coding"]),
            "non_coding": int(linha["non_coding"]),
            "ccr": float(linha["ccr"]),
            "ncr": float(linha["ncr"]),
            "type": None
            if linha["type"] is None or linha["type"] != linha["type"]
            else str(linha["type"]),
        }
        for _, linha in tab.iterrows()
    }
    shutil.rmtree(scratch, ignore_errors=True)
    return saida


def _roda_em_subprocesso(nome: str) -> dict:
    r = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--uma", nome],
        capture_output=True,
        text=True,
        cwd=ROOT,
        check=False,
    )
    if r.returncode != 0:
        raise SystemExit(f"variante {nome} falhou:\n{r.stderr[-2000:]}")
    return json.loads(r.stdout.strip().splitlines()[-1])


def _relatorio(tudo: dict[str, dict]) -> None:
    base = tudo["base"]
    linguagens = sorted(base, key=lambda k: -base[k]["coding"] - base[k]["non_coding"])

    print("\nCCR por linguagem, e o que cada chave move")
    print("A base é o default publicado: by_path, fallback repo_languages, primary.\n")
    largura = max(len(x) for x in linguagens) if linguagens else 8
    cab = f"{'variante':28}" + "".join(f"{x:>{largura + 3}}" for x in linguagens)
    print(cab)
    print("-" * len(cab))
    for nome, _ in VARIANTES:
        tab = tudo[nome]
        celulas = []
        for lang in linguagens:
            if lang not in tab:
                celulas.append(f"{'ausente':>{largura + 3}}")
                continue
            celulas.append(f"{tab[lang]['ccr']:>{largura + 3}.3f}")
        print(f"{nome:28}" + "".join(celulas))

    print("\nlado não-código (contribuidores), que é onde a herança pesa\n")
    print(cab)
    print("-" * len(cab))
    for nome, _ in VARIANTES:
        tab = tudo[nome]
        celulas = [
            f"{tab[lang]['non_coding'] if lang in tab else 0:>{largura + 3}}" for lang in linguagens
        ]
        print(f"{nome:28}" + "".join(celulas))

    print("\ntipo A-D\n")
    print(cab)
    print("-" * len(cab))
    for nome, _ in VARIANTES:
        tab = tudo[nome]
        celulas = [
            f"{str(tab[lang]['type']) if lang in tab else '-':>{largura + 3}}"
            for lang in linguagens
        ]
        print(f"{nome:28}" + "".join(celulas))

    print("\nleitura:")
    for nome, _ in VARIANTES[1:]:
        mudou = [
            lang
            for lang in linguagens
            if lang in tudo[nome]
            and lang in base
            and tudo[nome][lang]["type"] != base[lang]["type"]
        ]
        sumiu = [lang for lang in linguagens if lang not in tudo[nome]]
        recado = []
        if mudou:
            recado.append("muda o tipo de " + ", ".join(mudou))
        if sumiu:
            recado.append("some com " + ", ".join(sumiu))
        print(f"  {nome:28} {'; '.join(recado) or 'não muda tipo nenhum'}")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--uma", help=argparse.SUPPRESS)
    p.add_argument("--json", action="store_true", help="despeja o resultado cru")
    args = p.parse_args()

    if args.uma:
        print(json.dumps(_uma(args.uma)))
        return 0

    tudo = {}
    for nome, _ in VARIANTES:
        print(f"rodando {nome} ...", file=sys.stderr, flush=True)
        tudo[nome] = _roda_em_subprocesso(nome)

    if args.json:
        print(json.dumps(tudo, indent=2, ensure_ascii=False))
    else:
        _relatorio(tudo)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
