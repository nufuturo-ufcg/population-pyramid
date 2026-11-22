"""Versão B (faixas da largura do passo) contra a versão A: tabelas, testes, esparsidade, hipóteses HB1 a HB4 e respostas. Ver `hipoteses.md`.

Chamado no fim de `resumo_granularidade.py`. Acrescenta uma seção a `tabelas.md`, `resumo.md` e `vazamento.md` e grava `testes_ab.csv`, `decisao_b.csv`, `esparsidade.csv`
e `ab_por_faixa.csv`. A base AB exige todos os métodos da A e da B com previsão; a comparação A contra B só usa essa base.
"""

from pathlib import Path

import numpy as np
import pandas as pd
from previsao import metodos_b
from util_resumo import (
    FAIXAS,
    HONESTAS,
    METODOS,
    METODOS_B,
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

PASSOS_CURTOS = [p for p in PASSOS if p != 12]
COM_PAR = [m for m in METODOS if m + "_B" in set(METODOS_B)]  # métodos da A que têm versão B


def tabela_md(linhas_md: list[str], cab: list[str], linhas: list[list[str]]) -> None:
    linhas_md.append("| " + " | ".join(cab) + " |")
    linhas_md.append("|" + "|".join(["---"] + ["---:"] * (len(cab) - 1)) + "|")
    for linha in linhas:
        linhas_md.append("| " + " | ".join(linha) + " |")
    linhas_md.append("")


def melhor_combinacao(
    medias: dict, pop: str, passo: float, lingua: str, sufixo: str
) -> tuple[str, float]:
    valores = {c: medias.get((pop, passo, lingua, c + sufixo), np.nan) for c in HONESTAS}
    validos = {c: v for c, v in valores.items() if not np.isnan(v)}
    if not validos:
        return "n/d", np.nan
    c = min(validos, key=validos.get)
    return c, validos[c]


def escreve(saida: Path, decisao: list[str]) -> None:
    pasta = saida / "unidades"
    pares = pd.concat(
        [pd.read_csv(f) for f in sorted(pasta.glob("*_pares.csv.gz"))], ignore_index=True
    )
    pares = pares[pares["populacao"].isin(POPS)]
    faixas = pd.concat(
        [pd.read_csv(f) for f in sorted(pasta.glob("*_faixas.csv.gz"))], ignore_index=True
    )
    faixas = faixas[faixas["populacao"].isin(POPS)]
    marcas_b = [pd.read_csv(f) for f in sorted(pasta.glob("*_B_marcas.csv"))]
    marcas_a = [
        pd.read_csv(f)
        for f in sorted(pasta.glob("*_marcas.csv"))
        if not f.name.endswith("_B_marcas.csv")
    ]
    marcas_a = [m for m in marcas_a if m["populacao"].iloc[0] in POPS]
    todas = METODOS + METODOS_B
    linguas = [x for x in NOMES if x in set(pares["linguagem"])] + sorted(
        set(pares["linguagem"]) - set(NOMES)
    )
    if not marcas_b:
        (saida / "resumo.md").write_text(
            (saida / "resumo.md").read_text(encoding="utf-8")
            + "\n## Versão B\n\nA versão B ainda não rodou.\n",
            encoding="utf-8",
        )
        return

    # ------------------------------------------------------------ base AB
    medias, n_ab, ks_ab, mediana = {}, {}, {}, {}
    for (pop, passo, lingua), g in pares.groupby(["populacao", "passo_meses", "linguagem"]):
        largo = g.pivot(index="k", columns="metodo", values="abre").reindex(columns=todas)
        ok = largo.notna().all(axis=1)
        ks_ab[(pop, passo, lingua)] = largo.index[ok]
        n_ab[(pop, passo, lingua)] = int(ok.sum())
        for m in todas:
            x = largo.loc[ok, m]
            medias[(pop, passo, lingua, m)] = float(x.mean()) if len(x) else np.nan
            mediana[(pop, passo, lingua, m)] = float(x.median()) if len(x) else np.nan
    com_base = lambda pop, passo: [x for x in decisao if n_ab.get((pop, passo, x), 0) > 0]  # noqa: E731

    L = ["", "## Versão B, faixas da largura do passo (base AB)", "",
         "Base AB: pares em que todos os métodos das duas versões têm previsão. Cada linha da B fica logo abaixo da linha da A. Em negrito o menor de cada linguagem. As tabelas de cima (base A) não mudaram.", ""]  # fmt: skip
    L.append("### Pares na base AB")
    L.append("")
    linhas = []
    for pop in POPS:
        for passo in PASSOS:
            linhas.append(
                [
                    NOME_POP[pop],
                    NOME_PASSO[passo],
                    *[str(n_ab.get((pop, passo, x), "n/d")) for x in linguas],
                ]
            )
    tabela_md(L, ["População", "Passo", *[NOMES[x] for x in linguas]], linhas)

    # ------------------------------------------------------------ esparsidade
    esp = []
    for lista, versao in [(marcas_a, "A"), (marcas_b, "B")]:
        for m in lista:
            for (pop, passo, lingua), g in m.groupby(["populacao", "passo_meses", "linguagem"]):
                ks = ks_ab.get((pop, passo, lingua), [])
                usados = g[g["k"].isin(ks)] if len(ks) else g
                esp.append({"versao": versao, "populacao": pop, "passo_meses": passo, "linguagem": lingua, "origens": len(usados), "na_base_ab": bool(len(ks)),
                            "faixas_vazias": usados["esp_faixas_vazias"].mean(), "razoes_indefinidas": usados["esp_razoes_indefinidas"].mean(),
                            "faixas_bloqueantes": usados["esp_faixas_bloqueantes"].mean()})  # fmt: skip
    esp = pd.DataFrame(esp)
    esp.to_csv(saida / "esparsidade.csv", index=False, float_format="%.4f")
    fragil = set()
    for _, r in esp[esp["versao"] == "B"].iterrows():
        if r["faixas_vazias"] > 0.5:
            fragil.add((r["populacao"], r["passo_meses"], r["linguagem"]))

    # ------------------------------------------------------------ tabelas por passo e população
    for pop in POPS:
        for passo in PASSOS:
            colunas = [x for x in linguas if n_ab.get((pop, passo, x), 0) > 0]
            L.append(f"### {NOME_POP[pop]}, passo de {NOME_PASSO[passo]}")
            L.append("")
            if not colunas:
                L.append("Nenhuma linguagem tem par na base AB.")
                L.append("")
                continue
            linhas_ab = []
            for m in METODOS:
                linhas_ab.append((m, ROTULO[m]))
                if m + "_B" in set(METODOS_B):
                    linhas_ab.append((m + "_B", ROTULO[m + "_B"]))
            melhor = {x: min(todas, key=lambda m: medias[(pop, passo, x, m)]) for x in colunas}
            linhas = []
            for m, rotulo in linhas_ab:
                linha = [rotulo]
                for x in colunas:
                    texto = num(medias[(pop, passo, x, m)])
                    linha.append(f"**{texto}**" if m == melhor[x] else texto)
                linhas.append(linha)
            linhas.append(["Melhor método", *[ROTULO[melhor[x]] for x in colunas]])
            linhas.append(
                [
                    "Resultado frágil (mais da metade das faixas finas vazias na B)",
                    *["sim" if (pop, passo, x) in fragil else "não" for x in colunas],
                ]
            )
            tabela_md(L, ["Método", *[NOMES[x] for x in colunas]], linhas)

    # ------------------------------------------------------------ A contra B
    L.append("### A contra B: ABRE médio do total")
    L.append("")
    comparacao = {}
    for pop in POPS:
        linhas = []
        for passo in PASSOS:
            for x in linguas:
                if n_ab.get((pop, passo, x), 0) == 0:
                    continue
                ca, va = melhor_combinacao(medias, pop, passo, x, "")
                cb, vb = melhor_combinacao(medias, pop, passo, x, "_B")
                linha = [
                    NOME_PASSO[passo],
                    NOMES[x],
                    str(n_ab[(pop, passo, x)]),
                    num(medias[(pop, passo, x, "ingenua")]),
                ]
                for m in ["coorte_V0", "coorte_amortecida", "hp3"]:
                    linha += [
                        num(medias[(pop, passo, x, m)]),
                        num(medias[(pop, passo, x, m + "_B")]),
                    ]
                linha += [f"{ca} {num(va)}", f"{cb} {num(vb)}"]
                linhas.append(linha)
                comparacao[(pop, passo, x)] = (ca, va, cb, vb)
        L.append(f"#### {NOME_POP[pop]}")
        L.append("")
        tabela_md(L, ["Passo", "Linguagem", "Pares", "Ingênua", "Coorte V0 A", "Coorte V0 B", "Coorte amortecida A", "Coorte amortecida B", "Hamilton-Perry 3 A", "Hamilton-Perry 3 B", "Melhor combinação A", "Melhor combinação B"], linhas)  # fmt: skip

    # ------------------------------------------------------------ A contra B por faixa
    fx = []
    for (pop, passo, lingua), g in faixas.groupby(["populacao", "passo_meses", "linguagem"]):
        ks = ks_ab.get((pop, passo, lingua), [])
        na_base = g[g["k"].isin(ks)]
        for (m, f), h in na_base.groupby(["metodo", "faixa"]):
            fx.append(
                {
                    "populacao": pop,
                    "passo_meses": passo,
                    "linguagem": lingua,
                    "metodo": m,
                    "faixa": f,
                    "abre_medio": h["abre"].mean(),
                }
            )
    fx = pd.DataFrame(fx)
    fx.to_csv(saida / "ab_por_faixa.csv", index=False, float_format="%.6g")
    L.append("### A contra B por faixa: coorte V0")
    L.append("")
    L.append(
        "Número de linguagens (entre as de decisão com base AB) em que o ABRE médio da coorte V0 da B é menor que o da A. A ingênua, a coorte amortecida, o Hamilton-Perry e as combinações não têm previsão por faixa. Os valores estão em `ab_por_faixa.csv`."
    )
    L.append("")
    faixa_menor = {}
    for pop in POPS:
        linhas = []
        for f in range(6):
            linha = [FAIXAS[f]]
            for passo in PASSOS_CURTOS:
                n_menor, n_total = 0, 0
                for x in com_base(pop, passo):
                    s = fx[
                        (fx["populacao"] == pop)
                        & (fx["passo_meses"] == passo)
                        & (fx["linguagem"] == x)
                        & (fx["faixa"] == f)
                    ].set_index("metodo")["abre_medio"]
                    if (
                        "coorte_V0" in s.index
                        and "coorte_V0_B" in s.index
                        and not (np.isnan(s["coorte_V0"]) or np.isnan(s["coorte_V0_B"]))
                    ):
                        n_total += 1
                        n_menor += int(s["coorte_V0_B"] < s["coorte_V0"])
                faixa_menor[(pop, f, passo)] = n_menor
                linha.append(f"{n_menor} de {n_total}")
            linhas.append(linha)
        L.append(f"#### {NOME_POP[pop]}")
        L.append("")
        tabela_md(L, ["Faixa", *[NOME_PASSO[p] for p in PASSOS_CURTOS]], linhas)

    # ------------------------------------------------------------ testes B contra A
    linhas_teste = []
    for (pop, passo, lingua), ks in ks_ab.items():
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
        for mb in metodos_b():
            ma = mb[:-2]
            ps.append(teste(largo[mb].to_numpy(), largo[ma].to_numpy()))
            ficha.append({"populacao": pop, "passo_meses": passo, "linguagem": lingua, "metodo": ma, "n_pares": len(largo), "p_minimo": 2.0 / 2 ** len(largo),
                          "abre_medio_a": float(largo[ma].mean()), "abre_medio_b": float(largo[mb].mean()), "pares_em_que_b_vence": int((largo[mb] < largo[ma]).sum())})  # fmt: skip
        ps = np.array(ps)
        ajustado = holm(ps)
        for i, f in enumerate(ficha):
            f["p"], f["p_holm"] = ps[i], ajustado[i]
            linhas_teste.append(f)
    testes = pd.DataFrame(linhas_teste)
    testes.to_csv(saida / "testes_ab.csv", index=False, float_format="%.6g")
    L.append("### Wilcoxon pareado, B contra A")
    L.append("")
    L.append(
        "Por população e passo, entre as linguagens com base AB: testes com p definido e quantos passam o Holm (a correção é dentro de cada linguagem, passo e população). Menor p possível e número de pares em `testes_ab.csv`. Origens próximas se sobrepõem no alvo, então os p são indicativos."
    )
    L.append("")
    linhas = []
    for pop in POPS:
        for passo in PASSOS_CURTOS:
            t = (
                testes[(testes["populacao"] == pop) & (testes["passo_meses"] == passo)]
                if len(testes)
                else testes
            )
            if len(t) == 0:
                continue
            linhas.append(
                [
                    NOME_POP[pop],
                    NOME_PASSO[passo],
                    str(int(t["n_pares"].min())),
                    str(int(t["p"].notna().sum())),
                    str(int((t["p_holm"] < 0.05).sum())),
                    str(int((t["abre_medio_b"] < t["abre_medio_a"]).sum())),
                ]
            )
    tabela_md(
        L,
        [
            "População",
            "Passo",
            "Menor número de pares",
            "Testes com p",
            "Passam o Holm",
            "Métodos em que a B tem ABRE médio menor",
        ],
        linhas,
    )

    # ------------------------------------------------------------ esparsidade (tabela)
    L.append("### Esparsidade das faixas finas")
    L.append("")
    L.append(
        "Médias nas origens da base AB (todas as origens se a base é vazia). Faixas vazias: fração das faixas finas até 8 anos com zero pessoas na origem. Razões indefinidas: fração das razões de permanência sem valor. Bloqueantes: fração das faixas com gente e sem razão (tornam o total indefinido). Frágil: mais da metade das faixas finas vazia na B."
    )
    L.append("")
    for pop in POPS:
        linhas = []
        for passo in PASSOS:
            for x in linguas:
                a = esp[
                    (esp["versao"] == "A")
                    & (esp["populacao"] == pop)
                    & (esp["passo_meses"] == passo)
                    & (esp["linguagem"] == x)
                ]
                b = esp[
                    (esp["versao"] == "B")
                    & (esp["populacao"] == pop)
                    & (esp["passo_meses"] == passo)
                    & (esp["linguagem"] == x)
                ]
                if len(a) == 0 or len(b) == 0:
                    continue
                a, b = a.iloc[0], b.iloc[0]
                linhas.append([NOME_PASSO[passo], NOMES[x], num(a["faixas_vazias"]), num(b["faixas_vazias"]), num(a["razoes_indefinidas"]), num(b["razoes_indefinidas"]), num(a["faixas_bloqueantes"]), num(b["faixas_bloqueantes"]), "sim" if (pop, passo, x) in fragil else "não"])  # fmt: skip
        L.append(f"#### {NOME_POP[pop]}")
        L.append("")
        tabela_md(
            L,
            [
                "Passo",
                "Linguagem",
                "Vazias A",
                "Vazias B",
                "Indefinidas A",
                "Indefinidas B",
                "Bloqueantes A",
                "Bloqueantes B",
                "Frágil",
            ],
            linhas,
        )

    # ------------------------------------------------------------ hipóteses HB1 a HB4
    dec = []

    def b_menor(pop: str, passo: float, metodo: str) -> tuple[int, int]:
        usadas = com_base(pop, passo)
        return sum(
            int(medias[(pop, passo, x, metodo + "_B")] < medias[(pop, passo, x, metodo)])
            for x in usadas
        ), len(usadas)

    passos_ok = {}
    for pop in POPS:
        for metodo in ["coorte_V0", "coorte_amortecida", "hp3"]:
            passos_ok[(pop, metodo)] = sum(
                int(b_menor(pop, p, metodo)[0] >= 3) for p in PASSOS_CURTOS
            )
    for pop in POPS:  # melhor combinação honesta: a de cada versão na célula
        ok = 0
        for p in PASSOS_CURTOS:
            usadas = com_base(pop, p)
            ok += int(
                sum(int(comparacao[(pop, p, x)][3] < comparacao[(pop, p, x)][1]) for x in usadas)
                >= 3
            )
        passos_ok[(pop, "melhor_combinacao")] = ok
    hb1_ok = all(passos_ok[(pop, "coorte_V0")] >= 4 for pop in POPS)
    detalhe = "; ".join(
        f"{pop}: coorte V0 {passos_ok[(pop, 'coorte_V0')]} de 5 passos, coorte amortecida {passos_ok[(pop, 'coorte_amortecida')]}, Hamilton-Perry 3 anos {passos_ok[(pop, 'hp3')]}, melhor combinação {passos_ok[(pop, 'melhor_combinacao')]}"
        for pop in POPS
    )
    dec.append(
        {
            "hipotese": "HB1",
            "status": "sustentada" if hb1_ok else "não sustentada",
            "detalhe": f"Passos (de 5) em que a B tem ABRE médio menor em pelo menos 3 linguagens. {detalhe}",
        }
    )

    faixas_ok = []
    for f in range(6):
        if all(
            sum(int(faixa_menor.get((pop, f, p), 0) >= 3) for p in PASSOS_CURTOS) >= 4
            for pop in POPS
        ):
            faixas_ok.append(FAIXAS[f])
    dec.append({"hipotese": "HB2", "status": "sustentada" if len(faixas_ok) == 6 else ("parcial" if faixas_ok else "não sustentada"), "detalhe": f"Faixas em que a B da coorte V0 vence em pelo menos 3 linguagens em pelo menos 4 passos, nas duas populações: {', '.join(faixas_ok) or 'nenhuma'}"})  # fmt: skip

    celulas_hb3, melhor_b = [], 0
    for pop in POPS:
        for passo in PASSOS_CURTOS:
            usadas = com_base(pop, passo)
            if not usadas:
                continue
            for m in COM_PAR:
                n_a = sum(
                    int(medias[(pop, passo, x, m)] < medias[(pop, passo, x, "ingenua")])
                    for x in usadas
                )
                n_b = sum(
                    int(medias[(pop, passo, x, m + "_B")] < medias[(pop, passo, x, "ingenua")])
                    for x in usadas
                )
                melhor_b = max(melhor_b, n_b)
                if n_b > n_a:
                    celulas_hb3.append((pop, passo, m, n_a, n_b))
    texto_hb3 = "; ".join(
        f"{p}, {NOME_PASSO[s]}, {ROTULO[m]}: A {a}, B {b}" for p, s, m, a, b in celulas_hb3[:6]
    )
    dec.append({"hipotese": "HB3", "status": "sustentada" if celulas_hb3 else "não sustentada", "detalhe": f"{len(celulas_hb3)} células em que a B vence a ingênua em mais linguagens que a A (maior número de linguagens da B: {melhor_b} de {len(decisao)}){': ' + texto_hb3 if texto_hb3 else ''}"})  # fmt: skip

    xs, ys = [], []
    for pop in POPS:
        for passo in PASSOS_CURTOS:
            for x in decisao:
                a, b = (
                    medias.get((pop, passo, x, "coorte_V0"), np.nan),
                    medias.get((pop, passo, x, "coorte_V0_B"), np.nan),
                )
                linha = esp[
                    (esp["versao"] == "B")
                    & (esp["populacao"] == pop)
                    & (esp["passo_meses"] == passo)
                    & (esp["linguagem"] == x)
                ]
                if len(linha) and a > 0 and b > 0:
                    xs.append(float(linha["faixas_vazias"].iloc[0]))
                    ys.append(float(np.log(b / a)))
    rho_hb4 = rho(xs, ys)
    razao_gm = {}
    for pop in POPS:
        for passo in PASSOS_CURTOS:
            razoes = [
                medias[(pop, passo, x, "coorte_V0_B")] / medias[(pop, passo, x, "coorte_V0")]
                for x in com_base(pop, passo)
            ]
            razao_gm[(pop, passo)] = geometrica(razoes)
    pior_a_partir = {}
    for pop in POPS:
        pior_a_partir[pop] = next(
            (NOME_PASSO[p] for p in PASSOS_CURTOS if razao_gm[(pop, p)] > 1), "nenhum"
        )
    metade_vazia = next(
        (
            NOME_PASSO[p]
            for p in PASSOS_CURTOS
            if (
                esp[(esp["versao"] == "B") & (esp["passo_meses"] == p)]["faixas_vazias"].mean()
                > 0.5
            )
        ),
        "nenhum",
    )
    dec.append({"hipotese": "HB4", "status": "sustentada" if (not np.isnan(rho_hb4) and rho_hb4 >= 0.5) else "não sustentada",
                "detalhe": f"Spearman entre faixas vazias e log da razão B sobre A da coorte V0: {num(rho_hb4, 2)} em {len(xs)} células; a razão média geométrica passa de 1 (B pior) a partir do passo mais longo: P1 {pior_a_partir['P1']}, P2 {pior_a_partir['P2']}; passo mais longo com mais da metade das faixas vazias na B: {metade_vazia}"})  # fmt: skip
    dec = pd.DataFrame(dec)
    dec.to_csv(saida / "decisao_b.csv", index=False)
    L.append("### Hipóteses da versão B")
    L.append("")
    enunciado = {
        "HB1": "Avançar a coorte em passos menores melhora o total",
        "HB2": "O mesmo vale por faixa",
        "HB3": "A versão B vence a ingênua em mais linguagens que a A em algum passo",
        "HB4": "A esparsidade das faixas finas piora o resultado da B",
    }
    for _, r in dec.iterrows():
        L.append(f"- {r['hipotese']}, {enunciado[r['hipotese']]}: {r['status']}. {r['detalhe']}.")
    L.append("")
    with (saida / "tabelas.md").open("a", encoding="utf-8") as f:
        f.write("\n".join(L))

    # ------------------------------------------------------------ resumo.md
    fragilidade = sorted({(NOME_POP[p], NOME_PASSO[s], NOMES[x]) for p, s, x in fragil})
    R = ["", "## Versão B, faixas da largura do passo", "",
         "Detalhes em `tabelas.md` (seção Versão B), `testes_ab.csv`, `esparsidade.csv` e `ab_por_faixa.csv`. Comparações na base AB. Em 12 meses A e B são iguais (conferido a cada rodada).", ""]  # fmt: skip
    R.append("### Respostas diretas")
    R.append("")
    R.append(
        f"- Avançar a coorte em passos menores que um ano melhora a previsão do total? {dec.iloc[0]['status'].capitalize()}. {dec.iloc[0]['detalhe']}."
    )
    R.append(f"- E por faixa? {dec.iloc[1]['status'].capitalize()}. {dec.iloc[1]['detalhe']}.")
    R.append(
        f"- A B vence a ingênua em mais linguagens que a A em algum passo? {dec.iloc[2]['status'].capitalize()}. {dec.iloc[2]['detalhe']}."
    )
    R.append(f"- A partir de qual passo a esparsidade piora o resultado? {dec.iloc[3]['detalhe']}.")
    R.append("")
    if fragilidade:
        R.append("### Resultados frágeis (mais da metade das faixas finas vazia na B)")
        R.append("")
        for pop, passo, lingua in fragilidade:
            R.append(f"- {lingua}, {pop}, passo de {passo}.")
        R.append("")
    R.append("### Hipóteses da versão B")
    R.append("")
    for _, r in dec.iterrows():
        R.append(f"- {r['hipotese']}, {enunciado[r['hipotese']]}: {r['status']}. {r['detalhe']}.")
    R.append("")
    texto = (saida / "resumo.md").read_text(encoding="utf-8")
    (saida / "resumo.md").write_text(texto + "\n".join(R), encoding="utf-8")

    # ------------------------------------------------------------ vazamento.md: envelhecimento na B
    V = ["", "## Versão B: como a pirâmide envelhece entre um passo e outro", "",
         "- Idade na régua do passo, como na rodada oficial (idade descontada), recalculada em cada data só com dados até ela: idade(k) = número das datas k - 1, k - 2, ... em que a pessoa estava ativa na janela de 12 meses. A janela de atividade é de 12 meses. Faixas da largura do passo, de 0 a 8 anos, e uma aberta.",
         "- A cada passo quem estava ativo na data anterior sobe uma faixa. Quem passa de faixa dentro do passo já está na faixa nova na pirâmide da data seguinte. Quem não estava ativo na janela na data anterior mantém a idade e, se volta a ficar ativo, entra na faixa que já tinha.",
         "- Coorte e conservador (V0 a V4b), pessimista e otimista: a razão de permanência de cada faixa é a de um passo (quem está na faixa k+1 agora dividido por quem estava na faixa k na data anterior). A pirâmide avança um passo por vez, nb vezes (2 no passo de 6 meses, 4 no de 3, 6 no de 2, 12 no de 1 mês e 24 no de 15 dias), com os novatos de cada passo. Ao fim, as faixas finas somam nas 6 faixas de 1 ano e no total.",
         "- Hamilton-Perry de 3 e 5 anos (B): a última razão de permanência de um passo e os novatos pela média dos últimos 3 ou 5 anos (3, 6, 12, 18, 36 ou 72 passos de 3 anos e o dobro e meio para 5). É a mesma regra da A em escala de passo.",
         "- Faixa aberta: razão entre a faixa aberta no passo atual e a soma da faixa aberta com a última faixa fechada no passo anterior.",
         "- Razão indefinida (faixa vazia no passo anterior): não é preenchida. Faixa com gente na origem e sem razão deixa o total do método indefinido e o par sai da base, a regra da rodada oficial. Faixa vazia na origem não leva ninguém adiante. A esparsidade de cada passo está em `esparsidade.csv`.",
         "- Coorte amortecida e C1 a C7 da B usam os métodos da B no lugar dos de coorte da A. Ingênua, deriva e Holt são os mesmos.", ""]  # fmt: skip
    with (saida / "vazamento.md").open("a", encoding="utf-8") as f:
        f.write("\n".join(V))
