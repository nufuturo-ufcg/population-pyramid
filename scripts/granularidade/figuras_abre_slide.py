"""Duas figuras de slide com o ABRE, como Onoue et al. (IEICE16, Tabela 3) reportam o erro.

ABRE = |previsto - real| / min(previsto, real). Estatística: mediana, a mesma da Tabela 3 do IEICE16.
Dados: `pares_usados.csv` do Wilcoxon com uma previsão por ano (cenário Longo, não casuais, janela
de 4 trimestres, só as previsões de 31 de dezembro: 8 por método em Clojure e em Python).

  slide_abre_clojure_metodos        mediana do ABRE de cada método em Clojure
  slide_abre_python_ano_a_ano       ABRE da Ingênua e da Coorte em Python, por ano do alvo

Uso: .venv/bin/python scripts/granularidade/figuras_abre_slide.py <pares_usados.csv> <saida>
Grava PNG a 600 dpi, PDF, `tabela_abre.csv` e `tabela_abre.md`.
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch

PARES, SAIDA = Path(sys.argv[1]), Path(sys.argv[2])
SAIDA.mkdir(parents=True, exist_ok=True)
TELA = (6.4, 3.6)
DPI = 600
ORDEM = ["Ingênua", "Coorte", "Coorte^R", "Conservador", "Conservador^R", "Ingênua-Coorte^R"]
CINZA, AZUL, CONTORNO = "#9a9a9a", "#1f5fbf", "#222222"

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


def virgula(valor: float, casas: int = 2) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


def salva(fig, nome: str) -> None:
    fig.savefig(SAIDA / f"{nome}.png", dpi=DPI)
    fig.savefig(SAIDA / f"{nome}.pdf")
    plt.close(fig)


pares = pd.read_csv(PARES)
pares = pares[pares["janela"] == "4 trimestres"].copy()
pares["ano_alvo"] = pd.to_datetime(pares["alvo"]).dt.year

dados = {}
for lingua in ["clojure", "python"]:
    d = pares[pares["linguagem"] == lingua]
    assert set(d["metodo"]) == set(ORDEM), lingua
    for metodo in ORDEM:
        n = int((d["metodo"] == metodo).sum())
        assert n == 8, (lingua, metodo, n)
    dados[lingua] = d

# Conferência: o ABRE do arquivo bate com a fórmula e o real é o mesmo em todos os métodos
for lingua, d in dados.items():
    for _, linha in d.iterrows():
        menor = min(linha["previsto"], linha["real"])
        esperado = abs(linha["previsto"] - linha["real"]) / menor
        assert abs(esperado - linha["abre"]) < 1e-9, (lingua, linha["origem"], linha["metodo"])
    por_alvo = d.groupby("alvo")["real"].nunique()
    assert (por_alvo == 1).all(), lingua

# Figura 1: Clojure, mediana do ABRE de cada método
clojure = dados["clojure"]
medianas = []
for metodo in ORDEM:
    abre = clojure.loc[clojure["metodo"] == metodo, "abre"]
    medianas.append(float(abre.median()))
fig, eixo = plt.subplots(figsize=TELA)
posicao = np.arange(len(ORDEM))
cores = []
for metodo in ORDEM:
    cores.append(AZUL if metodo == "Coorte^R" else CINZA)
eixo.barh(posicao, medianas, color=cores, edgecolor=CONTORNO, linewidth=0.4, height=0.7)
for y, v in zip(posicao, medianas, strict=True):
    eixo.text(v + 0.002, y, virgula(v), va="center", ha="left", fontsize=7)
eixo.set_yticks(posicao, [m.replace("^R", "$^{R}$") for m in ORDEM])
eixo.invert_yaxis()
eixo.set_xlim(0, max(medianas) * 1.15)
eixo.set_xlabel("ABRE mediano")
eixo.xaxis.set_major_formatter(lambda x, _: virgula(x))
eixo.set_title("Clojure: erro da previsão de 12 meses (ABRE)")
fig.subplots_adjust(left=0.2, right=0.97, top=0.88, bottom=0.16)
salva(fig, "slide_abre_clojure_metodos")

# Figura 2: Python, Ingênua e Coorte ano a ano (ano do alvo)
python = dados["python"]
ingenua = python[python["metodo"] == "Ingênua"].sort_values("ano_alvo")
coorte = python[python["metodo"] == "Coorte"].sort_values("ano_alvo")
anos = ingenua["ano_alvo"].to_numpy()
assert (anos == coorte["ano_alvo"].to_numpy()).all()
largura = 0.38
x = np.arange(len(anos))
fig, eixo = plt.subplots(figsize=TELA)
barras = [(ingenua, -largura / 2, CINZA), (coorte, largura / 2, AZUL)]
for tabela_metodo, deslocamento, cor in barras:
    valores = tabela_metodo["abre"].to_numpy()
    eixo.bar(
        x + deslocamento,
        valores,
        width=largura,
        color=cor,
        edgecolor=CONTORNO,
        linewidth=0.4,
    )
    for xi, v in zip(x + deslocamento, valores, strict=True):
        eixo.text(xi, v + 0.002, virgula(v), ha="center", va="bottom", fontsize=6)
topo = max(ingenua["abre"].max(), coorte["abre"].max())
eixo.set_ylim(0, topo * 1.15)
eixo.yaxis.set_major_formatter(lambda y, _: virgula(y))
eixo.set_xticks(x, [str(int(a)) for a in anos])
eixo.set_ylabel("ABRE")
eixo.set_title("Python: erro da previsão de 12 meses, ano a ano (ABRE)", pad=16)
legenda = [
    Patch(facecolor=CINZA, edgecolor=CONTORNO, linewidth=0.4, label="Ingênua"),
    Patch(facecolor=AZUL, edgecolor=CONTORNO, linewidth=0.4, label="Coorte"),
]
eixo.legend(
    handles=legenda,
    loc="lower center",
    bbox_to_anchor=(0.5, 1.0),
    ncol=2,
    frameon=False,
    handlelength=1.4,
    borderaxespad=0.2,
)
fig.subplots_adjust(left=0.09, right=0.98, top=0.84, bottom=0.12)
salva(fig, "slide_abre_python_ano_a_ano")

# Tabela de conferência: por linguagem e ano do alvo, real e, por método, previsto e ABRE
linhas = []
for lingua, d in dados.items():
    for alvo in sorted(d["alvo"].unique()):
        do_alvo = d[d["alvo"] == alvo]
        linha = {
            "linguagem": lingua.capitalize(),
            "ano": int(alvo[:4]),
            "origem": do_alvo["origem"].iloc[0],
            "real": int(do_alvo["real"].iloc[0]),
        }
        for metodo in ORDEM:
            m = do_alvo[do_alvo["metodo"] == metodo].iloc[0]
            linha[f"{metodo} previsto"] = float(m["previsto"])
            linha[f"{metodo} abre"] = float(m["abre"])
        linhas.append(linha)
tabela = pd.DataFrame(linhas)
tabela.to_csv(SAIDA / "tabela_abre.csv", index=False)

md = []
for lingua in ["Clojure", "Python"]:
    parte = tabela[tabela["linguagem"] == lingua]
    md.append(f"## {lingua}\n")
    cab = "| Ano | Real |"
    sep = "|---:|---:|"
    for metodo in ORDEM:
        cab += f" {metodo} (previsto / ABRE) |"
        sep += "---:|"
    md.append(cab)
    md.append(sep)
    for _, linha in parte.iterrows():
        texto = f"| {linha['ano']} | {linha['real']:,} |".replace(",", ".")
        for metodo in ORDEM:
            previsto = f"{linha[metodo + ' previsto']:,.0f}".replace(",", ".")
            texto += f" {previsto} / {virgula(linha[metodo + ' abre'])} |"
        md.append(texto)
    texto = "| **Mediana** | |"
    for metodo in ORDEM:
        texto += f" {virgula(float(parte[metodo + ' abre'].median()))} |"
    md.append(texto)
    md.append("")
(SAIDA / "tabela_abre.md").write_text("\n".join(md) + "\n")
print("medianas Clojure:", dict(zip(ORDEM, [round(v, 4) for v in medianas], strict=True)))
