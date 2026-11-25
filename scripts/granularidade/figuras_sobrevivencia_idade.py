"""Curva de Kaplan-Meier e q(x) pela idade da pirâmide, nas cinco linguagens (tábua nova, `rq13_tabua_km.py`).

`rq2_sobrevivencia.pdf`: S(x) das cinco linguagens, a curva para quando restam menos de 30 pessoas em risco.
`rq2_qx_por_idade.pdf`: q(x), a fração que sai entre x e x+1, uma linha por linguagem e só as idades com ao menos 30 pessoas efetivamente observadas (`n_efetivo`).
Estilo de `figuras-v3/figuras_artigo.py` (uma coluna do IEEE, serifa, vírgula decimal). Grava também os CSV do que está desenhado.

Uso (na raiz do repo): .venv/bin/python scripts/granularidade/figuras_sobrevivencia_idade.py <kaplan_meier_por_idade.csv> <tabua_por_idade.csv> <saida>
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import FuncFormatter

KM, TABUA, SAIDA = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
SAIDA.mkdir(parents=True, exist_ok=True)
N_MINIMO = 30
AZUL = "#1f5fbf"
NOMES = {
    "clojure": "Clojure",
    "elixir": "Elixir",
    "zig": "Zig",
    "ocaml": "OCaml",
    "python": "Python",
}
ESTILOS = {
    "clojure": {"color": AZUL, "linewidth": 1.8, "linestyle": "-"},
    "elixir": {"color": "#7f7f7f", "linewidth": 0.9, "linestyle": "--"},
    "zig": {"color": "#7f7f7f", "linewidth": 0.9, "linestyle": ":"},
    "ocaml": {"color": "#7f7f7f", "linewidth": 0.9, "linestyle": "-."},
    "python": {"color": "#222222", "linewidth": 0.9, "linestyle": "-"},
}
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


def decimal(valor: float, _=None) -> str:
    return f"{valor:.1f}".replace(".", ",")


def legenda(eixo, local: str) -> None:
    linhas, rotulos = eixo.get_legend_handles_labels()
    ordem = [rotulos.index("Clojure")] + [
        i for i, r in enumerate(rotulos) if r != "Clojure"
    ]  # Clojure primeiro
    eixo.legend([linhas[i] for i in ordem], [rotulos[i] for i in ordem], loc=local, frameon=False)


# Kaplan-Meier
km = pd.read_csv(KM)
fig, eixo = plt.subplots(figsize=(3.5, 2.2), constrained_layout=True)
desenhado = []
for lingua in ["elixir", "zig", "ocaml", "python", "clojure"]:
    curva = km[(km["linguagem"] == lingua) & (km["em_risco"] >= N_MINIMO)]
    # shortcut: um ponto a cada 0,02 ano basta para a escada; o CSV tem milhares por linguagem
    curva = curva.assign(passo=(curva["anos"] / 0.02).round()).drop_duplicates("passo", keep="last")
    eixo.step(curva["anos"], curva["S"], where="post", label=NOMES[lingua], **ESTILOS[lingua])
    desenhado.append(curva[["linguagem", "anos", "S", "em_risco"]])
eixo.set_xlim(0, 10)
eixo.set_ylim(0, 1)
eixo.set_xlabel("Idade da pirâmide (anos com contribuição)")
eixo.set_ylabel("Fração ainda ativa")
eixo.yaxis.set_major_formatter(FuncFormatter(decimal))
legenda(eixo, "upper right")
fig.savefig(SAIDA / "rq2_sobrevivencia.pdf")
plt.close(fig)
pd.concat(desenhado).to_csv(SAIDA / "rq2_sobrevivencia.csv", index=False, float_format="%.10g")

# q(x) por idade
tabua = pd.read_csv(TABUA)
tabua = tabua[tabua["n_efetivo"] >= N_MINIMO]
fig, eixo = plt.subplots(figsize=(3.5, 2.2), constrained_layout=True)
for lingua in ["elixir", "zig", "ocaml", "python", "clojure"]:
    t = tabua[tabua["linguagem"] == lingua]
    estilo = dict(ESTILOS[lingua])
    eixo.plot(t["x"], 100 * t["q"], marker="o", markersize=2.2, label=NOMES[lingua], **estilo)
eixo.set_xlabel("Idade da pirâmide x (anos com contribuição)")
eixo.set_ylabel("q(x): saem entre x e x + 1 (%)")
eixo.set_ylim(bottom=0)
eixo.set_xticks(range(0, int(tabua["x"].max()) + 1, 2))
eixo.yaxis.set_major_formatter(FuncFormatter(lambda v, _: decimal(v).replace(",0", "")))
legenda(eixo, "upper right")
fig.savefig(SAIDA / "rq2_qx_por_idade.pdf")
plt.close(fig)
tabua[["linguagem", "x", "n_efetivo", "d", "q"]].to_csv(
    SAIDA / "rq2_qx_por_idade.csv", index=False, float_format="%.10g"
)
print("figuras gravadas em", SAIDA)
