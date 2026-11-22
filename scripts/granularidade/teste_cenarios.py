"""Teste com dados sintéticos dos cenários IEICE16 (sem a VM): S2 reproduz a versão A de `projecao-granularidade`, vazamento e controles em S1, S2, S3 e por repositório,
fatorial R0 a R3 definido e consistente, projeção por repositório sem vazamento.

Uso (na raiz do repo): .venv/bin/python scripts/granularidade/teste_cenarios.py <pasta temporária>
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cenarios
import repos_ieice
import rodar
from teste_sintetico import gera_linguagem, grava_carga

TMP = Path(sys.argv[1])
TMP.mkdir(parents=True, exist_ok=True)
pessoas_brutas, eventos_brutos = gera_linguagem()
grava_carga(pessoas_brutas, eventos_brutos, TMP)
pessoas, eventos = rodar.le_dados(TMP, "sint")
granularidade = TMP / "gran"
rodar.roda_unidade(
    pessoas, eventos, "sint", "P1", 12, granularidade / "unidades", False, None, ("A",), True
)
saida = TMP / "cen" / "unidades"
for c in ["S2", "S1", "S3", "S1b", "S3h"]:
    cenarios.roda_cenario(pessoas, eventos, "sint", c, saida, True, None, granularidade)
    teste = pd.read_csv(saida / f"sint_{c}_vazamento.csv")
    assert teste["estados_iguais"].all() and (teste["maior_diferenca_relativa"] < 1e-9).all(), (
        c,
        teste,
    )
    assert teste["controle_eventos_futuros_difere"].any(), (
        f"{c}: o controle de eventos futuros nunca difere"
    )
    if c == "S2":
        assert teste["controle_promocoes_difere"].any(), "S2: o controle de promoções nunca difere"
    principal = pd.read_csv(saida / f"sint_{c}_pares.csv.gz")
    r1 = pd.read_csv(saida / f"sint_{c}_R1_pares.csv.gz")
    assert {"coorte_R0", "coorte_V0", "C4_R0", "coorte_amortecida_R0"} <= set(
        principal["metodo"]
    ) and "coorte_R1" in set(r1["metodo"])
    # R0 é a V0 e R1 é a V2
    for a, b in [("coorte_R0", "coorte_V0"), ("conservador_R0", "conservador_V0")]:
        assert np.allclose(
            principal[principal["metodo"] == a]["previsto"],
            principal[principal["metodo"] == b]["previsto"],
            equal_nan=True,
        )
    assert np.allclose(
        r1[r1["metodo"] == "coorte_R1"]["previsto"],
        principal[principal["metodo"] == "coorte_V2"]["previsto"],
        equal_nan=True,
    )
    if (
        c != "S2"
    ):  # conservador e C3 do IEICE16: R1 e R3 coincidem com a V2 e com R3; C3 é a média da ingênua e da coorte
        todos = pd.concat(
            [principal] + [pd.read_csv(saida / f"sint_{c}_R{r}_pares.csv.gz") for r in (1, 2, 3)]
        )
        prev = todos.pivot(index="k", columns="metodo", values="previsto")
        for a, b in [("conservador_IEICE_R0", "conservador_IEICE"), ("conservador_IEICE_R1", "conservador_V2"),
                     ("conservador_IEICE_R3", "conservador_R3"), ("coorte_IEICE_R1", "coorte_R1"), ("coorte_IEICE_R3", "coorte_R3")]:  # fmt: skip
            assert np.allclose(prev[a], prev[b], equal_nan=True), (c, a, b)
        for r in range(4):
            media = (prev["ingenua"] + prev[f"coorte_IEICE_R{r}"]) / 2
            assert np.allclose(prev[f"C3_IEICE_R{r}"], media, equal_nan=True), (c, r)
        assert (
            prev["conservador_IEICE_R2"].notna().any()
            and prev["conservador_IEICE_R0"].notna().any()
        )
    print(
        f"{c}: {principal['metodo'].nunique()} métodos no arquivo principal, controles diferem, R0 igual à V0 e R1 igual à V2"
    )
repos_ieice.roda_repos(eventos, "sint", saida, True, None)
teste = pd.read_csv(saida / "sint_repos_vazamento.csv")
assert teste["estados_iguais"].all() and teste["controle_eventos_futuros_difere"].any()
somas = pd.read_csv(saida / "sint_repos_somas.csv")
assert set(somas["r"]) == {"R0", "R1", "R2", "R3"} and set(somas["metodo"]) == {
    "ingenua",
    "coorte",
    "conservador",
}
print("cenários sintéticos: tudo confere")
