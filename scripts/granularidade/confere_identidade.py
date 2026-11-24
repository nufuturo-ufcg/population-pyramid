"""Confere, por linguagem, ativos(t+1) = ativos(t) - saidas(t) + entradas(t+1) de 2008 a 2023, com a definição única de entrada e saída.

Usa os eventos compactos de cada linguagem (`<pasta>/<linguagem>/cache/vitalidade_eventos.parquet`) e a origem
(`<pasta>/<linguagem>/origem/pessoas.parquet`), na população de residentes (mais de uma ocasião). A tabela vem de
`vitalidade.tabela_anual`, que levanta erro se a conta não fecha; aqui o assert é explícito e a tabela anual é gravada.

Uso (na raiz do repo): .venv/bin/python scripts/granularidade/confere_identidade.py <pasta> <saida.csv> <linguagens...>
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, "src")
from pyramid import vitalidade

PASTA, SAIDA = Path(sys.argv[1]), Path(sys.argv[2])
LINGUAS = sys.argv[3:]
ULTIMO_ANO = 2025  # a rodada oficial vai até a data de corte de 2025-12-31
linhas = []
for lingua in LINGUAS:
    compactos = pd.read_parquet(PASTA / lingua / "cache" / "vitalidade_eventos.parquet")
    pessoas = pd.read_parquet(
        PASTA / lingua / "origem" / "pessoas.parquet", columns=["pessoa", "ocasioes"]
    )
    residentes = pessoas.loc[pessoas["ocasioes"] > 1, "pessoa"]
    compactos = compactos[compactos["contributor_id"].isin(residentes)]
    fim = compactos["timestamp"].max()
    pa = vitalidade.pessoa_ano(compactos, fim)
    pa = pa[pa["ano"] <= ULTIMO_ANO].reset_index(drop=True)
    anual = vitalidade.tabela_anual(pa, fim).set_index("ano").reindex(range(2008, ULTIMO_ANO + 1))
    contagens = [
        "ativos",
        "novatos",
        "voltas",
        "entradas",
        "saidas_sem_volta",
        "saidas_com_volta",
        "saidas",
    ]
    # ano sem ninguém (linguagem que ainda não existia) vale zero, exceto a saída do ano aberto
    anual[contagens[:4]] = anual[contagens[:4]].fillna(0)
    anual.loc[:2024, contagens[4:]] = anual.loc[:2024, contagens[4:]].fillna(0)
    for ano in range(2008, 2024):
        esperado = (
            anual.loc[ano, "ativos"] - anual.loc[ano, "saidas"] + anual.loc[ano + 1, "entradas"]
        )
        assert esperado == anual.loc[ano + 1, "ativos"], (
            f"{lingua} {ano}: esperado {esperado}, ativos {anual.loc[ano + 1, 'ativos']}"
        )
        assert anual.loc[ano, "entradas"] == anual.loc[ano, "novatos"] + anual.loc[ano, "voltas"]
        assert (
            anual.loc[ano, "saidas"]
            == anual.loc[ano, "saidas_sem_volta"] + anual.loc[ano, "saidas_com_volta"]
        )
    anual = anual.reset_index()
    anual.insert(0, "linguagem", lingua)
    linhas.append(anual)
    print(
        f"{lingua}: identidade confere de 2008 a 2023 ({len(compactos)} eventos, {len(residentes)} residentes)",
        flush=True,
    )
tabela = pd.concat(linhas, ignore_index=True)
tabela.to_csv(SAIDA, index=False)
print(f"tabela anual gravada em {SAIDA}")
