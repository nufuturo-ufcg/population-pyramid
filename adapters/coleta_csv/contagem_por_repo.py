"""Conta os eventos de cada repositório num CSV bruto da coleta, com o leitor da carga."""

from pathlib import Path

import duckdb
from adapters.coleta_csv.carga_duckdb import LINHA_MAXIMA, NULOS, _aspas


def conta_eventos_por_repo(
    arquivo: Path, saida: Path, memoria_gb: int = 24, threads: int = 4
) -> None:
    """Grava `saida` (CSV com `repo_id` e `eventos`). Só lê `arquivo`."""
    nulos = "[" + ", ".join(_aspas(n) for n in NULOS) + "]"
    con = duckdb.connect()
    con.execute(f"PRAGMA threads={threads}")
    con.execute(f"PRAGMA memory_limit='{memoria_gb}GB'")
    con.execute(f"PRAGMA temp_directory={_aspas(saida.parent / 'duckdb_tmp')}")
    con.execute(f"""
        COPY (
            SELECT repo_id, count(*) AS eventos
            FROM read_csv({_aspas(arquivo)}, delim='|', quote='"', escape='"', header=true,
                          all_varchar=true, ignore_errors=true, strict_mode=false,
                          nullstr={nulos}, max_line_size={LINHA_MAXIMA})
            GROUP BY repo_id
        ) TO {_aspas(saida)} (HEADER, DELIMITER ',')
    """)


def datas_por_repo(arquivo: Path, saida: Path, memoria_gb: int = 24, threads: int = 4) -> None:
    """Grava `saida` (CSV com `repo_id`, primeiro e último evento e a contagem), só com leitura.

    Estimativa sem os filtros da carga de commit copiado e identidade: tira só conta apagada
    (`ghost`), bot (`[bot]` no login) e data fora de 2008 até hoje.
    """
    nulos = "[" + ", ".join(_aspas(n) for n in NULOS) + "]"
    con = duckdb.connect()
    con.execute(f"PRAGMA threads={threads}")
    con.execute(f"PRAGMA memory_limit='{memoria_gb}GB'")
    con.execute(f"PRAGMA temp_directory={_aspas(saida.parent / 'duckdb_tmp')}")
    con.execute(f"""
        COPY (
            SELECT repo_id, min(ts) AS primeiro, max(ts) AS ultimo, count(*) AS eventos
            FROM (
                SELECT repo_id, CAST(try_cast(created_at AS TIMESTAMPTZ) AS TIMESTAMP) AS ts,
                       coalesce(author_login, '') AS login
                FROM read_csv({_aspas(arquivo)}, delim='|', quote='"', escape='"', header=true,
                              all_varchar=true, ignore_errors=true, strict_mode=false,
                              nullstr={nulos}, max_line_size={LINHA_MAXIMA})
            )
            WHERE ts >= TIMESTAMP '2008-01-01' AND ts <= now()
              AND login <> 'ghost' AND login NOT LIKE '%[bot]'
            GROUP BY repo_id
        ) TO {_aspas(saida)} (HEADER, DELIMITER ',')
    """)


def commits_copiados_por_repo(
    arquivo: Path, saida: Path, memoria_gb: int = 24, threads: int = 4
) -> None:
    """Grava `saida`: `repo_id`, commits e commits cujo SHA aparece em outro repositório."""
    nulos = "[" + ", ".join(_aspas(n) for n in NULOS) + "]"
    con = duckdb.connect()
    con.execute(f"PRAGMA threads={threads}")
    con.execute(f"PRAGMA memory_limit='{memoria_gb}GB'")
    con.execute(f"PRAGMA temp_directory={_aspas(saida.parent / 'duckdb_tmp')}")
    con.execute(f"""
        COPY (
            WITH c AS (
                SELECT DISTINCT repo_id, sha
                FROM read_csv({_aspas(arquivo)}, delim='|', quote='"', escape='"', header=true,
                              all_varchar=true, ignore_errors=true, strict_mode=false,
                              nullstr={nulos}, max_line_size={LINHA_MAXIMA})
                WHERE event_type = 'commit' AND sha IS NOT NULL
            ), n AS (
                SELECT sha, count(*) AS repos FROM c GROUP BY sha
            )
            SELECT c.repo_id, count(*) AS commits,
                   sum(CASE WHEN n.repos > 1 THEN 1 ELSE 0 END) AS commits_copiados
            FROM c JOIN n USING (sha)
            GROUP BY c.repo_id
        ) TO {_aspas(saida)} (HEADER, DELIMITER ',')
    """)


def duplicatas_por_repo(
    arquivo: Path, saida: Path, memoria_gb: int = 40, threads: int = 16
) -> None:
    """Grava `saida`: `repo_id`, `event_type`, linhas e linhas repetidas. Só lê `arquivo`.

    A chave de evento é a de `verificar_duplicatas_eventos.py` da coleta: todas as colunas,
    menos `collection_started_at`. Cada linha vira um hash de 64 bits dentro do seu repositório
    e tipo (colisão desprezível nesse grupo). Célula vazia fica como texto vazio, como no Python.
    """
    leitor = f"""read_csv({_aspas(arquivo)}, delim='|', quote='"', escape='"', header=true,
                          all_varchar=true, ignore_errors=true, strict_mode=false,
                          nullstr='__sem_nulo__', max_line_size={LINHA_MAXIMA})"""
    con = duckdb.connect()
    con.execute(f"PRAGMA threads={threads}")
    con.execute(f"PRAGMA memory_limit='{memoria_gb}GB'")
    con.execute(f"PRAGMA temp_directory={_aspas(saida.parent / 'duckdb_tmp')}")
    colunas = []
    for linha in con.execute(f"DESCRIBE SELECT * FROM {leitor}").fetchall():
        if linha[0] != "collection_started_at":
            colunas.append(f'"{linha[0]}"')
    con.execute(f"""
        COPY (
            SELECT repo_id, event_type, count(*) AS linhas,
                   count(*) - count(DISTINCT h) AS repetidas
            FROM (SELECT repo_id, event_type, hash({", ".join(colunas)}) AS h FROM {leitor})
            GROUP BY repo_id, event_type
        ) TO {_aspas(saida)} (HEADER, DELIMITER ',')
    """)
