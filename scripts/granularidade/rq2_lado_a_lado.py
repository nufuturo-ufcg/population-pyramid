"""Tabela de 2024 da RQ2: v3 (peso de 2025) ao lado da v3b (peso de 2024). Não interpreta nenhum número.

Entradas: `tabela_2024.csv` e `codigo_discussao_2024.csv` de `rq2-v3/` e `rq2-v3b/` (`rq2_v3.py`), e o `logrank.csv` das duas rodadas.
Cada célula mostra `v3 → v3b`; célula igual aparece uma vez. Grava `<saida>/rq2_tabela_v3_v3b.md` e `.csv`.

Uso (na raiz do repo): .venv/bin/python scripts/granularidade/rq2_lado_a_lado.py <pyramid-vitalidade> <saida>
"""

import sys
from pathlib import Path

import pandas as pd

RAIZ, SAIDA = Path(sys.argv[1]), Path(sys.argv[2])
LINGUAS = ["clojure", "elixir", "zig", "ocaml", "python"]
NOMES = {
    "clojure": "Clojure",
    "elixir": "Elixir",
    "zig": "Zig",
    "ocaml": "OCaml",
    "python": "Python",
}
a = pd.read_csv(RAIZ / "rq2-v3" / "tabela_2024.csv").set_index("linguagem")
b = pd.read_csv(RAIZ / "rq2-v3b" / "tabela_2024.csv").set_index("linguagem")
la = pd.read_csv(RAIZ / "rq2-v3" / "codigo_discussao_2024.csv").set_index("linguagem")
lb = pd.read_csv(RAIZ / "rq2-v3b" / "codigo_discussao_2024.csv").set_index("linguagem")
ra = pd.read_csv(
    RAIZ / "rodada-oficial-v3" / "geral-mais_de_uma_ocasiao" / "csv" / "vitalidade" / "logrank.csv"
).set_index("comparacao")
rb = pd.read_csv(
    RAIZ / "rodada-oficial-v3b" / "geral-mais_de_uma_ocasiao" / "csv" / "vitalidade" / "logrank.csv"
).set_index("comparacao")


def milhar(x: float) -> str:
    return f"{x:,.0f}".replace(",", ".")


def dec(x: float, casas: int = 1) -> str:
    return "n/a" if pd.isna(x) else f"{x:.{casas}f}".replace(".", ",")


def par(x: float, y: float, fmt) -> str:
    if pd.isna(x) and pd.isna(y):
        return "n/a"
    texto_x, texto_y = fmt(x), fmt(y)
    return texto_x if texto_x == texto_y else f"{texto_x} → {texto_y}"


LINHAS = [
    ("Ativos", a, b, "ativos", milhar),
    ("Novatos", a, b, "novatos", milhar),
    ("Saídas", a, b, "saidas", milhar),
    ("Natalidade (%)", a, b, "natalidade_pct", dec),
    ("Mortalidade (%)", a, b, "mortalidade_pct", dec),
    ("Crescimento natural (pontos)", a, b, "natural_pontos", dec),
    ("NCR em 31/12/2024", a, b, "ncr", lambda x: dec(x, 3)),
    ("Pessoas na tábua", a, b, "tabua_pessoas", milhar),
    ("e0 (anos, piso)", a, b, "e0", lambda x: dec(x, 2)),
    ("Permanecem 1 ano (%)", a, b, "permanece_1_ano_pct", dec),
    ("Permanecem 5 anos (%)", a, b, "permanece_5_anos_pct", dec),
    ("Taxa bruta de saída (%)", a, b, "taxa_bruta_pct", dec),
    ("Taxa padronizada, referência nicho (%)", a, b, "taxa_padronizada_nicho_pct", dec),
    ("SMR, referência nicho", a, b, "smr_nicho", lambda x: dec(x, 2)),
    ("Taxa padronizada, referência python (%)", a, b, "taxa_padronizada_python_pct", dec),
    ("SMR, referência python", a, b, "smr_python", lambda x: dec(x, 2)),
    ("Lado da discussão (%)", la, lb, "discussao_pct", dec),
    ("Lado do código (%)", la, lb, "codigo_pct", dec),
    ("Passaram a contribuir com código", la, lb, "passaram_a_contribuir_com_codigo", milhar),
    ("Deixaram de contribuir com código", la, lb, "deixaram_de_contribuir_com_codigo", milhar),
]
T = [
    "# RQ2, 2024: v3 com peso de 2025 ao lado da v3b com peso de 2024",
    "",
    "Cada célula mostra `v3 → v3b`; célula igual aparece uma vez. `n/a` é linguagem fora daquela referência.",
    "",
    "## Qual população forma cada referência e qual ano pesa",
    "",
    "| | v3 | v3b |",
    "|---|---|---|",
    "| Carga | leitura paralela do duckdb | leitura sequencial (`parallel=false`) |",
    "| Ano do peso da taxa padronizada | 2025 (`ano_pesos: 2025`) | 2024 (`ano_pesos: 2024`) |",
    "| Referência nicho | soma dos ativos de Clojure, Elixir, Zig e OCaml da v3; taxa de cada faixa e ano é saídas totais sobre ativos totais dos quatro | a mesma soma, com os ativos da v3b |",
    "| Referência python | soma dos ativos de Clojure e Python da v3 | a mesma soma, com os ativos da v3b |",
    "| Pesos da taxa padronizada | parte dos ativos de cada faixa na referência em 2025 | parte dos ativos de cada faixa na referência em 2024 |",
    "| SMR | não usa peso: saídas observadas sobre esperadas (taxa da referência em 2024 vezes os ativos da linguagem na faixa) | idem |",
    "",
    "## Tabela de 2024",
    "",
    "| | " + " | ".join(NOMES[x] for x in LINGUAS) + " |",
    "|---|" + "---|" * len(LINGUAS),
]
linhas_csv = []
for rotulo, ta, tb, coluna, fmt in LINHAS:
    celulas = []
    for lingua in LINGUAS:
        x = ta.loc[lingua].get(coluna) if lingua in ta.index else float("nan")
        y = tb.loc[lingua].get(coluna) if lingua in tb.index else float("nan")
        celulas.append(par(x, y, fmt))
        linhas_csv.append(
            {"linha": rotulo, "linguagem": lingua, "v3_peso_2025": x, "v3b_peso_2024": y}
        )
    T.append(f"| {rotulo} | " + " | ".join(celulas) + " |")
T += [
    "",
    "## Log-rank de Clojure contra cada linguagem (limite de Bonferroni 0,0125)",
    "",
    "| Comparação | Estatística | p | p abaixo do limite |",
    "|---|---|---|---|",
]
for nome in ra.index:
    rotulo = nome.replace("clojure x ", "Clojure contra ")
    for chave, valor in NOMES.items():
        if chave != "clojure":
            rotulo = rotulo.replace(chave, valor)
    ea, eb = float(ra.loc[nome, "estatistica"]), float(rb.loc[nome, "estatistica"])
    pa_, pb = float(ra.loc[nome, "p"]), float(rb.loc[nome, "p"])
    texto_p = par(pa_, pb, lambda x: f"{x:.2e}".replace(".", ","))
    limite = "sim" if (pa_ < 0.0125) == (pb < 0.0125) and pb < 0.0125 else "ver"
    T.append(f"| {rotulo} | {par(ea, eb, lambda x: dec(x, 2))} | {texto_p} | {limite} |")
SAIDA.mkdir(parents=True, exist_ok=True)
pd.DataFrame(linhas_csv).to_csv(SAIDA / "rq2_tabela_v3_v3b.csv", index=False)
(SAIDA / "rq2_tabela_v3_v3b.md").write_text("\n".join(T) + "\n", encoding="utf-8")
print("\n".join(T))
