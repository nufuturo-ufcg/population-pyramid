"""Três verificações da RQ3 em `projecao-rq3/investigacao/`, a partir de dados já salvos (nenhuma previsão nova).

1. Viés da previsão de parada no S2: `*_S2_calibracao.csv` e as previsões da coorte em `projecao-rq3/unidades/`.
2. Repositórios por ano e P1: `repos_por_ano.csv` (gerado na VM por `repos_por_ano.py`).
3. Erro com sinal por método no S2.

Uso (na raiz do repo): .venv/bin/python scripts/granularidade/investigacao_rq3.py <investigacao> <projecao-rq3>
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from util_resumo import num

SAIDA = Path(sys.argv[1])
RQ3 = Path(sys.argv[2])
UNIDADES = RQ3 / "unidades"
LINGUAS = ["clojure", "elixir", "ocaml", "python"]
NOMES = {"clojure": "Clojure", "elixir": "Elixir", "ocaml": "OCaml", "python": "Python"}
COMMITS = (SAIDA / "commit.txt").read_text(encoding="utf-8").strip().splitlines()
# os seis métodos que definem as origens da Parte 2 (mesma regra de testes_s2.py e da cobertura)
PARTE2 = ["ingenua", "coorte_R0", "coorte_R3", "C3_R3", "conservador_R3", "conservador_R0"]
METODOS = [
    ("ingenua", "Ingênua"),
    ("coorte_R0", "Coorte"),
    ("coorte_R3", "Coorte^R (R3)"),
    ("conservador_R3", "Conservador^R (R3)"),
    ("C3_R3", "Ingênua-Coorte^R (R3)"),
]


def carrega(lingua: str) -> pd.DataFrame:
    partes = [pd.read_csv(UNIDADES / f"{lingua}_S2_pares.csv.gz")]
    for r in (1, 2, 3):
        partes.append(pd.read_csv(UNIDADES / f"{lingua}_S2_R{r}_pares.csv.gz"))
    return pd.concat(partes, ignore_index=True)


def pct(x: float, casas: int = 1) -> str:
    return "n/d" if pd.isna(x) else f"{100 * x:+.{casas}f}%".replace(".", ",")


def pp(x: float) -> str:
    """Diferença de duas frações, em pontos percentuais."""
    return "n/d" if pd.isna(x) else f"{100 * x:+.2f}".replace(".", ",")


def frac(x: float) -> str:
    return "n/d" if pd.isna(x) else f"{100 * x:.2f}%".replace(".", ",")


T1 = []  # tabelas do item 1
T2 = []  # tabelas do item 2
T3 = []  # tabelas do item 3
origens_usadas = {}
for lingua in LINGUAS:
    t = carrega(lingua)
    previsto = t.pivot(index="k", columns="metodo", values="previsto")
    abre = t.pivot(index="k", columns="metodo", values="abre")
    base = t[t["metodo"] == "ingenua"].set_index("k")
    real, origem = base["real"], base["origem"]
    ks = list(abre.index[abre[PARTE2].notna().all(axis=1)])
    origens_usadas[lingua] = f"{origem[ks[0]]} a {origem[ks[-1]]} ({len(ks)})"

    # ---- item 1: parada prevista e observada, erro com sinal da coorte e crescimento do real
    cal = pd.read_csv(UNIDADES / f"{lingua}_S2_calibracao.csv").set_index("k")
    linhas = []
    for k in ks:
        r = real[k]
        prevista, observada = (
            cal.loc[k, "saida_por_parada_prevista"],
            cal.loc[k, "saida_por_parada_observada"],
        )
        linhas.append(
            {
                "k": k,
                "origem": origem[k],
                "prevista": prevista,
                "observada": observada,
                "diferenca": prevista - observada,
                "erro_coorte": (previsto.loc[k, "coorte_R0"] - r) / r,
                "erro_coorte_R": (previsto.loc[k, "coorte_R3"] - r) / r,
                "erro_coorte_R2": (previsto.loc[k, "coorte_R2"] - r) / r,
                "variacao_real": (r - previsto.loc[k, "ingenua"]) / previsto.loc[k, "ingenua"],
                "abre_coorte": abre.loc[k, "coorte_R0"],
                "abre_coorte_R": abre.loc[k, "coorte_R3"],
            }
        )
    d = pd.DataFrame(linhas)
    d["grupo"] = np.where(d["variacao_real"] > 0, "crescimento", "queda")
    T1 += [
        f"## {NOMES[lingua]}",
        "",
        f"Origens: {origens_usadas[lingua]}.",
        "",
        "### Parada e erro com sinal por origem",
        "",
    ]
    T1 += ["| Origem | Parada prevista | Parada observada | Diferença (pontos percentuais) | Sinal | Erro Coorte | Erro Coorte^R | Erro Coorte só R2 | Real contra a origem |", "|---|---|---|---|---|---|---|---|---|"]  # fmt: skip
    for _, x in d.iterrows():
        sinal = "prevista maior" if x["diferenca"] > 0 else "prevista menor"
        crescimento = "cresceu" if x["variacao_real"] > 0 else "caiu"
        T1.append(
            f"| {x['origem']} | {frac(x['prevista'])} | {frac(x['observada'])} | {pp(x['diferenca'])} | {sinal} | {pct(x['erro_coorte'])} | {pct(x['erro_coorte_R'])} | {pct(x['erro_coorte_R2'])} | {crescimento} ({pct(x['variacao_real'])}) |"
        )
    T1 += [
        "",
        "Erro com sinal = (previsto menos real) dividido pelo real. Positivo é previsão acima do real.",
        "",
    ]
    T1 += ["### Anos de crescimento e de queda", "", "| Grupo | Anos | ABRE médio Coorte | ABRE médio Coorte^R | Diferença média da parada (pontos percentuais) | Erro médio Coorte | Erro médio Coorte^R |", "|---|---|---|---|---|---|---|"]  # fmt: skip
    for grupo in ["crescimento", "queda"]:
        g = d[d["grupo"] == grupo]
        if len(g) == 0:
            T1.append(f"| {grupo.capitalize()} | 0 | n/d | n/d | n/d | n/d | n/d |")
            continue
        T1.append(
            f"| {grupo.capitalize()} | {len(g)} | {num(g['abre_coorte'].mean(), 4)} | {num(g['abre_coorte_R'].mean(), 4)} | {pp(g['diferenca'].mean())} | {pct(g['erro_coorte'].mean())} | {pct(g['erro_coorte_R'].mean())} |"
        )
    T1.append("")

    # ---- item 3: erro com sinal por método
    T3 += [f"## {NOMES[lingua]}", "", f"Origens: {origens_usadas[lingua]}.", "", "| Método | Anos acima do real | Anos abaixo do real | Erro médio com sinal |", "|---|---|---|---|"]  # fmt: skip
    for nome, rotulo in METODOS:
        erros = []
        for k in ks:
            erros.append((previsto.loc[k, nome] - real[k]) / real[k])
        erros = np.array(erros)
        T3.append(
            f"| {rotulo} | {int((erros > 0).sum())} | {int((erros < 0).sum())} | {pct(erros.mean())} |"
        )
    T3.append("")

# ---- item 2: repositórios por ano
rep = pd.read_csv(SAIDA / "repos_por_ano.csv")
for lingua in LINGUAS:
    r = rep[rep["linguagem"] == lingua].set_index("ano")
    total = int(r["repos_total_na_carga"].iloc[0])
    T2 += [
        f"## {NOMES[lingua]}",
        "",
        f"Repositórios na carga: {total}.",
        "",
        "### Por ano, de 2008 a 2024",
        "",
    ]
    T2 += ["| Ano | Repositórios com evento | Primeiro evento no ano | Com evento de residente | Primeiro evento de residente | P1 em 31 de dezembro |", "|---|---|---|---|---|---|"]  # fmt: skip
    for ano in range(2008, 2025):
        x = r.loc[ano]
        T2.append(
            f"| {ano} | {int(x['repos_com_evento'])} | {int(x['repos_primeiro_evento'])} | {int(x['repos_com_evento_residente'])} | {int(x['repos_primeiro_evento_residente'])} | {int(x['p1_dezembro'])} |"
        )
    T2 += ["", "### Repositórios pelo ano do último evento (todos os eventos da carga, até o fim da coleta)", "", "| Ano do último evento | Repositórios | Acumulado | Fração do total |", "|---|---|---|---|"]  # fmt: skip
    acumulado = 0
    for ano in range(2008, 2027):
        n = int(r.loc[ano, "repos_ultimo_evento"])
        acumulado += n
        T2.append(f"| {ano} | {n} | {acumulado} | {frac(acumulado / total)} |")
    T2.append("")

(SAIDA / "tabelas.md").write_text(
    "\n".join(
        [
            "# Tabelas das três verificações da RQ3",
            "",
            *[f"Código: commit `{c}`." for c in COMMITS],
            "",
            "# 1. Viés da previsão de parada (S2)",
            "",
            *T1,
            "# 2. Repositórios por ano e população P1",
            "",
            *T2,
            "# 3. Erro com sinal por método (S2)",
            "",
            "Erro com sinal = (previsto menos real) dividido pelo real. Acima: previsto maior que o real.",
            "",
            *T3,
        ]
    )
    + "\n",
    encoding="utf-8",
)
print("tabelas.md gravado")
