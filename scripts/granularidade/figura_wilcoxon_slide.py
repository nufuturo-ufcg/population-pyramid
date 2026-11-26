"""Slide: em quantos dos 28 anos cada método errou menos (Wilcoxon pareado, 4 linguagens juntas).

Lê `resultados.csv` do Wilcoxon com uma previsão por ano (commit 2c57ae9), janela de 4 trimestres,
recorte "juntas" (28 pares). Não recalcula nada. Vitórias, derrotas e p são os do ABRE, a medida
dos demais slides de erro. O p do erro percentual vai na tabela de conferência.

Uso: .venv/bin/python scripts/granularidade/figura_wilcoxon_slide.py <resultados.csv> <saida>
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from icones_metodos import ROXO, poe_icone

RESULTADOS, SAIDA = Path(sys.argv[1]), Path(sys.argv[2])
SAIDA.mkdir(parents=True, exist_ok=True)
TELA = (6.4, 3.6)
DPI = 600
CONTORNO = "#222222"
AZUL, AZUL_CLARO = "#1f5fbf", "#a9c1e8"
CINZA, CINZA_CLARO = "#9a9a9a", "#d4d4d4"
ALFA = 0.05
TOTAL = 28

# (método a, método b, texto da comparação, ícones de a, ícones de b); ícone = (nome, tem R)
COMPARACOES = [
    ("Coorte", "Ingênua", "Coorte contra Ingênua", [("coorte", False)], [("ingenua", False)]),
    (
        "Coorte^R",
        "Ingênua",
        "Coorte$^{R}$ contra Ingênua",
        [("coorte", True)],
        [("ingenua", False)],
    ),
    ("Coorte^R", "Coorte", "Coorte$^{R}$ contra Coorte", [("coorte", True)], [("coorte", False)]),
    (
        "Ingênua-Coorte^R",
        "Ingênua",
        "Ingênua-Coorte$^{R}$ contra Ingênua",
        [("ingenua", False), ("coorte", True)],
        [("ingenua", False)],
    ),
]

plt.rcParams.update(
    {
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Times", "Nimbus Roman", "DejaVu Serif"],
        "font.size": 7,
        "axes.titlesize": 7.5,
        "axes.labelsize": 7,
        "xtick.labelsize": 6.5,
        "ytick.labelsize": 6.5,
        "pdf.fonttype": 42,
        "mathtext.fontset": "stix",
    }
)


def virgula(valor: float, casas: int = 3) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


r = pd.read_csv(RESULTADOS)
r = r[(r["janela"] == "4 trimestres") & (r["recorte"] == "juntas")]
linhas = []
for a, b, texto, icones_a, icones_b in COMPARACOES:
    linha = r[(r["metodo_a"] == a) & (r["metodo_b"] == b)]
    assert len(linha) == 1, (a, b)
    linha = linha.iloc[0]
    assert int(linha["pares"]) == TOTAL
    vitorias = int(linha["abre_vitorias_a"])
    derrotas = int(linha["abre_vitorias_b"])
    empates = int(linha["abre_empates"])
    assert vitorias + derrotas + empates == TOTAL
    linhas.append(
        {
            "comparacao": f"{a} contra {b}",
            "texto": texto,
            "icones_a": icones_a,
            "icones_b": icones_b,
            "vitorias": vitorias,
            "derrotas": derrotas,
            "empates": empates,
            "p": float(linha["abre_p"]),
            "p_erro_percentual": float(linha["mape_p"]),
        }
    )
tabela = pd.DataFrame(linhas)

# Tabela de conferência
saida_tabela = tabela[
    ["comparacao", "vitorias", "derrotas", "empates", "p", "p_erro_percentual"]
].copy()
saida_tabela.to_csv(SAIDA / "tabela_wilcoxon.csv", index=False)
md = [
    "| Comparação | Vitórias | Derrotas | Empates | p (ABRE) | p (erro percentual) |",
    "|---|---:|---:|---:|---:|---:|",
]
for _, linha in tabela.iterrows():
    md.append(
        f"| {linha['comparacao']} | {linha['vitorias']} | {linha['derrotas']} | {linha['empates']} "
        f"| {virgula(linha['p'], 4)} | {virgula(linha['p_erro_percentual'], 4)} |"
    )
(SAIDA / "tabela_wilcoxon.md").write_text("\n".join(md) + "\n")

fig, eixo = plt.subplots(figsize=TELA)
fig.subplots_adjust(left=0.37, right=0.85, top=0.86, bottom=0.17)
eixo.set_xlim(0, TOTAL)
eixo.set_ylim(len(COMPARACOES) - 0.35, -0.8)  # espaço em cima para o rótulo "metade"
eixo.axis("off")
for i, linha in tabela.iterrows():
    passa = linha["p"] < ALFA
    cor_esq = AZUL if passa else CINZA
    cor_dir = AZUL_CLARO if passa else CINZA_CLARO
    eixo.barh(i, linha["vitorias"], height=0.62, color=cor_esq, edgecolor=CONTORNO, linewidth=0.4)
    eixo.barh(
        i,
        linha["derrotas"],
        left=linha["vitorias"],
        height=0.62,
        color=cor_dir,
        edgecolor=CONTORNO,
        linewidth=0.4,
    )
    cor_numero = "white" if passa else "black"
    eixo.text(
        linha["vitorias"] / 2.0,
        i,
        str(linha["vitorias"]),
        ha="center",
        va="center",
        color=cor_numero,
        fontsize=8,
    )
    eixo.text(
        linha["vitorias"] + linha["derrotas"] / 2.0,
        i,
        str(linha["derrotas"]),
        ha="center",
        va="center",
        color="black",
        fontsize=8,
    )
    eixo.text(
        TOTAL + 0.6,
        i,
        f"p = {virgula(linha['p'])}",
        ha="left",
        va="center",
        fontsize=7.5,
    )
eixo.plot([TOTAL / 2, TOTAL / 2], [-0.5, len(COMPARACOES) - 0.5], "--", color="#444444", lw=0.7)
eixo.text(TOTAL / 2, -0.56, "metade", ha="center", va="bottom", fontsize=6.5, color="#444444")

# Nome da comparação com os ícones dos dois métodos, em colunas fixas à esquerda das barras
fig.canvas.draw()
renderer = fig.canvas.get_renderer()
esquerda = eixo.get_position().x0 * TELA[0]  # polegadas
tamanho = 11.0 / 72.0
coluna_b = esquerda - 0.1 - tamanho / 2.0
coluna_a = 0.40
inicio_texto = coluna_a + 0.14
for i, linha in tabela.iterrows():
    y = eixo.transData.transform((0, i))[1] / fig.dpi
    fig.text(
        inicio_texto,
        y,
        linha["texto"],
        transform=fig.dpi_scale_trans,
        ha="left",
        va="center",
        fontsize=7.5,
    )
    centro = coluna_a
    ambos = len(linha["icones_a"]) == 2
    tamanho_a = tamanho * 0.82 if ambos else tamanho
    for nome, tem_r in reversed(linha["icones_a"]):
        poe_icone(fig, nome, tem_r, centro, y, tamanho_a, ROXO)
        centro = centro - tamanho_a - 0.04
    for nome, tem_r in linha["icones_b"]:
        poe_icone(fig, nome, tem_r, coluna_b, y, tamanho, ROXO)

fig.text(
    0.5,
    0.93,
    "Em quantos dos 28 anos o método errou menos? (4 linguagens)",
    ha="center",
    va="center",
    fontsize=7.5,
)
fig.text(
    0.5,
    0.06,
    "p < 0,05: a vantagem passa no teste de Wilcoxon.",
    ha="center",
    va="center",
    fontsize=6.5,
    color="#444444",
)
fig.savefig(SAIDA / "slide_wilcoxon_28_anos.png", dpi=DPI)
fig.savefig(SAIDA / "slide_wilcoxon_28_anos.pdf")
plt.close(fig)
print(saida_tabela.to_string(index=False))
