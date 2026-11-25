"""Figuras para slide da projeção de Clojure para 5 anos (1920 × 1080 px a 300 dpi, PNG e PDF). Lê `resultado/`; não projeta nada.

  - `slide_B_<método>`: entrada, saída e ativos por ano, de 2014 a 2031, com a faixa de incerteza como área sombreada sobre as barras;
  - `slide_piramide_<método>`: pirâmide observada em 2026 e projetada em 2031, lado a lado;
  - `slide_resumo_populacao`: população de 2014 a 2031, a linha observada e uma projetada por método, com rótulo no fim de cada linha.
Fontes de 18 pt nos eixos e na legenda e de 24 pt no título; linhas de 3 pt; marcadores grandes. Estilo de `figuras-v3/figuras_artigo.py` (serifa, vírgula decimal).

Uso (na raiz do repo): .venv/bin/python scripts/granularidade/figuras_slide_clojure.py <pasta do resultado> <saida>
"""

import sys
from itertools import pairwise
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter

RESULTADO, SAIDA = Path(sys.argv[1]), Path(sys.argv[2])
SAIDA.mkdir(parents=True, exist_ok=True)
FIGURA = (6.4, 3.6)  # 1920 x 1080 px a 300 dpi
DPI = 300
METODOS = ["Ingênua", "Coorte", "Coorte^R", "Conservador", "Conservador^R", "Ingênua-Coorte^R"]
ARQUIVO = {
    "Ingênua": "ingenua",
    "Coorte": "coorte",
    "Coorte^R": "coorte_r",
    "Conservador": "conservador",
    "Conservador^R": "conservador_r",
    "Ingênua-Coorte^R": "ingenua_coorte_r",
}
ROTULO = {m: m.replace("^R", "$^{R}$") for m in METODOS}
FAIXAS6 = ["0-1", "1-2", "2-3", "3-5", "5-8", "8+"]
ROTULO_FAIXA = ["[0,1)", "[1,2)", "[2,3)", "[3,5)", "[5,8)", "[8,∞)"]
AZUL, VERMELHO = "#1f5fbf", "#c0392b"
COR_METODO = {
    "Ingênua": "#7f7f7f",
    "Coorte": "#1f77b4",
    "Coorte^R": "#d62728",
    "Conservador": "#2ca02c",
    "Conservador^R": "#ff7f0e",
    "Ingênua-Coorte^R": "#9467bd",
}
CINZA_OBSERVADO, CINZA_PROJETADO = "#cfcfcf", "#efefef"
X_ORIGEM = 2025.5  # 30/06/2026 na régua em que o ano Y é o fim de Y
plt.rcParams.update(
    {
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
        "font.size": 18,
        "axes.labelsize": 18,
        "axes.titlesize": 24,
        "xtick.labelsize": 18,
        "ytick.labelsize": 18,
        "legend.fontsize": 18,
        "lines.linewidth": 3,
        "lines.markersize": 9,
        "axes.linewidth": 1.5,
        "axes.spines.top": False,
        "pdf.fonttype": 42,
        "mathtext.fontset": "stix",
    }
)


def milhar(x: float, _=None) -> str:
    return f"{x:,.0f}".replace(",", ".")


def salva(fig, nome: str) -> None:
    fig.savefig(SAIDA / f"{nome}.png", dpi=DPI)
    fig.savefig(SAIDA / f"{nome}.pdf", dpi=DPI)
    plt.close(fig)


serie = pd.read_csv(RESULTADO / "serie_anual.csv")
trajetorias = pd.read_csv(RESULTADO / "trajetorias.csv")
observada_trimestral = pd.read_csv(
    RESULTADO / "ativos_observados_por_trimestre.csv", parse_dates=["data"]
)

# Figura B
for metodo in METODOS:
    s = serie[(serie["metodo"] == metodo) & (serie["ano"] >= 2014)].set_index("ano")
    projetado = s["parte"] == "projetada"
    fig, eixo = plt.subplots(figsize=FIGURA, constrained_layout=True)
    eixo_ativos = eixo.twinx()
    eixo_ativos.bar(s.index[~projetado], s["ativos"][~projetado], color=CINZA_OBSERVADO, width=0.78)
    eixo_ativos.bar(
        s.index[projetado],
        s["ativos"][projetado],
        color=CINZA_PROJETADO,
        edgecolor="#aaaaaa",
        linewidth=1,
        width=0.78,
    )
    ultimo_observado = int(s.index[~projetado].max())
    cone = pd.concat(
        [
            s.loc[[ultimo_observado]].assign(
                ativos_baixo=s.loc[ultimo_observado, "ativos"],
                ativos_alto=s.loc[ultimo_observado, "ativos"],
            ),
            s[projetado],
        ]
    )
    eixo_ativos.fill_between(
        cone.index,
        cone["ativos_baixo"],
        cone["ativos_alto"],
        color="#333333",
        alpha=0.35,
        linewidth=0,
    )
    eixo_ativos.set_ylim(0, 5500)
    eixo_ativos.set_yticks([0, 2000, 4000])
    eixo_ativos.yaxis.set_major_formatter(FuncFormatter(milhar))
    eixo_ativos.spines["top"].set_visible(False)
    eixo.set_zorder(eixo_ativos.get_zorder() + 1)
    eixo.patch.set_visible(False)
    for coluna, cor, marcador in (("entrada_pct", AZUL, "o"), ("saida_pct", VERMELHO, "s")):
        y = s[coluna]
        if coluna == "entrada_pct":
            fim_observado = ultimo_observado
        else:
            fim_observado = int(s[s["parte_da_saida"] == "observada"].index.max())
        observado = y[y.index <= fim_observado]
        proj = y[(y.index >= fim_observado) & y.notna()]
        eixo.plot(observado.index, observado, color=cor, marker=marcador)
        eixo.plot(
            proj.index,
            proj,
            color=cor,
            linestyle="--",
            marker=marcador,
            markerfacecolor="white",
            markeredgewidth=2.5,
        )
    eixo.axvline(X_ORIGEM, color="black", linewidth=1.5, linestyle=":")
    eixo.text((X_ORIGEM + 2031.4) / 2, 58.5, "Projeção", ha="center", va="top", fontsize=18)
    eixo.set_ylim(0, 60)
    eixo.set_yticks([0, 20, 40, 60])
    eixo.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))
    eixo.set_xlim(2013.4, 2031.4)
    eixo.set_xticks([2014, 2018, 2022, 2026, 2030])
    eixo.set_title(ROTULO[metodo])
    itens = [
        Line2D([], [], color=AZUL, marker="o", label="Entrada"),
        Line2D([], [], color=VERMELHO, marker="s", label="Saída"),
        Patch(facecolor=CINZA_OBSERVADO, label="Ativos"),
    ]
    fig.legend(handles=itens, loc="outside lower center", ncol=3, frameon=False)
    salva(fig, f"slide_B_{ARQUIVO[metodo]}")

# Pirâmides: observada em 2026 e projetada em 2031
t_final = trajetorias[trajetorias["passo"] == 20]
t_inicial = trajetorias[trajetorias["passo"] == 0]
limite = float(
    np.ceil(trajetorias[trajetorias["passo"].isin([0, 20])][FAIXAS6].max().max() / 500.0) * 500.0
)
for metodo in METODOS:
    fig, eixos = plt.subplots(
        1, 2, figsize=FIGURA, sharey=True, sharex=True, constrained_layout=True
    )
    posicao = np.arange(len(FAIXAS6))
    dados = [
        (t_inicial[t_inicial["metodo"] == metodo].iloc[0], "Observada, 2026", "#777777"),
        (t_final[t_final["metodo"] == metodo].iloc[0], "Projetada, 2031", AZUL),
    ]
    for eixo, (linha, titulo, cor) in zip(eixos, dados, strict=True):
        eixo.barh(
            posicao,
            linha[FAIXAS6].to_numpy(dtype=float),
            color=cor,
            edgecolor="#222222",
            linewidth=1,
            height=0.8,
        )
        eixo.set_title(titulo, fontsize=18)
        eixo.set_xlim(0, limite)
        eixo.set_xticks([0, 500, 1000])
        eixo.xaxis.set_major_formatter(FuncFormatter(milhar))
        eixo.set_yticks(posicao, ROTULO_FAIXA)
        eixo.spines["right"].set_visible(False)
    fig.suptitle(ROTULO[metodo], fontsize=24)
    salva(fig, f"slide_piramide_{ARQUIVO[metodo]}")

# Figura-resumo: população de 2014 a 2031, rótulo no fim de cada linha
fig, eixo = plt.subplots(figsize=FIGURA)
fig.subplots_adjust(left=0.13, right=0.62, top=0.86, bottom=0.14)


def x_do_trimestre(data: pd.Timestamp) -> float:
    return data.year + (data.month - 12) / 12  # 31/12/Y em Y, 30/06/2026 em 2025,5


observada = observada_trimestral[observada_trimestral["data"] >= "2014-12-31"]
x_obs = observada["data"].map(x_do_trimestre)
eixo.plot(x_obs, observada["ativos"], color="black")
fins = {}
for metodo in METODOS:
    t = trajetorias[trajetorias["metodo"] == metodo].sort_values("passo")
    x = X_ORIGEM + t["passo"].to_numpy() / 4
    eixo.plot(x, t["total"], color=COR_METODO[metodo], linestyle="-")
    fins[metodo] = (x[-1], float(t["total"].iloc[-1]))
eixo.axvline(X_ORIGEM, color="black", linewidth=1.5, linestyle=":")
eixo.text(X_ORIGEM + 0.2, 4780, "Projeção", ha="left", va="top", fontsize=18)
eixo.set_ylim(1500, 4800)
eixo.set_yticks([2000, 3000, 4000])
eixo.yaxis.set_major_formatter(FuncFormatter(milhar))
eixo.set_xlim(2013.8, 2030.5)
eixo.set_xticks([2014, 2018, 2022, 2026, 2030])
eixo.spines["top"].set_visible(False)
eixo.spines["right"].set_visible(False)
eixo.set_title("População de Clojure")
# posições dos rótulos: perto de cada valor final, com espaço mínimo entre eles
altura_do_rotulo = 340.0
ordem = sorted(METODOS, key=lambda m: fins[m][1])
posicoes = {m: fins[m][1] for m in ordem}
for _ in range(200):
    movido = False
    for a, b in pairwise(ordem):
        falta = altura_do_rotulo - (posicoes[b] - posicoes[a])
        if falta > 1:
            posicoes[a] -= falta / 2
            posicoes[b] += falta / 2
            movido = True
    if not movido:
        break
for metodo in METODOS:
    x_fim, y_fim = fins[metodo]
    rotulo = ROTULO[metodo]
    eixo.plot(
        [x_fim, x_fim + 0.3],
        [y_fim, posicoes[metodo]],
        color=COR_METODO[metodo],
        linewidth=1.5,
        clip_on=False,
    )
    eixo.text(
        x_fim + 0.4,
        posicoes[metodo],
        rotulo,
        color=COR_METODO[metodo],
        fontsize=18,
        va="center",
        ha="left",
    )
salva(fig, "slide_resumo_populacao")
print("figuras gravadas em", SAIDA)
