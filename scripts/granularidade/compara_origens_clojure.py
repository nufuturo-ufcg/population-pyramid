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
T.append("")
SAIDA.write_text("\n".join(T) + "\n", encoding="utf-8")
print("\n".join(T))
