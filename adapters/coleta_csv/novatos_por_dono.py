r"""Novatos por trimestre, separados pelo dono do repositório onde a pessoa apareceu.

Serve para perguntar se a subida de novatos de uma linguagem veio de uma organização (por
exemplo `nubank`): conta, por trimestre do primeiro evento da pessoa, quantos novatos tiveram o
primeiro evento num repositório dos donos pedidos e quantos contribuíram nesses donos em algum
momento. Também conta os novatos que nunca passaram pelos repositórios de `--excluir-repos`
(por exemplo aplicativos com muitos usuários abrindo issue) e os que fizeram algum commit ou PR.

Regras, mais simples que as da carga (`carga_duckdb.py`), para olhar a origem do novato:

  - pessoa = nome do autor no commit e login nos eventos da API, como na carga;
  - commit entra se toca arquivo com extensão da linguagem; evento da API entra com login e
    `language` vazia ou igual à linguagem;
  - saem conta apagada (`ghost`), bot (`[bot]`) e datas antes de 2008 ou depois do fim do estudo;
  - população `passou_30_dias`: o último evento cai 30 dias ou mais depois do primeiro;
  - sem o filtro de commit copiado entre repositórios e sem o de elegibilidade (50%).

Uso (na batuta):

    uv run python adapters/coleta_csv/novatos_por_dono.py \
        --git '/home/wendell/dados-brutos/clojure/*/eventos_git.csv' \
        --api '/home/wendell/dados-brutos/clojure/*/eventos_api.csv' \
        --linguagem Clojure --extensoes .clj .cljs .cljc .cljx .edn .bb \
        --donos nubank --excluir-repos logseq/logseq penpot/penpot \
        --saida novatos_nubank.csv
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


def _texto(valor: str) -> str:
    return "'" + valor.replace("'", "''") + "'"


def novatos(args: argparse.Namespace) -> duckdb.DuckDBPyRelation:
    """Uma linha por trimestre: novatos, os que começaram nos donos e os que passaram por eles.

    `args` traz git, api, linguagem, extensoes, donos, excluir_repos e fim, como na linha de
    comando.
    """
    alternativas = []
    for extensao in args.extensoes:
        alternativas.append(re.escape(extensao.lower()))
    toca = "(?:" + "|".join(alternativas) + ")(?:;|$)"
    lista_donos = []
    for dono in args.donos:
        lista_donos.append(_texto(dono.lower()))
    lista_excluidos = ["''"]
    for repo in args.excluir_repos:
        lista_excluidos.append(_texto(repo.lower()))
    leitura = "delim='|', header=true, all_varchar=true, ignore_errors=true"
    con = duckdb.connect()
    con.execute(
        f"""CREATE TABLE ev AS
        SELECT pessoa, lower(repo_name) AS repo, lower(split_part(repo_name, '/', 1)) AS dono,
               try_cast(created_at AS TIMESTAMPTZ) AS ts, codigo
        FROM (
            SELECT author AS pessoa, repo_name, created_at, true AS codigo
            FROM read_csv({_lista(args.git)}, {leitura})
            WHERE event_type = 'commit' AND author IS NOT NULL
              AND regexp_matches(lower(files), {_texto(toca)})
            UNION ALL
            SELECT author_login AS pessoa, repo_name, created_at, event_type = 'pr' AS codigo
            FROM read_csv({_lista(args.api)}, {leitura})
            WHERE event_type <> 'commit' AND author_login IS NOT NULL
              AND (language IS NULL OR language = {_texto(args.linguagem)})
        )
        WHERE pessoa <> 'ghost' AND pessoa NOT LIKE '%[bot]'"""
    )
    con.execute(
        f"DELETE FROM ev WHERE ts IS NULL OR ts < TIMESTAMPTZ '2008-01-01' "
        f"OR ts > TIMESTAMPTZ {_texto(args.fim)}"
    )
    con.execute(
        f"""CREATE TABLE pessoas AS
        SELECT pessoa, min(ts) AS primeiro, max(ts) AS ultimo,
               arg_min(dono, ts) AS dono_do_primeiro,
               bool_or(dono IN ({", ".join(lista_donos)})) AS passou_pelos_donos,
               bool_or(repo IN ({", ".join(lista_excluidos)})) AS passou_pelos_excluidos,
               bool_or(codigo) AS codou
        FROM ev GROUP BY pessoa"""
    )
    return con.sql(
        f"""SELECT year(primeiro) || 'Q' || quarter(primeiro) AS periodo,
               count(*) AS novatos,
               count(*) FILTER (WHERE dono_do_primeiro IN ({", ".join(lista_donos)}))
                   AS comecaram_nos_donos,
               count(*) FILTER (WHERE passou_pelos_donos) AS passaram_pelos_donos,
               count(*) FILTER (WHERE NOT passou_pelos_excluidos) AS sem_os_repos_excluidos,
               count(*) FILTER (WHERE codou) AS fizeram_commit_ou_pr
        FROM pessoas
        WHERE ultimo - primeiro >= INTERVAL 30 DAY
        GROUP BY 1 ORDER BY 1"""
    )


def main() -> None:
    """Lê os argumentos, conta e grava o CSV."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--git", required=True, help="glob dos eventos_git.csv")
    parser.add_argument("--api", required=True, help="glob dos eventos_api.csv")
    parser.add_argument("--linguagem", required=True, help="valor de `language`, ex. Clojure")
    parser.add_argument("--extensoes", nargs="+", required=True)
    parser.add_argument("--donos", nargs="+", required=True, help="donos de repositório")
    parser.add_argument("--excluir-repos", nargs="*", default=[], help="dono/nome")
    parser.add_argument("--fim", default="2025-12-31 23:59:59+00")
    parser.add_argument("--saida", required=True, help="CSV de saída")
    args = parser.parse_args()
    tabela = novatos(args)
    tabela.write_csv(args.saida)
    print(f"gravado: {args.saida}")


if __name__ == "__main__":
    main()
