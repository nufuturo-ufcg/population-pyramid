"""Slide: o erro da Ingênua e da Coorte em Onoue et al. (IEICE16) contra o nosso.

Onoue: Tabela 3 do IEICE16 (página 1311 da revista, página 8 do PDF), linha "All types", coluna
"All": mediana do ABRE do cohort (0,4000) e do baseline (0,6000), 36 projetos. Previsão de setembro
de 2013 a partir de junho de 2013 (3 meses à frente).
Nosso: mediana do ABRE da Coorte e da Ingênua nas previsões de 31 de dezembro das 4 linguagens
(8 em Clojure, OCaml e Python e 4 em Elixir = 28), janela de 4 trimestres, horizonte de 12 meses.

Uso: .venv/bin/python scripts/granularidade/figura_abre_onoue.py <pares_usados.csv> <saida>
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch

PARES, SAIDA = Path(sys.argv[1]), Path(sys.argv[2])
SAIDA.mkdir(parents=True, exist_ok=True)
TELA = (6.4, 3.6)
DPI = 600
CINZA, AZUL, CONTORNO = "#9a9a9a", "#1f5fbf", "#222222"
ONOUE = {"Ingênua": 0.6000, "Coorte": 0.4000}  # Tabela 3, "All types", "All"

plt.rcParams.update(
    {
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Times", "Nimbus Roman", "DejaVu Serif"],
        "font.size": 7,
        "axes.titlesize": 7.5,
        "axes.labelsize": 7,
        "legend.fontsize": 6.5,
        "xtick.labelsize": 6.5,
        "ytick.labelsize": 6.5,
        "axes.linewidth": 0.5,
        "pdf.fonttype": 42,
        "axes.spines.top": False,
        "axes.spines.right": False,
    }
)


def virgula(valor: float) -> str:
    return f"{valor:.2f}".replace(".", ",")


pares = pd.read_csv(PARES)
pares = pares[pares["janela"] == "4 trimestres"]
linguas = ["clojure", "elixir", "ocaml", "python"]
nosso = {}
for metodo in ["Ingênua", "Coorte"]:
    d = pares[(pares["metodo"] == metodo) & pares["linguagem"].isin(linguas)]
    assert len(d) == 28, (metodo, len(d))
    nosso[metodo] = float(d["abre"].median())

grupos = ["Projetos\n(Onoue et al., 36 projetos)", "Linguagens\n(4 linguagens, 28 previsões)"]
valores = {
    "Ingênua": [ONOUE["Ingênua"], nosso["Ingênua"]],
    "Coorte": [ONOUE["Coorte"], nosso["Coorte"]],
}
largura = 0.34
x = np.arange(len(grupos))
fig, eixo = plt.subplots(figsize=TELA)
for metodo, deslocamento, cor in [("Ingênua", -largura / 2, CINZA), ("Coorte", largura / 2, AZUL)]:
    eixo.bar(
        x + deslocamento,
        valores[metodo],
        width=largura,
        color=cor,
        edgecolor=CONTORNO,
        linewidth=0.4,
    )
    for xi, v in zip(x + deslocamento, valores[metodo], strict=True):
        eixo.text(xi, v + 0.01, virgula(v), ha="center", va="bottom", fontsize=7)
eixo.set_ylim(0, 0.7)
eixo.set_yticks([0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7])
eixo.yaxis.set_major_formatter(lambda y, _: virgula(y))
eixo.set_xticks(x, grupos)
eixo.set_ylabel("ABRE mediano")
eixo.set_title("Erro da previsão: projetos contra linguagens", pad=16)
legenda = [
    Patch(facecolor=CINZA, edgecolor=CONTORNO, linewidth=0.4, label="Ingênua (baseline)"),
    Patch(facecolor=AZUL, edgecolor=CONTORNO, linewidth=0.4, label="Coorte"),
]
eixo.legend(
    handles=legenda,
    loc="lower center",
    bbox_to_anchor=(0.5, 1.0),
    ncol=2,
    frameon=False,
    handlelength=1.4,
    borderaxespad=0.2,
)
fig.subplots_adjust(left=0.1, right=0.97, top=0.84, bottom=0.14)
fig.savefig(SAIDA / "slide_abre_onoue_contra_linguagens.png", dpi=DPI)
fig.savefig(SAIDA / "slide_abre_onoue_contra_linguagens.pdf")
plt.close(fig)
print({m: round(v, 4) for m, v in nosso.items()})
