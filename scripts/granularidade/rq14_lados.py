"""RQ1.4 e RQ2.4: os dois lados (discussão e código) e o fluxo entre eles, com a definição única de lado.

Regra: fica no lado de discussão quem teve mais da metade dos eventos do ano em discussão; os demais ficam no lado de código (`vitalidade.lado_no_ano`).
Passaram a contribuir com código: começaram pela discussão e fizeram o primeiro commit ou PR no ano. Deixaram: o último commit ou PR é do ano e depois só discussão.
Para Clojure, de 2008 a 2024, a fatia de cada lado e o fluxo ano a ano. Para as cinco linguagens, os mesmos números em 2024.
Confere o lado de 2024 contra `composicao.csv` da rodada (se `<rodada>` for dado) e para se diferir.

Uso (na raiz do repo): .venv/bin/python scripts/granularidade/rq14_lados.py <pasta com <l>/cache e <l>/origem> <saida> [<pasta da rodada com <l>-mais_de_uma_ocasiao>]
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from carga_residentes import carrega_residentes

PASTA, SAIDA = Path(sys.argv[1]), Path(sys.argv[2])
RODADA = Path(sys.argv[3]) if len(sys.argv) > 3 else None
SAIDA.mkdir(parents=True, exist_ok=True)
LINGUAS = ["clojure", "elixir", "zig", "ocaml", "python"]
NOMES = {
    "clojure": "Clojure",
    "elixir": "Elixir",
    "zig": "Zig",
    "ocaml": "OCaml",
    "python": "Python",
}

linhas = []
for lingua in LINGUAS:
    _, pa, _ = carrega_residentes(PASTA, lingua)
    for ano in range(2008, 2025):
        d = pa[pa["ano"] == ano]
        if d.empty:
            continue
        discussao = int((d["categoria"] == "non_coding").sum())
        codigo = int((d["categoria"] == "coding").sum())
        linhas.append(
            {
                "linguagem": lingua,
                "ano": ano,
                "ativos": len(d),
                "discussao": discussao,
                "codigo": codigo,
                "discussao_pct": 100 * discussao / len(d),
                "codigo_pct": 100 * codigo / len(d),
                "passaram_a_contribuir_com_codigo": int(d["moved_no_ano"].sum()),
                "deixaram_de_contribuir_com_codigo": int(d["deixou_codigo_no_ano"].sum()),
            }
        )
    print(f"{lingua}: pronto", flush=True)
tabela = pd.DataFrame(linhas)
tabela.to_csv(SAIDA / "rq14_lados_por_ano.csv", index=False, float_format="%.10g")

if RODADA is not None:
    for lingua in LINGUAS:
        c = pd.read_csv(
            RODADA / f"{lingua}-mais_de_uma_ocasiao" / "csv" / "vitalidade" / "composicao.csv"
        )
        c = c[c["ano"] == 2024]
        t = tabela[(tabela["linguagem"] == lingua) & (tabela["ano"] == 2024)].iloc[0]
        assert (
            int(c["non_coding"].sum()) == t["discussao"] and int(c["coding"].sum()) == t["codigo"]
        ), f"{lingua}: o lado de 2024 difere da rodada"


def milhar(x: float) -> str:
    return f"{x:,.0f}".replace(",", ".")


def dec(x: float) -> str:
    return f"{x:.1f}".replace(".", ",")


T = [
    "# RQ1.4 e RQ2.4: lados de discussão e de código (definição única, v3b)",
    "",
    "Regra: lado de discussão é quem teve mais da metade dos eventos do ano em discussão; os demais ficam no lado de código. O lado vale só para o ano.",
    "",
    "## Clojure, 2008 a 2024",
    "",
    "| Ano | Ativos | Discussão | Código | Discussão (%) | Código (%) | Passaram a contribuir com código | Deixaram de contribuir com código |",
    "|---|---|---|---|---|---|---|---|",
]
for _, x in tabela[tabela["linguagem"] == "clojure"].iterrows():
    T.append(
        f"| {int(x['ano'])} | {milhar(x['ativos'])} | {milhar(x['discussao'])} | {milhar(x['codigo'])} | {dec(x['discussao_pct'])} | {dec(x['codigo_pct'])} | {milhar(x['passaram_a_contribuir_com_codigo'])} | {milhar(x['deixaram_de_contribuir_com_codigo'])} |"
    )
T += [
    "",
    "## As cinco linguagens em 2024",
    "",
    "| | " + " | ".join(NOMES[x] for x in LINGUAS) + " |",
    "|---|" + "---|" * len(LINGUAS),
]
d24 = tabela[tabela["ano"] == 2024].set_index("linguagem")
for rotulo, chave, formato in [
    ("Ativos", "ativos", milhar),
    ("Lado da discussão (pessoas)", "discussao", milhar),
    ("Lado do código (pessoas)", "codigo", milhar),
    ("Lado da discussão (%)", "discussao_pct", dec),
    ("Lado do código (%)", "codigo_pct", dec),
    ("Passaram a contribuir com código", "passaram_a_contribuir_com_codigo", milhar),
    ("Deixaram de contribuir com código", "deixaram_de_contribuir_com_codigo", milhar),
]:
    T.append(f"| {rotulo} | " + " | ".join(formato(d24.loc[x, chave]) for x in LINGUAS) + " |")
T.append("")
(SAIDA / "rq14_lados.md").write_text("\n".join(T) + "\n", encoding="utf-8")
print("\n".join(T[-14:]))
