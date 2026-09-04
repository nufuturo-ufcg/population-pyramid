#!/usr/bin/env python3
"""Corrige o header do CSV para o formato que load_repositories() espera.

Uso:
    python fix_header_csv.py runs/repositorios_elixir_alvo.csv
"""

import csv
import sys
from pathlib import Path

RENAME = {
    "id": "repo_id",
    "name": "repo_name",
    "defaultBranch": "default_branch",
}


def fix_header(csv_path):
    lines = csv_path.open("r", encoding="utf-8").readlines()
    header_line = lines[0]

    reader = csv.reader([header_line])
    fields = next(reader)

    new_fields = [RENAME.get(f, f) for f in fields]

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(new_fields)
        for line in lines[1:]:
            f.write(line)

    renomeadas = [f"{k} -> {v}" for k, v in RENAME.items() if k in fields]
    print(f"Arquivo: {csv_path}")
    print(f"Colunas originais: {len(fields)}")
    print(f"Renomeadas: {renomeadas}")
    print(f"OK")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Uso: python {Path(__file__).name} <caminho_do_csv>")
        sys.exit(1)
    fix_header(Path(sys.argv[1]))
