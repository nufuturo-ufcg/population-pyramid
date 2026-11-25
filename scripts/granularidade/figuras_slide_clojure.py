"""Figuras para slide (1920 × 1080 px a 300 dpi, PNG e PDF, fontes de 18 pt e título de 24 pt). Lê `resultado/` e os CSV das figuras 1 e 4; não projeta nada.

  - `slide_B_<método>`: entrada, saída e ativos por ano, de 2014 a 2031, com "% dos ativos" no eixo esquerdo e "Ativos" no direito; a faixa de incerteza é um retângulo sombreado em volta do
    topo de cada barra projetada;
  - `slide_piramide_<método>`: pirâmide observada em 2026 e projetada em 2031, lado a lado;
  - `slide_resumo_populacao`: população de 2014 a 2031 em toda a largura, o rótulo de cada método na ponta da linha, sem traço, e "Desenvolvedores ativos" no eixo y;
  - `slide_piramides_cinco_linguagens_2024`: a Figura 4 (discussão à esquerda, código à direita, % dos ativos);
  - `slide_piramide_clojure_2014_2024`: a Figura 1 (Clojure em 2014, 2018, 2022 e 2024, em pessoas).

Uso (na raiz do repo): .venv/bin/python scripts/granularidade/figuras_slide_clojure.py <pasta do resultado> <figura1.csv> <figura4.csv> <saida>
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
from matplotlib.patches import Patch, Rectangle
from matplotlib.ticker import FuncFormatter

RESULTADO, FIGURA1, FIGURA4, SAIDA = (
    Path(sys.argv[1]),
    Path(sys.argv[2]),
    Path(sys.argv[3]),
    Path(sys.argv[4]),
)
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
CINZA_ESCURO, CINZA_MEDIO, CINZA_CLARO = "#222222", "#777777", "#cccccc"
NOMES = {
    "clojure": "Clojure",
    "elixir": "Elixir",
    "zig": "Zig",
    "ocaml": "OCaml",
    "python": "Python",
}
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
LARGURA_BARRA = 0.78
for metodo in METODOS:
    s = serie[(serie["metodo"] == metodo) & (serie["ano"] >= 2014)].set_index("ano")
    projetado = s["parte"] == "projetada"
    fig, eixo = plt.subplots(figsize=FIGURA, constrained_layout=True)
    eixo_ativos = eixo.twinx()
    eixo_ativos.bar(
        s.index[~projetado], s["ativos"][~projetado], color=CINZA_OBSERVADO, width=LARGURA_BARRA
    )
    eixo_ativos.bar(
        s.index[projetado],
        s["ativos"][projetado],
        color=CINZA_PROJETADO,
        edgecolor="#aaaaaa",
        linewidth=1,
        width=LARGURA_BARRA,
    )
    ultimo_observado = int(s.index[~projetado].max())
    for ano, x in s[projetado].iterrows():
        assert x["ativos_baixo"] <= x["ativos"] <= x["ativos_alto"], (
            f"{metodo} {ano}: a barra fica fora da faixa"
        )
        eixo_ativos.add_patch(
            Rectangle(
                (ano - LARGURA_BARRA / 2, x["ativos_baixo"]),
                LARGURA_BARRA,
                x["ativos_alto"] - x["ativos_baixo"],
                facecolor="#222222",
                alpha=0.4,
                edgecolor="none",
            )
        )
    eixo_ativos.set_ylim(0, 5500)
    eixo_ativos.set_yticks([0, 2000, 4000])
    eixo_ativos.yaxis.set_major_formatter(FuncFormatter(milhar))
    eixo_ativos.set_ylabel("Ativos")
    eixo_ativos.spines["top"].set_visible(False)
    eixo.set_zorder(eixo_ativos.get_zorder() + 1)
    eixo.patch.set_visible(False)
    for coluna, cor, marcador in (("entrada_pct", AZUL, "o"), ("saida_pct", VERMELHO, "s")):
        y = s[coluna]
        fim_observado = (
            ultimo_observado
            if coluna == "entrada_pct"
            else int(s[s["parte_da_saida"] == "observada"].index.max())
        )
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
    eixo.set_ylabel("% dos ativos")
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

# Pirâmides por método: observada em 2026 e projetada em 2031
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

# Figura-resumo: população de 2014 a 2031 em toda a largura, rótulo na ponta de cada linha
fig, eixo = plt.subplots(figsize=FIGURA)
fig.subplots_adjust(left=0.16, right=0.995, top=0.86, bottom=0.14)


def x_do_trimestre(data: pd.Timestamp) -> float:
    return data.year + (data.month - 12) / 12  # 31/12/Y em Y, 30/06/2026 em 2025,5


observada = observada_trimestral[observada_trimestral["data"] >= "2014-12-31"]
eixo.plot(observada["data"].map(x_do_trimestre), observada["ativos"], color="black")
fins = {}
for metodo in METODOS:
    t = trajetorias[trajetorias["metodo"] == metodo].sort_values("passo")
    x = X_ORIGEM + t["passo"].to_numpy() / 4
    eixo.plot(x, t["total"], color=COR_METODO[metodo])
    fins[metodo] = (x[-1], float(t["total"].iloc[-1]))
eixo.axvline(X_ORIGEM, color="black", linewidth=1.5, linestyle=":")
eixo.text(X_ORIGEM + 0.2, 4780, "Projeção", ha="left", va="top", fontsize=18)
eixo.set_ylim(1500, 4800)
eixo.set_yticks([2000, 3000, 4000])
eixo.yaxis.set_major_formatter(FuncFormatter(milhar))
eixo.set_ylabel("Desenvolvedores ativos")
eixo.set_xlim(2013.8, 2037.6)
eixo.set_xticks([2014, 2018, 2022, 2026, 2030])
eixo.spines["bottom"].set_bounds(2013.8, 2030.5)
eixo.spines["right"].set_visible(False)
eixo.set_title("População de Clojure")
altura_do_rotulo = 340.0  # unidades de y de uma linha de rótulo
linhas_do_rotulo = {m: (2 if m == "Ingênua-Coorte^R" else 1) for m in METODOS}
ordem = sorted(METODOS, key=lambda m: fins[m][1])
posicoes = {m: fins[m][1] for m in ordem}
for _ in range(200):
    movido = False
    for a, b in pairwise(ordem):
        falta = altura_do_rotulo * (linhas_do_rotulo[a] + linhas_do_rotulo[b]) / 2 - (
            posicoes[b] - posicoes[a]
        )
        if falta > 1:
            posicoes[a] -= falta / 2
            posicoes[b] += falta / 2
            movido = True
    if not movido:
        break
for metodo in METODOS:
    rotulo = "Ingênua-\nCoorte$^{R}$" if metodo == "Ingênua-Coorte^R" else ROTULO[metodo]
    eixo.text(
        fins[metodo][0] + 0.25,
        posicoes[metodo],
        rotulo,
        color=COR_METODO[metodo],
        fontsize=18,
        va="center",
        ha="left",
        linespacing=0.95,
    )
salva(fig, "slide_resumo_populacao")


# Figura 4 e Figura 1: pirâmides de discussão (esquerda) e código (direita)
def desenha_piramide(
    eixo, d: pd.DataFrame, coluna_discussao: str, coluna_codigo: str, limite_x: float
) -> None:
    d = d.set_index("faixa").reindex(FAIXAS6)
    posicao = np.arange(len(FAIXAS6))
    eixo.barh(
        posicao,
        -d[coluna_discussao].to_numpy(),
        color=CINZA_CLARO,
        edgecolor=CINZA_ESCURO,
        linewidth=1,
        height=0.8,
    )
    eixo.barh(
        posicao,
        d[coluna_codigo].to_numpy(),
        color=CINZA_MEDIO,
        edgecolor=CINZA_ESCURO,
        linewidth=1,
        height=0.8,
    )
    eixo.axvline(0, color=CINZA_ESCURO, linewidth=1)
    eixo.set_xlim(-limite_x, limite_x)
    eixo.set_yticks(posicao, ROTULO_FAIXA)
    eixo.spines["right"].set_visible(False)


legenda_lado = [
    Patch(facecolor=CINZA_CLARO, edgecolor=CINZA_ESCURO, label="Discussão"),
    Patch(facecolor=CINZA_MEDIO, edgecolor=CINZA_ESCURO, label="Código"),
]
f4 = pd.read_csv(FIGURA4)
limite4 = float(np.ceil(f4[["discussao_pct", "codigo_pct"]].max().max() / 5.0) * 5.0)
fig, eixos = plt.subplots(1, 5, figsize=FIGURA, sharey=True, sharex=True, constrained_layout=True)
for eixo, lingua in zip(eixos, ["clojure", "elixir", "zig", "ocaml", "python"], strict=True):
    desenha_piramide(eixo, f4[f4["linguagem"] == lingua], "discussao_pct", "codigo_pct", limite4)
    eixo.set_title(NOMES[lingua], fontsize=24)
    eixo.set_xticks([-20, 0, 20])
    eixo.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{abs(v):.0f}"))
eixos[2].set_xlabel("% dos ativos")
fig.legend(handles=legenda_lado, loc="outside lower center", ncol=2, frameon=False)
salva(fig, "slide_piramides_cinco_linguagens_2024")

f1 = pd.read_csv(FIGURA1)
limite1 = float(np.ceil(f1[["discussao", "codigo"]].max().max() / 500.0) * 500.0)
anos = [2014, 2018, 2022, 2024]
fig, eixos = plt.subplots(1, 4, figsize=FIGURA, sharey=True, sharex=True, constrained_layout=True)
for eixo, ano in zip(eixos, anos, strict=True):
    desenha_piramide(eixo, f1[f1["ano"] == ano], "discussao", "codigo", limite1)
    eixo.set_title(str(ano), fontsize=24)
    eixo.set_xticks([-limite1 / 2, 0, limite1 / 2])
    eixo.xaxis.set_major_formatter(FuncFormatter(lambda v, _: milhar(abs(v))))
eixos[1].set_xlabel("Pessoas")
fig.legend(handles=legenda_lado, loc="outside lower center", ncol=2, frameon=False)
salva(fig, "slide_piramide_clojure_2014_2024")
print("figuras gravadas em", SAIDA)
