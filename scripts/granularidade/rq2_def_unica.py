"""Tabelas da RQ2 de 2024 com a carga v3b e a definição única de entrada e saída (`definicao-unica/hipoteses_rq2.md`). Não interpreta nenhum número.

Definição única: entradas = novatos + voltas, saídas = sem volta + com volta, natalidade = entradas / ativos, mortalidade = saídas / ativos, crescimento natural = diferença.
Ao lado, a definição antiga (do artigo): natalidade = novatos / ativos e mortalidade = saídas sem volta / ativos; padronização e SMR com `padronizacao_definicao_antiga.csv`.
A tábua usa x como o tempo da primeira à última contribuição em anos completos, com as pausas (método da RQ1.3), nos residentes
(mais de uma ocasião) que chegaram até 2024, com saída confirmada só até 2024. NCR, taxa padronizada, SMR e log-rank vêm dos CSV da rodada
oficial v3. Lado de código e de discussão pela regra da figura 1: código se a pessoa teve ao menos tantos eventos de código quanto de discussão no ano.

Uso (na raiz do repo): .venv/bin/python scripts/granularidade/rq2_def_unica.py <pasta da rodada, com <l>/origem e <l>-mais_de_uma_ocasiao/> <saida>
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, "src")
from pyramid import vitalidade as v

RODADA, SAIDA = Path(sys.argv[1]), Path(sys.argv[2])
GERAL = RODADA / "geral-mais_de_uma_ocasiao" / "csv" / "vitalidade"
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


def milhar(x: float) -> str:
    return f"{x:,.0f}".replace(",", ".")


def dec(x: float, casas: int = 1) -> str:
    return "n/d" if pd.isna(x) else f"{x:.{casas}f}".replace(".", ",")


def tabua_com_pausas(pessoas: pd.DataFrame) -> tuple[int, pd.DataFrame]:
    fim = pessoas["ultimo"].max()
    d = pessoas[pessoas["ocasioes"] > 1].copy()
    d["coorte"] = d["primeiro"].dt.year
    d = d[d["coorte"] <= ATE].copy()
    dias = (d["ultimo"] - d["primeiro"]).dt.total_seconds() / 86400
    d["duracao_anos"] = dias / v.DIAS_POR_ANO
    d["saiu"] = (fim - d["ultimo"]) > pd.Timedelta(days=v.GAP_DIAS)
    d.loc[d["ultimo"].dt.year > ATE, "saiu"] = False
    return len(d), v.tabua_de_vida(d)


trajetoria = pd.read_csv(GERAL / "trajetoria.csv")
trajetoria = trajetoria[trajetoria["ano"] == ATE].set_index("slug")
ccr = pd.read_csv(GERAL / "ccr_ncr_comparado.csv")
ccr = ccr[ccr["snapshot"] == "2024-12-31"].set_index("slug")
padron = pd.read_csv(GERAL / "padronizacao.csv")
padron = padron[padron["ano"] == ATE]
padron_antiga = pd.read_csv(GERAL / "padronizacao_definicao_antiga.csv")
padron_antiga = padron_antiga[padron_antiga["ano"] == ATE]
logrank = pd.read_csv(GERAL / "logrank.csv")

linhas = {}
for lingua in LINGUAS:
    t = trajetoria.loc[lingua]
    ativos, novatos, voltas = int(t["ativos"]), int(t["novatos"]), int(t["voltas"])
    entradas, saidas = int(t["entradas"]), int(t["saidas"])
    sem_volta, com_volta = int(t["saidas_sem_volta"]), int(t["saidas_com_volta"])
    n, tab = tabua_com_pausas(pd.read_parquet(RODADA / lingua / "origem" / "pessoas.parquet"))
    s = tab.set_index("x")["S"]
    linhas[lingua] = {
        "ativos": ativos,
        "entradas": entradas,
        "novatos": novatos,
        "voltas": voltas,
        "saidas": saidas,
        "saidas_sem_volta": sem_volta,
        "saidas_com_volta": com_volta,
        "natalidade_pct": 100 * entradas / ativos,
        "mortalidade_pct": 100 * saidas / ativos,
        "natural_pontos": 100 * (entradas - saidas) / ativos,
        "natalidade_antiga_pct": 100 * novatos / ativos,
        "mortalidade_antiga_pct": 100 * sem_volta / ativos,
        "natural_antigo_pontos": 100 * (novatos - sem_volta) / ativos,
        "ncr": float(ccr.loc[lingua, "ncr"]),
        "ncr_novos": int(ccr.loc[lingua, "new"]),
        "ncr_experientes": int(ccr.loc[lingua, "experienced"]),
        "ncr_ativos": int(ccr.loc[lingua, "total"]),
        "tabua_pessoas": n,
        "e0": float(tab.loc[tab["x"] == 0, "e"].iloc[0]),
        "q0_pct": 100 * float(tab["q"].iloc[0]),
        "permanece_1_ano_pct": 100 * float(s.loc[1]),
        "permanece_5_anos_pct": 100 * float(s.loc[5]),
    }
    for rodada in ["nicho", "python"]:
        p = padron[(padron["linguagem"] == lingua) & (padron["rodada"] == rodada)]
        if len(p):
            p = p.iloc[0]
            linhas[lingua][f"taxa_bruta_{rodada}_pct"] = 100 * float(p["taxa_bruta"])
            linhas[lingua][f"taxa_padronizada_{rodada}_pct"] = 100 * float(p["taxa_padronizada"])
            linhas[lingua][f"smr_{rodada}"] = float(p["smr"])
        a = padron_antiga[
            (padron_antiga["linguagem"] == lingua) & (padron_antiga["rodada"] == rodada)
        ]
        if len(a):
            a = a.iloc[0]
            linhas[lingua][f"taxa_bruta_antiga_{rodada}_pct"] = 100 * float(a["taxa_bruta"])
            linhas[lingua][f"taxa_padronizada_antiga_{rodada}_pct"] = 100 * float(
                a["taxa_padronizada"]
            )
            linhas[lingua][f"smr_antiga_{rodada}"] = float(a["smr"])
for lingua in LINGUAS:  # a taxa bruta é a mesma nas duas referências
    bruta = linhas[lingua].get("taxa_bruta_nicho_pct", linhas[lingua].get("taxa_bruta_python_pct"))
    linhas[lingua]["taxa_bruta_pct"] = bruta
    antiga = linhas[lingua].get(
        "taxa_bruta_antiga_nicho_pct", linhas[lingua].get("taxa_bruta_antiga_python_pct")
    )
    linhas[lingua]["taxa_bruta_antiga_pct"] = antiga
tabela = pd.DataFrame(linhas).T
tabela.index.name = "linguagem"
SAIDA.mkdir(parents=True, exist_ok=True)
tabela.to_csv(SAIDA / "tabela_2024.csv")

# Código e discussão em 2024
lados = {}
for lingua in LINGUAS:
    c = pd.read_csv(
        RODADA / f"{lingua}-mais_de_uma_ocasiao" / "csv" / "vitalidade" / "composicao.csv"
    )
    c = c[c["ano"] == ATE]
    discussao, codigo = int(c["non_coding"].sum()), int(c["coding"].sum())
    t = trajetoria.loc[lingua]
    lados[lingua] = {
        "ativos": discussao + codigo,
        "discussao": discussao,
        "codigo": codigo,
        "discussao_pct": 100 * discussao / (discussao + codigo),
        "codigo_pct": 100 * codigo / (discussao + codigo),
        "passaram_a_contribuir_com_codigo": int(t["moved"]),
        "deixaram_de_contribuir_com_codigo": int(t["deixou_codigo"]),
    }
pd.DataFrame(lados).T.rename_axis("linguagem").to_csv(SAIDA / "codigo_discussao_2024.csv")


def linha(rotulo: str, chave: str, formato) -> str:
    celulas = []
    for lingua in LINGUAS:
        valor = tabela.loc[lingua].get(chave)
        celulas.append("n/a" if pd.isna(valor) else formato(valor))
    return f"| {rotulo} | " + " | ".join(celulas) + " |"


cabecalho = "| | " + " | ".join(NOMES[x] for x in LINGUAS) + " |\n|---|" + "---|" * len(LINGUAS)
T = [
    "# RQ2 com a carga v3b e a definição única: tabelas de 2024",
    "",
    "Carga v3b, peso de 2024 na padronização. Residentes: pessoas com mais de uma ocasião. Cada linha com `(def. antiga)` repete a conta com a definição anterior: natalidade só com novatos, mortalidade só com saídas sem volta, padronização e SMR só com as saídas sem volta.",
    "",
    "## Tabela de 2024",
    "",
    cabecalho,
    linha("Ativos", "ativos", milhar),
    linha("Entradas (novatos + voltas)", "entradas", milhar),
    linha("  Novatos", "novatos", milhar),
    linha("  Voltas", "voltas", milhar),
    linha("Saídas (sem volta + com volta)", "saidas", milhar),
    linha("  Sem volta", "saidas_sem_volta", milhar),
    linha("  Com volta", "saidas_com_volta", milhar),
    linha("Natalidade (%)", "natalidade_pct", dec),
    linha("Natalidade (%) (def. antiga)", "natalidade_antiga_pct", dec),
    linha("Mortalidade (%)", "mortalidade_pct", dec),
    linha("Mortalidade (%) (def. antiga)", "mortalidade_antiga_pct", dec),
    linha("Crescimento natural (pontos)", "natural_pontos", dec),
    linha("Crescimento natural (pontos) (def. antiga)", "natural_antigo_pontos", dec),
    linha("NCR em 31/12/2024", "ncr", lambda x: dec(x, 3)),
    linha("Pessoas na tábua", "tabua_pessoas", milhar),
    linha("e0 (anos, piso)", "e0", lambda x: dec(x, 2)),
    linha("Permanecem 1 ano (%)", "permanece_1_ano_pct", dec),
    linha("Permanecem 5 anos (%)", "permanece_5_anos_pct", dec),
    linha("Taxa bruta de saída (%)", "taxa_bruta_pct", dec),
    linha("Taxa bruta de saída (%) (def. antiga)", "taxa_bruta_antiga_pct", dec),
    linha("Taxa padronizada, referência nicho (%)", "taxa_padronizada_nicho_pct", dec),
    linha(
        "Taxa padronizada, referência nicho (%) (def. antiga)",
        "taxa_padronizada_antiga_nicho_pct",
        dec,
    ),
    linha("SMR, referência nicho", "smr_nicho", lambda x: dec(x, 2)),
    linha("SMR, referência nicho (def. antiga)", "smr_antiga_nicho", lambda x: dec(x, 2)),
    linha("Taxa padronizada, referência python (%)", "taxa_padronizada_python_pct", dec),
    linha(
        "Taxa padronizada, referência python (%) (def. antiga)",
        "taxa_padronizada_antiga_python_pct",
        dec,
    ),
    linha("SMR, referência python", "smr_python", lambda x: dec(x, 2)),
    linha("SMR, referência python (def. antiga)", "smr_antiga_python", lambda x: dec(x, 2)),
    "",
    "Taxa bruta de saída: saídas de 2024 divididas pelos ativos de 2024 (igual à mortalidade da mesma definição). `n/a` é linguagem fora daquela referência.",
    "",
    "Definições:",
    "",
    "- Ativo: pessoa com ao menos um evento no ano, entre os residentes. Entrada: ativo sem contribuição nos 12 meses antes do primeiro evento do ano (novato ou volta). Saída: ativo cuja última contribuição do ano é seguida de 12 meses sem contribuir, com ou sem volta depois (confirmada com o acompanhamento até o fim da coleta).",
    "- Natalidade é entradas sobre ativos. Mortalidade é saídas sobre ativos. Crescimento natural é natalidade menos mortalidade, em pontos percentuais.",
    "- NCR (IEICE16, `ccr_ncr_comparado`): (novatos menos experientes) dividido pelo maior dos dois, na foto de 31/12/2024. A população da foto é quem contribuiu nos 12 meses até a data. Novato é quem tem 12 meses de idade ou menos, contados da primeira contribuição de código (ou, sem código, da primeira de discussão). Vai de -1 a 1.",
    "- Tábua: x é o tempo da primeira à última contribuição, em anos completos, com as pausas (o método da RQ1.3). Entram os residentes que chegaram até 2024. Quem tem o último evento depois de 2024 fica censurado. e0 é um piso, porque a cauda censurada não entra. As quantidades vêm de `tabua_de_vida`, com a exposição do censurado em meio intervalo.",
    "",
    "## Referências da padronização e da SMR",
    "",
    "- Referência nicho: a soma de Clojure, Elixir, Zig e OCaml (Clojure entra). A taxa de saída da referência em cada ano e faixa é o total de saídas dividido pelo total de ativos das quatro linguagens juntas, nessa faixa e nesse ano.",
    "- Referência python: a soma de Clojure e Python, com a mesma conta.",
    "- Taxa padronizada (direta): soma, nas seis faixas, da taxa de saída da linguagem em 2024 vezes o peso da faixa. O peso é a parte dos ativos de cada faixa na referência em 2024 (`ano_pesos` da rodada), isto é, os ativos das linguagens da referência somados em 2024.",
    "- SMR (indireta): saídas observadas da linguagem em 2024 divididas pelas esperadas, que são a soma, nas faixas, da taxa de saída da referência em 2024 vezes os ativos da linguagem na faixa.",
    "- A taxa padronizada fica `n/d` em um ano quando falta taxa em alguma faixa da linguagem (faixa sem ativos).",
    "",
    "## Log-rank de Clojure contra cada linguagem",
    "",
    f"Limite de Bonferroni: 0,05 dividido por 4 comparações, {dec(BONFERRONI, 4)}. Curvas de Kaplan-Meier da duração contínua da primeira à última contribuição, com censura.",
    "",
    "| Comparação | Estatística | p | p abaixo do limite |",
    "|---|---|---|---|",
]
for _, x in logrank.iterrows():
    nome = x["comparacao"].replace("clojure x ", "Clojure contra ")
    for k, vv in NOMES.items():
        nome = nome.replace(k, vv) if k != "clojure" else nome
    T.append(
        f"| {nome} | {dec(float(x['estatistica']), 2)} | {f'{float(x["p"]):.2e}'.replace('.', ',')} | {'sim' if float(x['p']) < BONFERRONI else 'não'} |"
    )
T += [
    "",
    "## Código e discussão em 2024",
    "",
    "Regra de dois lados, a mesma da figura 1: no ano, a pessoa fica do lado do código se teve ao menos tantos eventos de código (commits e PRs) quanto de discussão (issues, comentários e ações em issues e PRs), e do lado da discussão se teve mais de discussão. O lado vale só para o ano.",
    "",
    "| | " + " | ".join(NOMES[x] for x in LINGUAS) + " |",
    "|---|" + "---|" * len(LINGUAS),
]
for rotulo, chave, fmt in [
    ("Ativos de 2024", "ativos", milhar),
    ("Lado da discussão (pessoas)", "discussao", milhar),
    ("Lado do código (pessoas)", "codigo", milhar),
    ("Lado da discussão (%)", "discussao_pct", dec),
    ("Lado do código (%)", "codigo_pct", dec),
    ("Passaram a contribuir com código em 2024", "passaram_a_contribuir_com_codigo", milhar),
    ("Deixaram de contribuir com código em 2024", "deixaram_de_contribuir_com_codigo", milhar),
]:
    T.append(f"| {rotulo} | " + " | ".join(fmt(lados[x][chave]) for x in LINGUAS) + " |")
T += [
    "",
    "- Passaram a contribuir com código: pessoas que começaram pela discussão e fizeram o primeiro commit ou PR em 2024.",
    "- Deixaram de contribuir com código: pessoas cujo último commit ou PR é de 2024 e que depois só discutiram.",
    "",
]
(SAIDA / "tabelas.md").write_text("\n".join(T) + "\n", encoding="utf-8")
print("\n".join(T))
