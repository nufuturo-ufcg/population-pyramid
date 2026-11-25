"""Compara a população projetada de Clojure nos fins de ano de 2026 a 2030 partindo de 30/06/2026 e de 31/12/2025 (`projecao_clojure_5anos.py`, mesmo código e mesmo erro histórico).

Uso (na raiz do repo): .venv/bin/python scripts/granularidade/compara_origens_clojure.py <resultado da origem de junho> <resultado da origem de dezembro> <saida.md>
"""

import sys
from pathlib import Path

import pandas as pd

JUNHO, DEZEMBRO, SAIDA = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
METODOS = ["Ingênua", "Coorte", "Coorte^R", "Conservador", "Conservador^R", "Ingênua-Coorte^R"]


def milhar(x: float) -> str:
    return f"{x:,.0f}".replace(",", ".")


def dec(x: float) -> str:
    return f"{x:.1f}".replace(".", ",")


a = pd.read_csv(JUNHO / "populacao_projetada.csv")
b = pd.read_csv(DEZEMBRO / "populacao_projetada.csv")
a, b = a[a["tipo"] == "fim_de_ano"], b[b["tipo"] == "fim_de_ano"]
observado = {
    "junho": pd.read_csv(JUNHO / "trajetorias.csv").query("passo == 0")["total"].iloc[0],
    "dezembro": pd.read_csv(DEZEMBRO / "trajetorias.csv").query("passo == 0")["total"].iloc[0],
}
T = [
    "# População projetada de Clojure nos fins de ano: origem de 30/06/2026 contra origem de 31/12/2025",
    "",
    f"Observado na origem: {milhar(observado['junho'])} em 30/06/2026 e {milhar(observado['dezembro'])} em 31/12/2025. Mesmo cenário, mesmo código; só mudam a origem e, com ela, os novatos, as taxas e a previsão de repositórios que o método lê. Cada célula: projeção da origem de junho / da origem de dezembro (diferença da de junho sobre a de dezembro).",
    "",
    "| Método | 2026 | 2027 | 2028 | 2029 | 2030 |",
    "|---|---|---|---|---|---|",
]
for metodo in METODOS:
    celulas = []
    for ano in range(2026, 2031):
        x = a[(a["metodo"] == metodo) & (a["rotulo"] == str(ano))]["projecao"].iloc[0]
        y = b[(b["metodo"] == metodo) & (b["rotulo"] == str(ano))]["projecao"].iloc[0]
        celulas.append(
            f"{milhar(x)} / {milhar(y)} ({'+' if x >= y else ''}{dec(100 * (x - y) / y)}%)"
        )
    T.append(f"| {metodo} | " + " | ".join(celulas) + " |")
# A diferença entre as origens é maior que a faixa de incerteza?
T += [
    "",
    "## A diferença entre as origens é maior que a faixa de incerteza?",
    "",
    'Faixa de incerteza de cada projeção: previsão × (1 + p10) a previsão × (1 + p90) do erro (real − previsto) / previsto do horizonte. "Maior que a faixa": a distância entre as duas projeções é maior que a largura da faixa da origem de junho. "Fora da outra": a projeção de uma origem fica fora da faixa da outra.',
    "",
    "| Método | Ano | Distância | Largura da faixa de junho | Largura da faixa de dezembro | Maior que a faixa de junho? | Junho fora da faixa de dezembro? | Dezembro fora da faixa de junho? |",
    "|---|---|---|---|---|---|---|---|",
]
resumo = {}
for metodo in METODOS:
    maior = 0
    for ano in range(2026, 2031):
        x = a[(a["metodo"] == metodo) & (a["rotulo"] == str(ano))].iloc[0]
        y = b[(b["metodo"] == metodo) & (b["rotulo"] == str(ano))].iloc[0]
        distancia = abs(x["projecao"] - y["projecao"])
        largura_j, largura_d = x["alto"] - x["baixo"], y["alto"] - y["baixo"]
        j_fora = not (y["baixo"] <= x["projecao"] <= y["alto"])
        d_fora = not (x["baixo"] <= y["projecao"] <= x["alto"])
        maior += int(distancia > largura_j)
        T.append(
            f"| {metodo} | {ano} | {milhar(distancia)} | {milhar(largura_j)} | {milhar(largura_d)} | {'sim' if distancia > largura_j else 'não'} | {'sim' if j_fora else 'não'} | {'sim' if d_fora else 'não'} |"
        )
    resumo[metodo] = maior
T += [
    "",
    "Anos (de 5) em que a distância é maior que a faixa de junho: "
    + "; ".join(f"{m} {n}" for m, n in resumo.items())
    + ".",
    "",
]
SAIDA.write_text("\n".join(T) + "\n", encoding="utf-8")
print("\n".join(T))
