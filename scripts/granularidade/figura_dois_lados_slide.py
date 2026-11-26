"""Figura de slide: composição por tempo de casa em 2024, dois lados (discussion e coding).

Lê `composicao_pct.csv` da rodada v3b (definição única). Nele cada pessoa já está em um lado só,
pela regra de `pyramid.vitalidade.lado_no_ano`: discussion se mais da metade dos eventos dela no
ano forem de discussão, coding nos demais casos (empate vai para coding). Não existe grupo
"moved" nesse arquivo. A idade é a da pirâmide (anos de pausa não contam).

Uso: .venv/bin/python scripts/granularidade/figura_dois_lados_slide.py <composicao_pct.csv> <saida>
Grava PDF vetorial, PNG a 600 dpi, `tabela_2024.csv` e `tabela_2024.md` na pasta de saída.
"""

import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch

COMPOSICAO, SAIDA = Path(sys.argv[1]), Path(sys.argv[2])
SAIDA.mkdir(parents=True, exist_ok=True)

FAIXAS = ["0-1", "1-2", "2-3", "3-5", "5-8", "8+"]
ROTULOS = ["0-1 anos", "1-2 anos", "2-3 anos", "3-5 anos", "5-8 anos", "8+ anos"]
LINGUAS = ["clojure", "elixir", "zig", "ocaml", "python"]
NOMES = {
    "clojure": "Clojure",
    "elixir": "Elixir",
    "zig": "Zig",
    "ocaml": "OCaml",
    "python": "Python",
}

FUNDO = "#ebebeb"
CONTORNO = "#4d4d4d"
CODING = "#4d4d4d"
LARGURA, ALTURA = 11.0, 2.5  # mesma proporção da imagem de referência (3376 x 773)

plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.size": 9,
        "axes.titlesize": 12,
        "axes.labelsize": 9,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "legend.fontsize": 9,
        "hatch.linewidth": 0.8,
        "pdf.fonttype": 42,
    }
)

c = pd.read_csv(COMPOSICAO)
c = c[(c["ano"] == 2024) & c["faixa"].isin(FAIXAS) & c["slug"].isin(LINGUAS)]

# Tabela de conferência: % dos ativos do ano de cada linguagem, por faixa
linhas = []
for lingua in LINGUAS:
    soma = 0.0
    for faixa in FAIXAS:
        linha = c[(c["slug"] == lingua) & (c["faixa"] == faixa)]
        assert len(linha) == 1, (lingua, faixa)
        discussao = float(linha["non_coding"].iloc[0])
        codigo = float(linha["coding"].iloc[0])
        soma += discussao + codigo
        linhas.append(
            {
                "linguagem": NOMES[lingua],
                "faixa": faixa,
                "discussion_pct": discussao,
                "coding_pct": codigo,
            }
        )
    assert abs(soma - 100.0) < 1e-6, (lingua, soma)  # cada linguagem soma 100% dos ativos
tabela = pd.DataFrame(linhas)
tabela.to_csv(SAIDA / "tabela_2024.csv", index=False)

md = ["| Linguagem | Faixa | Discussion (%) | Coding (%) |", "|---|---|---:|---:|"]
for _, linha in tabela.iterrows():
    d = f"{linha['discussion_pct']:.1f}".replace(".", ",")
    k = f"{linha['coding_pct']:.1f}".replace(".", ",")
    md.append(f"| {linha['linguagem']} | {linha['faixa']} | {d} | {k} |")
(SAIDA / "tabela_2024.md").write_text("\n".join(md) + "\n")

# Limite do eixo: 33 como na imagem; sobe por igual nos cinco painéis se alguma barra passar de 30
maximo = float(tabela[["discussion_pct", "coding_pct"]].max().max())
limite = 33.0
if maximo > 30.0:
    limite = math.ceil(maximo) + 3.0

fig, eixos = plt.subplots(1, 5, figsize=(LARGURA, ALTURA), sharey=True, sharex=True)
posicao = np.arange(len(FAIXAS))
ticks = [-30, -20, -10, 0, 10, 20, 30]
for eixo, lingua in zip(eixos, LINGUAS, strict=True):
    parte = tabela[tabela["linguagem"] == NOMES[lingua]].set_index("faixa").reindex(FAIXAS)
    eixo.set_facecolor(FUNDO)
    eixo.set_axisbelow(True)
    eixo.grid(axis="x", color="white", linewidth=1.0)
    eixo.grid(axis="y", visible=False)
    for lado in eixo.spines.values():
        lado.set_visible(False)
    eixo.tick_params(length=0)
    eixo.barh(
        posicao,
        -parte["discussion_pct"].to_numpy(),
        height=0.85,
        facecolor="white",
        edgecolor=CONTORNO,
        hatch="///",
        linewidth=0.8,
    )
    eixo.barh(
        posicao,
        parte["coding_pct"].to_numpy(),
        height=0.85,
        facecolor=CODING,
        edgecolor=CONTORNO,
        linewidth=0.8,
    )
    eixo.set_xlim(-limite, limite)
    eixo.set_xticks(ticks)
    eixo.xaxis.set_major_formatter(lambda x, _: f"{abs(x):.0f}")
    eixo.set_title(NOMES[lingua])
    eixo.set_xlabel("% dos ativos do ano")
eixos[0].set_yticks(posicao, ROTULOS)  # rótulos das faixas só no primeiro painel

legenda = [
    Patch(facecolor="white", edgecolor=CONTORNO, hatch="///", linewidth=0.8, label="discussion"),
    Patch(facecolor=CODING, edgecolor=CONTORNO, linewidth=0.8, label="coding"),
]
fig.legend(handles=legenda, loc="lower center", ncol=2, frameon=False, bbox_to_anchor=(0.5, 0.0))
fig.subplots_adjust(left=0.07, right=0.995, top=0.88, bottom=0.27, wspace=0.08)

fig.savefig(SAIDA / "composicao_dois_lados_2024.pdf")
fig.savefig(SAIDA / "composicao_dois_lados_2024.png", dpi=600)
plt.close(fig)
print("limite do eixo:", limite, "maior barra:", round(maximo, 2))
