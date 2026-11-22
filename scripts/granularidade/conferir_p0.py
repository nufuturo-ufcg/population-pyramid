"""Confere P0 com 12 meses contra os experimentos anteriores (ver `hipoteses.md`, seção Conferências). Roda depois de `rodar.py` em P0 e passo 12.

Uso: .venv/bin/python conferir_p0.py <saida> <linguagem> <pasta com projecao-novos-metodos, projecao-combinacoes e projecao-variantes-passos> [--estrito]
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

saida, lingua, refs = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
estrito = "--estrito" in sys.argv
pasta = saida / "unidades"
novo = pd.read_csv(pasta / f"{lingua}_P0_12_pares.csv.gz")
novo["ano"] = novo["origem"].str[:4].astype(int)
novo = novo[novo["origem"].str.endswith("-12-31")]
confere = pd.read_csv(pasta / f"{lingua}_P0_12_conferencia.csv")
confere["ano"] = confere["origem"].str[:4].astype(int)
problemas = []


def compara(rotulo: str, a: pd.Series, b: pd.Series, estrito_aqui: bool) -> None:
    ambos = a.notna() & b.notna()
    diferentes = ambos & ((a - b).abs() > 1e-6 * np.maximum(1.0, b.abs()))
    print(
        f"{lingua} {rotulo}: {int(ambos.sum())} comparados, {int(diferentes.sum())} diferentes, {int((a.notna() & b.isna()).sum())} só no novo, {int((a.isna() & b.notna()).sum())} só no antigo"
    )
    if estrito_aqui and diferentes.any():
        problemas.append(rotulo)


# 1. sete métodos contra projecao-novos-metodos
antigo = pd.read_csv(refs / "projecao-novos-metodos" / "pares.csv")
antigo = antigo[(antigo["linguagem"] == lingua) & (antigo["horizonte"] == 1)]
for metodo in [
    "ingenua",
    "coorte_V0",
    "deriva",
    "holt_amortecido",
    "hp3",
    "hp5",
    "coorte_amortecida",
]:
    a = novo[novo["metodo"] == metodo].set_index("ano")["previsto"]
    b = antigo[antigo["metodo"] == metodo].set_index("origem")["previsto"]
    anos = a.index.intersection(b.index)
    compara(
        f"novos métodos, {metodo}",
        a.loc[anos],
        b.loc[anos],
        estrito or metodo != "coorte_amortecida",
    )
    r = novo[novo["metodo"] == metodo].set_index("ano")["real"]
    rb = antigo[antigo["metodo"] == metodo].set_index("origem")["real"]
    assert (r.loc[anos] == rb.loc[anos]).all(), ("real", metodo)

# 2. C1 a C7 do pool de 7 contra projecao-combinacoes
comb = pd.read_csv(refs / "projecao-combinacoes" / "pares.csv")
comb = comb[(comb["linguagem"] == lingua) & (comb["horizonte"] == 1)]
for c in ["C1", "C2", "C3", "C4", "C5", "C6", "C7"]:
    a = confere[confere["metodo"] == f"{c}_7"].set_index("ano")["previsto"]
    b = comb[comb["metodo"] == c].set_index("origem")["previsto"]
    anos = a.index.intersection(b.index)
    compara(f"combinações, {c}", a.loc[anos], b.loc[anos], c in ["C1", "C2", "C3", "C4", "C5"])

# 3. variantes contra projecao-variantes-passos (passo de 12 meses, dezembro)
passos = pd.read_csv(refs / "projecao-variantes-passos" / f"passos_{lingua}.csv")
passos = passos[
    (passos["passo_meses"] == 12)
    & (passos["medida"] == "total")
    & passos["origem"].str.endswith("-12-31")
    & passos["variante"].isin(["V0", "V1", "V2", "V3a", "V3b", "V4a", "V4b"])
]
passos["ano"] = passos["origem"].str[:4].astype(int)
for familia in ["coorte", "conservador", "pessimista", "otimista"]:
    for v in ["V0", "V1", "V2", "V3a", "V3b", "V4a", "V4b"]:
        a = novo[novo["metodo"] == f"{familia}_{v}"].set_index("ano")["previsto"]
        b = passos[(passos["metodo"] == familia) & (passos["variante"] == v)].set_index("ano")[
            "previsto"
        ]
        anos = a.index.intersection(b.index)
        # o repositório do primeiro evento varia até 0,1% entre cargas: tolerância larga nas variantes que dividem novatos por tipo de repositório
        compara(f"variantes, {familia} {v}", a.loc[anos], b.loc[anos], v in ["V0", "V1"])
if problemas:
    raise SystemExit(f"{lingua}: diferenças em {problemas}")
print(f"{lingua}: P0 com 12 meses confere")
