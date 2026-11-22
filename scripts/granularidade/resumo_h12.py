"""Resumo dos cenários com horizonte de 12 meses (S1b e S3h) contra S1, S2 e S3 de `projecao-cenarios-ieice/`. Ver `hipoteses.md`.

Grava `pares.csv`, `testes.csv`, `decisao.csv`, `base_perdas.csv`, `tabelas.md`, `resumo.md` e `vazamento.md`. Principal: origens de dezembro (alvos que não se sobrepõem); sensibilidade: todos os
recortes trimestrais (pares dependentes). Decisões só com Clojure, Elixir, OCaml e Python; Zig à parte.

Uso (na raiz do repo): .venv/bin/python scripts/granularidade/resumo_h12.py <saida> <pasta de projecao-cenarios-ieice>
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from previsao import todos_os_metodos
from util_resumo import NOMES, ROTULO, geometrica, holm, num, rho, teste

SAIDA, ANT = Path(sys.argv[1]), Path(sys.argv[2])
DEC = sys.argv[3:] or [
    "clojure",
    "elixir",
    "ocaml",
    "python",
]  # só as quatro linguagens decidem; o terceiro argumento em diante troca a lista (teste sintético)
NOVOS, ANTIGOS = ["S1b", "S3h"], ["S1", "S3", "S2"]
NOME = {"S1": "S1 (IEICE16, saída em 3 meses, horizonte de 3 meses)", "S1b": "S1b (IEICE16, saída em 3 meses, horizonte de 12 meses)", "S3": "S3 (saída em 12 meses, horizonte de 3 meses)",
        "S3h": "S3h (saída em 12 meses, horizonte de 12 meses)", "S2": "S2 (pirâmide da rodada oficial, P1, horizonte de 12 meses)"}  # fmt: skip
ROTULO.update(
    {
        "coorte": "coorte V0",
        "conservador": "conservador V0",
        "coorte_IEICE": "coorte do IEICE16",
        "ingenua": "ingênua",
        "coorte_amortecida": "coorte amortecida",
        "holt_amortecido": "Holt amortecido",
    }
)
BASES_R = [
    "coorte",
    "coorte_IEICE",
    "conservador",
    "coorte_amortecida",
    "C3",
    "C4",
]  # coorte e conservador são a V0 em R0
COMMIT = (
    (SAIDA / "commit.txt").read_text(encoding="utf-8").strip()
    if (SAIDA / "commit.txt").exists()
    else "não registrado"
)


def pontuais(c: str) -> list[str]:
    nomes = [
        m
        for m in todos_os_metodos()
        if not (m.startswith("pessimista_") or m.startswith("otimista_"))
    ]
    return nomes + (["coorte_IEICE"] if c != "S2" else [])


def le(pasta: Path, padrao: str) -> pd.DataFrame:
    arquivos = sorted((pasta / "unidades").glob(padrao))
    return (
        pd.concat([pd.read_csv(f) for f in arquivos], ignore_index=True)
        if arquivos
        else pd.DataFrame()
    )


pares = {c: le(SAIDA, f"*_{c}_pares.csv.gz") for c in NOVOS} | {
    c: le(ANT, f"*_{c}_pares.csv.gz") for c in ANTIGOS
}
pares_r = {
    c: pd.concat([le(SAIDA, f"*_{c}_R{r}_pares.csv.gz") for r in (1, 2, 3)], ignore_index=True)
    for c in NOVOS
}
marcas = {c: le(SAIDA, f"*_{c}_marcas.csv") for c in NOVOS}
vaza = le(SAIDA, "*_vazamento.csv")
presentes = {x for c in NOVOS if len(pares[c]) for x in set(pares[c]["linguagem"])}
TODAS = [*[x for x in NOMES if x in presentes], *sorted(presentes - set(NOMES))]
L = [
    "# Tabelas",
    "",
    "ABRE médio e, entre parênteses, mediano. Principal: origens de dezembro. Sensibilidade: todas as origens trimestrais (pares dependentes, porque com horizonte de 12 meses os alvos de recortes seguidos se sobrepõem). Em negrito o menor ABRE médio de cada linguagem (pessimista e otimista não entram no ranking). Clojure, Elixir, OCaml e Python; Zig à parte.",
    "",
]


def tabela(cab: list[str], linhas: list[list[str]]) -> None:
    L.append("| " + " | ".join(cab) + " |")
    L.append("|" + "|".join(["---"] + ["---:"] * (len(cab) - 1)) + "|")
    for linha in linhas:
        L.append("| " + " | ".join(linha) + " |")
    L.append("")


# ---------------------------------------------------------------- base e medidas
medio, mediano, n_base, ks_base = {}, {}, {}, {}
for c, df in pares.items():
    if not len(df):
        continue
    for conjunto in ["dez", "tri"]:
        sub = df if conjunto == "tri" else df[df["origem"].str.endswith("-12-31")]
        for x, g in sub.groupby("linguagem"):
            ms = pontuais(c)
            largo = g.pivot(index="k", columns="metodo", values="abre").reindex(
                columns=[
                    *ms,
                    *[
                        m
                        for m in g["metodo"].unique()
                        if m.startswith(("pessimista_", "otimista_"))
                    ],
                ]
            )
            ok = largo[ms].notna().all(axis=1)
            ks_base[(c, conjunto, x)] = largo.index[ok]
            n_base[(c, conjunto, x)] = int(ok.sum())
            for m in largo.columns:
                v = largo.loc[ok, m]
                medio[(c, conjunto, x, m)] = float(v.mean()) if len(v) else np.nan
                mediano[(c, conjunto, x, m)] = float(v.median()) if len(v) else np.nan
pd.concat([df.assign(cenario=c) for c, df in pares.items() if len(df)], ignore_index=True).to_csv(
    SAIDA / "pares.csv", index=False, float_format="%.10g"
)


def rotulo(m: str) -> str:
    return ROTULO.get(m, m.replace("_", " "))


melhor = {}
for conjunto, nome_conjunto in [
    ("dez", "origens de dezembro"),
    ("tri", "todas as origens trimestrais"),
]:
    L.append(f"# Resultados com {nome_conjunto}")
    L.append("")
    L.append(f"## Pares na base ({nome_conjunto})")
    L.append("")
    tabela(
        ["Cenário", *[NOMES[x] for x in TODAS]],
        [
            [NOME[c], *[str(n_base.get((c, conjunto, x), "n/d")) for x in TODAS]]
            for c in [*NOVOS, *ANTIGOS]
            if (c, conjunto, TODAS[0]) in n_base
        ],
    )
    for c in NOVOS:
        cols = [x for x in DEC if n_base.get((c, conjunto, x), 0) > 0]
        L.append(f"## {NOME[c]}, {nome_conjunto}")
        L.append("")
        if not cols:
            L.append("Nenhuma das quatro linguagens tem par na base.")
            L.append("")
            continue
        ms = pontuais(c)
        for x in cols:
            melhor[(c, conjunto, x)] = min(ms, key=lambda m: medio[(c, conjunto, x, m)])
        linhas = []
        for m in [
            *ms,
            *sorted(
                {
                    k[3]
                    for k in medio
                    if k[0] == c
                    and k[1] == conjunto
                    and k[3].startswith(("pessimista_", "otimista_"))
                }
            ),
        ]:
            linha = [rotulo(m)]
            for x in cols:
                t = f"{num(medio[(c, conjunto, x, m)])} ({num(mediano[(c, conjunto, x, m)])})"
                linha.append(f"**{t}**" if melhor[(c, conjunto, x)] == m else t)
            linhas.append(linha)
        linhas.append(["Melhor método", *[rotulo(melhor[(c, conjunto, x)]) for x in cols]])
        tabela(["Método", *[NOMES[x] for x in cols]], linhas)
        if n_base.get((c, conjunto, "zig"), 0) > 0:
            L.append(
                f"Zig, à parte ({n_base[(c, conjunto, 'zig')]} pares na base): ingênua {num(medio[(c, conjunto, 'zig', 'ingenua')])} ({num(mediano[(c, conjunto, 'zig', 'ingenua')])}), melhor método {rotulo(min(ms, key=lambda m: medio[(c, conjunto, 'zig', m)]))} {num(min(medio[(c, conjunto, 'zig', m)] for m in ms))}."
            )
        else:
            L.append(
                f"Zig, à parte: 0 pares na base ({'poucas origens de dezembro com todos os métodos definidos' if conjunto == 'dez' else 'a coorte de Zig quase nunca tem total definido'})."
            )
        L.append("")
    L.append(f"## Melhor método por cenário, {nome_conjunto}")
    L.append("")
    linhas = []
    for c in [*NOVOS, *ANTIGOS]:
        for x in DEC:
            if (c, conjunto, x, "ingenua") in medio and n_base.get((c, conjunto, x), 0) > 0:
                ms = pontuais(c)
                m = melhor.get((c, conjunto, x)) or min(
                    ms, key=lambda mm: medio[(c, conjunto, x, mm)]
                )
                linhas.append(
                    [
                        NOME[c].split(" (")[0],
                        NOMES[x],
                        rotulo(m),
                        num(medio[(c, conjunto, x, m)]),
                        num(medio[(c, conjunto, x, "ingenua")]),
                    ]
                )
    tabela(["Cenário", "Linguagem", "Melhor método", "ABRE médio", "ABRE médio da ingênua"], linhas)

# ---------------------------------------------------------------- fatorial R
L.append(
    "# Fatorial de nascimento e parada de repositórios (R0 nenhum, R1 só nascimento, R2 só parada, R3 os dois)"
)
L.append("")
fat = {}
for conjunto, nome_conjunto in [
    ("dez", "origens de dezembro"),
    ("tri", "todas as origens trimestrais"),
]:
    for c in NOVOS:
        todos = pd.concat([pares[c], pares_r[c]], ignore_index=True)
        if conjunto == "dez":
            todos = todos[todos["origem"].str.endswith("-12-31")]
        nomes_r = [f"{b}_R{r}" for b in BASES_R for r in range(4)]
        linhas = []
        for x in DEC:
            g = todos[(todos["linguagem"] == x) & todos["metodo"].isin(["ingenua", *nomes_r])]
            if not len(g):
                continue
            largo = g.pivot(index="k", columns="metodo", values="abre").reindex(
                columns=["ingenua", *nomes_r]
            )
            ok = largo.notna().all(axis=1)
            for b in BASES_R:
                for r in range(4):
                    fat[(c, conjunto, x, b, r)] = (
                        float(largo.loc[ok, f"{b}_R{r}"].mean()) if ok.any() else np.nan
                    )
                linhas.append(
                    [
                        NOMES[x],
                        rotulo(b),
                        str(int(ok.sum())),
                        *[num(fat[(c, conjunto, x, b, r)]) for r in range(4)],
                        num(float(largo.loc[ok, "ingenua"].mean())) if ok.any() else "n/d",
                    ]
                )
        L.append(f"## {NOME[c]}, {nome_conjunto}")
        L.append("")
        tabela(["Linguagem", "Método", "Pares", "R0", "R1", "R2", "R3", "Ingênua"], linhas)

# ---------------------------------------------------------------- testes
linhas_teste = []
for c in NOVOS:
    for conjunto in ["dez", "tri"]:
        for x in TODAS:
            ks = ks_base.get((c, conjunto, x), [])
            if len(ks) == 0:
                continue
            g = pares[c][(pares[c]["linguagem"] == x) & pares[c]["k"].isin(ks)]
            largo = g.pivot(index="k", columns="metodo", values="abre")
            ps, ficha = [], []
            for m in pontuais(c)[1:]:
                ps.append(teste(largo[m].to_numpy(), largo["ingenua"].to_numpy()))
                ficha.append({"cenario": c, "conjunto": "dezembro" if conjunto == "dez" else "trimestral (pares dependentes)", "linguagem": x, "metodo": m, "n_pares": len(largo), "p_minimo": 2.0 / 2 ** len(largo), "abre_medio_metodo": float(largo[m].mean()), "abre_medio_ingenua": float(largo["ingenua"].mean())})  # fmt: skip
            ps = np.array(ps)
            aj = holm(ps)
            for i, f in enumerate(ficha):
                f["p"], f["p_holm"] = ps[i], aj[i]
                linhas_teste.append(f)
testes = pd.DataFrame(linhas_teste)
testes.to_csv(SAIDA / "testes.csv", index=False, float_format="%.6g")
pd.DataFrame(
    [
        {"cenario": c, "conjunto": cj, "linguagem": x, "pares_na_base": n}
        for (c, cj, x), n in n_base.items()
    ]
).to_csv(SAIDA / "base_perdas.csv", index=False)

# ---------------------------------------------------------------- comparação dos quatro cenários (dezembro)
L.append("# Comparação de S1, S1b, S3h e S2 (origens de dezembro)")
L.append("")
razao, vence_m, vence_d = {}, {}, {}
CEN4 = ["S1", "S1b", "S3h", "S2"]
for c in [*CEN4, "S3"]:
    for m in pontuais(c)[1:]:
        cols = [x for x in DEC if n_base.get((c, "dez", x), 0) > 0]
        if not cols:
            continue
        razao[(c, m)] = (
            geometrica([medio[(c, "dez", x, m)] / medio[(c, "dez", x, "ingenua")] for x in cols]),
            geometrica(
                [mediano[(c, "dez", x, m)] / mediano[(c, "dez", x, "ingenua")] for x in cols]
            ),
        )
        vence_m[(c, m)] = [
            x for x in cols if medio[(c, "dez", x, m)] < medio[(c, "dez", x, "ingenua")]
        ]
        vence_d[(c, m)] = [
            x for x in cols if mediano[(c, "dez", x, m)] < mediano[(c, "dez", x, "ingenua")]
        ]
fixos = [
    "coorte_IEICE",
    "coorte_V0",
    "conservador_V0",
    "coorte_amortecida",
    "holt_amortecido",
    "C3",
    "C4",
]
tres = {
    c: sorted(
        [m for m in pontuais(c)[1:] if (c, m) in razao and not np.isnan(razao[(c, m)][0])],
        key=lambda m: razao[(c, m)][0],
    )[:3]
    for c in CEN4
}
linhas = []
for m in fixos:
    linha = [rotulo(m)]
    for c in CEN4:
        if (c, m) in razao:
            ncols = len([x for x in DEC if n_base.get((c, "dez", x), 0) > 0])
            linha.append(
                f"{num(razao[(c, m)][0])}; {len(vence_m[(c, m)])} de {ncols}; {len(vence_d[(c, m)])} de {ncols}"
            )
        else:
            linha.append("não se aplica")
    linhas.append(linha)
L.append(
    "Cada célula: razão geométrica do ABRE médio sobre o da ingênua; linguagens em que vence a ingênua na média; na mediana."
)
L.append("")
tabela(["Método", *CEN4], linhas)
L.append("Os três melhores de cada cenário pela razão geométrica do ABRE médio:")
L.append("")
tabela(
    ["Cenário", "Primeiro", "Segundo", "Terceiro"],
    [
        [
            c,
            *[
                f"{rotulo(m)} ({num(razao[(c, m)][0])}; {len(vence_m[(c, m)])} de 4)"
                for m in tres[c]
            ],
        ]
        for c in CEN4
        if tres.get(c)
    ],
)
(SAIDA / "tabelas.md").write_text("\n".join(L), encoding="utf-8")

# ---------------------------------------------------------------- hipóteses
dec = []
tres_ling = 3


def ranking_rho(c1: str, c2: str, conjunto1: str = "dez", conjunto2: str = "dez") -> dict:
    saida = {}
    for x in DEC:
        ms = [
            m
            for m in pontuais(c1)[1:]
            if m in pontuais(c2)
            and (c1, conjunto1, x, m) in medio
            and (c2, conjunto2, x, m) in medio
            and not np.isnan(medio[(c1, conjunto1, x, m)])
            and not np.isnan(medio[(c2, conjunto2, x, m)])
        ]
        if len(ms) >= 5:
            saida[x] = rho(
                [medio[(c1, conjunto1, x, m)] for m in ms],
                [medio[(c2, conjunto2, x, m)] for m in ms],
            )
    return saida


def texto_rho(r: dict) -> str:
    return (
        ", ".join(f"{NOMES[x]} {num(v, 2)}" for x, v in r.items())
        or "sem linguagem com pares suficientes"
    )


for h, c1, c2, enun in [
    (
        "HH1",
        "S1",
        "S1b",
        "Aumentar o horizonte de 3 para 12 meses muda o ranking dos métodos (S1 contra S1b)",
    ),
    (
        "HH3",
        "S1b",
        "S3h",
        "Mudar a saída de 3 para 12 meses, com horizonte de 12 meses, muda o ranking (S1b contra S3h)",
    ),
    (
        "HH4",
        "S3h",
        "S2",
        "Com saída e horizonte iguais, as faixas de 3 meses, a idade sem desconto e a população de todos mudam o ranking (S3h contra S2)",
    ),
]:
    r = ranking_rho(c1, c2)
    muda = [x for x, v in r.items() if v < 0.9]
    dec.append({"hipotese": h, "enunciado": enun, "status": "sustentada" if len(muda) >= tres_ling else "não sustentada", "detalhe": f"Spearman entre os ABRE médios dos métodos nos dois cenários, origens de dezembro: {texto_rho(r)}. Muda (abaixo de 0,9) em {len(muda)} de {len(r)}"})  # fmt: skip
# HH2: coorte do IEICE16 contra a ingênua, S1 e S1b
rs1, rs1b = (
    razao.get(("S1", "coorte_IEICE"), (np.nan,) * 2),
    razao.get(("S1b", "coorte_IEICE"), (np.nan,) * 2),
)
n1b = len(vence_m.get(("S1b", "coorte_IEICE"), []))
dec.append({"hipotese": "HH2", "enunciado": "A coorte do IEICE16 melhora em relação à ingênua quando o horizonte vai de 3 para 12 meses", "status": "sustentada" if rs1b[0] < rs1[0] and n1b >= tres_ling else "não sustentada",
            "detalhe": f"Razão geométrica da média sobre a ingênua: S1 {num(rs1[0])} e S1b {num(rs1b[0])} (mediana: {num(rs1[1])} e {num(rs1b[1])}); em S1b vence a ingênua na média em {n1b} de 4. A regra pede razão menor em S1b e vitória em pelo menos 3 de 4"})  # fmt: skip
# HH5: algum método vence nas quatro
for c in ["S1b", "S3h", "S1", "S3", "S2"]:
    cols = [x for x in DEC if n_base.get((c, "dez", x), 0) > 0]
    ach = [m for m in pontuais(c)[1:] if (c, m) in vence_m and len(vence_m[(c, m)]) == len(DEC)]
    mais = max(
        ((len(vence_m[(c, m)]), m) for m in pontuais(c)[1:] if (c, m) in vence_m),
        default=(0, "nenhum"),
    )
    dec.append({"hipotese": f"HH5 {c}", "enunciado": f"Em {c}, algum método vence a ingênua na média nas quatro linguagens, com origens de dezembro", "status": "sustentada" if ach else "não sustentada",
                "detalhe": f"{len(ach)} métodos vencem nas quatro ({', '.join(rotulo(m) for m in ach[:6]) or 'nenhum'}); o que vence em mais linguagens: {rotulo(mais[1])} ({mais[0]} de {len(cols)} com base)"})  # fmt: skip
# HH6: nascimento, parada, os dois (S1b e S3h)
for c in NOVOS:
    for b in ["coorte", "conservador"]:
        partes = []
        for r, nome in [(1, "nascimento"), (2, "parada"), (3, "os dois")]:
            n = sum(
                int(fat.get((c, "dez", x, b, r), np.nan) < fat.get((c, "dez", x, b, 0), np.nan))
                for x in DEC
            )
            partes.append((nome, n))
        dec.append({"hipotese": f"HH6 {c} {b}", "enunciado": f"Em {c}, nascimento, parada e os dois melhoram {rotulo(b)}", "status": "sustentada" if all(n >= tres_ling for _, n in partes) else ("parcial" if any(n >= tres_ling for _, n in partes) else "não sustentada"),
                    "detalhe": "; ".join(f"{nome}: ABRE médio menor que R0 em {n} de 4 linguagens (origens de dezembro)" for nome, n in partes)})  # fmt: skip
# HH7: sobreposição. A vantagem da coorte do IEICE16 sobre a ingênua diminui de S3 para S3h
r3, r3h = (
    razao.get(("S3", "coorte_IEICE"), (np.nan,) * 2),
    razao.get(("S3h", "coorte_IEICE"), (np.nan,) * 2),
)
dec.append({"hipotese": "HH7", "enunciado": "Parte da vantagem da coorte em S3 vinha da sobreposição entre a janela do alvo e a origem (a razão sobre a ingênua sobe de S3 para S3h)", "status": "sustentada" if r3h[0] > r3[0] else "não sustentada",
            "detalhe": f"Razão geométrica da média da coorte do IEICE16 sobre a ingênua, origens de dezembro: S3 {num(r3[0])} e S3h {num(r3h[0])} (mediana {num(r3[1])} e {num(r3h[1])}). A regra pede razão maior em S3h"})  # fmt: skip
dec = pd.DataFrame(dec)
dec.to_csv(SAIDA / "decisao.csv", index=False)

# ---------------------------------------------------------------- resumo.md
R = ["# Resumo: cenários com horizonte de 12 meses (S1b e S3h)", "", "Regras escritas antes de rodar em `hipoteses.md`, com a razão da mudança. Garantia contra vazamento em `vazamento.md`. Tabelas completas em `tabelas.md`.", "",
     f"Código rodado na VM: commit `{COMMIT}` (`scripts/granularidade/`). S1, S2 e S3 vêm de `projecao-cenarios-ieice/` e não rodaram de novo.", ""]  # fmt: skip
R.append("## Por que existe este experimento")
R.append("")
R.append(
    "Em S3 (saída em 12 meses) o horizonte era de 3 meses. Com a janela de atividade de 12 meses, 9 dos 12 meses que definem quem está ativo no alvo já estão observados na origem. O S3 media essa sobreposição e a capacidade de previsão ao mesmo tempo. S1b e S3h têm as mesmas regras de S1 e S3 com horizonte de 12 meses (a coorte avança 4 recortes) e S3h tem janela e horizonte iguais, o que não deixa meses do alvo observados na origem."
)
R.append("")
R.append("## As duas linhas de coorte em S1, S1b, S3 e S3h")
R.append("")
R.append(
    "- Coorte do IEICE16 (`coorte_IEICE`): a regra exata do IEICE16. Taxa de sobrevivência de cada faixa = faixa seguinte no recorte mais recente dividida pela faixa no recorte anterior; faixa 0 a 3 meses = média dessa faixa no recorte atual e no anterior (2 recortes). Faixa com gente sem taxa deixa o total indefinido."
)
R.append(
    "- Coorte V0 (`coorte_V0`): a mesma taxa do último recorte, mas a faixa 0 a 3 meses é a média dos últimos 8 recortes (2 anos), que é a regra dos 41 métodos da versão A de `projecao-granularidade` na escala trimestral. Só a faixa 0 muda."
)
R.append(
    "- Por que diferem: em S1, com recortes trimestrais, os novatos oscilam e crescem ou caem de um recorte para o outro. A média de 8 recortes segue o nível de dois anos atrás, e a de 2 recortes segue o nível de agora. Em S1 isso fez a V0 ficar em 1,255 vezes o ABRE médio da ingênua e o IEICE16 em 0,929. A que segue exatamente as regras do IEICE16 é a coorte do IEICE16."
)
R.append("")
R.append("## Respostas diretas")
R.append("")
for _, r in dec.iterrows():
    R.append(f"- {r['hipotese']}, {r['enunciado']}: {r['status']}. {r['detalhe']}.")
R.append("")
R.append("## Base, avisos e arquivos")
R.append("")
nb = {c: [n_base.get((c, "dez", x), 0) for x in DEC] for c in NOVOS}
for c in NOVOS:
    R.append(
        f"- {c}: pares com origens de dezembro (Clojure, Elixir, OCaml e Python) {nb[c]}; Zig {n_base.get((c, 'dez', 'zig'), 0)}. Com todas as origens trimestrais: {[n_base.get((c, 'tri', x), 0) for x in DEC]}."
    )
for c in NOVOS:
    if len(marcas[c]):
        m = marcas[c]
        R.append(
            f"- {c}: Holt substituído pela ingênua em {int(m['holt_ingenua'].sum())} de {len(m)} origens."
        )
R.append(
    "- Poucos pares nas origens de dezembro (de 4 a 8 por linguagem, menor p possível de 0,125 com 4 pares e 0,008 com 8) deixam o teste com pouco poder: ver `testes.csv` (colunas `n_pares` e `p_minimo`). Os testes de todas as origens trimestrais têm pares dependentes e só indicam."
)
if len(testes):
    d = testes[testes["conjunto"] == "dezembro"]
    R.append(
        f"- Testes de dezembro com Holm abaixo de 0,05: {int((d['p_holm'] < 0.05).sum())} de {int(d['p'].notna().sum())} com p definido."
    )
R.append(
    "- S1b e S3h rodam sem o lado (código ou conversa) de cada evento, como S1 e S3. Projeção por repositório não rodou, como pedido."
)
R.append(
    "- Arquivos: `pares.csv`, `testes.csv`, `decisao.csv`, `base_perdas.csv`, `tabelas.md` e `vazamento.md`."
)
(SAIDA / "resumo.md").write_text("\n".join(R), encoding="utf-8")

# ---------------------------------------------------------------- vazamento.md
V = ["# Garantia contra vazamento", "", "Mesma função protegida de `projecao-cenarios-ieice/`: `constroi_estado` corta os eventos em t (assert da maior data) e `preve_estado` recebe só o estado até a origem. O alvo (12 meses depois) é calculado em `cenarios.py`, fora da previsão. Os erros de origens anteriores só usam origens cujo alvo (origem mais 12 meses) já foi observado na origem atual.", "",
     "Teste: 5 origens espalhadas por linguagem e cenário; a previsão com o estado da produção, com os eventos até t e com os eventos até t + 12 meses precisa sair igual (1e-9) e as séries idênticas. Controle com vazamento de propósito: os eventos de (t, t + 12 meses] entram com a data t, e a previsão precisa mudar. O teste só vale onde o controle difere.", ""]  # fmt: skip
if len(vaza):
    v = vaza.copy()
    p = v["unidade"].str.split("_")
    v["linguagem"], v["cenario"] = p.str[0], p.str[1]
    V.append(
        "| Linguagem | Cenário | Origens | Estados iguais | Maior diferença relativa | Controle difere em | Teste vale |"
    )
    V.append("|---|---|---:|---|---:|---:|---|")
    for (x, c), g in v.groupby(["linguagem", "cenario"]):
        dif = int(g["controle_eventos_futuros_difere"].sum())
        V.append(
            f"| {NOMES[x]} | {c} | {len(g)} | {'sim' if g['estados_iguais'].all() else 'NÃO'} | {g['maior_diferenca_relativa'].max():.1e} | {dif} | {'sim' if dif > 0 else 'NÃO: teste sem poder'} |"
        )
    V.append("")
    limpo = bool(vaza["estados_iguais"].all()) and bool(
        (vaza["maior_diferenca_relativa"].fillna(0) < 1e-9).all()
    )
    V.append(
        f"Resultado: {'nenhum vazamento encontrado' if limpo else 'HÁ DIFERENÇAS, ver a tabela'} em {len(vaza)} origens testadas."
    )
V.append("")
V.append(
    "As ameaças à validade são as de `projecao-cenarios-ieice/vazamento.md` (filtros da carga que usam a coleta inteira, ligação de identidades, ausência do lado de cada evento)."
)
(SAIDA / "vazamento.md").write_text("\n".join(V), encoding="utf-8")
print("resumo pronto")
