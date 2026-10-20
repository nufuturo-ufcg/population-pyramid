"""Onde os novatos de cada linguagem chegaram: repositório e tipo do primeiro evento.

Roda a carga oficial (`carga_duckdb`, mesmas regras da pirâmide) e grava, por linguagem, em
`<saida>/<linguagem>/origem/`:

  - `pessoas.parquet`: uma linha por pessoa, com primeiro e último evento, repositório e tipo do
    primeiro evento e se fez algum commit ou PR;
  - `repos_por_trimestre.parquet`: pessoas distintas por repositório e trimestre;
  - `repos.parquet`: `codigo`, `repo_id`, nome, estrelas e data de criação de cada repositório.

Serve para perguntar de onde veio uma subida de novatos, comparando as linguagens.

    uv run python scripts/origem_dos_novatos.py --saida ~/pyramid-vitalidade-saida \\
        --linguagens clojure elixir ocaml zig python
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

import carga_compacta
import carga_fonte
import figuras_linguagem_bruta as fb


def grava_origem(slug: str, saida: Path, memoria: str, threads: int | None) -> None:
    """Carga de uma linguagem com a origem de cada pessoa gravada à parte."""
    carga_fonte.aplica_linguagem(slug)
    fb.CFG.aplica(fb.RODADA)
    fonte = carga_fonte.resolve_fonte(slug)
    pasta = saida / slug / "origem"
    carga_compacta.carrega(
        fonte,
        "duckdb",
        trabalho=saida / slug / "trabalho-origem",
        memoria=memoria,
        threads=threads,
        contar_brutas=False,
        origem=pasta,
    )
    partes = []
    for caminho in fonte.alvos:
        partes.append(
            pd.read_csv(
                caminho,
                usecols=["repo_id", "repo_name", "stars", "createdAt"],
                dtype={"repo_id": str},
            )
        )
    nomes = pd.concat(partes, ignore_index=True).drop_duplicates("repo_id")
    repos = pd.read_parquet(pasta / "repos.parquet").merge(nomes, on="repo_id", how="left")
    repos.to_parquet(pasta / "repos.parquet", index=False)
    print(f"{slug}: {pasta}")


def main() -> None:
    """Lê os argumentos e grava a origem de cada linguagem pedida."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--saida", required=True, type=Path)
    parser.add_argument(
        "--linguagens", nargs="+", required=True, choices=sorted(carga_fonte.LINGUAGENS)
    )
    parser.add_argument("--memoria", default="30GB")
    parser.add_argument("--threads", type=int, default=None)
    args = parser.parse_args()
    fb.TMP_BASE = args.saida.expanduser()
    for slug in args.linguagens:
        grava_origem(slug, args.saida.expanduser(), args.memoria, args.threads)


if __name__ == "__main__":
    main()
