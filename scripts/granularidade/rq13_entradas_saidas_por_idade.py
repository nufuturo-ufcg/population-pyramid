"""RQ1.3 de Clojure: entradas, saídas e ativos por faixa de idade e ano (2009 a 2024), com a definição única.

A idade é a da pirâmide (anos com contribuição). A pessoa conta na faixa da idade que tem naquele ano, nas entradas, nas saídas e nos ativos.
Taxa de entrada = entradas / ativos da faixa. Taxa de saída = saídas / ativos da faixa. Somados os anos, a taxa é a soma das entradas (ou das
saídas) dividida pela soma dos ativos da faixa (pessoas-ano). Na faixa [0, 1) as entradas são só novatos (a idade 0 é ser novato do ano); as
voltas aparecem nas faixas de 1 ano em diante e são mostradas à parte em todas as faixas.

Uso (na raiz do repo): .venv/bin/python scripts/granularidade/rq13_entradas_saidas_por_idade.py <pasta com <l>/cache e <l>/origem> <saida> [linguagem]
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, "src")
from carga_residentes import carrega_residentes

from pyramid import vitalidade

PASTA, SAIDA = Path(sys.argv[1]), Path(sys.argv[2])
LINGUA = sys.argv[3] if len(sys.argv) > 3 else "clojure"
SAIDA.mkdir(parents=True, exist_ok=True)
FAIXAS = vitalidade.FAIXAS
ANOS = list(range(2009, 2025))

compactos, pa, fim = carrega_residentes(PASTA, LINGUA)
pa = pa[pa["ano"].between(2009, 2024)].copy()
pa["entrou"] = vitalidade.entrou_no_ano(pa)
pa["saiu"] = vitalidade.saiu_no_ano(pa)

linhas = []
for ano in ANOS:
    do_ano = pa[pa["ano"] == ano]
    for faixa in FAIXAS:
        f = do_ano[do_ano["faixa"] == faixa]
        linhas.append(
            {
                "ano": ano,
                "faixa": faixa,
                "ativos": len(f),
                "entradas": int(f["entrou"].sum()),
                "novatos": int(f["novato"].sum()),
                "voltas": int(f["volta"].sum()),
                "saidas": int(f["saiu"].sum()),
                "saidas_sem_volta": int(f["saida"].sum()),
                "saidas_com_volta": int(f["pausa"].sum()),
            }
        )
tabela = pd.DataFrame(linhas)

# Conferência com a tabela anual (RQ1.1): a soma das faixas dá os totais do ano
anual = vitalidade.tabela_anual(pa.assign(), fim).set_index("ano")
for ano in ANOS:
    soma = tabela[tabela["ano"] == ano][
        [
            "ativos",
            "entradas",
            "novatos",
            "voltas",
            "saidas",
            "saidas_sem_volta",
            "saidas_com_volta",
        ]
    ].sum()
    for coluna in soma.index:
        esperado = anual.loc[ano, coluna]
        if not pd.isna(esperado):
            assert soma[coluna] == esperado, (
                f"{ano} {coluna}: faixas somam {soma[coluna]} e a tabela anual traz {esperado}"
            )
tabela["taxa_entrada_pct"] = 100 * tabela["entradas"] / tabela["ativos"].where(tabela["ativos"] > 0)
tabela["taxa_saida_pct"] = 100 * tabela["saidas"] / tabela["ativos"].where(tabela["ativos"] > 0)
tabela.to_csv(SAIDA / "rq13_por_faixa_e_ano.csv", index=False, float_format="%.10g")


def resume(t: pd.DataFrame) -> pd.DataFrame:
    g = (
        t.groupby("faixa", sort=False)[
            [
                "ativos",
                "entradas",
                "novatos",
                "voltas",
                "saidas",
                "saidas_sem_volta",
                "saidas_com_volta",
            ]
        ]
        .sum()
        .reindex(FAIXAS)
    )
    g["taxa_entrada_pct"] = 100 * g["entradas"] / g["ativos"]
    g["taxa_novatos_pct"] = 100 * g["novatos"] / g["ativos"]
    g["taxa_voltas_pct"] = 100 * g["voltas"] / g["ativos"]
    g["taxa_saida_pct"] = 100 * g["saidas"] / g["ativos"]
    return g


soma_2009_2024 = resume(tabela)
so_2024 = resume(tabela[tabela["ano"] == 2024])
soma_2009_2024.to_csv(SAIDA / "rq13_por_faixa_2009_2024.csv", float_format="%.10g")
so_2024.to_csv(SAIDA / "rq13_por_faixa_2024.csv", float_format="%.10g")


def milhar(x: float) -> str:
    return f"{x:,.0f}".replace(",", ".")


def dec(x: float) -> str:
    return "n/d" if pd.isna(x) else f"{x:.1f}".replace(".", ",")


def bloco(titulo: str, g: pd.DataFrame) -> list[str]:
    t = [
        f"## {titulo}",
        "",
        "| Faixa | Ativos (pessoas-ano) | Entradas | Novatos | Voltas | Saídas | Sem volta | Com volta | Taxa de entrada (%) | Taxa de novatos (%) | Taxa de voltas (%) | Taxa de saída (%) |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for faixa, x in g.iterrows():
        t.append(
            f"| [{faixa}) | {milhar(x['ativos'])} | {milhar(x['entradas'])} | {milhar(x['novatos'])} | {milhar(x['voltas'])} | {milhar(x['saidas'])} | {milhar(x['saidas_sem_volta'])} | {milhar(x['saidas_com_volta'])} | {dec(x['taxa_entrada_pct'])} | {dec(x['taxa_novatos_pct'])} | {dec(x['taxa_voltas_pct'])} | {dec(x['taxa_saida_pct'])} |"
        )
    t.append("")
    return t


T = [
    "# RQ1.3 de Clojure: entradas e saídas por idade (definição única, v3b)",
    "",
    "Idade da pirâmide. A pessoa entra e sai na faixa da idade que tem no ano. A faixa [0, 1) tem só novatos (idade 0 é ser novato do ano), então a coluna de voltas fica zerada nela. A taxa é a soma de 2009 a 2024 dividida pelos pessoas-ano da faixa. Conferido: a soma das faixas bate com a tabela anual da RQ1.1 em todos os anos.",
    "",
]
T += bloco("Somando 2009 a 2024", soma_2009_2024)
T += bloco("Só 2024", so_2024)
T += [
    "## Por ano (taxa de entrada e de saída, %)",
    "",
    "| Ano | " + " | ".join(f"[{f}) entrada | [{f}) saída" for f in FAIXAS) + " |",
    "|---|" + "---|---|" * len(FAIXAS),
]
for ano in ANOS:
    t = tabela[tabela["ano"] == ano].set_index("faixa").reindex(FAIXAS)
    T.append(
        f"| {ano} | "
        + " | ".join(
            f"{dec(t.loc[f, 'taxa_entrada_pct'])} | {dec(t.loc[f, 'taxa_saida_pct'])}"
            for f in FAIXAS
        )
        + " |"
    )
T.append("")
(SAIDA / "rq13_entradas_saidas_por_idade.md").write_text("\n".join(T) + "\n", encoding="utf-8")
print("\n".join(T[:30]))
