"""Impacto da leitura paralela do duckdb na carga de uma linguagem: compara a carga `-v3` (paralela) com a de teste `-v3b` (sequencial). Roda na VM.

Só lê. Mostra, por ano de 2017 a 2024:
  - eventos válidos que entram ou saem (`estatisticas_da_carga.json`);
  - pessoas que entram ou saem do conjunto de ativos não casuais (residentes pela vida inteira, como na RQ1);
  - pessoas que mudam de faixa (idade descontada, 6 faixas) entre as duas cargas;
  - pessoas que mudam de classificação não casual (uma ocasião contra mais de uma);
  - a população P1 (RQ3) por faixa em 31 de dezembro.

Uso (na raiz do repo, na VM): .venv/bin/python scripts/granularidade/compara_leituras_carga.py <carga v3> <carga v3b> <saida.md> <linguagem>
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, "src")
from estado import FIM, constroi_estado, soma_em_faixas6
from estado import junta_aberta_vet as junta_aberta

from pyramid import vitalidade as v

A, B, SAIDA, LINGUA = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]
ANOS = list(range(2017, 2025))


def milhar(x: float) -> str:
    return f"{x:,.0f}".replace(",", ".")


def sinal(x: float) -> str:
    return f"+{milhar(x)}" if x > 0 else milhar(x)


def le(carga: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    pasta = carga / LINGUA / "origem"
    pessoas = pd.read_parquet(
        pasta / "pessoas.parquet",
        columns=["pessoa", "primeiro", "ocasioes", "segunda_ocasiao", "codigo_do_primeiro"],
    )
    anos = pd.read_parquet(
        pasta / "pessoas_repos_por_ano.parquet", columns=["pessoa", "ano"]
    ).drop_duplicates()
    estat = json.loads((pasta / "estatisticas_da_carga.json").read_text(encoding="utf-8"))
    return pessoas, anos, estat


def faixa_por_pessoa_ano(pessoas: pd.DataFrame, anos: pd.DataFrame) -> pd.DataFrame:
    """Faixa (6 faixas) de cada pessoa em cada ano ativo, pela idade descontada de `pessoa_ano`."""
    d = anos.merge(pessoas[["pessoa", "primeiro"]], on="pessoa")
    d = d[d["ano"].between(ANOS[0], ANOS[-1])].copy()
    d = d.sort_values(["pessoa", "ano"])
    posicao = d.groupby("pessoa").cumcount()
    # anos ativos antes do ano de cada linha, contando todos os anos ativos da pessoa (inclusive antes de 2017)
    antes = anos[anos["ano"] < ANOS[0]].groupby("pessoa").size()
    posicao = posicao + d["pessoa"].map(antes).fillna(0).astype(int)
    referencia = pd.to_datetime((d["ano"] + 1).astype(str) + "-01-01") - pd.Timedelta(days=1)
    vazios = d["ano"] - d["primeiro"].dt.year - posicao
    idade = (v.anos_completos(d["primeiro"], referencia) - vazios).clip(lower=0)
    d["faixa"] = v.faixa_de(idade)
    return d[["pessoa", "ano", "faixa"]]


pa, aa, ea = le(A)
pb, ab, eb = le(B)

L = [
    f"# Leitura paralela contra leitura sequencial na carga de {LINGUA}",
    "",
    "Carga `-v3` (paralela, a usada em tudo) contra a de teste `-v3b` (sequencial). Cada célula mostra a diferença (v3b menos v3), quando há.",
    "",
    "## Eventos válidos",
    "",
    "| Estatística da carga | v3 | v3b | Diferença |",
    "|---|---|---|---|",
]
for chave in [
    "eventos_api_desta_linguagem", "eventos_git_desta_linguagem", "linhas_repetidas_descartadas_api", "linhas_repetidas_descartadas_git",
    "commits_duplicados_descartados", "eventos_antes_do_piso_descartados", "eventos_apos_elegibilidade", "eventos_finais",
    "repos_finais", "contribuidores_finais",
]:  # fmt: skip
    if chave in ea and chave in eb:
        L.append(
            f"| {chave} | {milhar(ea[chave])} | {milhar(eb[chave])} | {sinal(eb[chave] - ea[chave])} |"
        )

# pessoas
ja, jb = pa.set_index("pessoa"), pb.set_index("pessoa")
so_a, so_b = ja.index.difference(jb.index), jb.index.difference(ja.index)
comum = ja.index.intersection(jb.index)
L += [
    "",
    f"## Pessoas de {LINGUA} (todas, casuais inclusive)",
    "",
    f"- Só na v3: {milhar(len(so_a))}. Só na v3b: {milhar(len(so_b))}. Nas duas: {milhar(len(comum))}.",
]
ca, cb = ja.loc[comum], jb.loc[comum]
muda_entrada = (ca["primeiro"].dt.year != cb["primeiro"].dt.year).sum()
muda_ocasioes = ((ca["ocasioes"] > 1) != (cb["ocasioes"] > 1)).sum()
L += [
    f"- Mudam de ano de entrada: {milhar(int(muda_entrada))}.",
    f"- Mudam de classificação não casual (uma ocasião contra mais de uma): {milhar(int(muda_ocasioes))}.",
    "",
]

# ativos não casuais (RQ1) por ano e mudança de faixa
na_a, na_b = ja.index[ja["ocasioes"] > 1], jb.index[jb["ocasioes"] > 1]
fa = faixa_por_pessoa_ano(pa, aa)
fb_ = faixa_por_pessoa_ano(pb, ab)
fa = fa[fa["pessoa"].isin(na_a)]
fb_ = fb_[fb_["pessoa"].isin(na_b)]
L += [
    "## Ativos não casuais por ano (residentes pela vida inteira)",
    "",
    "| Ano | v3 | v3b | Entram na v3b | Saem na v3b | Mudam de faixa | Mudam de classificação não casual |",
    "|---|---|---|---|---|---|---|",
]
for ano in ANOS:
    sa = fa[fa["ano"] == ano].set_index("pessoa")["faixa"]
    sb = fb_[fb_["ano"] == ano].set_index("pessoa")["faixa"]
    entram, saem = sb.index.difference(sa.index), sa.index.difference(sb.index)
    ambos = sa.index.intersection(sb.index)
    muda_faixa = int((sa.loc[ambos].astype(str) != sb.loc[ambos].astype(str)).sum())
    ativos_a = set(aa.loc[aa["ano"] == ano, "pessoa"])
    ativos_b = set(ab.loc[ab["ano"] == ano, "pessoa"])
    comuns = ativos_a & ativos_b & set(comum)
    idx = pd.Index(sorted(comuns))
    flips = int(((ja.loc[idx, "ocasioes"] > 1) != (jb.loc[idx, "ocasioes"] > 1)).sum())
    L.append(
        f"| {ano} | {milhar(len(sa))} | {milhar(len(sb))} | {milhar(len(entram))} | {milhar(len(saem))} | {milhar(muda_faixa)} | {milhar(flips)} |"
    )

# P1 (RQ3)
L += [
    "",
    "## População P1 da RQ3 em 31 de dezembro, por faixa",
    "",
    "| Ano | Total v3 | Total v3b | Diferença | "
    + " | ".join(f"{f}" for f in ["0-1", "1-2", "2-3", "3-5", "5-8", "8+"])
    + " (diferença v3b menos v3) |",
    "|---|---|---|---|---|---|---|---|---|---|",
]
estados = {}
for rotulo, carga in [("v3", A), ("v3b", B)]:
    p = pd.read_parquet(
        carga / LINGUA / "origem" / "pessoas.parquet",
        columns=["pessoa", "ocasioes", "codigo_do_primeiro", "segunda_ocasiao"],
    )
    p["segunda"] = p["segunda_ocasiao"].dt.floor("D").to_numpy().astype("datetime64[D]")
    p = p.drop(columns=["segunda_ocasiao"])
    dias = pd.read_parquet(carga / LINGUA / "origem" / "pessoas_repos_por_dia.parquet")
    eventos = {
        "pessoa": dias["pessoa"].to_numpy(),
        "codigo": dias["codigo"].to_numpy(),
        "dia": pd.to_datetime(dias["dia"]).to_numpy().astype("datetime64[D]"),
    }
    estados[rotulo] = constroi_estado(
        p, eventos, 12, "P1", FIM, janela_blocos=None, idade="descontada", com_parada=True
    )
datas = estados["v3"]["datas"]
for ano in ANOS:
    k = int(np.where(datas == np.datetime64(f"{ano}-12-31"))[0][0])
    fa6 = soma_em_faixas6(junta_aberta(estados["v3"]["pop_p_b"][k]), estados["v3"]["nb"])
    fb6 = soma_em_faixas6(junta_aberta(estados["v3b"]["pop_p_b"][k]), estados["v3b"]["nb"])
    dif = fb6 - fa6
    L.append(
        f"| {ano} | {milhar(fa6.sum())} | {milhar(fb6.sum())} | {sinal(fb6.sum() - fa6.sum())} | "
        + " | ".join(sinal(x) for x in dif)
        + " |"
    )
SAIDA.write_text("\n".join(L) + "\n", encoding="utf-8")
print("\n".join(L))
