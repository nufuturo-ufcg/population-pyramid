"""Sazonalidade dos novatos de Clojure e efeito da média de 4 trimestres (no lugar de 2) nos novatos previstos na origem. Roda na VM. Sem projeção nova.

(a) Novatos do modelo: faixa de 0 a 3 meses da pirâmide da RQ3 (`est["N_b"]`) em cada fim de trimestre.
(b) Primeira contribuição de quem tem mais de uma ocasião na vida (RQ1), por trimestre do calendário.
De 2016 a 2026 (2026 só com o primeiro semestre). Compara primeiro e segundo semestres nos 10 anos completos (2016 a 2025).
Efeito dos 4 trimestres: os novatos que a Coorte (`nov["V0"]`) e a Coorte^R (`nov["V2"]`, com repositórios novos e razões) usam na origem, com `JANELA_DAS_CONTAGENS` 2 e 4.

Uso (na raiz do repo, na VM): .venv/bin/python scripts/granularidade/sazonalidade_novatos.py <carga> <saida> [origem]
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import previsao
from estado import constroi_estado, corta_estado
from previsao import (
    POOL,
    gera_regras,
    metodos_b,
    metodos_intervalo_nova,
    metodos_intervalo_r,
    metodos_r,
    preve_estado,
)
from rodar import le_dados

CARGA, SAIDA = Path(sys.argv[1]), Path(sys.argv[2])
ORIGEM = pd.Timestamp(sys.argv[3] if len(sys.argv) > 3 else "2026-06-30")
SAIDA.mkdir(parents=True, exist_ok=True)
OPCOES_ESTADO = {
    "janela_blocos": 4,
    "idade": "descontada",
    "com_parada": True,
    "transicoes_parada": 2,
}
TRIMESTRES = {1: "jan a mar", 2: "abr a jun", 3: "jul a set", 4: "out a dez"}


def dec(x: float, casas: int = 1) -> str:
    return "n/d" if pd.isna(x) else f"{x:.{casas}f}".replace(".", ",")


pessoas, eventos = le_dados(CARGA, "clojure")
previsao.JANELA_DAS_CONTAGENS = 2
previsao.JANELA_DO_CONSERVADOR = 20
est = constroi_estado(pessoas, eventos, 3, "P1", np.datetime64(ORIGEM), **OPCOES_ESTADO)
datas = pd.to_datetime(est["datas"])
K0 = len(datas) - 1
assert datas[K0] == ORIGEM

# (a) novatos do modelo por trimestre
modelo = pd.DataFrame({"data": datas, "novatos": est["N_b"]})
modelo["ano"], modelo["trimestre"] = modelo["data"].dt.year, modelo["data"].dt.quarter
modelo = modelo[(modelo["ano"] >= 2016) & (modelo["data"] <= ORIGEM)]
# (b) primeira contribuição de não casuais (RQ1)
p = pd.read_parquet(
    Path(CARGA) / "clojure" / "origem" / "pessoas.parquet",
    columns=["pessoa", "primeiro", "ocasioes"],
)
p = p[
    (p["ocasioes"] > 1)
    & (p["primeiro"] >= "2016-01-01")
    & (p["primeiro"] <= ORIGEM + pd.Timedelta(days=1))
]
rq1 = (
    p.groupby([p["primeiro"].dt.year.rename("ano"), p["primeiro"].dt.quarter.rename("trimestre")])
    .size()
    .rename("novatos")
    .reset_index()
)
tabelas = {"modelo": modelo[["ano", "trimestre", "novatos"]], "rq1": rq1}
for nome, t in tabelas.items():
    t.to_csv(SAIDA / f"novatos_por_trimestre_{nome}.csv", index=False)

T = [
    "# Sazonalidade dos novatos de Clojure, 2016 a 2026",
    "",
    "Novatos por trimestre do ano. 2026 só tem o primeiro semestre (o terceiro trimestre está incompleto nos dados). Ver `hipoteses.md` para o critério de sazonalidade.",
    "",
]
veredito = {}
for nome, titulo in (
    ("modelo", "(a) Novatos do modelo (faixa de 0 a 3 meses da pirâmide da RQ3)"),
    ("rq1", "(b) Primeira contribuição de não casuais (RQ1)"),
):
    t = tabelas[nome].pivot(index="ano", columns="trimestre", values="novatos")
    t["H1"], t["H2"] = t[1] + t[2], t[3] + t[4]
    t["razao"] = t["H1"] / t["H2"]
    completos = t.loc[2016:2025]
    mais = int((completos["H1"] > completos["H2"]).sum())
    menos = int((completos["H1"] < completos["H2"]).sum())
    mediana = float(completos["razao"].median())
    media_trim = completos[[1, 2, 3, 4]].mean()
    sazonal = (max(mais, menos) >= 8) and (abs(mediana - 1) >= 0.10)
    veredito[nome] = (sazonal, mais, menos, mediana)
    T += [
        f"## {titulo}",
        "",
        "| Ano | jan a mar | abr a jun | jul a set | out a dez | 1º semestre | 2º semestre | Razão 1º / 2º |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for ano, x in t.iterrows():
        h2 = "n/d" if pd.isna(x[3]) else f"{x['H2']:.0f}"
        T.append(
            f"| {ano} | {x[1]:.0f} | {x[2]:.0f} | {'n/d' if pd.isna(x[3]) else f'{x[3]:.0f}'} | {'n/d' if pd.isna(x[4]) else f'{x[4]:.0f}'} | {x['H1']:.0f} | {h2} | {dec(x['razao'], 2)} |"
        )
    T += [
        "",
        "Média por trimestre do ano, 2016 a 2025: "
        + "; ".join(f"{TRIMESTRES[q]} {dec(media_trim[q])}" for q in (1, 2, 3, 4))
        + ".",
        f"Em 2016 a 2025, o primeiro semestre teve mais novatos que o segundo em {mais} dos 10 anos e menos em {menos}. Razão mediana 1º/2º: {dec(mediana, 2)}. Critério de sazonalidade: {'atendido' if sazonal else 'não atendido'}.",
        "",
    ]

# Efeito da média de 4 trimestres nos novatos previstos na origem
regras = gera_regras(len(POOL))
K1 = len(datas)
nomes_hist = [
    "ingenua",
    "deriva",
    "holt_amortecido",
    *metodos_b(),
    *metodos_r(),
    *metodos_intervalo_r(),
    *metodos_intervalo_nova(),
]
hist = {
    "previsto": {m: np.full(K1, np.nan) for m in nomes_hist},
    "rf": np.full((K1, len(regras)), np.nan),
    "rf_B": np.full((K1, len(regras)), np.nan),
}
for r in (1, 2, 3):
    hist[f"rf_R{r}_B"] = np.full((K1, len(regras)), np.nan)
efeito = {}
for janela in (2, 4):
    previsao.JANELA_DAS_CONTAGENS = janela
    previsao.DETALHE = {}
    preve_estado(corta_estado(est, K0), hist, regras, POOL, ("B",), 20, False)
    d, previsao.DETALHE = previsao.DETALHE, None
    efeito[janela] = {
        "coorte": d["coorte_V0_B"]["novatos"],
        "coorte_r": d["coorte_R3_B"]["novatos"],
        **d["_componentes_V2"],
    }
previsao.JANELA_DAS_CONTAGENS = 2
n = est["N_b"]
T += [
    f"## Novatos previstos na origem {ORIGEM.date()}: média dos 2 últimos trimestres contra média dos 4 últimos",
    "",
    f"Novatos do modelo nos últimos 4 trimestres (do mais antigo ao mais recente): {', '.join(f'{n[K0 - i]:.0f}' for i in (3, 2, 1, 0))}.",
    "",
    "| Peça | 2 últimos | 4 últimos | Mudança |",
    "|---|---|---|---|",
]
linhas = {
    "Coorte: novatos por trimestre (média das contagens de novatos)": (
        efeito[2]["coorte"][0],
        efeito[4]["coorte"][0],
    ),
    "Coorte^R: novatos no 1º trimestre projetado": (
        efeito[2]["coorte_r"][0],
        efeito[4]["coorte_r"][0],
    ),
    "Coorte^R: novatos por trimestre, média dos 20 passos": (
        float(np.mean(efeito[2]["coorte_r"])),
        float(np.mean(efeito[4]["coorte_r"])),
    ),
    "Coorte^R: repositórios novos por trimestre": (
        efeito[2]["repos_novos"],
        efeito[4]["repos_novos"],
    ),
    "Coorte^R: novatos por repositório novo": (
        efeito[2]["novatos_por_repo_novo"],
        efeito[4]["novatos_por_repo_novo"],
    ),
    "Coorte^R: novatos por repositório existente": (
        efeito[2]["novatos_por_repo_existente"],
        efeito[4]["novatos_por_repo_existente"],
    ),
}
for nome, (a, b) in linhas.items():
    T.append(
        f"| {nome} | {dec(a, 2 if a < 20 else 1)} | {dec(b, 2 if b < 20 else 1)} | {dec(100 * (b - a) / a, 1)}% |"
    )
T.append("")
(SAIDA / "sazonalidade.md").write_text("\n".join(T) + "\n", encoding="utf-8")
print("\n".join(T))
print(veredito)
