"""RQ1 de Clojure, carga v3 (leitura paralela) contra v3b (leitura sequencial): cada número do artigo, lado a lado. Não interpreta nenhum número.

Entradas: `<vitalidade>` com `rodada-oficial-v3/` e `rodada-oficial-v3b/`; `<origens>` com `v3_clojure/` e `v3b_clojure/` (cada um
com `pessoas.parquet` e `pessoas_repos_por_ano.parquet`). Grava `<saida>/rq1_v3_contra_v3b.csv` e `.md`.

Uso (na raiz do repo): .venv/bin/python scripts/granularidade/rq1_v3_v3b.py <vitalidade> <origens> <saida>
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, "src")
from pyramid import vitalidade as v

VITALIDADE, ORIGENS, SAIDA = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
SAIDA.mkdir(parents=True, exist_ok=True)
ANTIGA = VITALIDADE / "rodada-oficial-v3" / "clojure-mais_de_uma_ocasiao" / "csv" / "vitalidade"
NOVA = VITALIDADE / "rodada-oficial-v3b" / "clojure-mais_de_uma_ocasiao" / "csv" / "vitalidade"
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


ARTIGO = {  # o que o artigo imprime (tcc/latex/artigo.tex, seções Dados e RQ1)
    "natural_maximo": 70.2, "natural_minimo": -24.8, "primeiro_negativo_valor": -0.5, "natural_2021": -0.3,
    "ativos_2024": 3204, "novatos_2024": 762, "saidas_2024": 1555, "natalidade_2021": 36.7, "natalidade_2024": 23.8,
    "mortalidade_2021": 37.0, "mortalidade_2024": 48.5, "saldo_voltas_2024": 14.6, "voltas_2024": 947, "pausas_2024": 479,
    "total_2024": -10.1, "indice_2020": 0.60, "indice_2023": 0.84, "indice_2024": 1.16, "veteranos_2024": 881,
    "fatia_5mais_2024": 27.5, "novatos_2022": 1658, "pessoas": 21229, "q0": 51.4, "q1": 22.7, "q3": 16.5,
    "passam_1_ano": 48.6, "chegam_5_anos": 21.6, "e0": 3.29, "casuais_pct": 45.6, "casuais_sem_codigo_pct": 86.4,
    "contribuidores": 42760,
}  # fmt: skip


antiga, nova = serie(ANTIGA), serie(NOVA)
p_a = pd.read_parquet(ORIGENS / "v3_clojure" / "pessoas.parquet")
p_b = pd.read_parquet(ORIGENS / "v3b_clojure" / "pessoas.parquet")
anos_a = pd.read_parquet(
    ORIGENS / "v3_clojure" / "pessoas_repos_por_ano.parquet", columns=["pessoa", "ano"]
).drop_duplicates()
anos_b = pd.read_parquet(
    ORIGENS / "v3b_clojure" / "pessoas_repos_por_ano.parquet", columns=["pessoa", "ano"]
).drop_duplicates()
n_a, t_a = tabua(p_a, "B")
n_b, t_b = tabua(p_b, "B")
n_aa, t_aa = tabua(p_a, "A", anos_a.groupby("pessoa").size())
n_bb, t_bb = tabua(p_b, "A", anos_b.groupby("pessoa").size())
tab_a, tab_b = linhas_da_tabua(t_a, n_a), linhas_da_tabua(t_b, n_b)
tab_aa, tab_bb = linhas_da_tabua(t_aa, n_aa), linhas_da_tabua(t_bb, n_bb)
cas_a, cas_b = casuais(p_a), casuais(p_b)
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
            "v3_leitura_paralela": fmt(antigo),
            "v3b_leitura_sequencial": fmt(novo),
            "muda": "sim" if round(antigo, casas) != round(novo, casas) else "não",
        }
    )


linha(
    "Contribuidores da linguagem (Tabela da amostra)",
    "contribuidores",
    len(p_a),
    len(p_b),
    inteiro=True,
)
linha("Casuais entre os que chegaram até 2024 (%)", "casuais_pct", cas_a[1], cas_b[1])
linha(
    "Casuais que nunca fizeram commit nem PR (%)",
    "casuais_sem_codigo_pct",
    cas_a[2],
    cas_b[2],
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
    tab_a["pessoas"],
    tab_b["pessoas"],
    inteiro=True,
)
linha("RQ1.3 q(0), ano 0 (%)", "q0", tab_a["q0"], tab_b["q0"])
linha("RQ1.3 q(1), ano 1 (%)", "q1", tab_a["q1"], tab_b["q1"])
linha("RQ1.3 q(3), ano 3 (%)", "q3", tab_a["q3"], tab_b["q3"])
linha(
    "RQ1.3 passam do primeiro ano (%)",
    "passam_1_ano",
    tab_a["passam_1_ano"],
    tab_b["passam_1_ano"],
)
linha(
    "RQ1.3 chegam a 5 anos (%)",
    "chegam_5_anos",
    tab_a["chegam_5_anos"],
    tab_b["chegam_5_anos"],
)
linha("RQ1.3 e0, piso (anos)", "e0", tab_a["e0"], tab_b["e0"], 2)
tabela = pd.DataFrame(linhas)
tabela.to_csv(SAIDA / "rq1_v3_contra_v3b.csv", index=False)
T = [
    "# RQ1 de Clojure: carga v3 contra v3b",
    "",
    "v3 lê o arquivo final com a leitura paralela do duckdb; v3b com a leitura sequencial. Mesmas definições do artigo. A coluna do artigo mostra o que o texto traz hoje (carga de 09/11).",
    "",
    "| Número | Artigo | v3 (paralela) | v3b (sequencial) | Muda |",
    "|---|---|---|---|---|",
]
for _, x in tabela.iterrows():
    T.append(
        f"| {x['numero']} | {x['artigo']} | {x['v3_leitura_paralela']} | {x['v3b_leitura_sequencial']} | {x['muda']} |"
    )
T += [
    "",
    "Tábua com a idade da pirâmide (a da rodada oficial):",
    "",
    "| Carga | Pessoas | q(0) | Passam de 1 ano | Chegam a 5 anos | e0 (piso) |",
    "|---|---|---|---|---|---|",
    f"| v3 | {milhar(tab_aa['pessoas'])} | {dec(tab_aa['q0'])}% | {dec(tab_aa['passam_1_ano'])}% | {dec(tab_aa['chegam_5_anos'])}% | {dec(tab_aa['e0'], 2)} |",
    f"| v3b | {milhar(tab_bb['pessoas'])} | {dec(tab_bb['q0'])}% | {dec(tab_bb['passam_1_ano'])}% | {dec(tab_bb['chegam_5_anos'])}% | {dec(tab_bb['e0'], 2)} |",
    "",
]
(SAIDA / "rq1_v3_contra_v3b.md").write_text("\n".join(T) + "\n", encoding="utf-8")
print("\n".join(T))
