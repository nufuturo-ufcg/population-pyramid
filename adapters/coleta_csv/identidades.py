r"""Mede o quanto a identidade das pessoas pode estar partida ou fundida nos CSV da coleta.

Na carga, a pessoa é o nome do autor no commit (`author`) e o login nos eventos da API
(`author_login`). Este script conta, nos commits que tocam a linguagem:

  - nomes de commit distintos e e-mails distintos;
  - e-mails com mais de um nome (a mesma pessoa partida em vários nomes);
  - nomes com mais de um e-mail (uma pessoa com vários e-mails, ou pessoas diferentes com o
    mesmo nome fundidas numa só);
  - nomes de commit que coincidem com algum login da API (só esses juntam o lado do commit e o
    lado da API na mesma pessoa).

Uso (na batuta):

    uv run python adapters/coleta_csv/identidades.py \
        --git '/home/wendell/dados-brutos/clojure/*/eventos_git.csv' \
        --api '/home/wendell/dados-brutos/clojure/*/eventos_api.csv' \
        --extensoes .clj .cljs .cljc .cljx .edn .bb
"""

import argparse
import re
from pathlib import Path

import duckdb


def _lista(padrao: str) -> str:
    arquivos = sorted(str(a) for a in Path("/").glob(padrao.lstrip("/")))
    if not arquivos:
        raise SystemExit(f"nenhum arquivo em {padrao}")
    nomes = []
    for arquivo in arquivos:
        nomes.append("'" + arquivo.replace("'", "''") + "'")
    return "[" + ", ".join(nomes) + "]"


def _um(con: duckdb.DuckDBPyConnection, sql: str) -> int:
    linha = con.execute(sql).fetchone()
    assert linha is not None
    return int(linha[0])


def mede(git: str, api: str, extensoes: list[str]) -> dict[str, int]:
    """As contagens descritas no topo do arquivo."""
    alternativas = []
    for extensao in extensoes:
        alternativas.append(re.escape(extensao.lower()))
    toca = "(?:" + "|".join(alternativas) + ")(?:;|$)"
    con = duckdb.connect()
    leitura = "delim='|', header=true, all_varchar=true, ignore_errors=true"
    con.execute(
        f"""CREATE VIEW commits AS SELECT author, lower(author_email) AS email
        FROM read_csv({_lista(git)}, {leitura})
        WHERE event_type = 'commit' AND author IS NOT NULL
          AND regexp_matches(lower(files), '{toca.replace("'", "''")}')"""
    )
    con.execute(
        f"""CREATE VIEW logins AS SELECT DISTINCT author_login AS nome
        FROM read_csv({_lista(api)}, {leitura}) WHERE author_login IS NOT NULL"""
    )
    contagens = {}
    contagens["nomes de commit"] = _um(con, "SELECT count(DISTINCT author) FROM commits")
    contagens["e-mails de commit"] = _um(con, "SELECT count(DISTINCT email) FROM commits")
    contagens["e-mails com mais de um nome"] = _um(
        con,
        "SELECT count(*) FROM (SELECT email FROM commits GROUP BY 1 "
        "HAVING count(DISTINCT author) > 1)",
    )
    contagens["nomes com mais de um e-mail"] = _um(
        con,
        "SELECT count(*) FROM (SELECT author FROM commits GROUP BY 1 "
        "HAVING count(DISTINCT email) > 1)",
    )
    contagens["logins da API"] = _um(con, "SELECT count(*) FROM logins")
    contagens["nomes de commit iguais a algum login"] = _um(
        con,
        "SELECT count(*) FROM (SELECT DISTINCT author FROM commits) c "
        "JOIN logins l ON c.author = l.nome",
    )
    return contagens


def main() -> None:
    """Lê os globs e as extensões da linha de comando e imprime as contagens."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--git", required=True, help="glob dos eventos_git.csv")
    parser.add_argument("--api", required=True, help="glob dos eventos_api.csv")
    parser.add_argument("--extensoes", nargs="+", required=True)
    args = parser.parse_args()
    for nome, valor in mede(args.git, args.api, args.extensoes).items():
        print(f"{nome}: {valor}")


if __name__ == "__main__":
    main()
