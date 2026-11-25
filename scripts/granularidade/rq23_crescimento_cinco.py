"""RQ2.3, espelho da RQ1.1: taxa de entrada, taxa de saída e crescimento (entrada menos saída, em pontos) das cinco linguagens, 2009 a 2024.

Lê a tabela anual da definição única (`confere_identidade.py`, que vem de `vitalidade.tabela_anual`) e a tabela de 2024 da RQ2 (SMR, peso de 2024).
Grava: `rq23_serie.csv`, `rq23_resumo_2024.csv`, `rq23_crescimento_cinco.md` e `rq23_crescimento_cinco.pdf` (uma linha de crescimento por
linguagem, uma coluna do IEEE, estilo de `figuras-v3/figuras_artigo.py`).

Uso (na raiz do repo): .venv/bin/python scripts/granularidade/rq23_crescimento_cinco.py <tabela_anual_5_linguas.csv> <tabela_2024.csv da RQ2> <saida>
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import FuncFormatter

ANUAL, TABELA_2024, SAIDA = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
SAIDA.mkdir(parents=True, exist_ok=True)
LINGUAS = ["clojure", "elixir", "zig", "ocaml", "python"]
NOMES = {
    "clojure": "Clojure",
    "elixir": "Elixir",
    "zig": "Zig",
    "ocaml": "OCaml",
    "python": "Python",
}
AZUL = "#1f5fbf"
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


def dec(x: float, casas: int = 1) -> str:
    return "n/d" if pd.isna(x) else f"{x:.{casas}f}".replace(".", ",")


def milhar(x: float) -> str:
    return f"{x:,.0f}".replace(",", ".")


anual = pd.read_csv(ANUAL)
anual = anual[anual["ano"].between(2009, 2024) & anual["linguagem"].isin(LINGUAS)].copy()
anual = anual[anual["ativos"] > 0].copy()  # Elixir e Zig não tinham ninguém nos primeiros anos
anual = anual.rename(
    columns={"natalidade_pct": "taxa_entrada_pct", "mortalidade_pct": "taxa_saida_pct"}
)
anual["crescimento_pontos"] = anual["taxa_entrada_pct"] - anual["taxa_saida_pct"]
assert ((anual["crescimento_pontos"] - anual["crescimento_natural_pct"]).abs() < 1e-9).all(), (
    "crescimento difere da tabela anual"
)
anual[
    [
        "linguagem",
        "ano",
        "ativos",
        "entradas",
        "saidas",
        "taxa_entrada_pct",
        "taxa_saida_pct",
        "crescimento_pontos",
    ]
].to_csv(SAIDA / "rq23_serie.csv", index=False, float_format="%.10g")

t2024 = pd.read_csv(TABELA_2024).set_index("linguagem")
resumo = []
for lingua in LINGUAS:
    a = anual[anual["linguagem"] == lingua].set_index("ano")
    negativos = a[a["crescimento_pontos"] < 0]
    resumo.append(
        {
            "linguagem": lingua,
            "ativos_2024": int(a.loc[2024, "ativos"]),
            "entradas_2024": int(a.loc[2024, "entradas"]),
            "saidas_2024": int(a.loc[2024, "saidas"]),
            "taxa_entrada_2024_pct": a.loc[2024, "taxa_entrada_pct"],
            "taxa_saida_2024_pct": a.loc[2024, "taxa_saida_pct"],
            "crescimento_2024_pontos": a.loc[2024, "crescimento_pontos"],
            "primeiro_ano_negativo": int(negativos.index[0]) if len(negativos) else None,
            "crescimento_no_primeiro_negativo": negativos["crescimento_pontos"].iloc[0]
            if len(negativos)
            else None,
            "anos_negativos": ", ".join(str(int(x)) for x in negativos.index),
            "smr_referencia_nicho": t2024.loc[lingua, "smr_nicho"],
            "smr_referencia_python": t2024.loc[lingua, "smr_python"],
        }
    )
resumo = pd.DataFrame(resumo).set_index("linguagem")
resumo.to_csv(SAIDA / "rq23_resumo_2024.csv", float_format="%.10g")

fig, eixo = plt.subplots(figsize=(3.5, 2.4), constrained_layout=True)
for lingua in ["elixir", "zig", "ocaml", "python", "clojure"]:
    a = anual[anual["linguagem"] == lingua]
    eixo.plot(a["ano"], a["crescimento_pontos"], label=NOMES[lingua], **ESTILOS[lingua])
eixo.axhline(0, color="black", linewidth=0.5)
eixo.set_xticks([2009, 2012, 2015, 2018, 2021, 2024])
eixo.set_xlabel("Ano")
eixo.set_ylabel("Crescimento (entrada menos saída, pontos)")
eixo.yaxis.set_major_formatter(FuncFormatter(lambda v, _: dec(v, 0)))
linhas, rotulos = eixo.get_legend_handles_labels()
ordem = [4, 0, 1, 2, 3]  # Clojure primeiro na legenda
eixo.legend(
    [linhas[i] for i in ordem], [rotulos[i] for i in ordem], loc="upper right", frameon=False
)
fig.savefig(SAIDA / "rq23_crescimento_cinco.pdf")
plt.close(fig)

T = [
    "# RQ2.3 das cinco linguagens: taxa de entrada, taxa de saída e crescimento (definição única, v3b)",
    "",
    "Taxa de entrada = entradas (novatos e voltas) / ativos. Taxa de saída = saídas (com e sem volta) / ativos. Crescimento = entrada menos saída, em pontos percentuais. SMR com a definição única e peso de 2024.",
    "",
    "## Valores de 2024",
    "",
    "| | " + " | ".join(NOMES[x] for x in LINGUAS) + " |",
    "|---|" + "---|" * len(LINGUAS),
    "| Ativos | " + " | ".join(milhar(resumo.loc[x, "ativos_2024"]) for x in LINGUAS) + " |",
    "| Entradas | " + " | ".join(milhar(resumo.loc[x, "entradas_2024"]) for x in LINGUAS) + " |",
    "| Saídas | " + " | ".join(milhar(resumo.loc[x, "saidas_2024"]) for x in LINGUAS) + " |",
    "| Taxa de entrada (%) | "
    + " | ".join(dec(resumo.loc[x, "taxa_entrada_2024_pct"]) for x in LINGUAS)
    + " |",
    "| Taxa de saída (%) | "
    + " | ".join(dec(resumo.loc[x, "taxa_saida_2024_pct"]) for x in LINGUAS)
    + " |",
    "| Crescimento (pontos) | "
    + " | ".join(dec(resumo.loc[x, "crescimento_2024_pontos"]) for x in LINGUAS)
    + " |",
    "| Primeiro ano com crescimento negativo | "
    + " | ".join(
        "nenhum"
        if pd.isna(resumo.loc[x, "primeiro_ano_negativo"])
        else str(int(resumo.loc[x, "primeiro_ano_negativo"]))
        for x in LINGUAS
    )
    + " |",
    "| Crescimento nesse ano (pontos) | "
    + " | ".join(dec(resumo.loc[x, "crescimento_no_primeiro_negativo"]) for x in LINGUAS)
    + " |",
    "| SMR, referência nicho | "
    + " | ".join(dec(resumo.loc[x, "smr_referencia_nicho"], 2) for x in LINGUAS)
    + " |",
    "| SMR, referência python | "
    + " | ".join(dec(resumo.loc[x, "smr_referencia_python"], 2) for x in LINGUAS)
    + " |",
    "",
    "Anos com crescimento negativo (2009 a 2024):",
    "",
]
for lingua in LINGUAS:
    T.append(f"- {NOMES[lingua]}: {resumo.loc[lingua, 'anos_negativos'] or 'nenhum'}.")
T += [
    "",
    "## Série de 2009 a 2024 (taxa de entrada / taxa de saída / crescimento)",
    "",
    "| Ano | " + " | ".join(NOMES[x] for x in LINGUAS) + " |",
    "|---|" + "---|" * len(LINGUAS),
]
for ano in range(2009, 2025):
    celulas = []
    for lingua in LINGUAS:
        x = anual[(anual["linguagem"] == lingua) & (anual["ano"] == ano)]
        celulas.append(
            "n/d"
            if x.empty
            else f"{dec(x['taxa_entrada_pct'].iloc[0])} / {dec(x['taxa_saida_pct'].iloc[0])} / {dec(x['crescimento_pontos'].iloc[0])}"
        )
    T.append(f"| {ano} | " + " | ".join(celulas) + " |")
T.append("")
(SAIDA / "rq23_crescimento_cinco.md").write_text("\n".join(T) + "\n", encoding="utf-8")
print("\n".join(T[:24]))
