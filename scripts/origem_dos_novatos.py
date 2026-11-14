"""Onde os novatos de cada linguagem chegaram: repositório e tipo do primeiro evento.

Roda a carga oficial (`carga_duckdb`, mesmas regras da pirâmide) e grava, por linguagem, em
`<saida>/<linguagem>/origem/`:

  - `pessoas.parquet`: uma linha por pessoa, com primeiro e último evento, repositório e tipo do
    primeiro evento, se fez algum commit ou PR e quantos eventos, commits e ocasiões teve;
  - `repos_por_trimestre.parquet`: pessoas distintas por repositório e trimestre;
  - `repos.parquet`: `codigo`, `repo_id`, nome, estrelas e data de criação de cada repositório.

Serve para perguntar de onde veio uma subida de novatos, comparando as linguagens.
`--sem-acoes` lista as ações de issue_event ignoradas (`Pedido.acoes_ignoradas`). O padrão é o
`acoes_ignoradas` de `vitalidade.yaml`; `--sem-acoes` sozinho mantém todas.
`--autores` liga o commit ao login pelo `autores:` de `vitalidade_fontes.yaml`. O padrão é o
`ligar_autores` de `vitalidade.yaml`.
`--fundir-identidades` junta nome de commit e login da mesma pessoa (`Pedido.fundir_identidades`).

    uv run python scripts/origem_dos_novatos.py --saida ~/pyramid-vitalidade-saida \\
        --linguagens clojure elixir ocaml zig python
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
import yaml

import carga_compacta
import carga_fonte
import figuras_linguagem_bruta as fb


def grava_origem(
    slug: str,
    saida: Path,
    memoria: str,
    threads: int | None,
    sem_acoes: tuple[str, ...] = (),
    fundir: bool = False,
    autores: bool = False,
    sem_duplicados: bool = False,
    commits_pelo_sha: bool = False,
    sem_contas_de_sistema: bool = False,
    fundir_duplicados: bool = False,
    contas_excluidas_csv: Path | None = None,
    contar_repos_sem_mapa: bool = False,
) -> None:
    """Carga de uma linguagem com a origem de cada pessoa gravada à parte."""
    carga_fonte.aplica_linguagem(slug)
    fb.CFG.aplica(fb.RODADA)
    fonte = carga_fonte.resolve_fonte(slug)
    if not autores:
        fonte.autores = None
    if not sem_duplicados and not fundir_duplicados:
        fonte.duplicados = None
    pasta = saida / slug / "origem"
    carga_compacta.carrega(
        fonte,
        "duckdb",
        trabalho=saida / slug / "trabalho-origem",
        memoria=memoria,
        threads=threads,
        contar_brutas=False,
        origem=pasta,
        acoes_ignoradas=sem_acoes,
        fundir_identidades=fundir,
        repos_excluidos=fonte.repos_excluidos() if sem_duplicados else (),
        repos_fundidos=fonte.grupos_de_duplicados() if fundir_duplicados else {},
        commits_pelo_sha=commits_pelo_sha,
        sem_contas_de_sistema=sem_contas_de_sistema,
        contas_extras=carga_fonte.le_contas(contas_excluidas_csv),
        repos_para_contar=carga_fonte.repos_sem_mapa(fonte) if contar_repos_sem_mapa else (),
    )
    (pasta / "estatisticas_da_carga.json").write_text(json.dumps(fb._stats(), default=str))
    partes = []
    for caminho in fonte.alvos:
        alvo = pd.read_csv(caminho, dtype={"repo_id": str})
        # A coleta de Clojure chama a coluna de `stars`; as outras, de `stargazers`.
        alvo = alvo.rename(columns={"stargazers": "stars"})
        partes.append(alvo[["repo_id", "repo_name", "stars", "createdAt"]])
    nomes = pd.concat(partes, ignore_index=True).drop_duplicates("repo_id")
    # Só as colunas da carga: rodar de novo sobre uma pasta antiga não duplica os nomes.
    repos = pd.read_parquet(pasta / "repos.parquet", columns=["codigo", "repo_id"])
    repos = repos.merge(nomes, on="repo_id", how="left")
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
    # A origem tem de sair da mesma carga da pirâmide: os padrões vêm do vitalidade.yaml.
    padrao = yaml.safe_load((Path(__file__).parent / "vitalidade.yaml").read_text())
    parser.add_argument(
        "--sem-acoes", nargs="*", default=padrao["acoes_ignoradas"],
        help="ações de issue_event ignoradas",
    )  # fmt: skip
    parser.add_argument("--fundir-identidades", action="store_true")
    parser.add_argument(
        "--autores", action=argparse.BooleanOptionalAction, default=padrao["ligar_autores"]
    )
    parser.add_argument(
        "--sem-duplicados", action=argparse.BooleanOptionalAction, default=padrao["sem_duplicados"]
    )
    parser.add_argument(
        "--contas-excluidas-csv", type=Path, default=None,
        help="CSV com a coluna conta: mais contas que saem (rodada de teste)",
    )  # fmt: skip
    parser.add_argument(
        "--contar-repos-sem-mapa", action="store_true",
        help="conta os contribuidores dos alvos com o mapa de linguagens vazio",
    )  # fmt: skip
    parser.add_argument(
        "--fundir-duplicados",
        action=argparse.BooleanOptionalAction,
        default=padrao["fundir_duplicados"],
    )
    parser.add_argument(
        "--commits-pelo-sha",
        action=argparse.BooleanOptionalAction,
        default=padrao["commits_pelo_sha"],
    )
    parser.add_argument(
        "--sem-contas-de-sistema",
        action=argparse.BooleanOptionalAction,
        default=padrao["sem_contas_de_sistema"],
    )
    args = parser.parse_args()
    fb.TMP_BASE = args.saida.expanduser()
    for slug in args.linguagens:
        grava_origem(
            slug,
            args.saida.expanduser(),
            args.memoria,
            args.threads,
            tuple(args.sem_acoes),
            args.fundir_identidades,
            args.autores,
            args.sem_duplicados,
            args.commits_pelo_sha,
            args.sem_contas_de_sistema,
            args.fundir_duplicados,
            args.contas_excluidas_csv,
            args.contar_repos_sem_mapa,
        )


if __name__ == "__main__":
    main()
