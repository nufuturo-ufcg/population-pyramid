"""Figuras da projeção de Clojure para 5 anos (`projecao_clojure_5anos.py`), uma por método.

Figura A: pirâmide observada na origem e projetadas 1, 3 e 5 anos depois, nas faixas do artigo ([0,1), [1,2), [2,3), [3,5), [5,8) e [8,∞) anos), total da faixa, o mesmo eixo nas quatro.
Figura B: taxa de entrada (azul), taxa de saída (vermelho) e ativos de cada ano (barras cinza), de 2009 até 2030; a parte projetada tem linhas tracejadas, barras mais claras com a faixa de incerteza e uma
linha vertical na origem. Estilo de `figuras-v3/figuras_artigo.py`. Também grava uma página PNG com as figuras B dos seis métodos.

Uso (na raiz do repo): .venv/bin/python scripts/granularidade/figuras_projecao_clojure.py <pasta do resultado> <saida>
"""

import sys
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
METODOS = ["Ingênua", "Coorte", "Coorte^R", "Conservador", "Conservador^R", "Ingênua-Coorte^R"]
ARQUIVO = {
    "Ingênua": "ingenua",
    "Coorte": "coorte",
    "Coorte^R": "coorte_r",
    "Conservador": "conservador",
    "Conservador^R": "conservador_r",
    "Ingênua-Coorte^R": "ingenua_coorte_r",
}
FAIXAS6 = ["0-1", "1-2", "2-3", "3-5", "5-8", "8+"]
ROTULO_FAIXA = ["[0,1)", "[1,2)", "[2,3)", "[3,5)", "[5,8)", "[8,∞)"]
AZUL, VERMELHO = "#1f5fbf", "#c0392b"
CINZA_OBSERVADO, CINZA_PROJETADO = "#d9d9d9", "#f0f0f0"
plt.rcParams.update(
    {
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
        "font.size": 7,
        "axes.labelsize": 7,
        "xtick.labelsize": 6.5,
        "ytick.labelsize": 6.5,
        "legend.fontsize": 6.5,
        "axes.spines.top": False,
        "pdf.fonttype": 42,
    }
)


def milhar(x: float, _=None) -> str:
    return f"{x:,.0f}".replace(",", ".")


def dec0(x: float, _=None) -> str:
    return f"{x:.0f}".replace(".", ",")


trajetorias = pd.read_csv(RESULTADO / "trajetorias.csv")
serie = pd.read_csv(RESULTADO / "serie_anual.csv")
origem = trajetorias[trajetorias["passo"] == 0]["data"].iloc[0]
ano_origem = int(origem[:4])

# Figura A
maximo = trajetorias[FAIXAS6].max().max()
limite = np.ceil(maximo / 100.0) * 100.0
for metodo in METODOS:
    t = trajetorias[trajetorias["metodo"] == metodo].set_index("passo")
    fig, eixos = plt.subplots(1, 4, figsize=(7.0, 2.2), sharey=True, sharex=True)
    posicao = np.arange(len(FAIXAS6))
    for eixo, (passo, titulo) in zip(
        eixos, [(0, "Observada"), (4, "+1 ano"), (12, "+3 anos"), (20, "+5 anos")], strict=True
    ):
        valores = t.loc[passo, FAIXAS6].to_numpy(dtype=float)
        cor = "#777777" if passo == 0 else AZUL
        eixo.barh(posicao, valores, color=cor, edgecolor="#222222", linewidth=0.4, height=0.8)
        data = t.loc[passo, "data"]
        eixo.set_title(
            f"{titulo}, {data[8:]}/{data[5:7]}/{data[:4]}\ntotal {milhar(t.loc[passo, 'total'])}",
            fontsize=6.8,
        )
        eixo.set_xlim(0, limite)
        eixo.set_yticks(posicao, ROTULO_FAIXA)
        eixo.xaxis.set_major_formatter(FuncFormatter(milhar))
        eixo.set_xlabel("Pessoas")
    eixos[0].set_ylabel("Faixa de idade (anos)")
    fig.suptitle(
        f"{metodo}: pirâmide de Clojure projetada a partir de {origem[8:]}/{origem[5:7]}/{origem[:4]}",
        fontsize=7.5,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(SAIDA / f"figuraA_piramides_{ARQUIVO[metodo]}.pdf")
    plt.close(fig)


# Figura B
def desenha_b(eixo_taxa, metodo: str) -> None:
    s = serie[serie["metodo"] == metodo].set_index("ano")
    anos = s.index.to_numpy()
    projetado = s["parte"].to_numpy() == "projetada"
    eixo_ativos = eixo_taxa.twinx()
    eixo_ativos.bar(anos[~projetado], s["ativos"][~projetado], color=CINZA_OBSERVADO, width=0.75)
    eixo_ativos.bar(
        anos[projetado],
        s["ativos"][projetado],
        color=CINZA_PROJETADO,
        edgecolor="#bbbbbb",
        linewidth=0.5,
        width=0.75,
    )
    p = s[projetado]
    eixo_ativos.errorbar(
        p.index,
        p["ativos"],
        yerr=[p["ativos"] - p["ativos_baixo"], p["ativos_alto"] - p["ativos"]],
        fmt="none",
        ecolor="#555555",
        elinewidth=0.8,
        capsize=1.8,
    )
    eixo_ativos.set_ylabel("Ativos no ano")
    eixo_ativos.yaxis.set_major_formatter(FuncFormatter(milhar))
    eixo_ativos.set_ylim(0, 5500)
    eixo_ativos.spines["top"].set_visible(False)
    eixo_taxa.set_zorder(eixo_ativos.get_zorder() + 1)
    eixo_taxa.patch.set_visible(False)
    for coluna, cor, marcador in (("entrada_pct", AZUL, "o"), ("saida_pct", VERMELHO, "s")):
        y = s[coluna]
        if coluna == "entrada_pct":
            ultimo_observado = ano_origem - 1  # 31/12 anterior à origem
        else:
            ultimo_observado = int(s[s["parte_da_saida"] == "observada"].index.max())
        observado = y[y.index <= ultimo_observado]
        proj = y[(y.index >= ultimo_observado) & y.notna()]
        eixo_taxa.plot(
            observado.index, observado, color=cor, linewidth=1.4, marker=marcador, markersize=2.3
        )
        eixo_taxa.plot(
            proj.index,
            proj,
            color=cor,
            linewidth=1.4,
            linestyle="--",
            marker=marcador,
            markersize=2.3,
            markerfacecolor="white",
        )
    eixo_taxa.axvline(ano_origem - 0.5, color="black", linewidth=0.7, linestyle=":")
    eixo_taxa.text(ano_origem - 0.4, 98, "origem\n30/06/2026", fontsize=5.5, va="top")
    eixo_taxa.set_ylabel("% dos ativos do ano")
    eixo_taxa.set_ylim(0, 100)
    eixo_taxa.yaxis.set_major_formatter(FuncFormatter(dec0))
    eixo_taxa.set_xlim(2008.4, 2030.6)
    eixo_taxa.set_xticks([2009, 2012, 2015, 2018, 2021, 2024, 2027, 2030])
    eixo_taxa.set_title(metodo, fontsize=7.5, y=1.0)


def itens_da_legenda() -> list:
    return [
        Line2D(
            [],
            [],
            color=AZUL,
            linewidth=1.4,
            marker="o",
            markersize=2.5,
            label="Taxa de entrada (novatos do ano)",
        ),
        Line2D(
            [],
            [],
            color=VERMELHO,
            linewidth=1.4,
            marker="s",
            markersize=2.5,
            label="Taxa de saída líquida",
        ),
        Patch(facecolor=CINZA_OBSERVADO, label="Ativos no ano"),
        Line2D(
            [], [], color="#444444", linewidth=1.2, linestyle="--", label="Projetado (tracejado)"
        ),
        Patch(
            facecolor=CINZA_PROJETADO,
            edgecolor="#bbbbbb",
            label="Ativos projetados e faixa de incerteza (p10 a p90)",
        ),
    ]


for metodo in METODOS:
    fig, eixo = plt.subplots(figsize=(3.5, 2.6), constrained_layout=True)
    desenha_b(eixo, metodo)
    fig.legend(
        handles=itens_da_legenda(), loc="outside lower center", ncol=2, frameon=False, fontsize=5.8
    )
    fig.savefig(SAIDA / f"figuraB_serie_{ARQUIVO[metodo]}.pdf")
    plt.close(fig)

fig, eixos = plt.subplots(2, 3, figsize=(12.5, 6.4), constrained_layout=True)
for eixo, metodo in zip(eixos.ravel(), METODOS, strict=True):
    desenha_b(eixo, metodo)
fig.legend(
    handles=itens_da_legenda(), loc="outside lower center", ncol=5, frameon=False, fontsize=7.5
)
fig.suptitle(
    f"Clojure: entrada, saída e ativos, observados até 2025 e projetados 5 anos a partir de {origem[8:]}/{origem[5:7]}/{origem[:4]} (Longo, não casuais)",
    fontsize=9,
)
fig.savefig(SAIDA / "figuraB_seis_metodos.png", dpi=200)
plt.close(fig)
print("figuras gravadas em", SAIDA)
