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
