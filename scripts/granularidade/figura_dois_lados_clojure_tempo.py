"""Pirâmide de Clojure em 2014, 2018, 2022 e 2024, no estilo da figura das cinco linguagens.

Mesmo desenho da versão para a caixa de 1260 x 244 px (`figura_dois_lados_slide.CAIXA`), com um
painel por ano. Lê `composicao_pct.csv` da rodada v3b (definição única): discussion se mais da
metade dos eventos do ano forem de discussão, coding nos demais casos (empate vai para coding).

Uso: .venv/bin/python scripts/granularidade/figura_dois_lados_clojure_tempo.py <composicao_pct.csv> <saida>
"""

import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from figura_dois_lados_slide import CAIXA, FAIXAS, desenha

ANOS = [2014, 2018, 2022, 2024]
LIMITE_CINCO_LINGUAGENS = 38.0

COMPOSICAO, SAIDA = Path(sys.argv[1]), Path(sys.argv[2])
SAIDA.mkdir(parents=True, exist_ok=True)

c = pd.read_csv(COMPOSICAO)
c = c[(c["slug"] == "clojure") & c["ano"].isin(ANOS) & c["faixa"].isin(FAIXAS)]

linhas = []
paineis = []
for ano in ANOS:
    soma = 0.0
    parte = {}
    for faixa in FAIXAS:
        linha = c[(c["ano"] == ano) & (c["faixa"] == faixa)]
        assert len(linha) == 1, (ano, faixa)
        discussao = float(linha["non_coding"].iloc[0])
        codigo = float(linha["coding"].iloc[0])
        soma += discussao + codigo
        parte[faixa] = {"discussion_pct": discussao, "coding_pct": codigo}
        linhas.append(
            {"ano": ano, "faixa": faixa, "discussion_pct": discussao, "coding_pct": codigo}
        )
    assert abs(soma - 100.0) < 1e-6, (ano, soma)  # cada ano soma 100% dos ativos
    paineis.append((str(ano), pd.DataFrame.from_dict(parte, orient="index")))
tabela = pd.DataFrame(linhas)
tabela.to_csv(SAIDA / "tabela_clojure.csv", index=False)

# Tabela larga para conferir: uma linha por faixa, duas colunas (discussion e coding) por ano
md = ["| Faixa | " + " | ".join(f"{a} discussion | {a} coding" for a in ANOS) + " |"]
md.append("|---|" + "---:|" * (2 * len(ANOS)))
for faixa in FAIXAS:
    texto = f"| {faixa} |"
    for ano in ANOS:
        linha = tabela[(tabela["ano"] == ano) & (tabela["faixa"] == faixa)].iloc[0]
        d = f"{linha['discussion_pct']:.1f}".replace(".", ",")
        k = f"{linha['coding_pct']:.1f}".replace(".", ",")
        texto += f" {d} | {k} |"
    md.append(texto)
(SAIDA / "tabela_clojure.md").write_text("\n".join(md) + "\n")

# Mesmo limite da figura das cinco linguagens, a menos que alguma barra passe dele
maximo = float(tabela[["discussion_pct", "coding_pct"]].max().max())
limite = LIMITE_CINCO_LINGUAGENS
if maximo > limite - 3.0:
    limite = math.ceil(maximo) + 3.0

fig = desenha(paineis, limite, **CAIXA)
fig.savefig(SAIDA / "piramide_clojure_caixa.pdf")
fig.savefig(SAIDA / "piramide_clojure_caixa_1260x244.png", dpi=100)
fig.savefig(SAIDA / "piramide_clojure_caixa_5040x976.png", dpi=400)
plt.close(fig)
print("limite do eixo:", limite, "maior barra:", round(maximo, 2))
