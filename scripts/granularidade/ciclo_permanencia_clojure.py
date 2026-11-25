"""Ciclo na taxa de permanência total da Coorte (última transição) de Clojure por trimestre do ano, de 2016 a 2026. Só reporta. Roda na VM.

Taxa total de permanência da transição de t − 1 para t = pessoas nas faixas de 1 em diante em t dividido por todas as pessoas em t − 1 (a média das taxas por faixa ponderada
pelas pessoas de cada faixa, como a Coorte usa com a taxa `taxas(pop[t], pop[t - 1])`). O trimestre do ano é o de t (jan a mar é a transição de dez para mar).
Critério (`hipoteses.md`): um trimestre fica sistematicamente acima (abaixo) se estiver acima (abaixo) da média dos 4 trimestres do mesmo ano em pelo menos 8 dos 10 anos completos de 2016 a 2025.

Uso (na raiz do repo, na VM): .venv/bin/python scripts/granularidade/ciclo_permanencia_clojure.py <carga> <saida>
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from estado import constroi_estado
from previsao import taxas
from rodar import le_dados

CARGA, SAIDA = Path(sys.argv[1]), Path(sys.argv[2])
SAIDA.mkdir(parents=True, exist_ok=True)
ORIGEM = pd.Timestamp("2026-06-30")
NOMES = {1: "jan a mar", 2: "abr a jun", 3: "jul a set", 4: "out a dez"}

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
    transicoes_parada=1,
)
datas = pd.to_datetime(est["datas"])
pop = est["pop_p_b"]
linhas = []
for k in range(1, len(datas)):
    antes, agora = pop[k - 1], pop[k]
    total = agora[1:].sum() / antes.sum()
    # confere com a Coorte: média das taxas por faixa ponderada pelas pessoas da faixa na data anterior
    sr = taxas(agora, antes)
    junta = np.concatenate([antes[:-2], [antes[-2] + antes[-1]]])
    ponderada = np.nansum(np.where(junta > 0, junta * np.nan_to_num(sr), 0.0)) / junta.sum()
    assert abs(total - ponderada) < 1e-9, (
        f"a taxa total não bate com a das faixas em {datas[k].date()}: {total} contra {ponderada}"
    )
    linhas.append(
        {
            "data": datas[k].date(),
            "ano": datas[k].year,
            "trimestre": datas[k].quarter,
            "pessoas_antes": antes.sum(),
            "permanecem": agora[1:].sum(),
            "taxa_total": total,
        }
    )
t = pd.DataFrame(linhas)
t = t[(t["ano"] >= 2016)]
t.to_csv(SAIDA / "permanencia_total_por_trimestre.csv", index=False, float_format="%.10g")
p = t.pivot(index="ano", columns="trimestre", values="taxa_total")
completos = p.loc[2016:2025]
media_do_ano = completos.mean(axis=1)
acima = completos.gt(media_do_ano, axis=0).sum()
abaixo = completos.lt(media_do_ano, axis=0).sum()
ordem = completos.rank(axis=1, ascending=False)


def pct(x: float) -> str:
    return "n/d" if pd.isna(x) else f"{100 * x:.1f}".replace(".", ",")


T = [
    "# Ciclo na taxa de permanência total da Coorte (Clojure, 2016 a 2026)",
    "",
    "Taxa total de permanência da última transição (de t − 1 para t), em %: pessoas nas faixas de 1 em diante em t dividido por todas as pessoas em t − 1. O trimestre é o de t. 2026 só tem os dois primeiros trimestres.",
    "",
    "| Ano | jan a mar | abr a jun | jul a set | out a dez | Média do ano |",
    "|---|---|---|---|---|---|",
]
for ano, x in p.iterrows():
    T.append(
        f"| {ano} | "
        + " | ".join(pct(x[q]) for q in (1, 2, 3, 4))
        + f" | {pct(x.mean()) if ano < 2026 else 'n/d'} |"
    )
T += [
    "",
    "Média por trimestre do ano, 2016 a 2025 (%): "
    + "; ".join(f"{NOMES[q]} {pct(completos[q].mean())}" for q in (1, 2, 3, 4))
    + ".",
    "",
    "| Trimestre | Anos acima da média do ano | Anos abaixo | Vezes em 1º lugar | Vezes em 4º lugar | Sistematicamente |",
    "|---|---|---|---|---|---|",
]
veredito = []
for q in (1, 2, 3, 4):
    sistematico = "acima" if acima[q] >= 8 else ("abaixo" if abaixo[q] >= 8 else "não")
    veredito.append(sistematico)
    T.append(
        f"| {NOMES[q]} | {acima[q]} de 10 | {abaixo[q]} de 10 | {int((ordem[q] == 1).sum())} | {int((ordem[q] == 4).sum())} | {sistematico} |"
    )
T += [
    "",
    "Critério: acima (abaixo) da média dos 4 trimestres do mesmo ano em pelo menos 8 dos 10 anos completos (2016 a 2025).",
    "",
]
(SAIDA / "ciclo_permanencia.md").write_text("\n".join(T) + "\n", encoding="utf-8")
print("\n".join(T))
