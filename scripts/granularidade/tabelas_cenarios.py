"""Seleção de origens e leitura das previsões dos cenários S1, S3h, S4, S5 e S2 (usada por `resumo_s1_a_s5.py` e `planilha_projecao.py`).

Origens de cada cenário (cada método precisa ter ABRE definido):
  S1, S3h, S5 (todas): todo recorte trimestral de 2017 em diante.
  S4, S2, S5 (dezembro): só dezembro de 2017 em diante.
"""

from pathlib import Path

import pandas as pd

LINGUAS = ["clojure", "elixir", "ocaml", "python"]  # Zig fica fora da RQ3
NOMES = {
    "clojure": "Clojure",
    "elixir": "Elixir",
    "ocaml": "OCaml",
    "python": "Python",
    "zig": "Zig",
}
METODOS = {
    "ingenua": "Ingênua",
    "coorte_R0": "Coorte",
    "coorte_R3": "Coorte^R",
    "conservador_R3": "Conservador^R",
    "C3_R3": "Ingênua-Coorte^R",
}
# coluna da tabela: (cenário, só dezembro?)
COLUNAS = [("S1", False), ("S3h", False), ("S4", True), ("S5", False), ("S5", True), ("S2", True)]
PRIMEIRA_ORIGEM = pd.Timestamp("2017-01-01")


def rotulo(cenario: str, so_dezembro: bool) -> str:
    return f"{cenario} (dezembro)" if cenario == "S5" and so_dezembro else cenario


def num3(x: float) -> str:
    return f"{x:.3f}".replace(".", ",")


def carrega(pastas: dict[str, Path], cenario: str, lingua: str) -> pd.DataFrame | None:
    pasta = pastas[cenario] / "unidades"
    caminhos = [
        pasta / f"{lingua}_{cenario}_pares.csv.gz",
        pasta / f"{lingua}_{cenario}_R3_pares.csv.gz",
    ]
    if not all(c.exists() for c in caminhos):
        return None
    t = pd.concat([pd.read_csv(c) for c in caminhos], ignore_index=True)
    t = t[t["metodo"].isin(METODOS)].drop_duplicates(["k", "metodo"])
    abre = t.pivot(index="k", columns="metodo", values="abre")[list(METODOS)]
    origem = pd.to_datetime(t.drop_duplicates("k").set_index("k")["origem"])
    abre["origem"] = origem
    return abre


def origens(abre: pd.DataFrame, so_dezembro: bool) -> pd.DataFrame:
    escolhidas = abre[abre["origem"] >= PRIMEIRA_ORIGEM]
    if so_dezembro:
        escolhidas = escolhidas[escolhidas["origem"].dt.month == 12]
    return escolhidas[escolhidas[list(METODOS)].notna().all(axis=1)]
