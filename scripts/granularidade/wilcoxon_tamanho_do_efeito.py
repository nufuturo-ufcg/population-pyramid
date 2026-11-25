"""Tamanho do efeito do Wilcoxon de dezembro (janela de 4 trimestres): estimativa de Hodges-Lehmann e intervalo de confiança exato que acompanha o teste de postos sinalizados.

Lê `pares_usados.csv` de `wilcoxon_uma_previsao_por_ano.py` (janela de 4 trimestres, uma previsão por ano, 31 de dezembro). Para cada comparação e recorte (cada linguagem e as quatro juntas):
  - estimativa de Hodges-Lehmann da diferença (primeiro método menos segundo) do erro percentual absoluto, em pontos percentuais: a mediana das médias de Walsh (d_i + d_j) / 2, i <= j;
  - intervalo exato [W_(c+1), W_(M−c)] das médias de Walsh ordenadas, com M = n (n + 1) / 2 e c o maior inteiro com P(T <= c) <= 0,025 sob H0. O intervalo exclui o zero se e só se o p exato é menor que 0,05
    (conferido). Quando n é pequeno e esse c não existe (n < 6), o mais estreito possível é o de c = 0 (de uma ponta a outra das médias de Walsh), com nível 1 − 2 / 2^n abaixo de 95%.
  - para Clojure, a mesma estimativa para a diferença do erro absoluto em pessoas.

Uso (na raiz do repo): uv run --no-project --with pandas --with numpy --with scipy python scripts/granularidade/wilcoxon_tamanho_do_efeito.py <pares_usados.csv> <resultados.csv do Wilcoxon> <saida>
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

PARES, RESULTADOS, SAIDA = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
SAIDA.mkdir(parents=True, exist_ok=True)
LINGUAS = ["clojure", "elixir", "ocaml", "python"]
NOMES = {"clojure": "Clojure", "elixir": "Elixir", "ocaml": "OCaml", "python": "Python"}
COMPARACOES = (
    [
        (m, "Ingênua")
        for m in ["Coorte", "Coorte^R", "Conservador", "Conservador^R", "Ingênua-Coorte^R"]
    ]
    + [(m, "Coorte") for m in ["Coorte^R", "Conservador", "Conservador^R", "Ingênua-Coorte^R"]]
    + [("Conservador^R", "Conservador")]
)


def dec(x: float, casas: int = 2) -> str:
    return "n/d" if pd.isna(x) else f"{x:.{casas}f}".replace(".", ",")


def distribuicao_exata(n: int) -> np.ndarray:
    """Probabilidade de a soma dos postos positivos ser s, para s = 0..n(n+1)/2, sob H0."""
    maximo = n * (n + 1) // 2
    contagem = np.zeros(maximo + 1)
    contagem[0] = 1
    for posto in range(1, n + 1):
        nova = contagem.copy()
        nova[posto:] += contagem[: maximo + 1 - posto]
        contagem = nova
    return contagem / 2.0**n


def hodges_lehmann(d: np.ndarray, alfa: float = 0.05) -> dict:
    n = len(d)
    walsh = np.sort(np.array([(d[i] + d[j]) / 2 for i in range(n) for j in range(i, n)]))
    m = len(walsh)
    acumulada = np.cumsum(distribuicao_exata(n))
    candidatos = [c for c in range(m) if acumulada[c] <= alfa / 2]
    c = max(candidatos) if candidatos else 0
    nivel = 1 - 2 * float(acumulada[c])
    return {
        "estimativa": float(np.median(walsh)),
        "inferior": float(walsh[c]),
        "superior": float(walsh[m - 1 - c]),
        "nivel": nivel,
        "c": c,
        "n": n,
        "alcanca_95": bool(candidatos),
    }


pares = pd.read_csv(PARES)
pares = pares[pares["janela"] == "4 trimestres"]
res = pd.read_csv(RESULTADOS)
res = res[res["janela"] == "4 trimestres"]
linhas = []
for recorte in [*LINGUAS, "juntas"]:
    base = pares if recorte == "juntas" else pares[pares["linguagem"] == recorte]
    for a, b in COMPARACOES:
        x = base[base["metodo"] == a].set_index(["linguagem", "origem"]).sort_index()
        y = base[base["metodo"] == b].set_index(["linguagem", "origem"]).sort_index()
        assert list(x.index) == list(y.index)
        d = (x["mape"] - y["mape"]).to_numpy()
        hl = hodges_lehmann(d)
        p_ref = res[(res["recorte"] == recorte) & (res["metodo_a"] == a) & (res["metodo_b"] == b)][
            "mape_p"
        ].iloc[0]
        p_proprio = float(
            wilcoxon(
                x["mape"].to_numpy(), y["mape"].to_numpy(), method="exact", alternative="two-sided"
            ).pvalue
        )
        assert abs(p_proprio - p_ref) < 1e-9, (
            f"{recorte} {a} contra {b}: p {p_proprio} contra o da tabela {p_ref}"
        )
        exclui_zero = not (hl["inferior"] <= 0 <= hl["superior"])
        registro = {
            "recorte": recorte,
            "metodo_a": a,
            "metodo_b": b,
            "pares": len(d),
            "p": p_ref,
            "p_menor_que_0_05": bool(p_ref < 0.05),
            "hl_pp": hl["estimativa"],
            "ic_inferior_pp": hl["inferior"],
            "ic_superior_pp": hl["superior"],
            "nivel_do_ic": hl["nivel"],
            "ic_de_95": hl["alcanca_95"],
            "ic_exclui_zero": exclui_zero,
        }
        if recorte == "clojure":
            dp = (x["erro_pessoas"] - y["erro_pessoas"]).to_numpy()
            hp = hodges_lehmann(dp)
            registro.update(
                {
                    "hl_pessoas": hp["estimativa"],
                    "ic_inferior_pessoas": hp["inferior"],
                    "ic_superior_pessoas": hp["superior"],
                }
            )
        linhas.append(registro)
r = pd.DataFrame(linhas)
r.to_csv(SAIDA / "tamanho_do_efeito.csv", index=False, float_format="%.10g")
# o intervalo exclui o zero exatamente quando o p é menor que 0,05, onde o intervalo é de 95% ou mais
valido = r[r["ic_de_95"]]
divergentes = valido[valido["ic_exclui_zero"] != valido["p_menor_que_0_05"]]
if len(divergentes):
    print(
        "ATENÇÃO: o intervalo e o p divergem em",
        divergentes[
            ["recorte", "metodo_a", "metodo_b", "p", "ic_inferior_pp", "ic_superior_pp"]
        ].to_string(index=False),
    )
    sys.exit(1)

NOME = {**NOMES, "juntas": "Quatro linguagens juntas"}
T = [
    "# Tamanho do efeito do Wilcoxon de dezembro, janela de 4 trimestres",
    "",
    "Estimativa de Hodges-Lehmann (mediana das médias de Walsh) da diferença do erro percentual absoluto, primeiro método menos segundo, em pontos percentuais; negativa favorece o primeiro. O intervalo é o exato de postos sinalizados que acompanha o teste: exclui o zero se e só se o p exato é menor que 0,05 (conferido em todas as linhas em que o intervalo chega a 95%). O nível é o realmente alcançado (o teste exato é discreto). Com 4 pares (Elixir) não existe intervalo de 95%: mostro o mais estreito possível, de uma ponta a outra das médias de Walsh, com nível de 87,5%. Esse intervalo só exclui o zero quando as 4 diferenças têm o mesmo sinal (p exato de 0,125, que não é significativo).",
    "",
]
for recorte in [*LINGUAS, "juntas"]:
    x = r[r["recorte"] == recorte]
    T += [
        f"## {NOME[recorte]} ({x['pares'].iloc[0]} pares)",
        "",
        "| Comparação | p | Hodges-Lehmann (p.p.) | Intervalo de confiança (p.p.) | Nível do intervalo | O intervalo exclui o zero? | p < 0,05 |",
        "|---|---|---|---|---|---|---|",
    ]
    for _, y in x.iterrows():
        p = f"{y['p']:.4f}".replace(".", ",")
        T.append(
            f"| {y['metodo_a']} contra {y['metodo_b']} | {p} | {dec(y['hl_pp'])} | de {dec(y['ic_inferior_pp'])} a {dec(y['ic_superior_pp'])} | {dec(100 * y['nivel_do_ic'], 1)}% | {'sim' if y['ic_exclui_zero'] else 'não'} | {'sim' if y['p_menor_que_0_05'] else 'não'} |"
        )
    T.append("")
cl = r[r["recorte"] == "clojure"]
T += [
    "## Clojure, diferença em pessoas (erro absoluto, primeiro método menos segundo)",
    "",
    "Mesma estimativa e mesmo tipo de intervalo, aplicados à diferença de |previsto − real| em pessoas, nas 8 previsões de dezembro.",
    "",
    "| Comparação | Hodges-Lehmann (pessoas) | Intervalo de confiança (pessoas) | Nível do intervalo |",
    "|---|---|---|---|",
]
for _, y in cl.iterrows():
    T.append(
        f"| {y['metodo_a']} contra {y['metodo_b']} | {dec(y['hl_pessoas'], 0)} | de {dec(y['ic_inferior_pessoas'], 0)} a {dec(y['ic_superior_pessoas'], 0)} | {dec(100 * y['nivel_do_ic'], 1)}% |"
    )
T.append("")
(SAIDA / "tamanho_do_efeito.md").write_text("\n".join(T) + "\n", encoding="utf-8")
print("\n".join(T[:30]))
print(
    "intervalo exclui o zero em",
    int(r["ic_exclui_zero"].sum()),
    "linhas; p < 0,05 em",
    int(r["p_menor_que_0_05"].sum()),
)
