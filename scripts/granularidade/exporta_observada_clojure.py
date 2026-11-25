"""Exporta os ativos observados de Clojure (RQ3, P1) em cada fim de trimestre até a origem, para a figura-resumo. Roda na VM. Não projeta nada.

Uso (na raiz do repo, na VM): .venv/bin/python scripts/granularidade/exporta_observada_clojure.py <carga> <saida.csv> [origem]
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from estado import constroi_estado
from rodar import le_dados

CARGA, SAIDA = Path(sys.argv[1]), Path(sys.argv[2])
ORIGEM = pd.Timestamp(sys.argv[3] if len(sys.argv) > 3 else "2026-06-30")
pessoas, eventos = le_dados(CARGA, "clojure")
est = constroi_estado(
    pessoas,
    eventos,
    3,
    "P1",
    np.datetime64(ORIGEM),
    janela_blocos=4,
    idade="descontada",
    com_parada=True,
    transicoes_parada=2,
)
datas = pd.to_datetime(est["datas"])
assert datas[-1] == ORIGEM
pd.DataFrame({"data": datas.date, "ativos": est["pop_p_b"].sum(axis=1)}).to_csv(SAIDA, index=False)
print(f"{len(datas)} trimestres até {ORIGEM.date()} em {SAIDA}")
