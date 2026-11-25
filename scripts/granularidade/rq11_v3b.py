"""RQ1.1 de Clojure na carga v3b com a definição única de entrada e saída (`definicao-unica/hipoteses.md`, item 2).

Lê a tabela anual de `confere_identidade.py` (que vem de `vitalidade.tabela_anual`) e grava, em `<saida>`:
  - `rq11_tabela_anual.csv` e `.md`: de 2008 a 2024, ativos, entradas (novatos e voltas), saídas (sem volta e com volta),
    natalidade, mortalidade e crescimento natural;
  - `rq11_extremos.csv`: ano de maior e de menor crescimento natural (de 2009 em diante) e primeiro ano negativo;
  - `rq11_natalidade_mortalidade.pdf`: taxa de entrada em azul, taxa de saída em vermelho e os ativos em barras cinza ao fundo, uma
    coluna do IEEE, no estilo de `figuras-v3/figuras_artigo.py`.

Uso (na raiz do repo): .venv/bin/python scripts/granularidade/rq11_v3b.py <tabela_anual.csv> <saida>
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import FuncFormatter

TABELA, SAIDA = Path(sys.argv[1]), Path(sys.argv[2])
SAIDA.mkdir(parents=True, exist_ok=True)
LARGURA = 3.5
AZUL = "#1f5fbf"
VERMELHO = "#c0392b"
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
        "mathtext.fontset": "stix",
    }
)


def milhar(x: float) -> str:
    return f"{x:,.0f}".replace(",", ".")


def dec(x: float, casas: int = 1) -> str:
    return f"{x:.{casas}f}".replace(".", ",")


t = pd.read_csv(TABELA)
t = t[(t["linguagem"] == "clojure") & (t["ano"] >= 2008) & (t["ano"] <= 2024)].set_index("ano")
colunas = [
    "ativos",
    "entradas",
    "novatos",
    "voltas",
    "saidas",
    "saidas_sem_volta",
    "saidas_com_volta",
    "natalidade_pct",
    "mortalidade_pct",
    "crescimento_natural_pct",
]
anual = t[colunas].copy()
anual.round(2).to_csv(SAIDA / "rq11_tabela_anual.csv")

natural = anual["crescimento_natural_pct"].loc[2009:2024]
negativos = natural[natural < 0]
extremos = pd.DataFrame(
    [
        {
            "medida": "maior crescimento natural",
            "ano": int(natural.idxmax()),
            "valor_pontos": round(float(natural.max()), 2),
        },
        {
            "medida": "menor crescimento natural",
            "ano": int(natural.idxmin()),
            "valor_pontos": round(float(natural.min()), 2),
        },
        {
            "medida": "primeiro ano negativo",
            "ano": int(negativos.index[0]),
            "valor_pontos": round(float(negativos.iloc[0]), 2),
        },
    ]
)
extremos.to_csv(SAIDA / "rq11_extremos.csv", index=False)

T = [
    "# RQ1.1, Clojure, v3b, definição única",
    "",
    "Entradas = novatos + voltas. Saídas = saídas sem volta + saídas com volta. Natalidade = entradas / ativos. Mortalidade = saídas / ativos. Crescimento natural = natalidade menos mortalidade, em pontos percentuais.",
    "",
    "| Ano | Ativos | Entradas | Novatos | Voltas | Saídas | Sem volta | Com volta | Natalidade (%) | Mortalidade (%) | Crescimento natural (pontos) |",
    "|---|---|---|---|---|---|---|---|---|---|---|",
]
for ano, x in anual.iterrows():
    T.append(
        f"| {ano} | {milhar(x['ativos'])} | {milhar(x['entradas'])} | {milhar(x['novatos'])} | {milhar(x['voltas'])} | {milhar(x['saidas'])} | {milhar(x['saidas_sem_volta'])} | {milhar(x['saidas_com_volta'])} | {dec(x['natalidade_pct'])} | {dec(x['mortalidade_pct'])} | {dec(x['crescimento_natural_pct'])} |"
    )
T += ["", "| Medida | Ano | Pontos |", "|---|---|---|"]
for _, x in extremos.iterrows():
    T.append(f"| {x['medida'].capitalize()} | {x['ano']} | {dec(x['valor_pontos'], 2)} |")
T.append("")
(SAIDA / "rq11_tabela_anual.md").write_text("\n".join(T) + "\n", encoding="utf-8")

fig, eixo_taxa = plt.subplots(figsize=(LARGURA, 2.3), constrained_layout=True)
eixo_ativos = eixo_taxa.twinx()
serie = anual.loc[2009:2024]
eixo_ativos.bar(serie.index, serie["ativos"], color="#d9d9d9", width=0.75, label="Ativos no ano")
eixo_ativos.set_ylabel("Ativos no ano")
eixo_ativos.yaxis.set_major_formatter(FuncFormatter(lambda v, _: milhar(v)))
eixo_ativos.spines["top"].set_visible(False)
eixo_taxa.set_zorder(eixo_ativos.get_zorder() + 1)
eixo_taxa.patch.set_visible(False)
eixo_taxa.plot(
    serie.index,
    serie["natalidade_pct"],
    color=AZUL,
    linewidth=1.5,
    marker="o",
    markersize=2.5,
    label="Taxa de entrada",
)
eixo_taxa.plot(
    serie.index,
    serie["mortalidade_pct"],
    color=VERMELHO,
    linewidth=1.5,
    marker="s",
    markersize=2.5,
    label="Taxa de saída",
)
eixo_taxa.set_ylabel("% dos ativos do ano")
eixo_taxa.set_ylim(0, 100)
eixo_taxa.yaxis.set_major_formatter(FuncFormatter(lambda v, _: dec(v, 0)))
eixo_taxa.set_xticks([2009, 2012, 2015, 2018, 2021, 2024])
linhas, nomes = eixo_taxa.get_legend_handles_labels()
barras, nome_barras = eixo_ativos.get_legend_handles_labels()
eixo_taxa.legend(
    linhas + barras,
    nomes + nome_barras,
    loc="lower center",
    bbox_to_anchor=(0.5, 1.0),
    ncol=3,
    frameon=False,
)
fig.savefig(SAIDA / "rq11_natalidade_mortalidade.pdf")
plt.close(fig)
print("\n".join(T))
