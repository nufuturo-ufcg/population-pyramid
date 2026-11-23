"""Compara a origem de duas cargas (`<carga>/<linguagem>/origem/*.parquet`): linhas e igualdade exata.

Serve para conferir que a carga nova repete a antiga nas linguagens que a correção não muda.
Uso (na VM): .venv/bin/python scripts/granularidade/compara_cargas.py <carga antiga> <carga nova> <linguagens...>
"""

import sys
from pathlib import Path

import pandas as pd

ANTIGA, NOVA = Path(sys.argv[1]), Path(sys.argv[2])
for lingua in sys.argv[3:]:
    pasta_antiga = ANTIGA / lingua / "origem"
    pasta_nova = NOVA / lingua / "origem"
    for arquivo in sorted(pasta_antiga.glob("*.parquet")):
        antigo = pd.read_parquet(arquivo)
        novo = pd.read_parquet(pasta_nova / arquivo.name)
        igual = "sim"
        if antigo.shape != novo.shape:
            igual = "NÃO (forma)"
        else:
            colunas = list(antigo.columns)
            a = antigo.sort_values(colunas).reset_index(drop=True)
            b = novo.sort_values(colunas).reset_index(drop=True)
            igual = "sim" if a.equals(b) else "NÃO (valores)"
        print(
            f"{lingua} {arquivo.name}: antiga {len(antigo)} linhas, nova {len(novo)} linhas, igual: {igual}"
        )
