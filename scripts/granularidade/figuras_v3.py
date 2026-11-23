"""Três figuras da correção da elegibilidade, em PDF, tons de cinza e rótulos em português (`figuras-v3/`).

Largura de duas colunas do IEEE (7 polegadas). Cada figura tem o CSV com os números que ela mostra.
  1. Pirâmide de Clojure em 2014, 2018, 2022 e 2024: discussão à esquerda e código à direita, em pessoas.
  2. Projeção de 2024 por faixa, origem 31/12/2023, um painel por linguagem.
  3. Cenários em Clojure: (a) taxas de permanência por faixa; (b) real de 2010 a 2024 e projeções de 2018 a 2024.

Entradas: `<dados>` com `fig2_faixas.csv`, `fig2_totais.csv`, `fig3a_taxas.csv` e `fig3b_serie.csv`
(`figuras_v3_dados.py`) e `<composicao>`, o `composicao.csv` de Clojure da rodada v3.

Uso (na raiz do repo): .venv/bin/python scripts/granularidade/figuras_v3.py <dados> <composicao> <saida>
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

DADOS, COMPOSICAO, SAIDA = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
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
ANOS = [2014, 2018, 2022, 2024]
dados1 = composicao[composicao["ano"].isin(ANOS) & composicao["faixa"].isin(FAIXAS)].copy()
dados1["faixa"] = pd.Categorical(dados1["faixa"], categories=FAIXAS, ordered=True)
dados1 = dados1.sort_values(["ano", "faixa"])
dados1.rename(columns={"non_coding": "discussao", "coding": "codigo"}).to_csv(
    SAIDA / "figura1.csv", index=False
)
maximo = float(dados1[["non_coding", "coding"]].max().max())
limite = float(np.ceil(maximo / 100.0) * 100.0)
fig, eixos = plt.subplots(1, 4, figsize=(LARGURA, 2.2), sharey=True, sharex=True)
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
fig.savefig(SAIDA / "figura1_piramide_clojure.pdf")
plt.close(fig)

# Figura 2 ---------------------------------------------------------------------------------------
faixas2 = pd.read_csv(DADOS / "fig2_faixas.csv")
totais2 = pd.read_csv(DADOS / "fig2_totais.csv")
faixas2.to_csv(SAIDA / "figura2_faixas.csv", index=False)
totais2.to_csv(SAIDA / "figura2_totais.csv", index=False)
linguas = [nome for nome in NOMES if nome in set(faixas2["linguagem"])]
MARCADORES = [  # coluna do CSV, rótulo, marcador e cor de preenchimento
    ("Coorte", "Coorte", "o", "white"),
    ("Conservador^R", "Conservador$^{R}$", "s", CINZA_ESCURO),
    ("Ingênua-Coorte^R", "Ingênua-Coorte$^{R}$", "^", CINZA_MEDIO),
]
fig, eixos = plt.subplots(1, len(linguas), figsize=(LARGURA, 3.3), sharey=True, squeeze=False)
for eixo, lingua in zip(eixos[0], linguas, strict=True):
    parte = faixas2[faixas2["linguagem"] == lingua].set_index("faixa").reindex(FAIXAS)
    total = totais2[totais2["linguagem"] == lingua].iloc[0]
    eixo.barh(
        posicao,
        parte["real_2024"].to_numpy(),
        color=CINZA_CLARO,
        edgecolor=CINZA_ESCURO,
        linewidth=0.4,
        height=0.62,
    )
    for i in posicao:
        eixo.plot(
            [parte["Pessimista R3"].iloc[i], parte["Otimista R3"].iloc[i]], [i, i],
            color="black", linewidth=1.0, solid_capstyle="butt", zorder=3,
        )  # fmt: skip
    for coluna, _, marcador, cor in MARCADORES:
        eixo.scatter(
            parte[coluna].to_numpy(), posicao, marker=marcador, s=14, facecolor=cor,
            edgecolor="black", linewidth=0.6, zorder=4,
        )  # fmt: skip
    eixo.set_yticks(posicao, FAIXAS)
    titulo = [NOMES[lingua], f"Real {milhar(total['real_2024'])}"]
    for coluna, rotulo, _, _ in MARCADORES:
        titulo.append(f"{rotulo} {milhar(total[coluna])}")
    eixo.set_title("\n".join(titulo), fontsize=6)
    eixo.set_xlim(left=0)
    eixo.xaxis.set_major_formatter(lambda x, _: milhar(x))
    eixo.set_xlabel("Pessoas em 2024")
eixos[0][0].set_ylabel("Faixa de idade (anos)")
manuais = [
    plt.Rectangle((0, 0), 1, 1, facecolor=CINZA_CLARO, edgecolor=CINZA_ESCURO, linewidth=0.4)
]
rotulos = ["Real 2024"]
for _, nome, marcador, cor in MARCADORES:
    manuais.append(
        plt.Line2D(
            [],
            [],
            marker=marcador,
            linestyle="",
            markerfacecolor=cor,
            markeredgecolor="black",
            markersize=4,
            markeredgewidth=0.6,
        )
    )
    rotulos.append(nome)
manuais.append(plt.Line2D([], [], color="black", linewidth=1.0))
rotulos.append("Pessimista a otimista, com repositórios")
fig.legend(manuais, rotulos, loc="upper center", ncol=5, frameon=False, bbox_to_anchor=(0.5, 1.01))
fig.tight_layout(rect=(0, 0, 1, 0.92))
fig.savefig(SAIDA / "figura2_projecao_2024.pdf")
plt.close(fig)

# Figura 3 ---------------------------------------------------------------------------------------
taxas = pd.read_csv(DADOS / "fig3a_taxas.csv")
serie = pd.read_csv(DADOS / "fig3b_serie.csv")
taxas.to_csv(SAIDA / "figura3a.csv", index=False)
serie.to_csv(SAIDA / "figura3b.csv", index=False)
fig, (eixo_a, eixo_b) = plt.subplots(
    1, 2, figsize=(LARGURA, 2.8), gridspec_kw={"width_ratios": [1, 1.25]}
)
anos_janela = taxas[taxas["ano_da_taxa"].str.fullmatch(r"\d{4}")]
n_faixas = int(taxas["faixa"].max()) + 1
rotulos_faixa = [f"{i}-{i + 1}" for i in range(n_faixas - 1)] + [f"{n_faixas - 1}+"]
eixo_a.scatter(
    anos_janela["faixa"],
    anos_janela["taxa"],
    s=8,
    color=CINZA_CLARO,
    edgecolor=CINZA_MEDIO,
    linewidth=0.3,
    zorder=2,
    label="Taxa de cada ano da janela",
)
MARCAS = [
    ("ultimo", "Último ano (Coorte)", "o", "white"),
    ("media_dois", "Média dos dois últimos (Conservador)", "s", CINZA_ESCURO),
    ("minimo", "Mínimo (pessimista)", "v", CINZA_MEDIO),
    ("maximo", "Máximo (otimista)", "^", "black"),
]
for chave, rotulo, marcador, cor in MARCAS:
    parte = taxas[taxas["ano_da_taxa"] == chave]
    eixo_a.scatter(
        parte["faixa"],
        parte["taxa"],
        marker=marcador,
        s=16,
        facecolor=cor,
        edgecolor="black",
        linewidth=0.6,
        zorder=4,
        label=rotulo,
    )
eixo_a.set_xticks(range(n_faixas), rotulos_faixa)
eixo_a.set_xlabel("Faixa de idade (anos)")
eixo_a.set_ylabel("Taxa de permanência")
eixo_a.set_title("(a) Origem 31/12/2023", fontsize=7)
eixo_a.set_ylim(0.38, 1.0)
eixo_a.yaxis.set_major_formatter(lambda y, _: f"{y:.1f}".replace(".", ","))
eixo_a.legend(loc="lower right", frameon=False, fontsize=5.5)

real = serie[serie["tipo"] == "real"]
proj = serie[serie["tipo"] == "projecao"]
eixo_b.plot(real["ano"], real["valor"], color="black", linewidth=1.0, label="Real", zorder=3)
DESLOCA = 0.16
for _, linha in proj.iterrows():
    ano = linha["ano"]
    eixo_b.plot(
        [ano - DESLOCA] * 2,
        [linha["pessimista_R0"], linha["otimista_R0"]],
        color=CINZA_MEDIO,
        linewidth=2.2,
        solid_capstyle="butt",
        zorder=2,
    )
    eixo_b.plot(
        [ano + DESLOCA] * 2,
        [linha["pessimista_R3"], linha["otimista_R3"]],
        color=CINZA_ESCURO,
        linewidth=2.2,
        solid_capstyle="butt",
        zorder=2,
    )
    if linha["fora_R0"]:
        eixo_b.scatter(
            [ano - DESLOCA],
            [linha["valor"]],
            marker="x",
            color="black",
            s=22,
            linewidth=0.9,
            zorder=5,
        )
    if linha["fora_R3"]:
        eixo_b.scatter(
            [ano + DESLOCA],
            [linha["valor"]],
            marker="x",
            color="black",
            s=22,
            linewidth=0.9,
            zorder=5,
        )
eixo_b.scatter(
    proj["ano"],
    proj["coorte_R"],
    marker="o",
    s=14,
    facecolor="white",
    edgecolor="black",
    linewidth=0.7,
    zorder=4,
)
manuais = [
    plt.Line2D([], [], color="black", linewidth=1.0),
    plt.Line2D(
        [],
        [],
        marker="o",
        linestyle="",
        markerfacecolor="white",
        markeredgecolor="black",
        markersize=4,
    ),
    plt.Line2D([], [], color=CINZA_MEDIO, linewidth=2.2),
    plt.Line2D([], [], color=CINZA_ESCURO, linewidth=2.2),
    plt.Line2D([], [], marker="x", linestyle="", color="black", markersize=4),
]
eixo_b.legend(
    manuais,
    ["Real", "Coorte$^{R}$", "Pessimista a otimista, sem repositórios", "Pessimista a otimista, com repositórios", "Real fora do intervalo sem repositórios"],
    loc="upper left", frameon=False, fontsize=5.5,
)  # fmt: skip
eixo_b.set_ylim(top=6800)
eixo_b.set_xlabel("Ano projetado")
eixo_b.set_ylabel("Pessoas ativas não casuais")
eixo_b.yaxis.set_major_formatter(lambda x, _: milhar(x))
eixo_b.set_title("(b) Real de 2010 a 2024 e projeções de 2018 a 2024", fontsize=7)
fig.tight_layout()
fig.savefig(SAIDA / "figura3_cenarios_clojure.pdf")
plt.close(fig)
print("figuras gravadas em", SAIDA)
