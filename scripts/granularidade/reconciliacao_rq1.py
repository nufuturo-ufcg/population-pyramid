"""Reconciliação da RQ1 do artigo (Clojure) com a rodada oficial v3 (`rq2-v3/hipoteses.md`, item 1).

Recalcula cada número da RQ1 do artigo com os mesmos dados de duas cargas: a de 09/11 sem correções (que gerou o artigo) e a
`-v3`. A tábua usa x como o tempo da primeira à última contribuição em anos completos, com as pausas (o método da RQ1.3), e,
só na carga v3, também a idade da pirâmide (a da `tabua_comparada.csv` da rodada). Não interpreta nenhum número.

Entradas: `<vitalidade>` (pasta `pyramid-vitalidade`) e `<origens>` com `abase/pessoas.parquet`, `v3/pessoas.parquet` e
`v3/pessoas_repos_por_ano.parquet` de Clojure. Grava `<saida>/reconciliacao.csv` e `<saida>/reconciliacao.md`.

Uso (na raiz do repo): .venv/bin/python scripts/granularidade/reconciliacao_rq1.py <vitalidade> <origens> <saida>
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, "src")
from pyramid import vitalidade as v

VITALIDADE, ORIGENS, SAIDA = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
SAIDA.mkdir(parents=True, exist_ok=True)
ANTIGA = (
    VITALIDADE / "rodada-2026-11-09-0945" / "clojure-mais_de_uma_ocasiao" / "csv" / "vitalidade"
)
NOVA = VITALIDADE / "rodada-oficial-v3" / "clojure-mais_de_uma_ocasiao" / "csv" / "vitalidade"
ATE = 2024


def milhar(x: float) -> str:
    return f"{x:,.0f}".replace(",", ".")


def dec(x: float, casas: int = 1) -> str:
    return f"{x:.{casas}f}".replace(".", ",")


def tabua(
    pessoas: pd.DataFrame, definicao: str, anos_ativos: pd.Series | None = None
) -> tuple[int, pd.DataFrame]:
    """Tábua de Clojure (residentes, coortes até 2024) com x pela permanência (B) ou pela idade da pirâmide (A)."""
    fim = pessoas["ultimo"].max()
    d = pessoas[pessoas["ocasioes"] > 1].copy()
    d["coorte"] = d["primeiro"].dt.year
    d = d[d["coorte"] <= ATE].copy()
    if definicao == "B":
        dias = (d["ultimo"] - d["primeiro"]).dt.total_seconds() / 86400
        d["duracao_anos"] = dias / v.DIAS_POR_ANO
    else:
        vazios = (d["ultimo"].dt.year - d["primeiro"].dt.year + 1) - d["pessoa"].map(anos_ativos)
        d["duracao_anos"] = (v.anos_completos(d["primeiro"], d["ultimo"]) - vazios).clip(lower=0)
    d["saiu"] = (fim - d["ultimo"]) > pd.Timedelta(days=v.GAP_DIAS)
    d.loc[d["ultimo"].dt.year > ATE, "saiu"] = False
    return len(d), v.tabua_de_vida(d)


def serie(pasta: Path) -> dict:
    """Os números da RQ1.1 e da RQ1.2 do artigo, pela definição do artigo (natalidade = novatos / ativos)."""
    a = pd.read_csv(pasta / "anual.csv").set_index("ano")
    nat = 100 * a["novatos"] / a["ativos"]
    mor = 100 * a["saidas"] / a["ativos"]
    natural = nat - mor
    saldo = 100 * (a["voltas"] - a["pausas"]) / a["ativos"]
    total = natural + saldo
    base = natural.loc[2009:ATE]
    negativos = base[base < 0]
    total_neg = total.loc[2009:ATE]
    primeiro_total_negativo_continuo = None
    for ano in range(2009, ATE + 1):
        if (total_neg.loc[ano:] < 0).all():
            primeiro_total_negativo_continuo = ano
            break
    i = pd.read_csv(pasta / "indice_envelhecimento.csv").set_index("ano")
    return {
        "natural_maximo_ano": int(base.idxmax()),
        "natural_maximo": float(base.max()),
        "primeiro_ano_negativo": int(negativos.index[0]),
        "primeiro_negativo_valor": float(negativos.iloc[0]),
        "natural_2021": float(natural.loc[2021]),
        "natural_minimo_ano": int(base.idxmin()),
        "natural_minimo": float(base.min()),
        "ativos_2024": int(a.loc[2024, "ativos"]),
        "novatos_2024": int(a.loc[2024, "novatos"]),
        "saidas_2024": int(a.loc[2024, "saidas"]),
        "natalidade_2021": float(nat.loc[2021]),
        "natalidade_2024": float(nat.loc[2024]),
        "mortalidade_2021": float(mor.loc[2021]),
        "mortalidade_2024": float(mor.loc[2024]),
        "voltas_2024": int(a.loc[2024, "voltas"]),
        "pausas_2024": int(a.loc[2024, "pausas"]),
        "saldo_voltas_2024": float(saldo.loc[2024]),
        "total_2024": float(total.loc[2024]),
        "total_negativo_desde": primeiro_total_negativo_continuo,
        "indice_2020": float(i.loc[2020, "indice"]),
        "indice_2021": float(i.loc[2021, "indice"]),
        "indice_2022": float(i.loc[2022, "indice"]),
        "indice_2023": float(i.loc[2023, "indice"]),
        "indice_2024": float(i.loc[2024, "indice"]),
        "veteranos_2024": int(i.loc[2024, "veteranos"]),
        "fatia_5mais_2024": float(100 * i.loc[2024, "veteranos"] / a.loc[2024, "ativos"]),
        "novatos_2022": int(a.loc[2022, "novatos"]),
        "veteranos_min_2022_2024": int(i.loc[2022:2024, "veteranos"].min()),
        "veteranos_max_2022_2024": int(i.loc[2022:2024, "veteranos"].max()),
    }


def casuais(pessoas: pd.DataFrame) -> tuple[int, float, float]:
    ate = pessoas[pessoas["primeiro"].dt.year <= ATE]
    casual = ate[ate["ocasioes"] == 1]
    return len(ate), 100 * len(casual) / len(ate), 100 * (~casual["codou"]).mean()


def linhas_da_tabua(t: pd.DataFrame, n: int) -> dict:
    q = t.set_index("x")["q"]
    s = t.set_index("x")["S"]
    return {
        "pessoas": n,
        "q0": 100 * float(q.loc[0]),
        "q1": 100 * float(q.loc[1]),
        "q3": 100 * float(q.loc[3]),
        "q3_a_q11_min": 100 * float(q.loc[3:11].min()),
        "q3_a_q11_max": 100 * float(q.loc[3:11].max()),
        "passam_1_ano": 100 * float(s.loc[1]),
        "chegam_5_anos": 100 * float(s.loc[5]),
        "e0": float(t.loc[t["x"] == 0, "e"].iloc[0]),
    }


antiga, nova = serie(ANTIGA), serie(NOVA)
p_antiga = pd.read_parquet(ORIGENS / "abase" / "pessoas.parquet")
p_nova = pd.read_parquet(ORIGENS / "v3" / "pessoas.parquet")
anos = pd.read_parquet(
    ORIGENS / "v3" / "pessoas_repos_por_ano.parquet", columns=["pessoa", "ano"]
).drop_duplicates()
n_antiga, t_antiga_b = tabua(p_antiga, "B")
n_nova, t_nova_b = tabua(p_nova, "B")
n_nova_a, t_nova_a = tabua(p_nova, "A", anos.groupby("pessoa").size())
tab_antiga_b = linhas_da_tabua(t_antiga_b, n_antiga)
tab_nova_b = linhas_da_tabua(t_nova_b, n_nova)
tab_nova_a = linhas_da_tabua(t_nova_a, n_nova_a)
cas_antiga, cas_nova = casuais(p_antiga), casuais(p_nova)

ARTIGO = {  # o que o artigo imprime (tcc/latex/artigo.tex, seções Dados e RQ1)
    "natural_maximo": 70.2, "natural_minimo": -24.8, "primeiro_negativo_valor": -0.5, "natural_2021": -0.3,
    "ativos_2024": 3204, "novatos_2024": 762, "saidas_2024": 1555, "natalidade_2021": 36.7, "natalidade_2024": 23.8,
    "mortalidade_2021": 37.0, "mortalidade_2024": 48.5, "saldo_voltas_2024": 14.6, "voltas_2024": 947, "pausas_2024": 479,
    "total_2024": -10.1, "indice_2020": 0.60, "indice_2023": 0.84, "indice_2024": 1.16, "veteranos_2024": 881,
    "fatia_5mais_2024": 27.5, "novatos_2022": 1658, "pessoas": 21229, "q0": 51.4, "q1": 22.7, "q3": 16.5,
    "passam_1_ano": 48.6, "chegam_5_anos": 21.6, "e0": 3.29, "casuais_pct": 45.6, "casuais_sem_codigo_pct": 86.4,
    "contribuidores": 42760,
}  # fmt: skip

linhas = []


def linha(
    rotulo: str, chave: str, antigo: float, novo: float, casas: int = 1, inteiro: bool = False
) -> None:
    fmt = milhar if inteiro else (lambda x: dec(x, casas))
    artigo = ARTIGO.get(chave)
    linhas.append(
        {
            "numero": rotulo,
            "artigo": "n/d" if artigo is None else fmt(artigo),
            "recalculado_com_a_carga_de_09_11": fmt(antigo),
            "carga_v3": fmt(novo),
            "muda": "sim" if round(antigo, casas) != round(novo, casas) else "não",
        }
    )


linha(
    "Contribuidores da linguagem (Tabela da amostra)",
    "contribuidores",
    len(p_antiga),
    len(p_nova),
    inteiro=True,
)
linha("Casuais entre os que chegaram até 2024 (%)", "casuais_pct", cas_antiga[1], cas_nova[1])
linha(
    "Casuais que nunca fizeram commit nem PR (%)",
    "casuais_sem_codigo_pct",
    cas_antiga[2],
    cas_nova[2],
)
linha(
    "RQ1.1 crescimento natural máximo, 2009 (pontos)",
    "natural_maximo",
    antiga["natural_maximo"],
    nova["natural_maximo"],
)
linha(
    "RQ1.1 primeiro ano negativo: valor (pontos)",
    "primeiro_negativo_valor",
    antiga["primeiro_negativo_valor"],
    nova["primeiro_negativo_valor"],
)
linha(
    "RQ1.1 crescimento natural em 2021 (pontos)",
    "natural_2021",
    antiga["natural_2021"],
    nova["natural_2021"],
)
linha(
    "RQ1.1 crescimento natural mínimo, 2024 (pontos)",
    "natural_minimo",
    antiga["natural_minimo"],
    nova["natural_minimo"],
)
linha(
    "RQ1.1 ativos em 2024", "ativos_2024", antiga["ativos_2024"], nova["ativos_2024"], inteiro=True
)
linha(
    "RQ1.1 novatos em 2024",
    "novatos_2024",
    antiga["novatos_2024"],
    nova["novatos_2024"],
    inteiro=True,
)
linha(
    "RQ1.1 saídas em 2024", "saidas_2024", antiga["saidas_2024"], nova["saidas_2024"], inteiro=True
)
linha(
    "RQ1.1 natalidade 2021 (%)",
    "natalidade_2021",
    antiga["natalidade_2021"],
    nova["natalidade_2021"],
)
linha(
    "RQ1.1 natalidade 2024 (%)",
    "natalidade_2024",
    antiga["natalidade_2024"],
    nova["natalidade_2024"],
)
linha(
    "RQ1.1 mortalidade 2021 (%)",
    "mortalidade_2021",
    antiga["mortalidade_2021"],
    nova["mortalidade_2021"],
)
linha(
    "RQ1.1 mortalidade 2024 (%)",
    "mortalidade_2024",
    antiga["mortalidade_2024"],
    nova["mortalidade_2024"],
)
linha(
    "RQ1.1 saldo de voltas 2024 (pontos)",
    "saldo_voltas_2024",
    antiga["saldo_voltas_2024"],
    nova["saldo_voltas_2024"],
)
linha(
    "RQ1.1 voltas em 2024", "voltas_2024", antiga["voltas_2024"], nova["voltas_2024"], inteiro=True
)
linha(
    "RQ1.1 pausas em 2024", "pausas_2024", antiga["pausas_2024"], nova["pausas_2024"], inteiro=True
)
linha(
    "RQ1.1 crescimento total 2024 (pontos)", "total_2024", antiga["total_2024"], nova["total_2024"]
)
linha(
    "RQ1.2 índice de envelhecimento 2020",
    "indice_2020",
    antiga["indice_2020"],
    nova["indice_2020"],
    2,
)
linha(
    "RQ1.2 índice de envelhecimento 2023",
    "indice_2023",
    antiga["indice_2023"],
    nova["indice_2023"],
    2,
)
linha(
    "RQ1.2 índice de envelhecimento 2024",
    "indice_2024",
    antiga["indice_2024"],
    nova["indice_2024"],
    2,
)
linha(
    "RQ1.2 veteranos em 2024",
    "veteranos_2024",
    antiga["veteranos_2024"],
    nova["veteranos_2024"],
    inteiro=True,
)
linha(
    "RQ1.2 fatia dos ativos com 5 anos ou mais, 2024 (%)",
    "fatia_5mais_2024",
    antiga["fatia_5mais_2024"],
    nova["fatia_5mais_2024"],
)
linha(
    "RQ1.2 novatos em 2022",
    "novatos_2022",
    antiga["novatos_2022"],
    nova["novatos_2022"],
    inteiro=True,
)
linha(
    "RQ1.3 pessoas na tábua",
    "pessoas",
    tab_antiga_b["pessoas"],
    tab_nova_b["pessoas"],
    inteiro=True,
)
linha("RQ1.3 q(0), ano 0 (%)", "q0", tab_antiga_b["q0"], tab_nova_b["q0"])
linha("RQ1.3 q(1), ano 1 (%)", "q1", tab_antiga_b["q1"], tab_nova_b["q1"])
linha("RQ1.3 q(3), ano 3 (%)", "q3", tab_antiga_b["q3"], tab_nova_b["q3"])
linha(
    "RQ1.3 passam do primeiro ano (%)",
    "passam_1_ano",
    tab_antiga_b["passam_1_ano"],
    tab_nova_b["passam_1_ano"],
)
linha(
    "RQ1.3 chegam a 5 anos (%)",
    "chegam_5_anos",
    tab_antiga_b["chegam_5_anos"],
    tab_nova_b["chegam_5_anos"],
)
linha("RQ1.3 e0, piso (anos)", "e0", tab_antiga_b["e0"], tab_nova_b["e0"], 2)
tabela = pd.DataFrame(linhas)
tabela.to_csv(SAIDA / "reconciliacao.csv", index=False)

T = [
    "# Reconciliação da RQ1 de Clojure com a carga v3",
    "",
    "Mesmas definições nas três colunas (a do artigo): não casual é quem tem mais de uma ocasião, saída é o fim do último período de atividade seguido de 12 meses sem contribuir, idade da pirâmide desconta os anos inteiros sem contribuição, natalidade é novatos sobre ativos, mortalidade é saídas sobre ativos, e x da tábua é o tempo da primeira à última contribuição em anos completos, com as pausas. Corte em 2024, acompanhamento até o fim da coleta.",
    "",
    "A coluna do meio refaz o número com a carga de 09/11 sem correções (`efeitos-clojure/A-base`) e deve repetir o artigo. A última usa a carga v3.",
    "",
    "| Número | Artigo | Carga de 09/11 (recalculado) | Carga v3 | Muda |",
    "|---|---|---|---|---|",
]
for _, x in tabela.iterrows():
    T.append(
        f"| {x['numero']} | {x['artigo']} | {x['recalculado_com_a_carga_de_09_11']} | {x['carga_v3']} | {x['muda']} |"
    )
T += [
    "",
    "Valores sem o número correspondente no artigo (anos e faixas citadas no texto):",
    "",
    f"- Primeiro ano com crescimento natural negativo: {antiga['primeiro_ano_negativo']} (09/11) e {nova['primeiro_ano_negativo']} (v3). Ano do máximo: {antiga['natural_maximo_ano']} e {nova['natural_maximo_ano']}. Ano do mínimo: {antiga['natural_minimo_ano']} e {nova['natural_minimo_ano']}.",
    f"- Crescimento total negativo de forma contínua desde: {antiga['total_negativo_desde']} (09/11) e {nova['total_negativo_desde']} (v3).",
    f"- Taxa q(x) de 3 a 11 anos: de {dec(tab_antiga_b['q3_a_q11_min'])}% a {dec(tab_antiga_b['q3_a_q11_max'])}% (09/11) e de {dec(tab_nova_b['q3_a_q11_min'])}% a {dec(tab_nova_b['q3_a_q11_max'])}% (v3). O artigo diz de 13% a 17%.",
    f"- Veteranos de 2022 a 2024: de {antiga['veteranos_min_2022_2024']} a {antiga['veteranos_max_2022_2024']} (09/11) e de {nova['veteranos_min_2022_2024']} a {nova['veteranos_max_2022_2024']} (v3). O artigo diz de 881 a 935.",
    "",
    "## A tábua da rodada oficial usa outro x",
    "",
    "A `tabua_comparada.csv` da rodada oficial v3 usa como x a idade da pirâmide (anos completos menos os anos inteiros sem contribuição), e não o tempo com as pausas do método da RQ1.3. Na mesma carga v3, com as mesmas pessoas:",
    "",
    "| x da tábua | Pessoas | q(0) | Passam de 1 ano | Chegam a 5 anos | e0 (piso) |",
    "|---|---|---|---|---|---|",
    f"| Tempo com as pausas, como no artigo (carga de 09/11) | {milhar(tab_antiga_b['pessoas'])} | {dec(tab_antiga_b['q0'])}% | {dec(tab_antiga_b['passam_1_ano'])}% | {dec(tab_antiga_b['chegam_5_anos'])}% | {dec(tab_antiga_b['e0'], 2)} |",
    f"| Tempo com as pausas, como no artigo (carga v3) | {milhar(tab_nova_b['pessoas'])} | {dec(tab_nova_b['q0'])}% | {dec(tab_nova_b['passam_1_ano'])}% | {dec(tab_nova_b['chegam_5_anos'])}% | {dec(tab_nova_b['e0'], 2)} |",
    f"| Idade da pirâmide, como na rodada oficial (carga v3) | {milhar(tab_nova_a['pessoas'])} | {dec(tab_nova_a['q0'])}% | {dec(tab_nova_a['passam_1_ano'])}% | {dec(tab_nova_a['chegam_5_anos'])}% | {dec(tab_nova_a['e0'], 2)} |",
    "",
    "A idade da pirâmide na carga de 09/11 não foi recalculada: a origem dela não guarda os anos com contribuição de cada pessoa.",
    "",
]
(SAIDA / "reconciliacao.md").write_text("\n".join(T) + "\n", encoding="utf-8")
print("\n".join(T))
