"""Figura 1: pirâmide de Clojure em 2014, 2018, 2022 e 2024, com o lado de cada pessoa pela regra única (`vitalidade.lado_no_ano`).

PDF, tons de cinza, 7 polegadas, rótulos em português. Discussão à esquerda e código à direita, em pessoas, 6 faixas. Lê `composicao.csv` de Clojure
da rodada com a definição única (v3b) e grava `figura1.csv` e `figura1_piramide_clojure.pdf`. É a Figura 1 de `figuras_v3.py` sem as figuras 2 e 3.

Uso (na raiz do repo): .venv/bin/python scripts/granularidade/figura1_piramide_clojure.py <composicao.csv> <saida> [<anos> [<nome>]]
`<anos>` são os anos separados por vírgula (padrão 2014,2018,2022,2024) e `<nome>` o nome dos arquivos (padrão
`figura1_piramide_clojure`, com o CSV em `figura1.csv`). Com `<nome>`, grava `<nome>.pdf`, `<nome>.png` e `<nome>.csv`.
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

COMPOSICAO, SAIDA = Path(sys.argv[1]), Path(sys.argv[2])
ANOS = [int(a) for a in sys.argv[3].split(",")] if len(sys.argv) > 3 else [2014, 2018, 2022, 2024]
NOME = sys.argv[4] if len(sys.argv) > 4 else "figura1_piramide_clojure"
NOME_CSV = f"{NOME}.csv" if len(sys.argv) > 4 else "figura1.csv"
SAIDA.mkdir(parents=True, exist_ok=True)
LARGURA = 7.0
FAIXAS = ["0-1", "1-2", "2-3", "3-5", "5-8", "8+"]
NOMES = {"clojure": "Clojure", "elixir": "Elixir", "ocaml": "OCaml", "python": "Python"}
CINZA_ESCURO, CINZA_MEDIO, CINZA_CLARO = "#222222", "#777777", "#cccccc"
plt.rcParams.update(
    {
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Times", "Nimbus Roman", "DejaVu Serif"],
        "font.size": 7,
        "axes.titlesize": 7,
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


def milhar(x: float) -> str:
    return f"{x:,.0f}".replace(",", ".")


# Figura 1 ---------------------------------------------------------------------------------------
composicao = pd.read_csv(COMPOSICAO)
dados1 = composicao[composicao["ano"].isin(ANOS) & composicao["faixa"].isin(FAIXAS)].copy()
dados1["faixa"] = pd.Categorical(dados1["faixa"], categories=FAIXAS, ordered=True)
dados1 = dados1.sort_values(["ano", "faixa"])
dados1.rename(columns={"non_coding": "discussao", "coding": "codigo"}).to_csv(
    SAIDA / NOME_CSV, index=False
)
maximo = float(dados1[["non_coding", "coding"]].max().max())
limite = float(np.ceil(maximo / 100.0) * 100.0)
fig, eixos = plt.subplots(1, len(ANOS), figsize=(LARGURA, 2.2), sharey=True, sharex=True)
posicao = np.arange(len(FAIXAS))
for eixo, ano in zip(eixos, ANOS, strict=True):
    parte = dados1[dados1["ano"] == ano].set_index("faixa").reindex(FAIXAS)
    eixo.barh(
        posicao,
        -parte["non_coding"].to_numpy(),
        color=CINZA_CLARO,
        edgecolor=CINZA_ESCURO,
        linewidth=0.4,
        height=0.8,
    )
    eixo.barh(
        posicao,
        parte["coding"].to_numpy(),
        color=CINZA_MEDIO,
        edgecolor=CINZA_ESCURO,
        linewidth=0.4,
        height=0.8,
    )
    eixo.axvline(0, color=CINZA_ESCURO, linewidth=0.5)
    eixo.set_title(str(ano))
    eixo.set_xlim(-limite, limite)
    eixo.set_yticks(posicao, FAIXAS)
    eixo.xaxis.set_major_formatter(lambda x, _: milhar(abs(x)))
    eixo.set_xlabel("Pessoas")
eixos[0].set_ylabel("Faixa de idade (anos)")
manuais = [
    plt.Rectangle((0, 0), 1, 1, facecolor=CINZA_CLARO, edgecolor=CINZA_ESCURO, linewidth=0.4),
    plt.Rectangle((0, 0), 1, 1, facecolor=CINZA_MEDIO, edgecolor=CINZA_ESCURO, linewidth=0.4),
]
fig.legend(
    manuais,
    ["Discussão", "Código"],
    loc="upper center",
    ncol=2,
    frameon=False,
    bbox_to_anchor=(0.5, 1.02),
)
fig.tight_layout(rect=(0, 0, 1, 0.93))
fig.savefig(SAIDA / f"{NOME}.pdf")
if len(sys.argv) > 4:
    fig.savefig(SAIDA / f"{NOME}.png", dpi=300)
plt.close(fig)
