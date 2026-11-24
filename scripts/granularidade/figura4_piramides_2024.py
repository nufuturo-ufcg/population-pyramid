"""Figura 4: pirâmides de 2024 das cinco linguagens, em porcentagem dos ativos do ano (`rq2-v3/hipoteses.md`, item 4).

Mesmo estilo da figura 1 (`figuras_v3.py`): PDF, tons de cinza, 7 polegadas, rótulos em português. Discussão à esquerda e código à
direita, 6 faixas, o mesmo eixo x em todos os painéis. Lê `composicao_pct.csv` da rodada oficial v3 e grava `figura4.csv`.

Uso (na raiz do repo): .venv/bin/python scripts/granularidade/figura4_piramides_2024.py <composicao_pct.csv> <saida>
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

COMPOSICAO, SAIDA = Path(sys.argv[1]), Path(sys.argv[2])
SAIDA.mkdir(parents=True, exist_ok=True)
FAIXAS = ["0-1", "1-2", "2-3", "3-5", "5-8", "8+"]
LINGUAS = ["clojure", "elixir", "zig", "ocaml", "python"]
NOMES = {
    "clojure": "Clojure",
    "elixir": "Elixir",
    "zig": "Zig",
    "ocaml": "OCaml",
    "python": "Python",
}
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
        "axes.spines.top": False,
        "axes.spines.right": False,
    }
)

c = pd.read_csv(COMPOSICAO)
c = c[(c["ano"] == 2024) & c["faixa"].isin(FAIXAS) & c["slug"].isin(LINGUAS)].copy()
c["faixa"] = pd.Categorical(c["faixa"], categories=FAIXAS, ordered=True)
c = c.sort_values(["slug", "faixa"])
c.rename(
    columns={"slug": "linguagem", "non_coding": "discussao_pct", "coding": "codigo_pct"}
).to_csv(SAIDA / "figura4.csv", index=False)
maximo = float(c[["non_coding", "coding"]].max().max())
limite = float(np.ceil(maximo / 5.0) * 5.0)
fig, eixos = plt.subplots(1, 5, figsize=(7.0, 2.2), sharey=True, sharex=True)
posicao = np.arange(len(FAIXAS))
for eixo, lingua in zip(eixos, LINGUAS, strict=True):
    parte = c[c["slug"] == lingua].set_index("faixa").reindex(FAIXAS)
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
    eixo.set_title(NOMES[lingua])
    eixo.set_xlim(-limite, limite)
    eixo.set_yticks(posicao, FAIXAS)
    eixo.xaxis.set_major_formatter(lambda x, _: f"{abs(x):.0f}")
    eixo.set_xlabel("% dos ativos")
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
fig.savefig(SAIDA / "figura4_piramides_2024.pdf")
plt.close(fig)
print("figura 4 gravada em", SAIDA)
