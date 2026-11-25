"""Figura 2 (RQ1.1) de Clojure em duas versões, com a definição única de entrada e saída.

A: taxa de entrada(t) = entradas(t) / ativos(t) e taxa de saída(t) = saídas(t) / ativos(t) (a figura atual).
B (saída no ano seguinte): taxa de entrada(t) = entradas(t) / ativos(t-1) e taxa de saída(t) = saídas(t-1) / ativos(t-1). O crescimento de B é a variação
das barras: (ativos(t) - ativos(t-1)) / ativos(t-1). Confere isso em todos os anos e para se falhar.
Nas duas, entrada em azul, saída em vermelho e ativos em barras cinza. Estilo de `figuras-v3/figuras_artigo.py`.

Grava em `<saida>`: `figura2_versao_A.pdf`, `figura2_versao_B.pdf`, `figura2_lado_a_lado.png`, `figura2_crescimento.csv` e `.md`.

Uso (na raiz do repo): .venv/bin/python scripts/granularidade/figura2_duas_versoes.py <tabela_anual com a coluna linguagem> <saida>
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


def milhar(x: float, _=None) -> str:
    return f"{x:,.0f}".replace(",", ".")


def dec(x: float, casas: int = 1) -> str:
    return "n/d" if pd.isna(x) else f"{x:.{casas}f}".replace(".", ",")


t = pd.read_csv(TABELA)
t = t[(t["linguagem"] == "clojure") & (t["ano"] >= 2008) & (t["ano"] <= 2024)].set_index("ano")
ativos, entradas, saidas = t["ativos"], t["entradas"], t["saidas"]
anos = list(range(2009, 2025))

serie = pd.DataFrame(index=anos)
serie["ativos"] = ativos.loc[anos]
serie["entrada_A"] = 100 * entradas.loc[anos] / ativos.loc[anos]
serie["saida_A"] = 100 * saidas.loc[anos] / ativos.loc[anos]
serie["crescimento_A"] = serie["entrada_A"] - serie["saida_A"]
anterior = ativos.shift(1).loc[anos]
saida_anterior = saidas.shift(1).loc[anos]
serie["entrada_B"] = 100 * entradas.loc[anos] / anterior
serie["saida_B"] = 100 * saida_anterior / anterior
serie["crescimento_B"] = serie["entrada_B"] - serie["saida_B"]
serie["variacao_das_barras"] = 100 * (ativos.loc[anos] - anterior) / anterior
# Conferência da versão B: crescimento = variação das barras, em todos os anos
diferenca = (serie["crescimento_B"] - serie["variacao_das_barras"]).abs()
if not (diferenca < 1e-9).all():
    sys.exit(
        f"o crescimento da versão B não é a variação das barras em {list(diferenca[diferenca >= 1e-9].index)}: {diferenca.max()}"
    )
serie.index.name = "ano"
serie.to_csv(SAIDA / "figura2_crescimento.csv", float_format="%.10g")


def desenha(eixo_taxa, versao: str, titulo: str | None = None) -> None:
    eixo_ativos = eixo_taxa.twinx()
    eixo_ativos.bar(
        serie.index, serie["ativos"], color="#d9d9d9", width=0.75, label="Ativos no ano"
    )
    eixo_ativos.set_ylabel("Ativos no ano")
    eixo_ativos.yaxis.set_major_formatter(FuncFormatter(milhar))
    eixo_ativos.spines["top"].set_visible(False)
    eixo_taxa.set_zorder(eixo_ativos.get_zorder() + 1)
    eixo_taxa.patch.set_visible(False)
    eixo_taxa.plot(
        serie.index,
        serie[f"entrada_{versao}"],
        color=AZUL,
        linewidth=1.5,
        marker="o",
        markersize=2.5,
        label="Taxa de entrada",
    )
    eixo_taxa.plot(
        serie.index,
        serie[f"saida_{versao}"],
        color=VERMELHO,
        linewidth=1.5,
        marker="s",
        markersize=2.5,
        label="Taxa de saída",
    )
    eixo_taxa.set_ylabel("% dos ativos" + (" do ano" if versao == "A" else " do ano anterior"))
    limite = 100 if versao == "A" else 150
    eixo_taxa.set_ylim(0, limite)
    # Na versão B a entrada de 2009 e 2010 passa do eixo (entradas sobre poucos ativos do ano anterior): o valor vai escrito no topo
    fora = [(ano, valor) for ano, valor in serie[f"entrada_{versao}"].items() if valor > limite]
    if fora:
        texto = "Acima do eixo:\n" + "\n".join(f"{ano}: {dec(valor)}%" for ano, valor in fora)
        eixo_taxa.text(
            0.38,
            0.97,
            texto,
            transform=eixo_taxa.transAxes,
            ha="left",
            va="top",
            fontsize=5.5,
            color=AZUL,
            bbox={"facecolor": "white", "edgecolor": "none", "pad": 1.5, "alpha": 0.85},
        )
    eixo_taxa.yaxis.set_major_formatter(FuncFormatter(lambda v, _: dec(v, 0)))
    eixo_taxa.set_xlim(2008.4, 2024.6)
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
    if titulo:
        eixo_taxa.set_title(titulo, y=1.14, fontsize=7.5)


for versao in ("A", "B"):
    fig, eixo = plt.subplots(figsize=(3.5, 2.3), constrained_layout=True)
    desenha(eixo, versao)
    fig.savefig(SAIDA / f"figura2_versao_{versao}.pdf")
    plt.close(fig)
fig, eixos = plt.subplots(1, 2, figsize=(7.2, 2.5), constrained_layout=True)
desenha(eixos[0], "A", "A: entrada e saída sobre os ativos do próprio ano")
desenha(eixos[1], "B", "B: saída no ano seguinte (sobre os ativos do ano anterior)")
fig.savefig(SAIDA / "figura2_lado_a_lado.png", dpi=220)
plt.close(fig)

primeiro = {}
for versao in ("A", "B"):
    negativos = serie[serie[f"crescimento_{versao}"] < 0]
    primeiro[versao] = int(negativos.index[0]) if len(negativos) else None
T = [
    "# Figura 2 em duas versões: crescimento ano a ano (Clojure, definição única, v3b)",
    "",
    "A: entrada(t) / ativos(t) menos saída(t) / ativos(t). B: entrada(t) / ativos(t−1) menos saída(t−1) / ativos(t−1), que é a variação dos ativos de t−1 para t. Conferido: na versão B o crescimento é igual a (ativos(t) − ativos(t−1)) / ativos(t−1) em todos os anos (diferença máxima abaixo de 1e-9).",
    "",
    f"Primeiro ano com crescimento negativo: versão A {primeiro['A']}, versão B {primeiro['B']}.",
    "",
    "| Ano | Ativos | Entrada A (%) | Saída A (%) | Crescimento A (pontos) | Entrada B (%) | Saída B (%) | Crescimento B (pontos) = variação dos ativos (%) |",
    "|---|---|---|---|---|---|---|---|",
]
for ano, x in serie.iterrows():
    T.append(
        f"| {ano} | {milhar(x['ativos'])} | {dec(x['entrada_A'])} | {dec(x['saida_A'])} | {dec(x['crescimento_A'])} | {dec(x['entrada_B'])} | {dec(x['saida_B'])} | {dec(x['crescimento_B'])} |"
    )
T.append("")
(SAIDA / "figura2_crescimento.md").write_text("\n".join(T) + "\n", encoding="utf-8")
print("\n".join(T[:8]))
