"""Auditoria dos eventos de API de uma linguagem, sobre os CSV brutos da coleta.

Duas perguntas, as duas só com eventos de API (commit sai):

  - `pares_duplicados`: dois repositórios (`repo_id` diferentes) com as mesmas issues e PRs, como
    um repositório renomeado e coletado duas vezes. A chave de um evento é (tipo, autor, data,
    número).
  - `issues_antes_do_lancamento`: issues e comentários de issue datados antes de 15/04/2009, quando
    o GitHub lançou as issues. Só podem vir de migração de outro rastreador, com a data original.
  - `contas`: eventos e repositórios de cada conta (login nos eventos de API, nome do autor nos
    commits), para listar as excluídas, as mais ativas e as que têm "bot" no nome sem `[bot]`.

O SQL mora aqui porque o repositório só o permite em `adapters/`. O `scripts/auditoria_repos.py`
chama estas funções.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import duckdb
import pandas as pd
from adapters.coleta_csv.carga_duckdb import (
    CONTAS_EXCLUIDAS,
    LOGIN_DE_MIGRACAO,
    LOGIN_UUID,
    _aspas,
    _leitura,
    _pessoa,
    _ts,
)

LANCAMENTO_DAS_ISSUES = "2009-04-15"
TIPOS_DA_CONVERSA = "('issue', 'pr')"


def conecta(
    trabalho: Path, memoria: str = "20GB", threads: int | None = None
) -> duckdb.DuckDBPyConnection:
    """Banco em disco com derrame, como a carga."""
    shutil.rmtree(trabalho, ignore_errors=True)
    trabalho.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(trabalho / "auditoria.duckdb"))
    con.execute(f"SET memory_limit = {_aspas(memoria)}")
    con.execute(f"SET temp_directory = {_aspas(trabalho / 'derrame')}")
    con.execute("SET preserve_insertion_order = false")
    con.execute("SET TimeZone = 'UTC'")
    if threads:
        con.execute(f"SET threads = {int(threads)}")
    return con


def cria_api(con: duckdb.DuckDBPyConnection, eventos: list[tuple[Path, str]]) -> None:
    """A visão `api`: um evento de API por linha, com a conversa a que ele pertence."""
    leituras = []
    for caminho, papel in eventos:
        if papel != "git":
            leituras.append(_leitura(caminho, papel))
    con.execute("CREATE VIEW bruto AS " + " UNION ALL ".join(leituras))
    conversa = "coalesce(number, regexp_extract(url, '/(?:issues|pull)/([0-9]+)', 1))"
    con.execute(f"""
        CREATE VIEW api AS
        SELECT repo_id, event_type, author_login, created_at, {conversa} AS conversa, title
        FROM bruto WHERE NOT eh_commit AND author_login IS NOT NULL
    """)


def pares_duplicados(con: duckdb.DuckDBPyConnection, minimo_em_comum: int = 1) -> pd.DataFrame:
    """Pares de repositórios com issues e PRs em comum.

    `fracao_do_menor` é a parte das issues e PRs do repositório menor que também está no outro.
    `titulo_igual_pct` é, nas issues e PRs em comum, a parte com o mesmo título. `comuns_todos` e
    `fracao_todos_do_menor` repetem a conta com todos os tipos de evento de API.
    """
    con.execute(f"""
        CREATE TABLE chaves AS
        SELECT DISTINCT repo_id, hash(event_type, author_login, created_at, conversa) AS h
        FROM api WHERE event_type IN {TIPOS_DA_CONVERSA}
    """)
    con.execute("CREATE TABLE totais AS SELECT repo_id, count(*) AS n FROM chaves GROUP BY repo_id")
    con.execute(f"""
        CREATE TABLE pares AS
        SELECT a.repo_id AS repo_a, b.repo_id AS repo_b, count(*) AS comuns
        FROM chaves a JOIN chaves b ON a.h = b.h AND a.repo_id < b.repo_id
        GROUP BY ALL HAVING count(*) >= {int(minimo_em_comum)}
    """)
    con.execute("""
        CREATE TABLE pares_com_total AS
        SELECT p.*, ta.n AS conversas_a, tb.n AS conversas_b,
               p.comuns / least(ta.n, tb.n) AS fracao_do_menor
        FROM pares p JOIN totais ta ON ta.repo_id = p.repo_a JOIN totais tb ON tb.repo_id = p.repo_b
    """)
    con.execute("""
        CREATE TABLE sinalizados AS
        SELECT repo_a AS repo_id FROM pares_com_total WHERE fracao_do_menor > 0.5
        UNION SELECT repo_b FROM pares_com_total WHERE fracao_do_menor > 0.5
    """)
    # Título igual nas conversas em comum, só dos repositórios sinalizados.
    con.execute(f"""
        CREATE TABLE conversas AS
        SELECT DISTINCT repo_id, hash(event_type, author_login, created_at, conversa) AS h, title
        FROM api WHERE event_type IN {TIPOS_DA_CONVERSA}
          AND repo_id IN (SELECT repo_id FROM sinalizados)
    """)
    con.execute("""
        CREATE TABLE titulos AS
        SELECT a.repo_id AS repo_a, b.repo_id AS repo_b,
               100.0 * count(*) FILTER (WHERE a.title IS NOT DISTINCT FROM b.title) / count(*)
                   AS titulo_igual_pct
        FROM conversas a JOIN conversas b ON a.h = b.h AND a.repo_id < b.repo_id
        GROUP BY ALL
    """)
    # Todos os tipos de evento de API, só dos repositórios sinalizados.
    con.execute("""
        CREATE TABLE todos AS
        SELECT DISTINCT repo_id, hash(event_type, author_login, created_at, conversa) AS h
        FROM api WHERE repo_id IN (SELECT repo_id FROM sinalizados)
    """)
    con.execute(
        "CREATE TABLE totais_todos AS SELECT repo_id, count(*) AS n FROM todos GROUP BY repo_id"
    )
    con.execute("""
        CREATE TABLE comuns_todos AS
        SELECT a.repo_id AS repo_a, b.repo_id AS repo_b, count(*) AS comuns_todos
        FROM todos a JOIN todos b ON a.h = b.h AND a.repo_id < b.repo_id
        GROUP BY ALL
    """)
    return con.execute("""
        SELECT p.repo_a, p.repo_b, p.conversas_a, p.conversas_b, p.comuns,
               round(p.fracao_do_menor, 4) AS fracao_do_menor,
               round(t.titulo_igual_pct, 2) AS titulo_igual_pct,
               ta.n AS eventos_a, tb.n AS eventos_b, c.comuns_todos,
               round(c.comuns_todos / least(ta.n, tb.n), 4) AS fracao_todos_do_menor
        FROM pares_com_total p
        LEFT JOIN titulos t ON t.repo_a = p.repo_a AND t.repo_b = p.repo_b
        LEFT JOIN comuns_todos c ON c.repo_a = p.repo_a AND c.repo_b = p.repo_b
        LEFT JOIN totais_todos ta ON ta.repo_id = p.repo_a
        LEFT JOIN totais_todos tb ON tb.repo_id = p.repo_b
        ORDER BY p.fracao_do_menor DESC, p.comuns DESC
    """).df()


def issues_antes_do_lancamento(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Issues e comentários de issue datados antes de `LANCAMENTO_DAS_ISSUES`, um por linha.

    `pessoa` é o identificador da carga (`carga_duckdb._pessoa` do login), o de `pessoas.parquet`.
    """
    return con.execute(f"""
        SELECT repo_id, event_type, conversa AS numero, author_login,
               {_pessoa("author_login")} AS pessoa, {_ts("created_at")} AS ts, title
        FROM api
        WHERE event_type IN ('issue', 'issue_comment')
          AND {_ts("created_at")} >= TIMESTAMP '2008-01-01'
          AND {_ts("created_at")} < TIMESTAMP {_aspas(LANCAMENTO_DAS_ISSUES)}
        ORDER BY ts
    """).df()


def cria_todos(con: duckdb.DuckDBPyConnection, eventos: list[tuple[Path, str]]) -> None:
    """A visão `todos`: todo evento, de API e de git, com a conta que o assina."""
    leituras = [_leitura(caminho, papel) for caminho, papel in eventos]
    con.execute("CREATE VIEW bruto_todos AS " + " UNION ALL ".join(leituras))
    con.execute("""
        CREATE VIEW todos_os_eventos AS
        SELECT repo_id, eh_commit, CASE WHEN eh_commit THEN author ELSE author_login END AS conta
        FROM bruto_todos
    """)


def contas(con: duckdb.DuckDBPyConnection, maiores: int = 200) -> pd.DataFrame:
    """Contas com eventos, repositórios e commits: as `maiores` por eventos mais as que têm padrão.

    Padrão: as excluídas por `sem_contas_de_sistema`, as com `bot` no nome sem `[bot]` e as que só
    casam com a busca solta por trac, bugzilla, mantis, jira, import ou migrat.
    """
    con.execute("""
        CREATE TABLE por_conta_repo AS
        SELECT conta, repo_id, count(*) AS n, count(*) FILTER (WHERE eh_commit) AS commits
        FROM todos_os_eventos WHERE conta IS NOT NULL GROUP BY conta, repo_id
    """)
    con.execute("""
        CREATE TABLE por_conta AS
        SELECT conta, sum(n) AS eventos, count(*) AS repositorios, sum(commits) AS commits
        FROM por_conta_repo GROUP BY conta
    """)
    lista = ", ".join(_aspas(c) for c in CONTAS_EXCLUIDAS)
    return con.execute(f"""
        SELECT * FROM por_conta
        WHERE conta IN (SELECT conta FROM por_conta ORDER BY eventos DESC LIMIT {int(maiores)})
           OR lower(conta) IN ({lista})
           OR regexp_matches(lower(conta), {_aspas(LOGIN_UUID)})
           OR regexp_matches(lower(conta), {_aspas(LOGIN_DE_MIGRACAO)})
           OR (lower(conta) LIKE '%bot%' AND conta NOT LIKE '%[bot]')
           OR regexp_matches(lower(conta), 'trac|bugzilla|mantis|jira|import|migrat')
        ORDER BY eventos DESC
    """).df()
