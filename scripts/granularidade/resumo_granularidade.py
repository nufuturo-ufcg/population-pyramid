"""Tabelas, testes, figura, hipóteses e textos do experimento de granularidade, a partir de `<saida>/unidades/`. Ver `hipoteses.md`.

Grava `pares.csv`, `testes.csv`, `decisao.csv`, `intervalos.csv`, `tabelas.md`, `resumo.md` e `vazamento.md`, e a figura `figura_abre_por_passo.png` (e `.pdf`).

Uso (na raiz do repo): .venv/bin/python <este arquivo> <saida> [--decisao clojure elixir ocaml python]
"""

import contextlib
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from previsao import VARIANTES

SAIDA = Path(sys.argv[1])
DECISAO = ["clojure", "elixir", "ocaml", "python"]
if "--decisao" in sys.argv:
    DECISAO = sys.argv[sys.argv.index("--decisao") + 1 :]


from util_resumo import (  # noqa: E402
    FAIXAS,
    HONESTAS,
    METODOS,
    NOME_PASSO,
    NOME_POP,
    NOMES,
    PASSOS,
    POPS,
    ROTULO,
    geometrica,
    holm,
    num,
    rho,
    teste,
)

pasta = SAIDA / "unidades"
pares = pd.concat([pd.read_csv(f) for f in sorted(pasta.glob("*_pares.csv.gz"))], ignore_index=True)
faixas = pd.concat(
    [pd.read_csv(f) for f in sorted(pasta.glob("*_faixas.csv.gz"))], ignore_index=True
)
marcas = pd.concat(
    [
        pd.read_csv(f)
        for f in sorted(pasta.glob("*_marcas.csv"))
        if not f.name.endswith("_B_marcas.csv")
    ],
    ignore_index=True,
)  # só as marcas da versão A: as da B repetem Holt e negativas
vaza_arquivos = sorted(pasta.glob("*_vazamento.csv"))
vaza = (
    pd.concat([pd.read_csv(f) for f in vaza_arquivos], ignore_index=True)
    if vaza_arquivos
    else pd.DataFrame()
)
LINGUAS = [x for x in NOMES if x in set(pares["linguagem"])] + sorted(
    set(pares["linguagem"]) - set(NOMES)
)

# ---------------------------------------------------------------- base de comparação
pares["na_base"] = False
base_info = []  # linguagem, populacao, passo, pares na base, e por método quantos perderia
abre_medio, abre_mediano, n_base, base_por_grupo = {}, {}, {}, {}
for (pop, passo, lingua), g in pares[pares["populacao"].isin(POPS)].groupby(
    ["populacao", "passo_meses", "linguagem"]
):
    largo = g.pivot(index="k", columns="metodo", values="abre").reindex(columns=METODOS)
    na_base = largo.notna().all(axis=1)
    base_ks = largo.index[na_base]
    base_por_grupo[(pop, passo, lingua)] = base_ks
    pares.loc[g.index[g["k"].isin(base_ks)], "na_base"] = True
    n_base[(pop, passo, lingua)] = len(base_ks)
    for m in METODOS:
        definidos = int(largo[m].notna().sum())
        base_info.append(
            {
                "populacao": pop,
                "passo_meses": passo,
                "linguagem": lingua,
                "metodo": m,
                "pares_com_previsao": definidos,
                "pares_na_base": len(base_ks),
                "perdidos_pela_exigencia": definidos - len(base_ks),
            }
        )
        x = largo.loc[na_base, m]
        abre_medio[(pop, passo, lingua, m)] = float(x.mean()) if len(x) else np.nan
        abre_mediano[(pop, passo, lingua, m)] = float(x.median()) if len(x) else np.nan
base_info = pd.DataFrame(base_info)
P0 = pares[pares["populacao"] == "P0"]
pares.to_csv(SAIDA / "pares.csv", index=False, float_format="%.10g")

# ---------------------------------------------------------------- testes
linhas = []
for (pop, passo, lingua), ks in base_por_grupo.items():
    if len(ks) == 0:
        continue
    g = pares[
        (pares["populacao"] == pop)
        & (pares["passo_meses"] == passo)
        & (pares["linguagem"] == lingua)
        & pares["k"].isin(ks)
    ]
    largo = g.pivot(index="k", columns="metodo", values="abre")
    ps, ficha = [], []
    for m in METODOS[1:]:
        ps.append(teste(largo[m].to_numpy(), largo["ingenua"].to_numpy()))
        ficha.append({"populacao": pop, "passo_meses": passo, "linguagem": lingua, "metodo": m, "n_pares": len(largo), "p_minimo": 2.0 / 2 ** len(largo), "abre_medio_metodo": float(largo[m].mean()),
                      "abre_medio_ingenua": float(largo["ingenua"].mean()), "pares_que_vencem_a_ingenua": int((largo[m] < largo["ingenua"]).sum())})  # fmt: skip
    ps = np.array(ps)
    ajustado = holm(ps)
    for i, f in enumerate(ficha):
        f["p"], f["p_holm"] = ps[i], ajustado[i]
        linhas.append(f)
testes = pd.DataFrame(linhas)
testes.to_csv(SAIDA / "testes.csv", index=False, float_format="%.6g")

# ---------------------------------------------------------------- tabelas por passo e população
L = [
    "# Tabelas",
    "",
    "ABRE médio sobre os pares da base de comparação (todos os métodos com previsão no par). Em negrito o menor de cada linguagem.",
    "",
]


def tabela(cab: list[str], linhas_md: list[list[str]]) -> None:
    L.append("| " + " | ".join(cab) + " |")
    L.append("|" + "|".join(["---"] + ["---:"] * (len(cab) - 1)) + "|")
    for linha in linhas_md:
        L.append("| " + " | ".join(linha) + " |")
    L.append("")


L.append("## Pares na base de comparação")
L.append("")
linhas_md = []
for pop in POPS:
    for passo in PASSOS:
        linhas_md.append(
            [NOME_POP[pop], NOME_PASSO[passo]]
            + [str(n_base.get((pop, passo, x), "n/d")) for x in LINGUAS]
        )
tabela(["População", "Passo"] + [NOMES[x] for x in LINGUAS], linhas_md)
L.append(
    "Pares perdidos pela exigência de todos os métodos (soma entre linguagens, por método, só os que perderiam algum par) estão em `base_perdas.csv`."
)
L.append("")
base_info.to_csv(SAIDA / "base_perdas.csv", index=False)

razao_geral = {}
melhor_por = {}
for pop in POPS:
    for passo in PASSOS:
        L.append(f"## {NOME_POP[pop]}, passo de {NOME_PASSO[passo]}")
        L.append("")
        colunas = [x for x in LINGUAS if n_base.get((pop, passo, x), 0) > 0]
        if not colunas:
            L.append("Nenhuma linguagem tem par na base.")
            L.append("")
            continue
        melhor = {}
        for x in colunas:
            valores = {m: abre_medio[(pop, passo, x, m)] for m in METODOS}
            melhor[x] = min(valores, key=valores.get)
            melhor_por[(pop, passo, x)] = melhor[x]
        linhas_md = []
        for m in METODOS:
            linha = [ROTULO[m]]
            for x in colunas:
                texto = num(abre_medio[(pop, passo, x, m)])
                linha.append(f"**{texto}**" if m == melhor[x] else texto)
            linhas_md.append(linha)
        linhas_md.append(["Melhor método"] + [ROTULO[melhor[x]] for x in colunas])
        razoes = []
        for x in colunas:
            razoes.append(
                [
                    abre_medio[(pop, passo, x, m)] / abre_medio[(pop, passo, x, "ingenua")]
                    for m in METODOS
                ]
            )
        linha_geo = ["Média geométrica do ABRE médio relativo à ingênua, entre linguagens"]
        geo = {m: geometrica([r[i] for r in razoes]) for i, m in enumerate(METODOS)}
        razao_geral.update({(pop, passo, m): v for m, v in geo.items()})
        tabela(["Método"] + [NOMES[x] for x in colunas], linhas_md)
        L.append(
            "Média geométrica do ABRE médio relativo à ingênua, entre as linguagens da tabela (abaixo de 1: erra menos que a ingênua):"
        )
        L.append("")
        tabela(
            ["Método", "Razão geométrica"],
            [[ROTULO[m], num(geo[m])] for m in METODOS if m != "ingenua"],
        )

# tabela-resumo final
L.append("## Resumo: melhor método de cada linguagem em cada passo")
L.append("")
for x in LINGUAS:
    for pop in POPS:
        if not any(n_base.get((pop, p, x), 0) > 0 for p in PASSOS):
            continue
        L.append(f"### {NOMES[x]}, {NOME_POP[pop]}")
        L.append("")
        linhas_md = []
        for passo in PASSOS:
            if n_base.get((pop, passo, x), 0) == 0:
                linhas_md.append([NOME_PASSO[passo], "n/d", "n/d", "n/d"])
                continue
            m = melhor_por[(pop, passo, x)]
            linhas_md.append(
                [
                    NOME_PASSO[passo],
                    ROTULO[m],
                    num(abre_medio[(pop, passo, x, m)]),
                    num(abre_medio[(pop, passo, x, "ingenua")]),
                ]
            )
        tabela(["Passo", "Melhor método", "ABRE médio", "ABRE médio da ingênua"], linhas_md)

# P0 contra P1 e P2 no passo de 12 meses
L.append("## P0 contra P1 e P2, passo de 12 meses, origens de dezembro")
L.append("")
L.append(
    "Mesmas origens nas três populações (as em que o método tem ABRE definido nas três). ABRE médio."
)
L.append("")
quatro = ["ingenua", "coorte_V0", "coorte_amortecida", "holt_amortecido"]
comparacao_p0 = {}
linhas_md = []
for x in LINGUAS:
    for m in quatro:
        tres = []
        for pop in ["P0", "P1", "P2"]:
            g = pares[
                (pares["populacao"] == pop)
                & (pares["passo_meses"] == 12)
                & (pares["linguagem"] == x)
                & (pares["metodo"] == m)
            ].set_index("k")["abre"]
            tres.append(g)
        comuns = (
            tres[0]
            .dropna()
            .index.intersection(tres[1].dropna().index)
            .intersection(tres[2].dropna().index)
        )
        if len(comuns) == 0:
            continue
        medias_3 = [float(t.loc[comuns].mean()) for t in tres]
        comparacao_p0[(x, m)] = medias_3
        linhas_md.append([NOMES[x], ROTULO[m], str(len(comuns))] + [num(v) for v in medias_3])
tabela(["Linguagem", "Método", "Origens", "P0", "P1", "P2"], linhas_md)

# intervalos pessimista-otimista
interv = []
for (pop, passo, lingua), ks in base_por_grupo.items():
    if len(ks) == 0:
        continue
    g = pares[
        (pares["populacao"] == pop)
        & (pares["passo_meses"] == passo)
        & (pares["linguagem"] == lingua)
        & pares["k"].isin(ks)
    ]
    largo = g.pivot(index="k", columns="metodo", values="previsto")
    real = g[g["metodo"] == "ingenua"].set_index("k")["real"]
    for v in VARIANTES:
        pess, otim = largo[f"pessimista_{v}"], largo[f"otimista_{v}"]
        interv.append({"populacao": pop, "passo_meses": passo, "linguagem": lingua, "variante": v, "pares": len(largo), "cobertura": float(((pess <= real) & (real <= otim)).mean()),
                       "largura_relativa_mediana": float(((otim - pess) / largo["ingenua"]).median())})  # fmt: skip
interv = pd.DataFrame(interv)
interv.to_csv(SAIDA / "intervalos.csv", index=False, float_format="%.6g")
L.append("## Intervalo pessimista-otimista da V0: cobertura e largura relativa mediana")
L.append("")
linhas_md = []
for pop in POPS:
    for passo in PASSOS:
        s = interv[
            (interv["populacao"] == pop)
            & (interv["passo_meses"] == passo)
            & (interv["variante"] == "V0")
        ]
        if len(s):
            linhas_md.append(
                [
                    NOME_POP[pop],
                    NOME_PASSO[passo],
                    num(s["cobertura"].mean()),
                    num(s["largura_relativa_mediana"].mean()),
                ]
            )
tabela(
    [
        "População",
        "Passo",
        "Cobertura média entre linguagens",
        "Largura relativa média entre linguagens",
    ],
    linhas_md,
)
L.append("Todas as variantes e linguagens: `intervalos.csv`.")
L.append("")

# faixas: ABRE médio nos pares da base
fx = faixas[faixas["populacao"].isin(POPS)].copy()
fx["na_base"] = [
    k in set(base_por_grupo.get((p, s, lingua_g), []))
    for p, s, lingua_g, k in zip(
        fx["populacao"], fx["passo_meses"], fx["linguagem"], fx["k"], strict=True
    )
]
fx = fx[fx["na_base"]]
abre_faixa = fx.groupby(["populacao", "passo_meses", "linguagem", "metodo", "faixa"])["abre"].mean()
abre_faixa.reset_index().to_csv(SAIDA / "abre_por_faixa.csv", index=False, float_format="%.6g")
L.append("## ABRE médio por faixa de idade, ingênua, coorte V0 e conservador V0 (P1 contra P2)")
L.append("")
L.append("Quantas das células (linguagem e passo) têm ABRE médio maior em P2 do que em P1.")
L.append("")
linhas_md = []
cresce = {}
for m in ["ingenua", "coorte_V0", "conservador_V0"]:
    for f in range(6):
        maior, total = 0, 0
        linguas_com = {}
        for x in LINGUAS:
            passos_maior = 0
            passos_total = 0
            for passo in PASSOS:
                try:
                    a, b = abre_faixa[("P1", passo, x, m, f)], abre_faixa[("P2", passo, x, m, f)]
                except KeyError:
                    continue
                if np.isnan(a) or np.isnan(b):
                    continue
                passos_total += 1
                passos_maior += int(b > a)
            maior += passos_maior
            total += passos_total
            linguas_com[x] = (passos_maior, passos_total)
        cresce[(m, f)] = linguas_com
        linhas_md.append([ROTULO[m], FAIXAS[f], f"{maior} de {total}"])
tabela(["Método", "Faixa", "Células com erro maior em P2"], linhas_md)

# ---------------------------------------------------------------- figura
cores = {
    "ingenua": "#222222",
    "coorte_V0": "#1b6ca8",
    "coorte_amortecida": "#c1440e",
    "holt_amortecido": "#2a9d4b",
    "melhor_combinacao": "#8e44ad",
}
rotulos_fig = {
    "ingenua": "Ingênua",
    "coorte_V0": "Coorte V0",
    "coorte_amortecida": "Coorte amortecida",
    "holt_amortecido": "Holt amortecido",
    "melhor_combinacao": "Melhor combinação (C1 a C7)",
}
fig, eixos = plt.subplots(
    1, len(LINGUAS), figsize=(max(3.6 * len(LINGUAS), 9), 4.2), sharey=False, squeeze=False
)
melhor_comb = {}
for j, x in enumerate(LINGUAS):
    ax = eixos[0, j]
    for pop, estilo in [("P1", "-"), ("P2", "--")]:
        medias_c = {
            c: np.nanmean([abre_medio.get((pop, p, x, c), np.nan) for p in PASSOS])
            for c in HONESTAS
        }
        if all(np.isnan(v) for v in medias_c.values()):
            continue
        melhor_comb[(pop, x)] = min(
            medias_c, key=lambda c: medias_c[c] if not np.isnan(medias_c[c]) else np.inf
        )
        for chave, metodo in [
            ("ingenua", "ingenua"),
            ("coorte_V0", "coorte_V0"),
            ("coorte_amortecida", "coorte_amortecida"),
            ("holt_amortecido", "holt_amortecido"),
            ("melhor_combinacao", melhor_comb[(pop, x)]),
        ]:
            y = [abre_medio.get((pop, p, x, metodo), np.nan) for p in PASSOS]
            ax.plot(
                range(len(PASSOS)),
                y,
                estilo,
                color=cores[chave],
                marker="o",
                markersize=3,
                label=rotulos_fig[chave] if pop == "P1" else None,
            )
    ax.set_xticks(range(len(PASSOS)))
    ax.set_xticklabels(
        [
            NOME_PASSO[p].replace(" meses", "m").replace(" mês", "m").replace(" dias", "d")
            for p in PASSOS
        ],
        fontsize=8,
    )
    ax.set_yscale("log")
    ax.set_xlabel("Passo")
    ax.set_ylabel("ABRE médio" if j == 0 else "")
    ax.set_title(NOMES[x], fontsize=10)
    ax.grid(alpha=0.3)
h, r = eixos[0, 0].get_legend_handles_labels()
fig.legend(h, r, loc="lower center", ncol=5, fontsize=8, frameon=False, bbox_to_anchor=(0.5, 0.04))
fig.text(0.5, 0.01, "Linha cheia: P1. Linha tracejada: P2.", ha="center", fontsize=8)
fig.tight_layout(rect=(0, 0.14, 1, 1))
fig.savefig(SAIDA / "figura_abre_por_passo.png", dpi=160)
fig.savefig(SAIDA / "figura_abre_por_passo.pdf")
plt.close(fig)
(SAIDA / "tabelas.md").write_text("\n".join(L), encoding="utf-8")

# ---------------------------------------------------------------- hipóteses
dec = []
tem_base = lambda pop, passo: all(n_base.get((pop, passo, x), 0) > 0 for x in DECISAO)  # noqa: E731
# H1
achados = []
for pop in POPS:
    for passo in PASSOS:
        if not tem_base(pop, passo):
            continue
        for m in METODOS[1:]:
            if all(
                abre_medio[(pop, passo, x, m)] < abre_medio[(pop, passo, x, "ingenua")]
                for x in DECISAO
            ):
                achados.append((pop, passo, m))
holm_ok = 0
for pop, passo, m in achados:
    t = testes[
        (testes["populacao"] == pop)
        & (testes["passo_meses"] == passo)
        & (testes["metodo"] == m)
        & testes["linguagem"].isin(DECISAO)
    ]
    if len(t) == len(DECISAO) and (t["p_holm"] < 0.05).all():
        holm_ok += 1
por_pop = {pop: sorted({(p, m) for q, p, m in achados if q == pop}) for pop in POPS}
dec.append({"hipotese": "H1", "status": "sustentada" if achados else "não sustentada",
            "detalhe": f"{len(achados)} combinações de passo, população e método vencem a ingênua nas {len(DECISAO)} linguagens (P1: {len(por_pop['P1'])}, P2: {len(por_pop['P2'])}); {holm_ok} passam o Holm nas {len(DECISAO)}"})  # fmt: skip
# H2
vantagem = {}
for pop in POPS:
    pontos = [
        (
            p,
            geometrica(
                [
                    abre_medio[(pop, p, x, "coorte_V0")] / abre_medio[(pop, p, x, "ingenua")]
                    for x in DECISAO
                ]
            ),
        )
        for p in PASSOS
        if tem_base(pop, p)
    ]
    vantagem[pop] = pontos
rhos = {pop: rho([p for p, _ in v], [r for _, r in v]) for pop, v in vantagem.items()}
cresce_ok = all(
    len(v) == len(PASSOS) and rhos[pop] <= -0.7 and v[-1][1] > v[0][1]
    for pop, v in vantagem.items()
)
dec.append({"hipotese": "H2", "status": "sustentada" if cresce_ok else "não sustentada", "detalhe": "; ".join(f"{pop}: Spearman {num(rhos[pop], 2)}, razão {num(v[0][1])} em 12 meses e {num(v[-1][1])} no passo mais curto" for pop, v in vantagem.items() if v)})  # fmt: skip
# H3
muda = {pop: [] for pop in POPS}
for pop in POPS:
    for x in DECISAO:
        melhores = {melhor_por[(pop, p, x)] for p in PASSOS if (pop, p, x) in melhor_por}
        muda[pop].append(len(melhores) > 1)
h3_ok = all(sum(v) >= min(3, len(DECISAO)) for v in muda.values())
dec.append({"hipotese": "H3", "status": "sustentada" if h3_ok else ("parcial" if any(any(v) for v in muda.values()) else "não sustentada"), "detalhe": "; ".join(f"{pop}: muda em {sum(v)} de {len(v)} linguagens" for pop, v in muda.items())})  # fmt: skip
# H4
diferem, celulas = 0, 0
for x in DECISAO:
    for p in PASSOS:
        if (("P1", p, x) in melhor_por) and (("P2", p, x) in melhor_por):
            celulas += 1
            diferem += int(melhor_por[("P1", p, x)] != melhor_por[("P2", p, x)])
dec.append({"hipotese": "H4", "status": "sustentada" if celulas and diferem * 2 >= celulas and diferem >= min(12, celulas) else "não sustentada", "detalhe": f"O melhor difere entre P1 e P2 em {diferem} de {celulas} células"})  # fmt: skip


# H5
def p2_maior(metodo: str) -> tuple[int, int]:
    bons = 0
    for p in PASSOS:
        n_lingua = sum(
            1
            for x in DECISAO
            if abre_medio.get(("P2", p, x, metodo), np.nan)
            > abre_medio.get(("P1", p, x, metodo), np.nan)
        )
        bons += int(n_lingua >= min(3, len(DECISAO)))
    return bons, len(PASSOS)


contagem_ing, contagem_coo = p2_maior("ingenua"), p2_maior("coorte_V0")
h5_ok = contagem_ing[0] >= 5 and contagem_coo[0] >= 5
faixas_que_crescem = []
for m, f in cresce:
    passos_ok = 0
    for p in PASSOS:
        n_l = 0
        for x in DECISAO:
            with contextlib.suppress(KeyError):
                n_l += int(abre_faixa[("P2", p, x, m, f)] > abre_faixa[("P1", p, x, m, f)])
        passos_ok += int(n_l >= min(3, len(DECISAO)))
    if passos_ok >= 5:
        faixas_que_crescem.append(f"{ROTULO[m]} {FAIXAS[f]}")
dec.append({"hipotese": "H5", "status": "sustentada" if h5_ok else "não sustentada",
            "detalhe": f"P2 erra mais em {contagem_ing[0]} de 6 passos na ingênua e em {contagem_coo[0]} de 6 na coorte V0; faixas com erro maior em P2 em pelo menos 5 passos: {', '.join(faixas_que_crescem) or 'nenhuma'}"})  # fmt: skip
# H6
direcoes = []
vence_p0 = {}
for m in quatro:
    n_p0 = sum(
        1
        for x in DECISAO
        if (x, m) in comparacao_p0 and comparacao_p0[(x, m)][0] < comparacao_p0[(x, m)][1]
    )
    vence_p0[m] = n_p0
    direcoes.append(f"{ROTULO[m].capitalize()}: P0 menor que P1 em {n_p0} de {len(DECISAO)}")
dec.append({"hipotese": "H6", "status": "sustentada" if all(v >= min(3, len(DECISAO)) for v in vence_p0.values()) and comparacao_p0 else "não sustentada", "detalhe": "; ".join(direcoes)})  # fmt: skip
# H7
rhos7 = {}
for pop in POPS:
    s = (
        interv[
            (interv["populacao"] == pop)
            & (interv["variante"] == "V0")
            & interv["linguagem"].isin(DECISAO)
        ]
        .groupby("passo_meses")[["cobertura", "largura_relativa_mediana"]]
        .mean()
        .reindex(PASSOS)
        .dropna()
    )
    rhos7[pop] = (
        rho(list(s.index), list(s["largura_relativa_mediana"])),
        rho(list(s.index), list(s["cobertura"])),
    )
h7_ok = all(
    not np.isnan(a) and not np.isnan(b) and a <= -0.7 and b <= -0.7 for a, b in rhos7.values()
)
dec.append({"hipotese": "H7", "status": "sustentada" if h7_ok else "não sustentada", "detalhe": "; ".join(f"{pop}: Spearman da largura {num(a, 2)} e da cobertura {num(b, 2)}" for pop, (a, b) in rhos7.items())})  # fmt: skip
dec = pd.DataFrame(dec)
dec.to_csv(SAIDA / "decisao.csv", index=False)

# ---------------------------------------------------------------- resumo
ARQ_COMMIT = SAIDA / "commit.txt"
COMMIT = ARQ_COMMIT.read_text(encoding="utf-8").strip() if ARQ_COMMIT.exists() else "não registrado"
R = [
    "# Resumo: granularidade do passo e população (RQ3)",
    "",
    "Regras escritas antes de rodar em `hipoteses.md`. Garantia contra vazamento em `vazamento.md`. Tabelas completas em `tabelas.md`.",
    "",
    f"Código rodado na VM: commit `{COMMIT}` (adaptador `carga_duckdb.py` e `scripts/granularidade/`).",
    "",
]
R.append("## Respostas diretas")
R.append("")
if achados:
    R.append(
        f"- Algum método vence a ingênua na média nas {len(DECISAO)} linguagens: sim. {dec.iloc[0]['detalhe']}."
    )
    exemplos = sorted(achados)[:8]
    R.append(
        "  Primeiros casos: "
        + "; ".join(f"{p}, {NOME_PASSO[s]}, {ROTULO[m]}" for p, s, m in exemplos)
        + "."
    )
else:
    R.append(
        f"- Algum método vence a ingênua na média nas {len(DECISAO)} linguagens: não, em nenhum passo nem população."
    )
R.append(
    "- Melhor método por linguagem e passo: `tabelas.md`, seção Resumo. "
    + dec.iloc[2]["detalhe"]
    + " (mudança com o passo); "
    + dec.iloc[3]["detalhe"]
    + " (mudança com a população)."
)
R.append("- Vantagem da ingênua quando o passo encurta: " + dec.iloc[1]["detalhe"] + ".")
R.append("- P2 contra P1: " + dec.iloc[4]["detalhe"] + ".")
R.append("- P0 contra P1 (12 meses): " + dec.iloc[5]["detalhe"] + ".")
R.append("")
R.append("![ABRE médio por passo](figura_abre_por_passo.png)")
R.append("")
R.append("## Hipóteses")
R.append("")
ENUNCIADO = {
    "H1": "Algum método vence a ingênua nas quatro linguagens em algum passo e população", "H2": "A vantagem da ingênua aumenta quando o passo encurta", "H3": "O melhor método muda com o passo",
    "H4": "O melhor método muda com a população", "H5": "Prever P2 é mais difícil que prever P1", "H6": "P0 erra menos que P1 no passo de 12 meses", "H7": "O intervalo pessimista-otimista alarga e cobre mais com o passo curto",
}  # fmt: skip
for _, linha in dec.iterrows():
    R.append(
        f"- {linha['hipotese']}, {ENUNCIADO[linha['hipotese']]}: {linha['status']}. {linha['detalhe']}."
    )
R.append("")
R.append("## Pares e marcas")
R.append("")
perdas = (
    base_info[base_info["perdidos_pela_exigencia"] > 0]
    .groupby("metodo")["perdidos_pela_exigencia"]
    .sum()
    .sort_values(ascending=False)
)
R.append(
    f"- Pares na base: ver `tabelas.md`. Métodos que mais perdem pares pela exigência de todos terem previsão: {', '.join(f'{ROTULO[m]} ({int(v)})' for m, v in perdas.head(5).items()) or 'nenhum'}."
)
R.append(
    f"- Holt substituído pela ingênua por série curta: {int(marcas['holt_ingenua'].sum())} de {len(marcas)} origens. w da coorte amortecida sem origem anterior: {int(marcas['w_sem_origem_anterior'].sum())}. Previsões negativas viradas para zero: {int(marcas['negativas'].sum())} de {int(marcas['avaliacoes_negativas'].sum())}."
)
R.append(
    "- Origens próximas se sobrepõem no alvo (com passo de 15 dias, duas origens seguidas compartilham quase todo o ano de alvo). Os pares do Wilcoxon não são independentes e os p são indicativos. Número de pares e menor p possível de cada teste: `testes.csv`."
)
R.append(
    f"- Testes com Holm abaixo de 0,05: {int((testes['p_holm'] < 0.05).sum())} de {int(testes['p'].notna().sum())} com p definido."
)
R.append("")
R.append("## Arquivos")
R.append("")
R.append(
    "- `pares.csv`, `testes.csv`, `decisao.csv`, `intervalos.csv`, `abre_por_faixa.csv`, `base_perdas.csv` e `figura_abre_por_passo.png`."
)
(SAIDA / "resumo.md").write_text("\n".join(R), encoding="utf-8")

# ---------------------------------------------------------------- vazamento.md
V = [
    "# Garantia contra vazamento",
    "",
    "## Estrutura",
    "",
    "- `estado.constroi_estado(pessoas, eventos, passo, populacao, corte)` descarta todo evento depois de `corte`, confere com assert que a maior data restante é no máximo `corte` e ignora segunda ocasião depois do corte. Cada valor de um bloco depende só de eventos até o fim do bloco.",
    "- `previsao.preve_estado(est, hist, regras, pool)` recebe só o estado cortado na origem (`corta_estado`) e o histórico de previsões anteriores. Não abre arquivo. Asserts conferem que nenhuma série tem dado depois da origem e que nenhum repositório nasce depois dela.",
    "- Os erros de origens anteriores (para w da coorte amortecida, C6 e C7) só usam origens s com s + 12 meses menor ou igual à origem atual.",
    "- O alvo real é calculado em `rodar.py`, depois da previsão, e a função de previsão não o acessa.",
    "- Em P1 a pessoa entra como residente no bloco da segunda ocasião. A pirâmide de cada data é a conhecida naquela data e não é revista depois.",
    "- P0 classifica pela vida inteira (`ocasioes > 1`) e por isso não passa pelo teste: é a referência que usa informação posterior à origem.",
    "",
]
V.append("## Teste")
V.append("")
V.append(
    "Para cada linguagem, população (P1 e P2) e passo, 5 origens espalhadas entre a primeira com 5 anos de histórico e a última. A previsão de todos os métodos com o estado da produção (construído uma vez com todos os dados e cortado na origem), com o estado construído só com os eventos até t e com o construído recebendo os eventos até t + 12 meses precisa sair igual (diferença relativa abaixo de 1e-9, só para a ordem das somas), e as séries inteiras precisam ser idênticas."
)
V.append("")
V.append(
    "Dois controles com vazamento de propósito mostram que o teste enxerga um vazamento. No controle de eventos futuros, os eventos de (t, t + 12 meses] entram com a data t (P1 e P2). No controle de promoções, quem só vira residente até t + 12 meses entra como residente desde o início (P1). Em cada um a previsão precisa mudar. **O teste só vale nos passos e populações em que o controle difere.**"
)
V.append("")
if len(vaza):
    resumo_v = vaza.copy()
    resumo_v["linguagem"] = resumo_v["unidade"].str.split("_").str[0]
    resumo_v["populacao"] = resumo_v["unidade"].str.split("_").str[1]
    resumo_v["passo"] = resumo_v["unidade"].str.split("_").str[2].astype(float)
    if "controle_promocoes_difere" not in resumo_v:
        resumo_v["controle_promocoes_difere"] = np.nan
    V.append("### Validade do teste por passo")
    V.append("")
    V.append(
        "| Passo | População | Origens testadas | Controle de eventos futuros difere em | Controle de promoções difere em | Teste vale |"
    )
    V.append("|---|---|---:|---:|---:|---|")
    todos_validos = True
    for passo in PASSOS:
        for pop in POPS:
            g = resumo_v[(resumo_v["passo"] == passo) & (resumo_v["populacao"] == pop)]
            if len(g) == 0:
                V.append(f"| {NOME_PASSO[passo]} | {pop} | 0 | n/d | n/d | não rodou |")
                todos_validos = False
                continue
            futuros = int(g["controle_eventos_futuros_difere"].sum())
            promocoes = int(g["controle_promocoes_difere"].sum()) if pop == "P1" else None
            vale = futuros > 0 and (pop != "P1" or promocoes > 0)
            todos_validos = todos_validos and vale
            V.append(
                f"| {NOME_PASSO[passo]} | {pop} | {len(g)} | {futuros} | {promocoes if pop == 'P1' else 'n/a'} | {'sim' if vale else 'NÃO: teste sem poder'} |"
            )
    V.append("")
    V.append("### Resultado por linguagem, população e passo")
    V.append("")
    g = (
        resumo_v.groupby(["linguagem", "populacao", "passo"])
        .agg(
            origens=("k", "size"),
            iguais=("estados_iguais", "all"),
            maior=("maior_diferenca_relativa", "max"),
        )
        .reset_index()
    )
    V.append(
        "| Linguagem | População | Passo (meses) | Origens | Séries idênticas | Maior diferença relativa |"
    )
    V.append("|---|---|---:|---:|---|---:|")
    for _, r in g.iterrows():
        V.append(
            f"| {NOMES[r['linguagem']]} | {r['populacao']} | {r['passo']:g} | {int(r['origens'])} | {'sim' if r['iguais'] else 'não'} | {r['maior']:.1e} |"
        )
    V.append("")
    limpo = vaza["estados_iguais"].all() and (vaza["maior_diferenca_relativa"] < 1e-9).all()
    V.append(
        f"Resultado: {'nenhum vazamento encontrado' if limpo else 'HÁ DIFERENÇAS, ver a tabela'} em {len(vaza)} origens testadas. Teste válido em todos os passos e populações: {'sim' if todos_validos else 'não, ver a tabela de validade'}."
    )
else:
    V.append("O teste ainda não rodou com dados reais (use `rodar.py --vazamento`).")
V.append("")
V.append("## Idade e como a pirâmide envelhece entre um passo e outro")
V.append("")
V.append(
    "- Idade em anos, como na rodada oficial (idade descontada): número de anos anteriores com atividade. É recalculada em cada data da grade só com os eventos até ela. Os anos são contados para trás a partir da data, 12 meses cada um: idade(k) = número das datas k - 12 meses, k - 24 meses, ... em que a pessoa estava ativa na janela de 12 meses. Em 31 de dezembro isso é o ano de calendário da rodada oficial. Nas outras datas o ano termina na própria data (`estado.py`). Faixas de 1 ano (0 a 8 e uma aberta), em todos os passos."
)
V.append(
    "- A janela de atividade é de 12 meses em todos os passos e populações. O passo só define as datas em que o estado é atualizado e o intervalo entre origens."
)
V.append(
    "- Quem passa de faixa no meio do passo: a pessoa não é movida dentro do passo. A idade é recalculada em cada data, então ela já está na faixa nova na pirâmide da data seguinte. Entre duas datas da grade nada é interpolado."
)
V.append(
    "- Coorte (V0 a V4a e V4b), conservador, pessimista, otimista e Hamilton-Perry: a taxa de permanência de cada faixa é a de 12 meses, quem está na faixa k+1 na data t dividido por quem estava na faixa k em t - 12 meses (duas pirâmides da grade 12 meses afastadas, cada uma com a idade recalculada na sua data). Essa taxa já inclui quem passou de faixa em algum ponto dos 12 meses. A projeção de 12 meses avança a pirâmide um ano de uma vez: cada faixa vai para a seguinte com a sua taxa e entram os novatos. Avançar em passos menores com 1/n de ano de envelhecimento por passo, com a massa de cada faixa espalhada de modo uniforme e a taxa dividida igualmente entre os passos, dá o mesmo total em 12 meses. Por isso o passo não muda a conta da projeção."
)
V.append(
    "- O que o passo muda nesses métodos: as origens (uma a cada passo) e as séries sobre as datas da grade. Novatos pela média dos últimos 2 anos (V0), 3 anos (Hamilton-Perry de 3 anos) e 5 anos (Hamilton-Perry de 5 anos) são médias das pirâmides de todas as datas da grade nesses períodos; as retas (V1, V3, V4) e as taxas do conservador (2 anos), do pessimista e do otimista (5 anos) também. Com passo de 12 meses cada janela tem 2, 3 ou 5 pontos, como na rodada oficial."
)
V.append(
    "- Repositórios (V2, V3 e V4): a mesma regra, com a idade do repositório em anos (datas k - 12 meses, k - 24 meses, ... em que o repositório tinha evento de pessoa residente na janela de 12 meses)."
)
V.append(
    "- Ingênua, deriva e Holt não usam a pirâmide: atualizam a série do total a cada passo. O phi do Holt é por passo, com amortecimento de 12 meses entre 0,80 e 0,98."
)
V.append("- Coorte amortecida e C1 a C7 combinam totais já previstos na mesma origem.")
V.append("")
V.append("## O que não pode ser cortado por data (ameaças à validade)")
V.append("")
V.append(
    "A carga aplica as regras sobre a coleta inteira, feita em 2026. Os eventos que chegam ao experimento já passaram por elas e a data de corte só tira eventos:"
)
V.append("")
V.append(
    "- Elegibilidade do repositório (fatia da linguagem no repositório, regra dos 50%) e a lista de repositórios vêm do dia da coleta. Um repositório que hoje é elegível entra desde o primeiro evento, e um que deixou de ser fica de fora em todas as datas."
)
V.append("- Fusão de repositórios duplicados: os grupos foram achados com os dados completos.")
V.append(
    "- Evento de API anterior ao primeiro commit da linguagem no repositório sai: usa um commit que pode ser posterior à origem."
)
V.append(
    "- Commit idêntico em mais de um repositório fica no mais antigo, decidido com todos os dados."
)
V.append(
    "- Contas apagadas (`ghost`) e bots saem. Uma conta apagada depois da origem não aparece em nenhuma data, o que reduz a população antiga."
)
V.append(
    "- Identidade do autor: a ligação do e-mail do commit ao login foi coletada depois e vale para todas as datas."
)
V.append(
    "- Repositório do primeiro evento de cada pessoa: desempate por instante na carga, com variação de até 0,1% entre cargas (afeta só a divisão dos novatos por tipo de repositório, V2 a V4)."
)
V.append("- P0 usa a vida inteira da pessoa para classificar o residente.")
(SAIDA / "vazamento.md").write_text("\n".join(V), encoding="utf-8")
print("resumo pronto")

from resumo_versao_b import escreve  # noqa: E402

escreve(SAIDA, DECISAO)
