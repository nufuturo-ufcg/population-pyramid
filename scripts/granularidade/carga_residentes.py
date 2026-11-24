"""Eventos compactos e pessoa-ano dos residentes (mais de uma ocasião) de uma linguagem, como na rodada.

Usa `<pasta>/<linguagem>/cache/vitalidade_eventos.parquet` e `<pasta>/<linguagem>/origem/pessoas.parquet`.
`fim` é o último instante dos eventos (fim do acompanhamento). O pessoa-ano vai até 2025.
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, "src")
from pyramid import vitalidade

ULTIMO_ANO = 2025


def carrega_residentes(pasta: Path, lingua: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.Timestamp]:
    compactos = pd.read_parquet(pasta / lingua / "cache" / "vitalidade_eventos.parquet")
    pessoas = pd.read_parquet(
        pasta / lingua / "origem" / "pessoas.parquet", columns=["pessoa", "ocasioes"]
    )
    residentes = pessoas.loc[pessoas["ocasioes"] > 1, "pessoa"]
    compactos = compactos[compactos["contributor_id"].isin(residentes)]
    fim = compactos["timestamp"].max()
    pa = vitalidade.pessoa_ano(compactos, fim)
    pa = pa[pa["ano"] <= ULTIMO_ANO].reset_index(drop=True)
    return compactos, pa, fim
