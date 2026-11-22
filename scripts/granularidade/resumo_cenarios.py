"""Tabelas, testes, hipóteses e textos do experimento de cenários IEICE16 (S1, S2 e S3), a partir de `<saida>/unidades/`. Ver `hipoteses.md`.

Grava `pares.csv`, `testes.csv`, `decisao.csv`, `esparsidade.csv`, `intervalos.csv`, `tabelas.md`, `resumo.md` e `vazamento.md`.

Uso (na raiz do repo): .venv/bin/python scripts/granularidade/resumo_cenarios.py <saida> [--decisao clojure elixir ocaml python]
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from previsao import todos_os_metodos
from util_resumo import NOMES, ROTULO, geometrica, holm, num, rho, teste

SAIDA = Path(sys.argv[1])
DECISAO = ["clojure", "elixir", "ocaml", "python"]
if "--decisao" in sys.argv:
    DECISAO = sys.argv[sys.argv.index("--decisao") + 1 :]
UNIDADES = SAIDA / "unidades"
CENARIOS = ["S1", "S2", "S3"]
NOME_CENARIO = {
    "S1": "S1 (igual ao IEICE16, saída em 3 meses)",
    "S2": "S2 (igual à pirâmide da rodada oficial, P1, 12 meses)",
    "S3": "S3 (IEICE16 com saída em 12 meses)",
}
HORIZONTE = {"S1": "3 meses", "S2": "12 meses", "S3": "3 meses"}
BASES_R = ["coorte", "conservador", "coorte_amortecida", "C4"]
ROTULO.update({"coorte_IEICE": "coorte do IEICE16", "ingenua": "ingênua"})


def eh_intervalo(m: str) -> bool:
    return m.startswith("pessimista_") or m.startswith("otimista_")


def pontuais(cenario: str) -> list[str]:
    """Métodos com previsão pontual do cenário, na ordem das tabelas. Pessimista e otimista ficam de fora (só cobertura e largura)."""
    nomes = [m for m in todos_os_metodos() if not eh_intervalo(m)]
    return nomes + (["coorte_IEICE"] if cenario != "S2" else [])


def le(padrao: str) -> pd.DataFrame:
    arquivos = sorted(UNIDADES.glob(padrao))
    return (
        pd.concat([pd.read_csv(f) for f in arquivos], ignore_index=True)
        if arquivos
        else pd.DataFrame()
    )


pares = {c: le(f"*_{c}_pares.csv.gz") for c in CENARIOS}
pares_r = {
    c: pd.concat([le(f"*_{c}_R{r}_pares.csv.gz") for r in (1, 2, 3)], ignore_index=True)
    for c in CENARIOS
}
marcas = {c: le(f"*_{c}_marcas.csv") for c in CENARIOS}
vazamento = pd.concat([le("*_vazamento.csv")], ignore_index=True)
erros_repos, somas_repos = le("*_repos_erros.csv"), le("*_repos_somas.csv")
LINGUAS = [
    x for x in NOMES if any(x in set(pares[c]["linguagem"]) for c in CENARIOS if len(pares[c]))
]
ARQ_COMMIT = SAIDA / "commit.txt"
COMMIT = ARQ_COMMIT.read_text(encoding="utf-8").strip() if ARQ_COMMIT.exists() else "não registrado"

L = [
    "# Tabelas",
    "",
    "ABRE médio e, entre parênteses, mediano, na base de comparação de cada cenário. Em negrito o menor ABRE médio de cada linguagem (pessimista e otimista não entram no ranking).",
    "",
]


def tabela(cab: list[str], linhas: list[list[str]]) -> None:
    L.append("| " + " | ".join(cab) + " |")
    L.append("|" + "|".join(["---"] + ["---:"] * (len(cab) - 1)) + "|")
    for linha in linhas:
        L.append("| " + " | ".join(linha) + " |")
    L.append("")


# ---------------------------------------------------------------- base e medidas
medio, mediano, n_base, ks_base, perdas = {}, {}, {}, {}, []
todos_pares = []
for c in CENARIOS:
    if not len(pares[c]):
        continue
    metodos = pontuais(c)
    for lingua, g in pares[c].groupby("linguagem"):
        largo = g.pivot(index="k", columns="metodo", values="abre").reindex(
            columns=[*metodos, *[m for m in g["metodo"].unique() if eh_intervalo(m)]]
        )
        ok = largo[metodos].notna().all(axis=1)
        ks_base[(c, lingua)] = largo.index[ok]
        n_base[(c, lingua)] = int(ok.sum())
        for m in largo.columns:
            x = largo.loc[ok, m]
            medio[(c, lingua, m)] = float(x.mean()) if len(x) else np.nan
            mediano[(c, lingua, m)] = float(x.median()) if len(x) else np.nan
        for m in metodos:
            perdas.append({"cenario": c, "linguagem": lingua, "metodo": m, "pares_com_previsao": int(largo[m].notna().sum()), "pares_na_base": int(ok.sum()), "perdidos_pela_exigencia": int(largo[m].notna().sum() - ok.sum())})  # fmt: skip
        gg = g.copy()
        gg["na_base"] = gg["k"].isin(ks_base[(c, lingua)])
        todos_pares.append(gg)
pd.concat(todos_pares, ignore_index=True).to_csv(
    SAIDA / "pares.csv", index=False, float_format="%.10g"
)
pd.DataFrame(perdas).to_csv(SAIDA / "base_perdas.csv", index=False)

# ---------------------------------------------------------------- testes (alvos que não se sobrepõem: todos os recortes de cada cenário)
linhas_teste = []
for (c, lingua), ks in ks_base.items():
    if len(ks) == 0:
        continue
    g = pares[c][(pares[c]["linguagem"] == lingua) & pares[c]["k"].isin(ks)]
    largo = g.pivot(index="k", columns="metodo", values="abre")
    ps, ficha = [], []
    for m in pontuais(c)[1:]:
        ps.append(teste(largo[m].to_numpy(), largo["ingenua"].to_numpy()))
        ficha.append({"cenario": c, "linguagem": lingua, "metodo": m, "n_pares": len(largo), "p_minimo": 2.0 / 2 ** len(largo), "abre_medio_metodo": float(largo[m].mean()), "abre_medio_ingenua": float(largo["ingenua"].mean()), "pares_que_vencem_a_ingenua": int((largo[m] < largo["ingenua"]).sum())})  # fmt: skip
    ps = np.array(ps)
    ajustado = holm(ps)
    for i, f in enumerate(ficha):
        f["p"], f["p_holm"] = ps[i], ajustado[i]
        linhas_teste.append(f)
testes = pd.DataFrame(linhas_teste)
testes.to_csv(SAIDA / "testes.csv", index=False, float_format="%.6g")

# ---------------------------------------------------------------- tabelas por cenário
razao_geo, vence_media, vence_mediana, melhor = {}, {}, {}, {}
L.append("## Pares na base de comparação")
L.append("")
tabela(
    ["Cenário", *[NOMES[x] for x in LINGUAS]],
    [[NOME_CENARIO[c], *[str(n_base.get((c, x), "n/d")) for x in LINGUAS]] for c in CENARIOS],
)
for c in CENARIOS:
    colunas = [x for x in LINGUAS if n_base.get((c, x), 0) > 0]
    L.append(f"## {NOME_CENARIO[c]}")
    L.append("")
    if not colunas:
        L.append("Nenhuma linguagem tem par na base.")
        L.append("")
        continue
    metodos = pontuais(c)
    for x in colunas:
        melhor[(c, x)] = min(metodos, key=lambda m: medio[(c, x, m)])
    linhas = []
    for m in [*metodos, *sorted({m for (cc, xx, m) in medio if cc == c and eh_intervalo(m)})]:
        linha = [ROTULO.get(m, m.replace("_", " "))]
        for x in colunas:
            texto = f"{num(medio[(c, x, m)])} ({num(mediano[(c, x, m)])})"
            linha.append(f"**{texto}**" if melhor[(c, x)] == m else texto)
        linhas.append(linha)
    linhas.append(["Melhor método", *[ROTULO.get(melhor[(c, x)], melhor[(c, x)]) for x in colunas]])
    tabela(["Método", *[NOMES[x] for x in colunas]], linhas)
    for m in metodos[1:]:
        rm = [medio[(c, x, m)] / medio[(c, x, "ingenua")] for x in colunas]
        rd = [mediano[(c, x, m)] / mediano[(c, x, "ingenua")] for x in colunas]
        razao_geo[(c, m)] = (geometrica(rm), geometrica(rd))
        vence_media[(c, m)] = [x for x in colunas if medio[(c, x, m)] < medio[(c, x, "ingenua")]]
        vence_mediana[(c, m)] = [
            x for x in colunas if mediano[(c, x, m)] < mediano[(c, x, "ingenua")]
        ]
    L.append(
        "Razão sobre a ingênua (média geométrica entre as linguagens da tabela) e em quantas linguagens o método vence a ingênua na média e na mediana:"
    )
    L.append("")
    tabela(
        ["Método", "Razão da média", "Razão da mediana", "Vence na média", "Vence na mediana"],
        [
            [
                ROTULO.get(m, m),
                num(razao_geo[(c, m)][0]),
                num(razao_geo[(c, m)][1]),
                f"{len(vence_media[(c, m)])} de {len(colunas)}",
                f"{len(vence_mediana[(c, m)])} de {len(colunas)}",
            ]
            for m in metodos[1:]
        ],
    )

L.append("## Melhor método de cada linguagem")
L.append("")
for c in CENARIOS:
    linhas = [
        [
            NOMES[x],
            ROTULO.get(melhor[(c, x)], melhor[(c, x)]),
            num(medio[(c, x, melhor[(c, x)])]),
            num(medio[(c, x, "ingenua")]),
        ]
        for x in LINGUAS
        if (c, x) in melhor
    ]
    if linhas:
        L.append(f"### {NOME_CENARIO[c]}")
        L.append("")
        tabela(["Linguagem", "Melhor método", "ABRE médio", "ABRE médio da ingênua"], linhas)

# ---------------------------------------------------------------- fatorial R0 a R3
L.append(
    "## Fatorial de nascimento e parada de repositórios (R0 nenhum, R1 só nascimento, R2 só parada, R3 os dois)"
)
L.append("")
L.append(
    "ABRE médio na base do fatorial (pares em que a ingênua e as 16 combinações de método e R têm previsão). R0 é a coorte, o conservador, a coorte amortecida e C4 sem a regra de repositórios."
)
L.append("")
fatorial = {}
for c in CENARIOS:
    if not len(pares[c]):
        continue
    todos = pd.concat([pares[c], pares_r[c]], ignore_index=True)
    nomes_r = [f"{b}_R{r}" for b in BASES_R for r in range(4)]
    linhas = []
    for x in LINGUAS:
        g = todos[(todos["linguagem"] == x) & todos["metodo"].isin(["ingenua", *nomes_r])]
        if not len(g):
            continue
        largo = g.pivot(index="k", columns="metodo", values="abre").reindex(
            columns=["ingenua", *nomes_r]
        )
        ok = largo.notna().all(axis=1)
        for b in BASES_R:
            for r in range(4):
                fatorial[(c, x, b, r)] = (
                    float(largo.loc[ok, f"{b}_R{r}"].mean()) if ok.any() else np.nan
                )
        fatorial[(c, x, "ingenua", 0)] = (
            float(largo.loc[ok, "ingenua"].mean()) if ok.any() else np.nan
        )
        fatorial[(c, x, "pares", 0)] = int(ok.sum())
        for b in BASES_R:
            linhas.append(
                [
                    NOMES[x],
                    ROTULO.get(b, b.replace("_", " ")),
                    str(int(ok.sum())),
                    *[num(fatorial[(c, x, b, r)]) for r in range(4)],
                    num(fatorial[(c, x, "ingenua", 0)]),
                ]
            )
    L.append(f"### {NOME_CENARIO[c]}")
    L.append("")
    tabela(["Linguagem", "Método", "Pares", "R0", "R1", "R2", "R3", "Ingênua"], linhas)

# ---------------------------------------------------------------- projeção por repositório (S1)
L.append("## Projeção por repositório em S1")
L.append("")
repos_frageis = set()
if len(erros_repos):
    L.append(
        "Erro por repositório, ABRE do total de pares do repositório (média das origens da média e da mediana entre repositórios) e ABRE mediano por célula (repositório e faixa de idade), que é a unidade do ABRE publicado pelo IEICE16 (0,40, coorte, todos os tipos). Fração de faixas vazias: média, entre repositórios ativos e origens, da fração de faixas de 3 meses sem pares."
    )
    L.append("")
    linhas = []
    for (x, corte, metodo), g in erros_repos.groupby(["linguagem", "corte", "metodo"]):
        vazias = g["fracao_faixas_vazias"].mean()
        fragil = vazias > 0.5
        if fragil:
            repos_frageis.add((x, corte))
        linhas.append(
            [
                NOMES[x],
                "mais de 100 ativos" if corte == "mais_de_100" else "todos",
                metodo,
                str(int(g["repositorios"].mean())),
                num(g["abre_medio"].mean()),
                num(g["abre_mediano"].median()),
                num(g["abre_mediano_por_faixa"].median()),
                num(vazias),
                "sim" if fragil else "não",
            ]
        )
    tabela(
        [
            "Linguagem",
            "Corte",
            "Método",
            "Repositórios por origem",
            "ABRE médio",
            "ABRE mediano",
            "ABRE mediano por célula",
            "Faixas vazias",
            "Frágil",
        ],
        linhas,
    )
if len(somas_repos):
    L.append(
        "Soma dos repositórios para a linguagem (pares convertidos em pessoas pela razão pessoas por pares da origem), ABRE mediano entre origens. Erro em pares e erro da conversão separados: (1 + erro em pessoas) = (1 + erro em pares) x (1 + erro da conversão), com erro da conversão = razão da origem / razão do alvo - 1."
    )
    L.append("")
    s = somas_repos.copy()
    s["e_pares"] = s["pares_previstos"] / s["pares_reais"] - 1
    s["e_conv"] = s["razao_origem"] / s["razao_alvo"] - 1
    s["e_pessoas"] = s["pessoas_previstas"] / s["pessoas_reais"] - 1
    s["abre_pares"] = np.abs(s["e_pares"]) / np.minimum(1, 1 + s["e_pares"])
    s["abre_conv"] = np.abs(s["e_conv"]) / np.minimum(1, 1 + s["e_conv"])
    s["abre_pessoas"] = np.abs(s["e_pessoas"]) / np.minimum(1, 1 + s["e_pessoas"])
    s.to_csv(SAIDA / "repos_somas_com_erros.csv", index=False, float_format="%.8g")
    linhas = []
    for (x, corte, metodo, r), g in s.groupby(["linguagem", "corte", "metodo", "r"]):
        linhas.append(
            [
                NOMES[x],
                "mais de 100 ativos" if corte == "mais_de_100" else "todos",
                metodo,
                r,
                num(g["abre_pares"].median()),
                num(g["abre_conv"].median()),
                num(g["abre_pessoas"].median()),
                num(g["e_pares"].median()),
                num(g["e_conv"].median()),
            ]
        )
    tabela(
        [
            "Linguagem",
            "Corte",
            "Método",
            "R",
            "ABRE em pares",
            "ABRE da conversão",
            "ABRE em pessoas",
            "Viés em pares",
            "Viés da conversão",
        ],
        linhas,
    )
    s1 = (
        pares["S1"][
            pares["S1"]["metodo"].isin(["ingenua", "coorte_IEICE", "coorte_V0", "conservador_V0"])
        ]
        if len(pares["S1"])
        else pd.DataFrame()
    )
    if len(s1):
        L.append(
            "A linguagem inteira em S1, nos mesmos recortes (ABRE mediano em pessoas), para comparar com a soma:"
        )
        L.append("")
        linhas = []
        for x in LINGUAS:
            ks = set(s[s["linguagem"] == x]["k"])
            g = s1[(s1["linguagem"] == x) & s1["k"].isin(ks)]
            if len(g):
                linhas.append(
                    [
                        NOMES[x],
                        *[
                            num(g[g["metodo"] == m]["abre"].median())
                            for m in ["ingenua", "coorte_IEICE", "coorte_V0", "conservador_V0"]
                        ],
                    ]
                )
        tabela(["Linguagem", "Ingênua", "Coorte IEICE16", "Coorte V0", "Conservador V0"], linhas)

# ---------------------------------------------------------------- comparação dos cenários
L.append("## Comparação dos três cenários")
L.append("")
metodos_fixos = ["ingenua", "coorte_V0", "conservador_V0"]
linhas = []
for c in CENARIOS:
    if not any((c, m) in razao_geo for m in metodos_fixos[1:]):
        continue
    ranking = sorted(
        [m for m in pontuais(c)[1:] if (c, m) in razao_geo and not np.isnan(razao_geo[(c, m)][0])],
        key=lambda m: razao_geo[(c, m)][0],
    )
    for m in [*metodos_fixos[1:], *[r for r in ranking[:3] if r not in metodos_fixos]]:
        if (c, m) in razao_geo:
            linhas.append(
                [
                    NOME_CENARIO[c],
                    ROTULO.get(m, m),
                    num(razao_geo[(c, m)][0]),
                    num(razao_geo[(c, m)][1]),
                    f"{len(vence_media[(c, m)])} de {len(n_base_langs := [x for x in LINGUAS if n_base.get((c, x), 0) > 0])}",
                    f"{len(vence_mediana[(c, m)])} de {len(n_base_langs)}",
                ]
            )
tabela(
    [
        "Cenário",
        "Método (coorte V0, conservador V0 e os três melhores pela razão da média)",
        "Razão da média sobre a ingênua",
        "Razão da mediana",
        "Vence a ingênua na média",
        "Vence na mediana",
    ],
    linhas,
)

# ---------------------------------------------------------------- intervalos e esparsidade
interv = []
for c in CENARIOS:
    if not len(pares[c]):
        continue
    for x in LINGUAS:
        g = pares[c][(pares[c]["linguagem"] == x) & pares[c]["k"].isin(ks_base.get((c, x), []))]
        if not len(g):
            continue
        largo = g.pivot(index="k", columns="metodo", values="previsto")
        real = g[g["metodo"] == "ingenua"].set_index("k")["real"]
        for v in ["V0", "V1", "V2", "V3a", "V3b", "V4a", "V4b"]:
            pess, otim = largo[f"pessimista_{v}"], largo[f"otimista_{v}"]
            interv.append({"cenario": c, "linguagem": x, "variante": v, "pares": len(largo), "cobertura": float(((pess <= real) & (real <= otim)).mean()), "largura_relativa_mediana": float(((otim - pess) / largo["ingenua"]).median())})  # fmt: skip
interv = pd.DataFrame(interv)
interv.to_csv(SAIDA / "intervalos.csv", index=False, float_format="%.6g")
esp = pd.concat(
    [
        marcas[c]
        .groupby("linguagem")[
            ["esp_faixas_vazias", "esp_razoes_indefinidas", "esp_faixas_bloqueantes"]
        ]
        .mean()
        .assign(cenario=c)
        .reset_index()
        for c in CENARIOS
        if len(marcas[c])
    ],
    ignore_index=True,
)
esp.to_csv(SAIDA / "esparsidade.csv", index=False, float_format="%.4f")
L.append("## Intervalo pessimista-otimista da V0 e esparsidade das faixas")
L.append("")
linhas = []
for c in CENARIOS:
    for x in LINGUAS:
        i = (
            interv[
                (interv["cenario"] == c) & (interv["linguagem"] == x) & (interv["variante"] == "V0")
            ]
            if len(interv)
            else interv
        )
        e = esp[(esp["cenario"] == c) & (esp["linguagem"] == x)]
        if len(i) and len(e):
            linhas.append(
                [
                    c,
                    NOMES[x],
                    num(i["cobertura"].iloc[0]),
                    num(i["largura_relativa_mediana"].iloc[0]),
                    num(e["esp_faixas_vazias"].iloc[0]),
                    num(e["esp_razoes_indefinidas"].iloc[0]),
                    num(e["esp_faixas_bloqueantes"].iloc[0]),
                ]
            )
tabela(
    [
        "Cenário",
        "Linguagem",
        "Cobertura",
        "Largura relativa mediana",
        "Faixas vazias",
        "Razões indefinidas",
        "Faixas com gente sem razão",
    ],
    linhas,
)
(SAIDA / "tabelas.md").write_text("\n".join(L), encoding="utf-8")

# ---------------------------------------------------------------- hipóteses
dec = []
tres = min(3, len(DECISAO))


def n_menor(c: str, m: str, ref: str = "ingenua", estat: dict | None = None) -> int:
    estat = estat or medio
    return sum(int(estat.get((c, x, m), np.nan) < estat.get((c, x, ref), np.nan)) for x in DECISAO)


for c, coorte in [("S1", "coorte_IEICE"), ("S2", "coorte_V0"), ("S3", "coorte_IEICE")]:
    if (c, DECISAO[0], coorte) not in medio:
        continue
    nm, nd = n_menor(c, coorte), n_menor(c, coorte, estat=mediano)
    dec.append({"hipotese": f"HS1 {c}", "status": "sustentada" if nm >= tres and nd >= tres else ("parcial" if nm >= tres or nd >= tres else "não sustentada"), "detalhe": f"A coorte ({ROTULO.get(coorte, coorte)}) vence a ingênua na média em {nm} de {len(DECISAO)} linguagens e na mediana em {nd}"})  # fmt: skip
# HS2 e HS3: por repositório em S1
if len(erros_repos):
    vitorias, celula = {}, {}
    for corte in CORTES if (CORTES := ["mais_de_100", "todos"]) else []:
        n = 0
        for x in DECISAO:
            g = erros_repos[(erros_repos["linguagem"] == x) & (erros_repos["corte"] == corte)]
            a, b = (
                g[g["metodo"] == "coorte"]["abre_mediano"].median(),
                g[g["metodo"] == "ingenua"]["abre_mediano"].median(),
            )
            n += int(a < b)
        vitorias[corte] = n
        c100 = erros_repos[
            (erros_repos["corte"] == corte)
            & erros_repos["linguagem"].isin(DECISAO)
            & (erros_repos["metodo"] == "coorte")
        ]["abre_mediano_por_faixa"].median()
        celula[corte] = c100
    dec.append({"hipotese": "HS2", "status": "sustentada" if all(v >= tres for v in vitorias.values()) else ("parcial" if any(v >= tres for v in vitorias.values()) else "não sustentada"), "detalhe": "; ".join(f"corte {k.replace('_', ' ')}: a coorte tem ABRE mediano por repositório menor que a ingênua em {v} de {len(DECISAO)} linguagens" for k, v in vitorias.items())})  # fmt: skip
    ok3 = (
        abs(celula["mais_de_100"] - 0.40) <= 0.10 if not np.isnan(celula["mais_de_100"]) else False
    )
    dec.append({"hipotese": "HS3", "status": "sustentada" if ok3 else "não sustentada", "detalhe": f"ABRE mediano por célula da coorte com mais de 100 contribuidores: {num(celula['mais_de_100'])} (publicado: 0,40; a regra pede diferença de até 0,10). Todos os repositórios: {num(celula['todos'])}"})  # fmt: skip
# HS4: ranking de S1 contra S3
rhos = {}
for x in DECISAO:
    ms = [
        m
        for m in pontuais("S1")[1:]
        if (("S1", x, m) in medio)
        and (("S3", x, m) in medio)
        and not np.isnan(medio[("S1", x, m)])
        and not np.isnan(medio[("S3", x, m)])
    ]
    if len(ms) >= 5:
        rhos[x] = rho([medio[("S1", x, m)] for m in ms], [medio[("S3", x, m)] for m in ms])
muda = [x for x, r in rhos.items() if r < 0.9]
dec.append({"hipotese": "HS4", "status": "sustentada" if len(muda) >= tres else "não sustentada", "detalhe": "Spearman entre o ranking de S1 e o de S3 por linguagem: " + ", ".join(f"{NOMES[x]} {num(r, 2)}" for x, r in rhos.items()) + f". O ranking muda (Spearman abaixo de 0,9) em {len(muda)} de {len(rhos)}"})  # fmt: skip
# HS5: S2 reproduz a granularidade
conf = SAIDA / "conferencia_s2.txt"
linhas_conf = conf.read_text(encoding="utf-8").strip().splitlines() if conf.exists() else []
zero_diferentes = bool(linhas_conf) and all(
    linha.split(", ")[-1].startswith("0 diferentes") for linha in linhas_conf
)
dec.append({"hipotese": "HS5", "status": "sustentada" if zero_diferentes else ("não sustentada" if linhas_conf else "não verificada"), "detalhe": conf.read_text(encoding="utf-8").strip().replace("\n", "; ") if conf.exists() else "Sem o arquivo conferencia_s2.txt"})  # fmt: skip
# HS6: algum método vence a ingênua nas quatro linguagens
for c in CENARIOS:
    achados = [
        m
        for m in pontuais(c)[1:]
        if (c, m) in vence_media and all(x in vence_media[(c, m)] for x in DECISAO)
    ]
    achados_md = [m for m in achados if all(x in vence_mediana[(c, m)] for x in DECISAO)]
    mais = max(
        (
            (len([x for x in vence_media[(c, m)] if x in DECISAO]), m)
            for m in pontuais(c)[1:]
            if (c, m) in vence_media
        ),
        default=(0, "nenhum"),
    )
    dec.append({"hipotese": f"HS6 {c}", "status": "sustentada" if achados else "não sustentada", "detalhe": f"{len(achados)} métodos vencem a ingênua na média nas {len(DECISAO)} linguagens ({', '.join(ROTULO.get(m, m) for m in achados[:6]) or 'nenhum'}); {len(achados_md)} também na mediana. O que vence em mais linguagens: {ROTULO.get(mais[1], mais[1])} ({mais[0]})"})  # fmt: skip
# HS7: nascimento, parada e os dois
for c in CENARIOS:
    for b in ["coorte", "conservador"]:
        partes = []
        for r, nome in [(1, "nascimento"), (2, "parada"), (3, "os dois")]:
            n = sum(
                int(fatorial.get((c, x, b, r), np.nan) < fatorial.get((c, x, b, 0), np.nan))
                for x in DECISAO
            )
            partes.append((nome, n))
        dec.append({"hipotese": f"HS7 {c} {b}", "status": "sustentada" if all(n >= tres for _, n in partes) else ("parcial" if any(n >= tres for _, n in partes) else "não sustentada"), "detalhe": "; ".join(f"{nome}: ABRE médio menor que R0 em {n} de {len(DECISAO)} linguagens" for nome, n in partes)})  # fmt: skip
# HS8: soma por repositório com nascimento e parada
if len(somas_repos):
    partes = []
    for metodo in ["coorte", "conservador"]:
        n = 0
        for x in DECISAO:
            g = s[(s["linguagem"] == x) & (s["corte"] == "todos") & (s["metodo"] == metodo)]
            n += int(
                g[g["r"] == "R3"]["abre_pares"].median() < g[g["r"] == "R0"]["abre_pares"].median()
            )
        partes.append((metodo, n))
    dec.append({"hipotese": "HS8", "status": "sustentada" if all(n >= tres for _, n in partes) else ("parcial" if any(n >= tres for _, n in partes) else "não sustentada"), "detalhe": "; ".join(f"{m}: a soma com nascimento e parada (R3) tem ABRE mediano em pares menor que R0 em {n} de {len(DECISAO)} linguagens" for m, n in partes)})  # fmt: skip
    n9 = 0
    for x in DECISAO:
        g = s[
            (s["linguagem"] == x)
            & (s["corte"] == "todos")
            & (s["metodo"] == "coorte")
            & (s["r"] == "R0")
        ]
        ref = pares["S1"][
            (pares["S1"]["linguagem"] == x)
            & (pares["S1"]["metodo"] == "coorte_IEICE")
            & pares["S1"]["k"].isin(set(g["k"]))
        ]["abre"].median()
        n9 += int(g["abre_pessoas"].median() < ref)
    dec.append({"hipotese": "HS9", "status": "sustentada" if n9 >= tres else "não sustentada", "detalhe": f"A soma dos repositórios (coorte, todos, R0) tem ABRE mediano em pessoas menor que o da coorte da linguagem inteira em S1 em {n9} de {len(DECISAO)} linguagens"})  # fmt: skip
dec = pd.DataFrame(dec)
dec.to_csv(SAIDA / "decisao.csv", index=False)

# ---------------------------------------------------------------- resumo
ENUNCIADO = {
    "HS1": "A coorte vence a ingênua na média e na mediana", "HS2": "Por repositório a coorte vence a ingênua na mediana", "HS3": "O ABRE mediano por célula da coorte fica perto de 0,40 do IEICE16",
    "HS4": "Mudar a saída de 3 para 12 meses (S1 para S3) muda o ranking dos métodos", "HS5": "S2 reproduz a versão A de projecao-granularidade", "HS6": "Algum método vence a ingênua na média nas quatro linguagens",
    "HS7": "Nascimento, parada e os dois melhoram a coorte e o conservador", "HS8": "A soma por repositório melhora com nascimento e parada", "HS9": "A soma por repositório erra menos que a coorte da linguagem inteira",
}  # fmt: skip


def linha_dec(r: pd.Series) -> str:
    base = r["hipotese"].split()[0]
    return f"- {r['hipotese']}, {ENUNCIADO[base]}: {r['status']}. {r['detalhe']}."


R = [
    "# Resumo: cenários de pirâmide do IEICE16 (RQ3)",
    "",
    "Regras escritas antes de rodar em `hipoteses.md`. Garantia contra vazamento em `vazamento.md`. Tabelas completas em `tabelas.md`.",
    "",
    f"Código rodado na VM: commit `{COMMIT}` (`scripts/granularidade/`).",
    "",
]
R.append("## Respostas diretas")
R.append("")
for _, r in dec[dec["hipotese"].str.startswith("HS1")].iterrows():
    R.append(linha_dec(r))
for prefixo in ["HS2", "HS3", "HS4", "HS5"]:
    for _, r in dec[dec["hipotese"] == prefixo].iterrows():
        R.append(linha_dec(r))
R.append("")
R.append(
    "- Método que vence a ingênua na média em mais linguagens, por cenário (e se algum vence nas quatro):"
)
for _, r in dec[dec["hipotese"].str.startswith("HS6")].iterrows():
    R.append("  - " + linha_dec(r)[2:])
R.append("- Nascimento, parada ou os dois melhoram a coorte e o conservador?")
for _, r in dec[dec["hipotese"].str.startswith("HS7")].iterrows():
    R.append("  - " + linha_dec(r)[2:])
R.append("")
R.append("## Hipóteses")
R.append("")
for _, r in dec.iterrows():
    R.append(linha_dec(r))
R.append("")
R.append("## Base, marcas e avisos")
R.append("")
R.append(
    "- Pares na base de comparação por cenário e linguagem: `tabelas.md`. Métodos que perdem pares pela exigência de todos terem previsão: `base_perdas.csv`."
)
for c in CENARIOS:
    if len(marcas[c]):
        m = marcas[c]
        R.append(
            f"- {c}: Holt substituído pela ingênua em {int(m['holt_ingenua'].sum())} de {len(m)} origens; previsões negativas viradas para zero: {int(m['negativas'].sum())} de {int(m['avaliacoes_negativas'].sum())}."
        )
if repos_frageis:
    R.append(
        "- Projeção por repositório marcada como frágil (mais da metade das faixas vazias): "
        + "; ".join(
            f"{NOMES[x]}, {'mais de 100 ativos' if c == 'mais_de_100' else 'todos'}"
            for x, c in sorted(repos_frageis)
        )
        + "."
    )
R.append(
    "- Alvos que não se sobrepõem: todos os recortes de S1 e S3 (horizonte de 3 meses) e um por ano em S2. Número de pares e menor p possível de cada teste: `testes.csv`. Holm dentro de cada linguagem e cenário."
)
if len(testes):
    R.append(
        f"- Testes com Holm abaixo de 0,05: {int((testes['p_holm'] < 0.05).sum())} de {int(testes['p'].notna().sum())} com p definido."
    )
R.append(
    "- Diferença em relação ao IEICE16: a rodada oficial não tem o lado (código ou conversa) de cada evento, então S1 e S3 rodam sem lado."
)
(SAIDA / "resumo.md").write_text("\n".join(R), encoding="utf-8")

# ---------------------------------------------------------------- vazamento.md
V = [
    "# Garantia contra vazamento",
    "",
    "## Estrutura",
    "",
    "- `estado.constroi_estado` e `repos_ieice.constroi_repos` descartam todo evento depois do corte e conferem com assert que a maior data restante é no máximo o corte. Cada valor de um recorte depende só de eventos até o fim do recorte.",
    "- `previsao.preve_estado` e `repos_ieice.preve_repos` recebem só o estado cortado na origem (`corta_estado`, `corta_repos`) e o histórico de previsões anteriores. Não abrem arquivo. Asserts conferem que nenhuma série passa da origem.",
    "- O alvo real é calculado em `cenarios.py` e `repos_ieice.py`, depois da previsão. Os erros de origens anteriores (coorte amortecida, C6, C7) só usam origens cujo alvo já foi observado na origem atual.",
    "- A probabilidade de parada de repositório e a taxa sem parada usam só a última transição observada (e as 8 anteriores no conservador). As pessoas que ficaram sem repositório entre dois recortes entram no recorte seguinte, que é quando se conhecem.",
    "- S2 e P1: a pessoa é residente a partir do bloco da segunda ocasião (`pessoas.segunda`, ignorada se depois do corte). P0 (vida inteira) não é usado.",
    "",
]
V.append("## Teste")
V.append("")
V.append(
    "Para cada linguagem e cenário, 5 origens espalhadas entre a primeira com 5 anos de histórico e a última (e na projeção por repositório, 5 origens também). A previsão com o estado da produção, com o estado construído só com os eventos até t e com o construído recebendo os eventos até o alvo precisa sair igual (tolerância relativa de 1e-9) e as séries precisam ser idênticas. Controle de eventos futuros: os eventos entre t e o alvo entram com a data t, e a previsão precisa mudar. Em S2 há também o controle de promoções a residente. O teste só vale onde o controle difere."
)
V.append("")
if len(vazamento):
    v = vazamento.copy()
    partes = v["unidade"].str.split("_")
    v["linguagem"], v["cenario"] = partes.str[0], partes.str[1]
    V.append(
        "| Linguagem | Cenário | Origens | Estados iguais | Maior diferença relativa | Controle de eventos futuros difere em | Teste vale |"
    )
    V.append("|---|---|---:|---|---:|---:|---|")
    tudo_vale = True
    for (x, c), g in v.groupby(["linguagem", "cenario"]):
        dif = int(g["controle_eventos_futuros_difere"].sum())
        vale = dif > 0
        tudo_vale = tudo_vale and vale
        maior = g["maior_diferenca_relativa"].max() if "maior_diferenca_relativa" in g else np.nan
        V.append(
            f"| {NOMES[x]} | {c} | {len(g)} | {'sim' if g['estados_iguais'].all() else 'NÃO'} | {num(maior, 0) if pd.isna(maior) else f'{maior:.1e}'} | {dif} | {'sim' if vale else 'NÃO: teste sem poder'} |"
        )
    V.append("")
    limpo = bool(vazamento["estados_iguais"].all()) and bool(
        (vazamento["maior_diferenca_relativa"].fillna(0) < 1e-9).all()
    )
    V.append(
        f"Resultado: {'nenhum vazamento encontrado' if limpo else 'HÁ DIFERENÇAS, ver a tabela'} em {len(vazamento)} origens testadas. Teste válido em todos os cenários: {'sim' if tudo_vale else 'não, ver a tabela'}."
    )
else:
    V.append("O teste ainda não rodou com dados reais.")
V.append("")
V.append("## O que não pode ser cortado por data (ameaças à validade)")
V.append("")
V.append(
    "A carga aplica as regras sobre a coleta inteira, feita em 2026, e a data de corte só tira eventos:"
)
V.append("")
for t in [
    "Elegibilidade do repositório (fatia da linguagem, regra dos 50%) e a lista de repositórios vêm do dia da coleta.",
    "A fusão de repositórios duplicados foi decidida com os dados completos.",
    "Evento de API anterior ao primeiro commit da linguagem no repositório sai: usa um commit que pode ser posterior à origem.",
    "Commit idêntico em mais de um repositório fica no mais antigo, decidido com todos os dados.",
    "Contas apagadas e bots saem. Uma conta apagada depois da origem não aparece em nenhuma data.",
    "A ligação do e-mail do commit ao login foi coletada depois e vale para todas as datas.",
    "O repositório do primeiro evento de cada pessoa tem desempate por instante na carga, com variação de até 0,1% entre cargas (afeta só a divisão dos novatos por tipo de repositório, V2 a V4).",
    "Falta o lado (código ou conversa) de cada evento: S1 e S3 rodam sem lado.",
]:
    V.append(f"- {t}")
(SAIDA / "vazamento.md").write_text("\n".join(V), encoding="utf-8")
print("resumo pronto")
