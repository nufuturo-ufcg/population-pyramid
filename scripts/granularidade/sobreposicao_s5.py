"""Sobreposição do S5: dos ativos do alvo (janela de 12 meses terminada em k+1), que fração já contribuiu nos 9 meses observados antes da origem (blocos k-2 a k).

População do S4 e do S5 (P1: segunda ocasião até o bloco do alvo). Grava, por linguagem, a média sobre todas as origens trimestrais de 2017 a 2024 e sobre as de dezembro.

Uso (na raiz do repo): .venv/bin/python scripts/granularidade/sobreposicao_s5.py <carga> <saida.csv> <linguagens...>
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from estado import FIM, grade
from rodar import le_dados

CARGA, SAIDA, LINGUAS = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3:]
datas = grade(3, FIM)
linhas = []
for lingua in LINGUAS:
    pessoas, eventos = le_dados(CARGA, lingua)
    ids = np.sort(pessoas["pessoa"].to_numpy())
    dentro = eventos["dia"] <= FIM  # a carga vai além de 31/12/2024
    pessoa_do_evento = np.searchsorted(ids, eventos["pessoa"][dentro])
    bloco = np.searchsorted(datas, eventos["dia"][dentro], side="left")
    ativ = np.zeros((len(ids), len(datas)), dtype=bool)
    ativ[pessoa_do_evento, bloco] = True
    segunda = pessoas.set_index("pessoa")["segunda"].reindex(ids).to_numpy().astype("datetime64[D]")
    sem_segunda = np.isnat(segunda) | (segunda > FIM)
    residente_desde = np.full(len(ids), len(datas) + 1)
    residente_desde[~sem_segunda] = np.searchsorted(datas, segunda[~sem_segunda], side="left")
    for k in range(len(datas) - 1):
        origem = pd.Timestamp(datas[k])
        if origem.year < 2017:
            continue
        no_alvo = ativ[:, k - 2 : k + 2].any(axis=1) & (residente_desde <= k + 1)
        observados = ativ[:, k - 2 : k + 1].any(axis=1) & no_alvo
        linhas.append(
            {
                "linguagem": lingua,
                "origem": origem.date().isoformat(),
                "ativos_do_alvo": int(no_alvo.sum()),
                "ja_contribuiram_nos_9_meses": int(observados.sum()),
                "sobreposicao": observados.sum() / no_alvo.sum() if no_alvo.sum() else np.nan,
            }
        )
    print(f"{lingua}: pronto", flush=True)
tabela = pd.DataFrame(linhas)
tabela.to_csv(SAIDA, index=False)
tabela["dezembro"] = pd.to_datetime(tabela["origem"]).dt.month == 12
resumo = tabela.groupby("linguagem")["sobreposicao"].agg(["mean", "min", "max"])
resumo_dez = (
    tabela[tabela["dezembro"]].groupby("linguagem")["sobreposicao"].agg(["mean", "min", "max"])
)
print("todas as origens trimestrais:\n", resumo.round(4), "\nsó dezembro:\n", resumo_dez.round(4))
