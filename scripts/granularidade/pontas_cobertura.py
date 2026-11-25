"""Cobertura (RQ3.3) do pessimista e do otimista pelo pior e pelo melhor ano de 4 trimestres (`S4p`), com a regra antiga ao lado, e a conferência do Conservador. Sem projeção nova.

Lê `<S4p>/<l>_S4p_*` (previsões de todos os métodos, antigos e novos) e `<S4m>/<l>_S4m_*` (o cenário sem as pontas novas, para conferir que nada antigo mudou).
Origens: a sequência contínua de cada linguagem (a primeira origem a partir da qual os cinco métodos projetam em todos as seguintes, até 31/12/2023). Recortes: todas as trimestrais e só as de 31 de dezembro.
Cobertura: previsões com o real entre o pessimista e o otimista (limites incluídos). Largura relativa mediana: (otimista − pessimista) / real.
Regra antiga: `pessimista_R0`/`otimista_R0` (sem repositórios) e `pessimista_nova_R3`/`otimista_nova_R3` (com repositórios): o pior ou o melhor trimestre de cada faixa repetido nos 4 passos.
Regra nova: `pessimista_ano_V0`/`otimista_ano_V0` e `pessimista_ano_R3`/`otimista_ano_R3`: o pior ou o melhor ano de 4 trimestres, na ordem.
Conferência: o Conservador (`conservador_R0`) fica entre as pontas sem repositórios e o Conservador^R (`conservador_R3`) entre as com repositórios; exceções listadas.

Uso (na raiz do repo): uv run --no-project --with pandas --with numpy python scripts/granularidade/pontas_cobertura.py <S4p unidades> <S4m unidades> <saida>
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

S4P, S4M, SAIDA = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
SAIDA.mkdir(parents=True, exist_ok=True)
LINGUAS = ["clojure", "elixir", "ocaml", "python"]
NOMES = {"clojure": "Clojure", "elixir": "Elixir", "ocaml": "OCaml", "python": "Python"}
CINCO = ["ingenua", "coorte_R0", "coorte_R3", "conservador_R3", "C3_R3"]
PONTAS = {
    ("sem repositórios", "antiga"): ("pessimista_R0", "otimista_R0", "conservador_R0"),
    ("sem repositórios", "nova"): ("pessimista_ano_V0", "otimista_ano_V0", "conservador_R0"),
    ("com repositórios", "antiga"): ("pessimista_nova_R3", "otimista_nova_R3", "conservador_R3"),
    ("com repositórios", "nova"): ("pessimista_ano_R3", "otimista_ano_R3", "conservador_R3"),
}
ULTIMA = pd.Timestamp("2023-12-31")


def dec(x: float, casas: int = 3) -> str:
    return "n/d" if pd.isna(x) else f"{x:.{casas}f}".replace(".", ",")


def le(pasta: Path, codigo: str, lingua: str) -> pd.DataFrame:
    partes = []
    for sufixo in ("", "_R1", "_R2", "_R3"):
        caminho = pasta / f"{lingua}_{codigo}{sufixo}_pares.csv.gz"
        if not caminho.exists():
            sys.exit(f"falta o arquivo {caminho}")
        partes.append(pd.read_csv(caminho))
    t = pd.concat(partes, ignore_index=True).drop_duplicates(["k", "metodo"])
    t["origem"] = pd.to_datetime(t["origem"])
    return t


def sequencia(t: pd.DataFrame) -> list[int]:
    abre = t[t["metodo"].isin(CINCO)].pivot(index="k", columns="metodo", values="abre")[CINCO]
    origem = t.drop_duplicates("k").set_index("k")["origem"]
    ks = [k for k in abre.index if origem.loc[k] <= ULTIMA]
    ok = abre.notna().all(axis=1)
    ultimo_indefinido = max([k for k in ks if not ok.loc[k]] or [-1])
    return [k for k in ks if k > ultimo_indefinido]


novas = {x: le(S4P, "S4p", x) for x in LINGUAS}
antigas = {x: le(S4M, "S4m", x) for x in LINGUAS}

# 1. Nada do que existia mudou
C = [
    "# Conferências",
    "",
    "| Conferência | Linguagem | Previsões comparadas | Diferentes |",
    "|---|---|---|---|",
]
for lingua in LINGUAS:
    a, b = (
        antigas[lingua].set_index(["k", "metodo"])["previsto"],
        novas[lingua].set_index(["k", "metodo"])["previsto"],
    )
    comuns = a.index.intersection(b.index)
    x, y = a.loc[comuns].to_numpy(), b.loc[comuns].to_numpy()
    ok = (np.isnan(x) & np.isnan(y)) | (np.abs(x - y) <= 1e-8 * np.maximum(1.0, np.abs(y)))
    C.append(
        f"| S4p contra S4m, todos os métodos que já existiam | {NOMES[lingua]} | {len(comuns)} | {int((~ok).sum())} |"
    )
    if not ok.all():
        (SAIDA / "conferencia.md").write_text("\n".join(C) + "\n", encoding="utf-8")
        sys.exit(
            f"{lingua}: o S4p mudou {int((~ok).sum())} previsões que já existiam no S4m; parei"
        )

# 2. Origens por recorte
origens = {x: sequencia(novas[x]) for x in LINGUAS}
quando = {x: novas[x].drop_duplicates("k").set_index("k")["origem"] for x in LINGUAS}
RECORTES = {"todas as trimestrais": lambda _: True, "só 31 de dezembro": lambda d: d.month == 12}
ORIGENS_MD = [
    "# Origens",
    "",
    "| Linguagem | Trimestrais | Primeira | Última | 31 de dezembro |",
    "|---|---|---|---|---|",
]
for lingua in LINGUAS:
    ks = origens[lingua]
    ORIGENS_MD.append(
        f"| {NOMES[lingua]} | {len(ks)} | {quando[lingua].loc[ks].min().date()} | {quando[lingua].loc[ks].max().date()} | {sum(quando[lingua].loc[k].month == 12 for k in ks)} |"
    )
ORIGENS_MD.append("")
(SAIDA / "origens.md").write_text("\n".join(ORIGENS_MD) + "\n", encoding="utf-8")

# 3. Cobertura, largura, ordem das pontas e conferência do Conservador
linhas, excecoes, ordem_ruim = [], [], []
for lingua in LINGUAS:
    t = novas[lingua]
    p = t.pivot(index="k", columns="metodo", values="previsto")
    real = t.drop_duplicates("k").set_index("k")["real"]
    for recorte, filtro in RECORTES.items():
        ks = [k for k in origens[lingua] if filtro(quando[lingua].loc[k])]
        for (repos, regra), (pess, otim, conservador) in PONTAS.items():
            sub = pd.DataFrame(
                {
                    "pess": p.loc[ks, pess],
                    "otim": p.loc[ks, otim],
                    "cons": p.loc[ks, conservador],
                    "real": real.loc[ks],
                }
            )
            indefinidos = int(sub[["pess", "otim"]].isna().any(axis=1).sum())
            valido = sub.dropna(subset=["pess", "otim"])
            dentro = (valido["pess"] <= valido["real"]) & (valido["real"] <= valido["otim"])
            largura = (valido["otim"] - valido["pess"]) / valido["real"]
            entre = (valido["pess"] <= valido["cons"]) & (valido["cons"] <= valido["otim"])
            linhas.append(
                {
                    "linguagem": lingua,
                    "recorte": recorte,
                    "repositorios": repos,
                    "regra": regra,
                    "previsoes": len(ks),
                    "indefinidas": indefinidos,
                    "real_dentro": int(dentro.sum()),
                    "largura_relativa_mediana": float(largura.median()),
                    "conservador_entre": int(entre.sum()),
                    "otimista_abaixo_do_pessimista": int((valido["otim"] < valido["pess"]).sum()),
                }
            )
            if recorte == "todas as trimestrais":
                for k in valido.index[~entre]:
                    x = valido.loc[k]
                    excecoes.append(
                        {
                            "linguagem": lingua,
                            "origem": quando[lingua].loc[k].date().isoformat(),
                            "repositorios": repos,
                            "regra": regra,
                            "conservador": x["cons"],
                            "pessimista": x["pess"],
                            "otimista": x["otim"],
                            "real": x["real"],
                        }
                    )
                for k in valido.index[valido["otim"] < valido["pess"]]:
                    ordem_ruim.append(
                        (lingua, quando[lingua].loc[k].date().isoformat(), repos, regra)
                    )
cob = pd.DataFrame(linhas)
cob.to_csv(SAIDA / "cobertura.csv", index=False, float_format="%.10g")
exc = pd.DataFrame(excecoes)
exc.to_csv(SAIDA / "excecoes_do_conservador.csv", index=False, float_format="%.10g")

T = [
    "# Cobertura do pessimista e do otimista (RQ3.3), cenário Longo, não casuais, janela de 4 trimestres",
    "",
    "Previsões de 12 meses. Cobertura: previsões com o real entre o pessimista e o otimista (limites incluídos). Largura relativa mediana: (otimista − pessimista) / real. Regra antiga: o pior (melhor) trimestre de cada faixa repetido 4 vezes. Regra nova: o pior (melhor) ano de 4 trimestres, na ordem. Sem repositórios: Coorte, Conservador. Com repositórios: Coorte^R, Conservador^R.",
    "",
]
for recorte in RECORTES:
    T += [
        f"## {recorte.capitalize()}",
        "",
        "| Linguagem | Previsões | Sem repositórios, antiga: dentro | Sem, nova: dentro | Com, antiga: dentro | Com, nova: dentro | Largura sem, antiga | Largura sem, nova | Largura com, antiga | Largura com, nova |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for lingua in LINGUAS:
        c = cob[(cob["linguagem"] == lingua) & (cob["recorte"] == recorte)].set_index(
            ["repositorios", "regra"]
        )
        n = int(c["previsoes"].iloc[0])
        T.append(
            f"| {NOMES[lingua]} | {n} | "
            + " | ".join(
                f"{c.loc[(r, g), 'real_dentro']} de {n}"
                for r, g in [
                    ("sem repositórios", "antiga"),
                    ("sem repositórios", "nova"),
                    ("com repositórios", "antiga"),
                    ("com repositórios", "nova"),
                ]
            )
            + " | "
            + " | ".join(
                dec(c.loc[(r, g), "largura_relativa_mediana"])
                for r, g in [
                    ("sem repositórios", "antiga"),
                    ("sem repositórios", "nova"),
                    ("com repositórios", "antiga"),
                    ("com repositórios", "nova"),
                ]
            )
            + " |"
        )
    T.append("")
T += [
    "## Conferência: o Conservador entre o pessimista e o otimista",
    "",
    "Todas as previsões trimestrais da sequência. Sem repositórios, o Conservador (`conservador_R0`) contra as pontas sem repositórios; com repositórios, o Conservador^R (`conservador_R3`) contra as pontas com repositórios.",
    "",
    "| Linguagem | Previsões | Sem, antiga | Sem, nova | Com, antiga | Com, nova |",
    "|---|---|---|---|---|---|",
]
for lingua in LINGUAS:
    c = cob[(cob["linguagem"] == lingua) & (cob["recorte"] == "todas as trimestrais")].set_index(
        ["repositorios", "regra"]
    )
    n = int(c["previsoes"].iloc[0])
    T.append(
        f"| {NOMES[lingua]} | {n} | "
        + " | ".join(
            f"{c.loc[(r, g), 'conservador_entre']} de {n}"
            for r, g in [
                ("sem repositórios", "antiga"),
                ("sem repositórios", "nova"),
                ("com repositórios", "antiga"),
                ("com repositórios", "nova"),
            ]
        )
        + " |"
    )
T += [
    "",
    f"Previsões com o otimista abaixo do pessimista: {len(ordem_ruim)}"
    + (f" ({ordem_ruim[:10]})" if ordem_ruim else "")
    + ".",
    "",
    "### Exceções (o Conservador fora das pontas)",
    "",
]
if exc.empty:
    T.append("Nenhuma.")
else:
    T += [
        "| Linguagem | Origem | Repositórios | Regra | Conservador | Pessimista | Otimista | Real |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for _, x in exc.iterrows():
        T.append(
            f"| {NOMES[x['linguagem']]} | {x['origem']} | {x['repositorios']} | {x['regra']} | {x['conservador']:,.0f} | {x['pessimista']:,.0f} | {x['otimista']:,.0f} | {x['real']:,.0f} |".replace(
                ",", "."
            )
        )
T.append("")
(SAIDA / "cobertura.md").write_text("\n".join(T) + "\n", encoding="utf-8")
print("\n".join(ORIGENS_MD))
print("\n".join(T))
print("\n".join(C))
