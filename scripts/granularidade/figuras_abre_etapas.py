"""ABRE mediano de Clojure em dois slides, para apresentar os métodos em duas etapas.

Slide A: Ingênua, Coorte e Conservador (cinza). Slide B: os seis métodos, com os três novos em azul.
Mesmos dados de `figuras_abre_slide.py` (cenário Longo, não casuais, janela de 4 trimestres, as 8
previsões de 31 de dezembro). As duas figuras têm o mesmo eixo (0 a 0,10), os seis lugares de barra
e a mesma espessura: o slide A deixa vazio o espaço das três barras que ainda não entraram.

Uso: .venv/bin/python scripts/granularidade/figuras_abre_etapas.py <pares_usados.csv> <saida>
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

PARES, SAIDA = Path(sys.argv[1]), Path(sys.argv[2])
SAIDA.mkdir(parents=True, exist_ok=True)
TELA = (6.4, 3.6)
DPI = 600
ORDEM = ["Ingênua", "Coorte", "Conservador", "Coorte^R", "Conservador^R", "Ingênua-Coorte^R"]
CINZA, AZUL, CONTORNO = "#9a9a9a", "#1f5fbf", "#222222"
LIMITE_X = 0.10

plt.rcParams.update(
    {
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Times", "Nimbus Roman", "DejaVu Serif"],
        "font.size": 7,
        "axes.titlesize": 7.5,
        "axes.labelsize": 7,
        "xtick.labelsize": 6.5,
        "ytick.labelsize": 6.5,
        "axes.linewidth": 0.5,
        "pdf.fonttype": 42,
        "mathtext.fontset": "stix",
        "axes.spines.top": False,
        "axes.spines.right": False,
    }
)


def virgula(valor: float) -> str:
    return f"{valor:.2f}".replace(".", ",")


pares = pd.read_csv(PARES)
clojure = pares[(pares["janela"] == "4 trimestres") & (pares["linguagem"] == "clojure")]
medianas = {}
for metodo in ORDEM:
    abre = clojure.loc[clojure["metodo"] == metodo, "abre"]
    assert len(abre) == 8, metodo
    medianas[metodo] = float(abre.median())
assert max(medianas.values()) < LIMITE_X


def desenha(quantos: int, nome: str) -> None:
    """Desenha as `quantos` primeiras barras de ORDEM, nos seis lugares fixos."""
    fig, eixo = plt.subplots(figsize=TELA)
    posicoes = []
    valores = []
    cores = []
    for i in range(quantos):
        metodo = ORDEM[i]
        posicoes.append(i)
        valores.append(medianas[metodo])
        cores.append(CINZA if i < 3 else AZUL)
    eixo.barh(posicoes, valores, color=cores, edgecolor=CONTORNO, linewidth=0.4, height=0.7)
    for y, v in zip(posicoes, valores, strict=True):
        eixo.text(v + 0.002, y, virgula(v), va="center", ha="left", fontsize=7)
    eixo.set_ylim(len(ORDEM) - 0.5, -0.5)  # seis lugares, o primeiro no topo
    eixo.set_yticks(posicoes, [ORDEM[i].replace("^R", "$^{R}$") for i in posicoes])
    eixo.set_xlim(0, LIMITE_X)
    eixo.set_xticks([0, 0.02, 0.04, 0.06, 0.08, 0.10])
    eixo.xaxis.set_major_formatter(lambda x, _: virgula(x))
    eixo.set_xlabel("ABRE mediano")
    eixo.set_title("Clojure: erro da previsão de 12 meses (ABRE)")
    fig.subplots_adjust(left=0.2, right=0.93, top=0.88, bottom=0.16)
    fig.savefig(SAIDA / f"{nome}.png", dpi=DPI)
    fig.savefig(SAIDA / f"{nome}.pdf")
    plt.close(fig)


desenha(3, "slide_abre_clojure_A_tres_metodos")
desenha(6, "slide_abre_clojure_B_seis_metodos")
print({m: round(v, 4) for m, v in medianas.items()})
