"""Projeção de 5 anos de Clojure com a Coorte^R a partir de uma origem, uma linha só, no estilo de `slide_projecao_clojure_coorte_r`.

Duas figuras, uma por origem:
  origem 30/06/2026: a última origem em que todas as peças da Coorte^R estão completas (ver `pecas_da_coorte_r.md`);
  origem 30/06/2025: a origem com 12 meses de dados depois dela. Os trimestres seguintes (30/09/2025 a 30/06/2026) já são observados e entram como pontos vazados, fora da projeção.
Faixa sombreada: previsão × (1 + p10) a previsão × (1 + p90) do erro (real − previsto) / previsto por passo, o mesmo de `erro_por_passo.csv`.

Grava também `tabela_coorte_r_fim_de_ano.md` e `.csv` (projeção e faixa por fim de ano, nas duas origens).

Uso: .venv/bin/python scripts/granularidade/figura_projecao_origem_valida.py <origem-2026-06-30> <origem-2025-06-30> <saida>
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter

PASTA_2026, PASTA_2025, SAIDA = (Path(a) for a in sys.argv[1:4])
SAIDA.mkdir(parents=True, exist_ok=True)
TELA = (6.4, 3.6)
DPI = 300
AZUL = "#1f5fbf"
NOTA_DA_FAIXA = "Faixa sombreada: p10 a p90 do erro histórico"

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


observada = pd.read_csv(PASTA_2026 / "ativos_observados_por_trimestre.csv", parse_dates=["data"])
observada = observada[observada["data"] >= "2014-01-01"]


def trajetoria_com_faixa(pasta: Path) -> pd.DataFrame:
    """Coorte^R por passo: total, limite de baixo (p10) e de cima (p90). No passo 0 a faixa é o próprio valor."""
    t = pd.read_csv(pasta / "trajetorias.csv", parse_dates=["data"])
    t = t[t["metodo"] == "Coorte^R"].sort_values("passo").reset_index(drop=True)
    e = pd.read_csv(pasta / "erro_por_passo.csv")
    e = e[e["metodo"] == "Coorte^R"].set_index("passo")
    baixo = []
    alto = []
    for _, linha in t.iterrows():
        passo = int(linha["passo"])
        if passo == 0:
            baixo.append(linha["total"])
            alto.append(linha["total"])
        else:
            baixo.append(linha["total"] * (1 + e.loc[passo, "real_sobre_previsto_p10"]))
            alto.append(linha["total"] * (1 + e.loc[passo, "real_sobre_previsto_p90"]))
    t["baixo"] = baixo
    t["alto"] = alto
    return t


def desenha(
    pasta: Path,
    origem: pd.Timestamp,
    depois_da_origem: bool,
    nome: str,
    dpi: int = DPI,
    nota: str = NOTA_DA_FAIXA,
) -> None:
    t = trajetoria_com_faixa(pasta)
    fig, eixo = plt.subplots(figsize=TELA)
    ate_a_origem = observada[observada["data"] <= origem]
    eixo.plot(ate_a_origem["data"], ate_a_origem["ativos"], color="black", linewidth=1.2)
    itens = [Line2D([], [], color="black", linewidth=1.2, label="Observado")]
    if depois_da_origem:
        depois = observada[observada["data"] >= origem]
        eixo.plot(
            depois["data"],
            depois["ativos"],
            color="black",
            linewidth=0.6,
            marker="o",
            markersize=2.8,
            markerfacecolor="white",
            markeredgewidth=0.7,
        )
        itens.append(
            Line2D(
                [],
                [],
                color="black",
                linewidth=0.6,
                marker="o",
                markersize=2.8,
                markerfacecolor="white",
                markeredgewidth=0.7,
                label="Observado depois da origem (fora da projeção)",
            )
        )
    eixo.fill_between(t["data"], t["baixo"], t["alto"], color=AZUL, alpha=0.2, linewidth=0)
    eixo.plot(t["data"], t["total"], color=AZUL, linestyle="--", linewidth=1.2)
    itens.append(
        Line2D(
            [],
            [],
            color=AZUL,
            linewidth=1.2,
            linestyle="--",
            label=f"Coorte$^{{R}}$ de {origem:%d/%m/%Y}",
        )
    )
    eixo.axvline(origem, color="black", linewidth=0.6, linestyle=":")
    eixo.text(origem + pd.Timedelta(days=60), 4750, "Projeção", ha="left", va="top", fontsize=7)
    eixo.set_ylim(1000, 4800)
    eixo.yaxis.set_major_formatter(FuncFormatter(milhar))
    eixo.set_ylabel("Desenvolvedores ativos")
    eixo.set_xlim(pd.Timestamp("2014-01-01"), pd.Timestamp("2031-09-30"))
    eixo.set_xticks([pd.Timestamp(f"{a}-01-01") for a in (2014, 2018, 2022, 2026, 2030)])
    eixo.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    fig.legend(
        handles=itens,
        loc="upper center",
        ncol=len(itens),
        frameon=False,
        bbox_to_anchor=(0.5, 0.995),
    )
    eixo.text(
        0.01,
        0.02,
        nota,
        transform=eixo.transAxes,
        fontsize=6,
        va="bottom",
    )
    fig.subplots_adjust(left=0.1, right=0.985, top=0.9, bottom=0.1)
    fig.savefig(SAIDA / f"{nome}.png", dpi=dpi)
    fig.savefig(SAIDA / f"{nome}.pdf")
    plt.close(fig)


desenha(PASTA_2026, pd.Timestamp("2026-06-30"), False, "slide_projecao_coorte_r_origem_2026-06-30")
desenha(PASTA_2025, pd.Timestamp("2025-06-30"), True, "slide_projecao_coorte_r_origem_2025-06-30")
# Mesma figura sem os pontos observados depois da origem: a linha observada termina em 30/06/2025
desenha(
    PASTA_2025,
    pd.Timestamp("2025-06-30"),
    False,
    "slide_projecao_coorte_r_origem_2025-06-30_sem_pontos",
    dpi=600,
    nota="Faixa: margem de erro do método no passado",
)

# Tabela da Coorte^R por fim de ano, nas duas origens, com o observado
linhas = []
for rotulo, pasta in (("2026-06-30", PASTA_2026), ("2025-06-30", PASTA_2025)):
    s = pd.read_csv(pasta / "serie_anual.csv")
    s = s[(s["metodo"] == "Coorte^R") & (s["parte"] == "projetada")]
    for _, linha in s.iterrows():
        linhas.append(
            {
                "origem": rotulo,
                "ano": int(linha["ano"]),
                "projecao": float(linha["ativos"]),
                "faixa_baixo": float(linha["ativos_baixo"]),
                "faixa_alto": float(linha["ativos_alto"]),
            }
        )
tabela = pd.DataFrame(linhas)
observado_fim_de_ano = {}
for _, linha in observada.iterrows():
    if linha["data"].month == 12:
        observado_fim_de_ano[linha["data"].year] = float(linha["ativos"])
tabela["observado"] = tabela["ano"].map(observado_fim_de_ano)
tabela.to_csv(SAIDA / "tabela_coorte_r_fim_de_ano.csv", index=False, float_format="%.6g")

anos = sorted(tabela["ano"].unique())
md = [
    "| Fim de ano | Observado | Origem 30/06/2026: projeção (faixa) | Origem 30/06/2025: projeção (faixa) |",
    "|---|---:|---|---|",
]
for ano in anos:
    texto = f"| 31/12/{ano} | "
    texto += milhar(observado_fim_de_ano[ano]) if ano in observado_fim_de_ano else "n/d"
    texto += " |"
    for rotulo in ("2026-06-30", "2025-06-30"):
        achou = tabela[(tabela["origem"] == rotulo) & (tabela["ano"] == ano)]
        if achou.empty:
            texto += " - |"
        else:
            x = achou.iloc[0]
            texto += f" {milhar(x['projecao'])} ({milhar(x['faixa_baixo'])} a {milhar(x['faixa_alto'])}) |"
    md.append(texto)
(SAIDA / "tabela_coorte_r_fim_de_ano.md").write_text("\n".join(md) + "\n")
print("\n".join(md))
