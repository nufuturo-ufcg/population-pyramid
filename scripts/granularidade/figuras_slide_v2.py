"""Figuras para slide no estilo das figuras do paper (`figuras-v3/figura1_piramide_clojure.pdf` e `figura4_piramides_2024.pdf`). Sem conta nova: os mesmos dados das figuras atuais.

O desenho do paper (serifa, dois cinzas, contorno fino de 0,4, legenda numa linha acima dos painéis, texto de 6,5 a 7 pt) é refeito numa tela de 6,4 × 3,6 pol (1920 × 1080 px a 300 dpi, 16:9) com
pouca margem. Num slide de 13,33 pol de largura a tela é ampliada 2,08 vezes e o texto aparece com 13 a 15 pt; as proporções entre texto e barras são as do paper.
  - `slide_piramide_clojure_2014_2024`: Figura 1 (pessoas, o mesmo eixo nos quatro painéis, rótulos 1.000, 0 e 1.000);
  - `slide_piramides_cinco_linguagens_2024`: Figura 4 (% dos ativos, o mesmo eixo nos cinco painéis, rótulos 20%, 0 e 20%);
  - `slide_erro_medio_clojure`: MAPE médio das previsões de 12 meses (janela de 4 trimestres) de cada método em Clojure;
  - `slide_projecao_clojure_coorte_r`: ativos observados e a Coorte^R a partir de 30/06/2026 e de 31/12/2025, com a faixa p10 a p90.

Uso (na raiz do repo): .venv/bin/python scripts/granularidade/figuras_slide_v2.py <figura1.csv> <figura4.csv> <avaliacao/comparacao.csv> <clojure-5anos> <saida>
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter

FIGURA1, FIGURA4, COMPARACAO, PROJECAO, SAIDA = (Path(a) for a in sys.argv[1:6])
SAIDA.mkdir(parents=True, exist_ok=True)
TELA = (6.4, 3.6)  # 1920 x 1080 px a 300 dpi
DPI = 300
FAIXAS = ["0-1", "1-2", "2-3", "3-5", "5-8", "8+"]
ROTULO_FAIXA = ["[0,1)", "[1,2)", "[2,3)", "[3,5)", "[5,8)", "[8,∞)"]
NOMES = {
    "clojure": "Clojure",
    "elixir": "Elixir",
    "zig": "Zig",
    "ocaml": "OCaml",
    "python": "Python",
}
CINZA_ESCURO, CINZA_MEDIO, CINZA_CLARO = (
    "#222222",
    "#777777",
    "#cccccc",
)  # contorno, código e discussão (os do paper)
AZUL, LARANJA = "#1f5fbf", "#e07b00"
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
        "mathtext.fontset": "stix",
        "axes.spines.top": False,
        "axes.spines.right": False,
    }
)


def milhar(x: float, _=None) -> str:
    return f"{x:,.0f}".replace(",", ".")


def salva(fig, nome: str) -> None:
    fig.savefig(SAIDA / f"{nome}.png", dpi=DPI)
    fig.savefig(SAIDA / f"{nome}.pdf", dpi=DPI)
    plt.close(fig)


def desenha_piramide(eixo, d: pd.DataFrame, discussao: str, codigo: str, limite: float) -> None:
    d = d.set_index("faixa").reindex(FAIXAS)
    posicao = np.arange(len(FAIXAS))
    eixo.barh(
        posicao,
        -d[discussao].to_numpy(),
        color=CINZA_CLARO,
        edgecolor=CINZA_ESCURO,
        linewidth=0.4,
        height=0.8,
    )
    eixo.barh(
        posicao,
        d[codigo].to_numpy(),
        color=CINZA_MEDIO,
        edgecolor=CINZA_ESCURO,
        linewidth=0.4,
        height=0.8,
    )
    eixo.axvline(0, color=CINZA_ESCURO, linewidth=0.5)
    eixo.set_xlim(-limite, limite)
    eixo.set_yticks(posicao, ROTULO_FAIXA)


LEGENDA_LADO = [
    Patch(facecolor=CINZA_CLARO, edgecolor=CINZA_ESCURO, linewidth=0.4, label="Discussão"),
    Patch(facecolor=CINZA_MEDIO, edgecolor=CINZA_ESCURO, linewidth=0.4, label="Código"),
]


def pirami_slide(
    colunas: int,
    nome: str,
    dados: list,
    titulos: list,
    discussao: str,
    codigo: str,
    limite: float,
    ticks: list,
    formato,
    rotulo_x: str,
) -> None:
    fig, eixos = plt.subplots(1, colunas, figsize=TELA, sharey=True, sharex=True)
    for eixo, d, titulo in zip(eixos, dados, titulos, strict=True):
        desenha_piramide(eixo, d, discussao, codigo, limite)
        eixo.set_title(titulo)
        eixo.set_xticks(ticks)
        eixo.xaxis.set_major_formatter(FuncFormatter(formato))
    eixos[0].set_ylabel("Faixa de idade (anos)")
    eixos[colunas // 2].set_xlabel(rotulo_x, labelpad=2)
    fig.legend(
        handles=LEGENDA_LADO, loc="upper center", ncol=2, frameon=False, bbox_to_anchor=(0.5, 0.995)
    )
    fig.subplots_adjust(left=0.07, right=0.995, top=0.885, bottom=0.115, wspace=0.12)
    salva(fig, nome)


# Figura 1: Clojure em 2014, 2018, 2022 e 2024, em pessoas
f1 = pd.read_csv(FIGURA1)
anos = [2014, 2018, 2022, 2024]
limite1 = float(np.ceil(f1[["discussao", "codigo"]].max().max() / 100.0) * 100.0)
pirami_slide(
    4,
    "slide_piramide_clojure_2014_2024",
    [f1[f1["ano"] == a] for a in anos],
    [str(a) for a in anos],
    "discussao",
    "codigo",
    limite1,
    [-1000, 0, 1000],
    lambda v, _: milhar(abs(v)),
    "Pessoas",
)

# Figura 4: as cinco linguagens em 2024, em % dos ativos
f4 = pd.read_csv(FIGURA4)
linguas = ["clojure", "elixir", "zig", "ocaml", "python"]
limite4 = float(np.ceil(f4[["discussao_pct", "codigo_pct"]].max().max() / 5.0) * 5.0)
pirami_slide(
    5,
    "slide_piramides_cinco_linguagens_2024",
    [f4[f4["linguagem"] == x] for x in linguas],
    [NOMES[x] for x in linguas],
    "discussao_pct",
    "codigo_pct",
    limite4,
    [-20, 0, 20],
    lambda v, _: "0" if v == 0 else f"{abs(v):.0f}%",
    "% dos ativos",
)

# Erro médio de cada método em Clojure (MAPE médio, janela de 4 trimestres)
comp = pd.read_csv(COMPARACAO)
comp = comp[comp["linguagem"] == "clojure"].set_index("metodo")
ordem = ["Ingênua", "Coorte", "Coorte^R", "Conservador", "Conservador^R", "Ingênua-Coorte^R"]
valores = [float(comp.loc[m, "mape_4"]) for m in ordem]
fig, eixo = plt.subplots(figsize=TELA)
posicao = np.arange(len(ordem))
cores = [AZUL if m == "Coorte^R" else "#9a9a9a" for m in ordem]
eixo.barh(posicao, valores, color=cores, edgecolor=CINZA_ESCURO, linewidth=0.4, height=0.7)
for y, v in zip(posicao, valores, strict=True):
    eixo.text(v + 0.12, y, f"{v:.1f}".replace(".", ","), va="center", ha="left", fontsize=7)
eixo.set_yticks(posicao, [m.replace("^R", "$^{R}$") for m in ordem])
eixo.invert_yaxis()
eixo.set_xlim(0, max(valores) * 1.15)
eixo.set_xlabel("MAPE médio das previsões de 12 meses (%)")
eixo.set_title("Clojure: erro médio de cada método")
fig.subplots_adjust(left=0.2, right=0.97, top=0.88, bottom=0.16)
salva(fig, "slide_erro_medio_clojure")

# Projeção de Clojure com a Coorte^R, a partir de 30/06/2026 e de 31/12/2025
observada = pd.read_csv(
    PROJECAO / "origem-2026-06-30" / "ativos_observados_por_trimestre.csv", parse_dates=["data"]
)
observada = observada[observada["data"] >= "2014-01-01"]
fig, eixo = plt.subplots(figsize=TELA)
eixo.plot(observada["data"], observada["ativos"], color="black", linewidth=1.2)
for pasta, cor in (("origem-2026-06-30", AZUL), ("origem-2025-12-31", LARANJA)):
    t = pd.read_csv(PROJECAO / pasta / "trajetorias.csv", parse_dates=["data"])
    t = t[t["metodo"] == "Coorte^R"].sort_values("passo")
    e = pd.read_csv(PROJECAO / pasta / "erro_por_passo.csv")
    e = e[e["metodo"] == "Coorte^R"].set_index("passo")
    baixo = [t["total"].iloc[0]] + [
        row["total"] * (1 + e.loc[row["passo"], "real_sobre_previsto_p10"])
        for _, row in t[t["passo"] >= 1].iterrows()
    ]
    alto = [t["total"].iloc[0]] + [
        row["total"] * (1 + e.loc[row["passo"], "real_sobre_previsto_p90"])
        for _, row in t[t["passo"] >= 1].iterrows()
    ]
    eixo.fill_between(t["data"], baixo, alto, color=cor, alpha=0.2, linewidth=0)
    eixo.plot(t["data"], t["total"], color=cor, linestyle="--", linewidth=1.2)
origem = pd.Timestamp("2025-12-31")
eixo.axvline(origem, color="black", linewidth=0.6, linestyle=":")
eixo.text(origem + pd.Timedelta(days=60), 4750, "Projeção", ha="left", va="top", fontsize=7)
eixo.set_ylim(1000, 4800)
eixo.yaxis.set_major_formatter(FuncFormatter(milhar))
eixo.set_ylabel("Desenvolvedores ativos")
eixo.set_xlim(pd.Timestamp("2014-01-01"), pd.Timestamp("2031-09-30"))
eixo.set_xticks([pd.Timestamp(f"{a}-01-01") for a in (2014, 2018, 2022, 2026, 2030)])
eixo.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
itens = [
    Line2D([], [], color="black", linewidth=1.2, label="Observado"),
    Line2D([], [], color=AZUL, linewidth=1.2, linestyle="--", label="Coorte$^{R}$ de 30/06/2026"),
    Line2D(
        [], [], color=LARANJA, linewidth=1.2, linestyle="--", label="Coorte$^{R}$ de 31/12/2025"
    ),
]
fig.legend(handles=itens, loc="upper center", ncol=3, frameon=False, bbox_to_anchor=(0.5, 0.995))
eixo.text(
    0.01,
    0.02,
    "Faixa sombreada: p10 a p90 do erro histórico",
    transform=eixo.transAxes,
    fontsize=6,
    va="bottom",
)
fig.subplots_adjust(left=0.1, right=0.985, top=0.9, bottom=0.1)
salva(fig, "slide_projecao_clojure_coorte_r")
print("figuras gravadas em", SAIDA)
