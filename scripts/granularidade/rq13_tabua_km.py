"""Tábua de vida e Kaplan-Meier por idade da pirâmide, nas cinco linguagens, com log-rank de Clojure contra cada uma.

A idade é a da pirâmide (os anos de pausa não somam). Quem volta continua a vida com a idade que tinha. A vida termina só na saída definitiva
(12 meses sem contribuir até o fim do acompanhamento). Quem ainda pode voltar, ou tem o último evento depois de 2024, entra censurado.
Usa `vitalidade.duracoes_pela_idade` (coortes até 2024), `tabua_de_vida`, `kaplan_meier` e `logrank`, o mesmo código da rodada.

Critério de estabilidade de q(x): o primeiro x0 tal que, para todo x >= x0 com n_efetivo >= 30, |q(x) - qbar| <= 0,05, com
qbar = soma de d(x) / soma de n_efetivo(x) de x0 em diante.

Confere a tábua contra `tabua_comparada.csv` da rodada (se `<rodada>` for dado) e para se diferir.

Uso (na raiz do repo): .venv/bin/python scripts/granularidade/rq13_tabua_km.py <pasta com <l>/cache e <l>/origem> <saida> [<csv da tabua_comparada da rodada>]
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, "src")
from carga_residentes import carrega_residentes

from pyramid import vitalidade

PASTA, SAIDA = Path(sys.argv[1]), Path(sys.argv[2])
RODADA_TABUA = Path(sys.argv[3]) if len(sys.argv) > 3 else None
SAIDA.mkdir(parents=True, exist_ok=True)
LINGUAS = ["clojure", "elixir", "zig", "ocaml", "python"]
NOMES = {
    "clojure": "Clojure",
    "elixir": "Elixir",
    "zig": "Zig",
    "ocaml": "OCaml",
    "python": "Python",
}
ATE = 2024
BONFERRONI = 0.0125
TOLERANCIA = 0.05
N_MINIMO = 30
# e0 da tábua antiga (tempo da primeira à última contribuição, com pausas), de `rq2-v3b/tabela_2024.csv`
E0_ANTIGO = {"clojure": 3.3396, "elixir": 4.0124, "zig": 3.8675, "ocaml": 3.9876, "python": 5.1946}


def primeiro_ano_estavel(tab: pd.DataFrame) -> float:
    valido = tab[tab["n_efetivo"] >= N_MINIMO]
    for x0 in valido["x"]:
        resto = valido[valido["x"] >= x0]
        q_medio = resto["d"].sum() / resto["n_efetivo"].sum()
        if (resto["q"] - q_medio).abs().max() <= TOLERANCIA:
            return float(x0)
    return float("nan")


duracoes = {}
tabuas = []
resumo = []
for lingua in LINGUAS:
    compactos, _, fim = carrega_residentes(PASTA, lingua)
    dur = vitalidade.duracoes_pela_idade(compactos, fim, ATE)
    duracoes[lingua] = dur
    tab = vitalidade.tabua_de_vida(dur)
    estavel = primeiro_ano_estavel(tab)
    s = tab.set_index("x")["S"]
    resumo.append(
        {
            "linguagem": lingua,
            "pessoas": len(dur),
            "saidas": int(dur["saiu"].sum()),
            "censuradas": int((~dur["saiu"]).sum()),
            "e0": float(tab.loc[tab["x"] == 0, "e"].iloc[0]),
            "e0_truncado": bool(tab.loc[tab["x"] == 0, "e_truncado"].iloc[0]),
            "e0_tabua_antiga": E0_ANTIGO[lingua],
            "chega_a_1_ano_pct": 100 * float(s.loc[1]),
            "chega_a_3_anos_pct": 100 * float(s.loc[3]),
            "chega_a_5_anos_pct": 100 * float(s.loc[5]),
            "q0_pct": 100 * float(tab["q"].iloc[0]),
            "primeiro_ano_com_q_estavel": estavel,
        }
    )
    tabuas.append(tab.assign(linguagem=lingua))
    print(f"{lingua}: pronto", flush=True)
tabua = pd.concat(tabuas, ignore_index=True)
tabua.to_csv(SAIDA / "tabua_por_idade.csv", index=False, float_format="%.10g")
resumo = pd.DataFrame(resumo).set_index("linguagem")
resumo.to_csv(SAIDA / "tabua_resumo.csv", float_format="%.10g")

# Confere contra a tábua da rodada (a mesma conta)
if RODADA_TABUA is not None:
    da_rodada = pd.read_csv(RODADA_TABUA)
    for lingua in LINGUAS:
        a = tabua[
            (tabua["linguagem"] == lingua) & (tabua["x"] <= da_rodada["x"].max())
        ].reset_index(drop=True)
        b = da_rodada[da_rodada["linguagem"] == lingua].reset_index(drop=True)
        assert len(a) == len(b), f"{lingua}: {len(a)} linhas contra {len(b)} da rodada"
        for coluna in ["l", "d", "censurados", "q", "S", "e"]:
            assert np.allclose(a[coluna], b[coluna], rtol=1e-9, atol=1e-12), (
                f"{lingua}: a coluna {coluna} difere da rodada"
            )

# Kaplan-Meier e log-rank de Clojure contra cada linguagem
curvas = []
for lingua in LINGUAS:
    curvas.append(vitalidade.kaplan_meier(duracoes[lingua]).assign(linguagem=lingua))
pd.concat(curvas, ignore_index=True).to_csv(
    SAIDA / "kaplan_meier_por_idade.csv", index=False, float_format="%.10g"
)
testes = []
for lingua in LINGUAS[1:]:
    estatistica, p = vitalidade.logrank(duracoes["clojure"], duracoes[lingua])
    testes.append(
        {
            "comparacao": f"Clojure contra {NOMES[lingua]}",
            "estatistica": estatistica,
            "p": p,
            "abaixo_de_bonferroni": p < BONFERRONI,
        }
    )
logrank = pd.DataFrame(testes)
logrank.to_csv(SAIDA / "logrank_por_idade.csv", index=False)


def dec(x: float, casas: int = 1) -> str:
    return "n/d" if pd.isna(x) else f"{x:.{casas}f}".replace(".", ",")


def milhar(x: float) -> str:
    return f"{x:,.0f}".replace(",", ".")


T = [
    "# Tábua de vida e Kaplan-Meier por idade da pirâmide (definição única, v3b)",
    "",
    "A idade é a da pirâmide (os anos de pausa não somam). Quem volta continua com a idade que tinha. A vida termina só na saída definitiva; quem ainda pode voltar, ou tem o último evento depois de 2024, entra censurado. Coortes de 2008 a 2024. e0 é um piso porque a cauda censurada não entra na tábua.",
    "",
    "| | " + " | ".join(NOMES[x] for x in LINGUAS) + " |",
    "|---|" + "---|" * len(LINGUAS),
    "| Pessoas | " + " | ".join(milhar(resumo.loc[x, "pessoas"]) for x in LINGUAS) + " |",
    "| Saídas definitivas | " + " | ".join(milhar(resumo.loc[x, "saidas"]) for x in LINGUAS) + " |",
    "| Censuradas | " + " | ".join(milhar(resumo.loc[x, "censuradas"]) for x in LINGUAS) + " |",
    "| q(0) (%) | " + " | ".join(dec(resumo.loc[x, "q0_pct"]) for x in LINGUAS) + " |",
    "| e0 (anos, piso) | " + " | ".join(dec(resumo.loc[x, "e0"], 2) for x in LINGUAS) + " |",
    "| e0 da tábua antiga (anos) | "
    + " | ".join(dec(resumo.loc[x, "e0_tabua_antiga"], 2) for x in LINGUAS)
    + " |",
    "| Chegam a 1 ano (%) | "
    + " | ".join(dec(resumo.loc[x, "chega_a_1_ano_pct"]) for x in LINGUAS)
    + " |",
    "| Chegam a 3 anos (%) | "
    + " | ".join(dec(resumo.loc[x, "chega_a_3_anos_pct"]) for x in LINGUAS)
    + " |",
    "| Chegam a 5 anos (%) | "
    + " | ".join(dec(resumo.loc[x, "chega_a_5_anos_pct"]) for x in LINGUAS)
    + " |",
    "| Primeiro ano com q(x) estável | "
    + " | ".join(dec(resumo.loc[x, "primeiro_ano_com_q_estavel"], 0) for x in LINGUAS)
    + " |",
    "",
    "Critério de estabilidade: o primeiro x0 tal que, para todo x a partir de x0 com pelo menos 30 pessoas efetivamente observadas (`n_efetivo`), q(x) fica a até 5 pontos percentuais de q̄, que é a soma das saídas dividida pela soma da exposição de x0 em diante.",
    "",
    "## q(x) por linguagem (%)",
    "",
    "| x | " + " | ".join(NOMES[x] for x in LINGUAS) + " |",
    "|---|" + "---|" * len(LINGUAS),
]
for x in range(0, 13):
    celulas = []
    for lingua in LINGUAS:
        t = tabua[(tabua["linguagem"] == lingua) & (tabua["x"] == x)]
        celulas.append(
            dec(100 * float(t["q"].iloc[0]))
            + (f" (n {milhar(t['n_efetivo'].iloc[0])})" if len(t) else "")
            if len(t)
            else "n/d"
        )
    T.append(f"| {x} | " + " | ".join(celulas) + " |")
T += [
    "",
    "## Log-rank de Clojure contra cada linguagem",
    "",
    f"Limite de Bonferroni: 0,05 dividido por 4 comparações, {dec(BONFERRONI, 4)}. Kaplan-Meier sobre a duração pela idade da pirâmide, com censura.",
    "",
    "| Comparação | Estatística | p | p abaixo do limite |",
    "|---|---|---|---|",
]
for _, x in logrank.iterrows():
    p_texto = (
        "abaixo de 1e-300 (o p da conta sai zero)"
        if x["p"] == 0
        else f"{x['p']:.2e}".replace(".", ",")
    )
    T.append(
        f"| {x['comparacao']} | {dec(x['estatistica'], 2)} | {p_texto} | {'sim' if x['abaixo_de_bonferroni'] else 'não'} |"
    )
T.append("")
(SAIDA / "rq13_tabua_e_km.md").write_text("\n".join(T) + "\n", encoding="utf-8")
print("\n".join(T))
