"""Apoio dos scripts de resumo: nomes, rótulos, formatação, Wilcoxon, Holm e médias geométricas."""

import numpy as np
import pandas as pd
from previsao import COMBOS, metodos_b, todos_os_metodos
from scipy.stats import spearmanr, wilcoxon


class Nomes(dict):
    def __missing__(self, chave: str) -> str:  # linguagem fora da lista (teste sintético)
        return chave


NOMES = Nomes(
    {"clojure": "Clojure", "elixir": "Elixir", "ocaml": "OCaml", "zig": "Zig", "python": "Python"}
)
PASSOS = [12, 6, 3, 2, 1, 0.5]
NOME_PASSO = {12: "12 meses", 6: "6 meses", 3: "3 meses", 2: "2 meses", 1: "1 mês", 0.5: "15 dias"}
POPS = ["P1", "P2"]
NOME_POP = {"P0": "P0 (vida inteira)", "P1": "P1 (residentes pelo passado)", "P2": "P2 (todos)"}
METODOS = todos_os_metodos()
HONESTAS = COMBOS
FAIXAS = ["0-1", "1-2", "2-3", "3-5", "5-8", "8+"]
ROTULO = {m: m.replace("_", " ") for m in METODOS}
ROTULO.update(
    {
        "ingenua": "ingênua",
        "hp3": "Hamilton-Perry 3 anos",
        "hp5": "Hamilton-Perry 5 anos",
        "holt_amortecido": "Holt amortecido",
        "coorte_amortecida": "coorte amortecida",
        "deriva": "ingênua com deriva",
    }
)


def num(x: float, casas: int = 3) -> str:
    return "n/d" if pd.isna(x) else f"{x:.{casas}f}".replace(".", ",")


def pvalor(x: float) -> str:
    if pd.isna(x):
        return "n/d"
    return f"{x:.3f}".replace(".", ",") if x >= 0.001 else f"{x:.1e}".replace(".", ",")


def teste(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) < 2 or np.allclose(a, b):
        return np.nan
    try:
        return float(wilcoxon(a, b).pvalue)
    except ValueError:
        return np.nan


def holm(p: np.ndarray) -> np.ndarray:
    ajustado = np.full(len(p), np.nan)
    validos = np.where(~np.isnan(p))[0]
    ordem = validos[np.argsort(p[validos])]
    maximo = 0.0
    for posicao, i in enumerate(ordem):
        maximo = max(maximo, min(1.0, (len(ordem) - posicao) * p[i]))
        ajustado[i] = maximo
    return ajustado


def geometrica(x: list[float]) -> float:
    bons = [v for v in x if not np.isnan(v) and v > 0]
    return float(np.exp(np.mean(np.log(bons)))) if bons else np.nan


def rho(x: list[float], y: list[float]) -> float:
    if len(x) < 3 or np.isnan(y).any() or len(set(y)) < 2:
        return np.nan
    return float(spearmanr(x, y).statistic)


METODOS_B = metodos_b()
for _m in METODOS_B:
    ROTULO[_m] = ROTULO[_m[:-2]] + " (B)" if _m[:-2] in ROTULO else _m.replace("_", " ")
