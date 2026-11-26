"""Slide: ABRE mediano da Ingênua e da Coorte em cada linguagem.

Dados: `pares_usados.csv` do Wilcoxon com uma previsão por ano (cenário Longo, não casuais, janela
de 4 trimestres, previsões de 31 de dezembro): 8 em Clojure, 4 em Elixir, 8 em OCaml e 8 em Python.

Uso: .venv/bin/python scripts/granularidade/figura_abre_por_linguagem.py <pares_usados.csv> <saida>
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from icones_metodos import HandlerIcone, Icone

PARES, SAIDA = Path(sys.argv[1]), Path(sys.argv[2])
SAIDA.mkdir(parents=True, exist_ok=True)
TELA = (6.4, 3.6)
DPI = 600
CINZA, AZUL, CONTORNO = "#9a9a9a", "#1f5fbf", "#222222"
LINGUAS = [
    ("clojure", "Clojure", 8),
    ("elixir", "Elixir", 4),
    ("ocaml", "OCaml", 8),
    ("python", "Python", 8),
]

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


def virgula(valor: float, casas: int = 2) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


pares = pd.read_csv(PARES)
pares = pares[pares["janela"] == "4 trimestres"]
valores = {"Ingênua": [], "Coorte": []}
rotulos = []
linhas = []
for slug, nome, esperado in LINGUAS:
    for metodo in ["Ingênua", "Coorte"]:
        d = pares[(pares["linguagem"] == slug) & (pares["metodo"] == metodo)]
        assert len(d) == esperado, (slug, metodo, len(d))
        mediana = float(d["abre"].median())
        valores[metodo].append(mediana)
        linhas.append(
            {"linguagem": nome, "metodo": metodo, "previsoes": len(d), "abre_mediano": mediana}
        )
    rotulos.append(f"{nome}\n{esperado} previsões")
pd.DataFrame(linhas).to_csv(SAIDA / "valores.csv", index=False)

largura = 0.36
x = np.arange(len(LINGUAS))
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
        eixo.text(xi, v + 0.003, virgula(v), ha="center", va="bottom", fontsize=7)
eixo.set_ylim(0, 0.25)
eixo.set_yticks([0, 0.05, 0.10, 0.15, 0.20, 0.25])
eixo.yaxis.set_major_formatter(lambda y, _: virgula(y))
eixo.set_xticks(x, rotulos)
eixo.set_ylabel("ABRE mediano")
eixo.set_title("Erro da previsão de 12 meses em cada linguagem (ABRE)", pad=16)
icones_da_legenda = [Icone("ingenua", CINZA), Icone("coorte", AZUL)]
nomes_da_legenda = ["Ingênua", "Coorte"]
eixo.legend(
    handles=icones_da_legenda,
    labels=nomes_da_legenda,
    handler_map={Icone: HandlerIcone()},
    handleheight=2.0,
    loc="lower center",
    bbox_to_anchor=(0.5, 1.0),
    ncol=2,
    frameon=False,
    handlelength=2.0,
    borderaxespad=0.2,
)
fig.subplots_adjust(left=0.1, right=0.97, top=0.84, bottom=0.14)
fig.savefig(SAIDA / "slide_abre_por_linguagem.png", dpi=DPI)
fig.savefig(SAIDA / "slide_abre_por_linguagem.pdf")
plt.close(fig)
for linha in linhas:
    print(linha["linguagem"], linha["metodo"], f"{linha['abre_mediano']:.4f}")
