"""Seção de Dados com a carga `-v3` e a diferença entre a RQ1 e a RQ3 (`rq2-v3/`, itens 6 e 7). Não interpreta nenhum número.

6. Tabela de amostra do artigo (repositórios com 10 ou mais estrelas, com mais de 50% da linguagem, finais e contribuidores) e o
   percentual de casuais que nunca fizeram commit nem PR, nas cinco linguagens. Mostra o corte de `carga_fonte.py` e quantos
   candidatos têm exatamente 50%.
7. Ativos de 2024 da RQ1 (residente pela vida inteira) contra os da RQ3 (P1: residente só pelo passado, com a segunda ocasião até
   31/12/2024), por linguagem.

Uso (na raiz do repo): .venv/bin/python scripts/granularidade/dados_v3.py <correcao-elegibilidade/dados> <origens com v3_<l>/> <figuras-v3/dados> <saida>
"""

import json
import sys
from pathlib import Path

import pandas as pd

DADOS, ORIGENS, FIG_DADOS, SAIDA = (
    Path(sys.argv[1]),
    Path(sys.argv[2]),
    Path(sys.argv[3]),
    Path(sys.argv[4]),
)
SAIDA.mkdir(parents=True, exist_ok=True)
LINGUAS = ["clojure", "elixir", "zig", "python", "ocaml"]  # a ordem da tabela do artigo
NOMES = {
    "clojure": "Clojure",
    "elixir": "Elixir",
    "zig": "Zig",
    "python": "Python",
    "ocaml": "OCaml",
}
ARTIGO = {  # Tabela de amostra do artigo: 10 estrelas, 50% ou mais, finais, contribuidores
    "clojure": (7476, 7363, 7340, 42760),
    "elixir": (6440, 6284, 6265, 45973),
    "zig": (2177, 2092, 2085, 15132),
    "python": (422720, 309920, 307766, 3732588),
    "ocaml": (3567, 3426, 3372, 21240),
}
ATE = 2024
FIM_2024 = pd.Timestamp("2024-12-31 23:59:59")


def milhar(x: float) -> str:
    return f"{x:,.0f}".replace(",", ".")


def dec(x: float) -> str:
    return f"{x:.1f}".replace(".", ",")


candidatos = pd.read_csv(DADOS / "candidatos_compacto.csv", dtype={"repo_id": str})
estatisticas = {
    x: json.loads((DADOS / "carga-v3" / "nova" / f"{x}.json").read_text(encoding="utf-8"))
    for x in LINGUAS
}
pessoas = {x: pd.read_parquet(ORIGENS / f"v3_{x}" / "pessoas.parquet") for x in LINGUAS}

linhas = []
for lingua in LINGUAS:
    e = estatisticas[lingua]
    p = pessoas[lingua]
    chegaram = p[p["primeiro"].dt.year <= ATE]
    casuais = chegaram[chegaram["ocasioes"] == 1]
    exatos = int((candidatos[(candidatos["linguagem"] == lingua)]["fracao_seart"] == 0.5).sum())
    linhas.append(
        {
            "linguagem": lingua,
            "repos_10_estrelas": e["repos_total"],
            "repos_mais_de_50_pct": e["repos_elegiveis"],
            "repos_finais": e["repos_finais"],
            "contribuidores": e["contribuidores_finais"],
            "exatamente_50_pct_na_seart": exatos,
            "chegaram_ate_2024": len(chegaram),
            "casuais_pct": 100 * len(casuais) / len(chegaram),
            "casuais_sem_commit_nem_pr_pct": 100 * (~casuais["codou"]).mean(),
        }
    )
tabela = pd.DataFrame(linhas).set_index("linguagem")
tabela.to_csv(SAIDA / "dados_v3.csv")

T = [
    "# Seção de Dados com a carga -v3",
    "",
    "## Tabela de amostra",
    "",
    "Cada célula mostra `artigo → v3` quando muda. Repositórios finais são os que têm ao menos um evento válido depois da remoção de bots, de eventos duplicados e de eventos sem data ou sem contribuidor identificável, com cada grupo de repositórios duplicados contado como um. Contribuidores são as pessoas distintas da carga (casuais inclusive).",
    "",
    "| Etapa | " + " | ".join(NOMES[x] for x in LINGUAS) + " |",
    "|---|" + "---|" * len(LINGUAS),
]
for i, (rotulo, chave) in enumerate(
    [
        ("Repo. com 10 ou mais estrelas", "repos_10_estrelas"),
        ("Repo. com mais de 50% da linguagem", "repos_mais_de_50_pct"),
        ("Repo. finais", "repos_finais"),
        ("Contribuidores", "contribuidores"),
    ]
):
    celulas = []
    for lingua in LINGUAS:
        antigo, novo = ARTIGO[lingua][i], int(tabela.loc[lingua, chave])
        celulas.append(milhar(novo) if antigo == novo else f"{milhar(antigo)} → {milhar(novo)}")
    T.append(f"| {rotulo} | " + " | ".join(celulas) + " |")
T += [
    "",
    "## Corte de elegibilidade",
    "",
    '- `carga_fonte.py` usa mais de 50% (`>`): `elegivel = fracao > fb.LIMIAR_SHARE_LINGUAGEM`, com o limiar em 0,5. O texto do artigo diz "pelo menos 50%" (`>=`).',
    "- Candidatos com exatamente 50% na SEART: "
    + ", ".join(f"{NOMES[x]} {int(tabela.loc[x, 'exatamente_50_pct_na_seart'])}" for x in LINGUAS)
    + ". Com `>=` Python ganharia esses repositórios. Nenhum candidato com resposta da API tem exatamente 50%.",
    "",
    "## Casuais",
    "",
    "Casual é quem teve uma ocasião só. Entre as pessoas que chegaram até 2024:",
    "",
    "| | " + " | ".join(NOMES[x] for x in LINGUAS) + " |",
    "|---|" + "---|" * len(LINGUAS),
    "| Pessoas que chegaram até 2024 | "
    + " | ".join(milhar(tabela.loc[x, "chegaram_ate_2024"]) for x in LINGUAS)
    + " |",
    "| Casuais (%) | " + " | ".join(dec(tabela.loc[x, "casuais_pct"]) for x in LINGUAS) + " |",
    "| Casuais que nunca fizeram commit nem PR (%) | "
    + " | ".join(dec(tabela.loc[x, "casuais_sem_commit_nem_pr_pct"]) for x in LINGUAS)
    + " |",
    "",
    "O artigo traz 45,6% e 86,4% para Clojure.",
    "",
]
(SAIDA / "dados_v3.md").write_text("\n".join(T) + "\n", encoding="utf-8")

# Item 7: ativos de 2024 na RQ1 e na RQ3
rq3 = pd.read_csv(FIG_DADOS / "fig2_totais.csv").set_index("linguagem")["real_2024"]
saida7 = []
for lingua in LINGUAS:
    p = pessoas[lingua]
    anos = pd.read_parquet(
        ORIGENS / f"v3_{lingua}" / "pessoas_repos_por_ano.parquet", columns=["pessoa", "ano"]
    )
    ativos_2024 = set(anos.loc[anos["ano"] == ATE, "pessoa"])
    q = p[p["pessoa"].isin(ativos_2024)]
    rq1 = q[q["ocasioes"] > 1]
    p1 = rq1[rq1["segunda_ocasiao"] <= FIM_2024]
    depois = rq1[rq1["segunda_ocasiao"] > FIM_2024]
    saida7.append(
        {
            "linguagem": lingua,
            "ativos_2024_todas_as_pessoas": len(q),
            "rq1_mais_de_uma_ocasiao_na_vida": len(rq1),
            "rq3_segunda_ocasiao_ate_31_12_2024": len(p1),
            "rq3_publicado": float(rq3[lingua]) if lingua in rq3.index else float("nan"),
            "segunda_ocasiao_em_2025": int((depois["segunda_ocasiao"].dt.year == 2025).sum()),
            "segunda_ocasiao_em_2026": int((depois["segunda_ocasiao"].dt.year == 2026).sum()),
        }
    )
t7 = pd.DataFrame(saida7).set_index("linguagem")
t7.to_csv(SAIDA / "rq1_contra_rq3.csv")
T7 = [
    "# RQ1 contra RQ3: ativos de 2024",
    "",
    "RQ1: pessoas com evento em 2024 e mais de uma ocasião na vida toda (os eventos vão até o fim da coleta). RQ3 (P1): pessoas com evento em 2024 cuja segunda ocasião começou até 31/12/2024, isto é, residentes só pelo passado da origem.",
    "",
    "| | " + " | ".join(NOMES[x] for x in LINGUAS) + " |",
    "|---|" + "---|" * len(LINGUAS),
    "| Ativos de 2024, todas as pessoas | "
    + " | ".join(milhar(t7.loc[x, "ativos_2024_todas_as_pessoas"]) for x in LINGUAS)
    + " |",
    "| RQ1: mais de uma ocasião na vida | "
    + " | ".join(milhar(t7.loc[x, "rq1_mais_de_uma_ocasiao_na_vida"]) for x in LINGUAS)
    + " |",
    "| RQ3: segunda ocasião até 31/12/2024 (recalculado) | "
    + " | ".join(milhar(t7.loc[x, "rq3_segunda_ocasiao_ate_31_12_2024"]) for x in LINGUAS)
    + " |",
    "| RQ3: população real de 2024 (`fig2_totais.csv`) | "
    + " | ".join(
        "n/a" if pd.isna(t7.loc[x, "rq3_publicado"]) else milhar(t7.loc[x, "rq3_publicado"])
        for x in LINGUAS
    )
    + " |",
    "| Segunda ocasião em 2025 | "
    + " | ".join(milhar(t7.loc[x, "segunda_ocasiao_em_2025"]) for x in LINGUAS)
    + " |",
    "| Segunda ocasião em 2026 | "
    + " | ".join(milhar(t7.loc[x, "segunda_ocasiao_em_2026"]) for x in LINGUAS)
    + " |",
    "",
]
(SAIDA / "rq1_contra_rq3.md").write_text("\n".join(T7) + "\n", encoding="utf-8")
print("\n".join(T))
print("\n".join(T7))
