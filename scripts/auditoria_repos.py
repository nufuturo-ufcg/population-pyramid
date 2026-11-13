"""Auditoria dos CSV brutos: repositórios duplicados e issues anteriores ao GitHub Issues.

Grava, em `<saida>/<linguagem>/auditoria/`:

  - `pares_duplicados.csv`: pares de repositórios com issues e PRs em comum;
  - `issues_antes_de_2009_04_15.csv`: issues e comentários de issue anteriores às issues.

O SQL está em `adapters/coleta_csv/auditoria.py`.

    uv run python scripts/auditoria_repos.py --saida ~/pyramid/rodadas/oficial \\
        --linguagens zig clojure elixir ocaml python
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

import carga_fonte
import figuras_linguagem_bruta as fb

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters.coleta_csv import auditoria
from adapters.coleta_csv.carga_duckdb import (
    CONTAS_EXCLUIDAS,
    CONTAS_QUE_SAO_PESSOAS,
    LOGIN_DE_MIGRACAO,
    LOGIN_UUID,
)


def nomes_dos_repositorios(fonte: carga_fonte.Fonte) -> pd.DataFrame:
    """`repo_id`, nome, estrelas e criação de cada repositório da coleta."""
    partes = []
    for caminho in fonte.alvos:
        alvo = pd.read_csv(caminho, dtype={"repo_id": str})
        alvo = alvo.rename(columns={"stargazers": "stars"})
        partes.append(alvo[["repo_id", "repo_name", "stars", "createdAt"]])
    return pd.concat(partes, ignore_index=True).drop_duplicates("repo_id")


def repos_excluidos(pares: pd.DataFrame, nomes: pd.DataFrame) -> pd.DataFrame:
    """Um repositório de cada grupo de duplicados fica, o resto sai.

    Grupo é o que se liga por pares com mais da metade das issues e PRs em comum. Fica o criado
    antes, como na carga, que já mantém o commit do repositório mais antigo; no empate, o de menor
    `repo_id`.
    """
    duplicados = pares[pares["fracao_do_menor"] > 0.5]
    pai: dict[str, str] = {}

    def raiz(repo: str) -> str:
        while pai.get(repo, repo) != repo:
            repo = pai[repo]
        return repo

    for a, b in zip(duplicados["repo_a"], duplicados["repo_b"], strict=True):
        if raiz(a) != raiz(b):
            pai[raiz(b)] = raiz(a)
    grupos: dict[str, list[str]] = {}
    for repo in set(duplicados["repo_a"]) | set(duplicados["repo_b"]):
        grupos.setdefault(raiz(repo), []).append(repo)

    linhas = []
    for membros in grupos.values():
        ordenados = sorted(membros, key=lambda r: (nomes["createdAt"].get(r, "9999"), int(r)))
        for repo in ordenados[1:]:
            linhas.append(
                {
                    "repo_id": repo,
                    "repo_name": nomes["repo_name"].get(repo),
                    "mantido_repo_id": ordenados[0],
                    "mantido_nome": nomes["repo_name"].get(ordenados[0]),
                    "repositorios_no_grupo": len(membros),
                }
            )
    return pd.DataFrame(
        linhas,
        columns=[
            "repo_id",
            "repo_name",
            "mantido_repo_id",
            "mantido_nome",
            "repositorios_no_grupo",
        ],
    )


def lista_de_contas(tabela: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Separa as contas excluídas por `sem_contas_de_sistema` das que ficam para revisão."""
    motivos = []
    for conta in tabela["conta"]:
        minuscula = conta.lower()
        motivo = ""
        if minuscula in CONTAS_EXCLUIDAS:
            motivo = "lista"
        elif re.match(LOGIN_UUID, minuscula):
            motivo = "uuid"
        elif minuscula not in CONTAS_QUE_SAO_PESSOAS and re.search(LOGIN_DE_MIGRACAO, minuscula):
            motivo = "migracao"
        motivos.append(motivo)
    tabela = tabela.assign(motivo=motivos)
    excluidas = tabela[tabela["motivo"] != ""]
    nao_excluidas = tabela[tabela["motivo"] == ""]
    bots = nao_excluidas[
        nao_excluidas["conta"].str.lower().str.contains("bot")
        & ~nao_excluidas["conta"].str.endswith("[bot]")
    ]
    soltas = nao_excluidas[
        nao_excluidas["conta"].str.lower().str.contains("trac|bugzilla|mantis|jira|import|migrat")
    ]
    return {
        "contas_excluidas": excluidas,
        "contas_30_com_mais_eventos": tabela.sort_values("eventos", ascending=False).head(30),
        "contas_com_bot_sem_marcador": bots,
        "contas_so_na_busca_solta": soltas,
    }


def audita_duplicados(
    slug: str, fonte: carga_fonte.Fonte, pasta: Path, saida: Path, memoria: str, threads: int | None
) -> None:
    """Pares duplicados, repositórios a excluir e issues anteriores ao lançamento das issues."""
    con = auditoria.conecta(saida / slug / "trabalho-auditoria", memoria, threads)
    try:
        auditoria.cria_api(con, [(a.caminho, a.papel) for a in fonte.eventos])
        nomes = nomes_dos_repositorios(fonte).set_index("repo_id")
        pares = auditoria.pares_duplicados(con)
        for lado in ["a", "b"]:
            info = nomes.reindex(pares["repo_" + lado])
            pares["nome_" + lado] = info["repo_name"].to_numpy()
            pares["criado_" + lado] = info["createdAt"].to_numpy()
        pares.to_csv(pasta / "pares_duplicados.csv", index=False)
        excluidos = repos_excluidos(pares, nomes)
        excluidos.to_csv(pasta / "repos_excluidos.csv", index=False)
        issues = auditoria.issues_antes_do_lancamento(con)
        issues["repo_name"] = nomes.reindex(issues["repo_id"])["repo_name"].to_numpy()
        issues.to_csv(pasta / "issues_antes_de_2009_04_15.csv", index=False)
    finally:
        con.close()
    print(
        f"{slug}: {len(pares)} pares, {len(excluidos)} repositórios a excluir, "
        f"{len(issues)} eventos antes do lançamento das issues"
    )


def audita_contas(
    slug: str, fonte: carga_fonte.Fonte, pasta: Path, saida: Path, memoria: str, threads: int | None
) -> None:
    """Contas excluídas, as 30 com mais eventos e as com bot no nome sem `[bot]`."""
    con = auditoria.conecta(saida / slug / "trabalho-auditoria-contas", memoria, threads)
    try:
        auditoria.cria_todos(con, [(a.caminho, a.papel) for a in fonte.eventos])
        partes = lista_de_contas(auditoria.contas(con))
    finally:
        con.close()
    for nome, parte in partes.items():
        parte.to_csv(pasta / f"{nome}.csv", index=False)
    print(f"{slug}: {len(partes['contas_excluidas'])} contas excluídas")


def audita(slug: str, saida: Path, memoria: str, threads: int | None, so_contas: bool) -> None:
    carga_fonte.aplica_linguagem(slug)
    fb.CFG.aplica(fb.RODADA)
    fonte = carga_fonte.resolve_fonte(slug)
    pasta = saida / slug / "auditoria"
    pasta.mkdir(parents=True, exist_ok=True)
    if not so_contas:
        audita_duplicados(slug, fonte, pasta, saida, memoria, threads)
    audita_contas(slug, fonte, pasta, saida, memoria, threads)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--saida", required=True, type=Path)
    parser.add_argument(
        "--linguagens", nargs="+", required=True, choices=sorted(carga_fonte.LINGUAGENS)
    )
    parser.add_argument("--memoria", default="20GB")
    parser.add_argument("--threads", type=int, default=None)
    parser.add_argument("--so-contas", action="store_true", help="pula duplicados e issues antigas")
    args = parser.parse_args()
    fb.TMP_BASE = args.saida.expanduser()
    for slug in args.linguagens:
        audita(slug, args.saida.expanduser(), args.memoria, args.threads, args.so_contas)


if __name__ == "__main__":
    main()
