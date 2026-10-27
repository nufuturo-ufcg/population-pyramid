"""Carga dos eventos de uma linguagem, compactados, com o motor à escolha.

    carrega(fonte, motor="pandas")   # até algumas dezenas de GB, tudo em memória
    carrega(fonte, motor="duckdb")   # centenas de GB, em paralelo e com derrame em disco

Os dois aplicam as mesmas regras de `figuras_linguagem_bruta.carrega_eventos` e devolvem
[contributor_id, event_type, timestamp]. Outro motor entra registrando uma função em
`MOTORES` que recebe a `Fonte` e as opções e devolve esse DataFrame. `tests/test_carga.py`
confere os dois contra a carga original.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

import pandas as pd

import figuras_linguagem_bruta as fb
from carga_fonte import Fonte, le_alvos, marca_elegiveis


def _pandas(fonte: Fonte, **_: object) -> pd.DataFrame:
    import carga_pandas

    return carga_pandas.carrega(fonte)


def _duckdb(
    fonte: Fonte,
    trabalho: Path,
    memoria: str = "30GB",
    threads: int | None = None,
    contar_brutas: bool = True,
    origem: Path | None = None,
    acoes_ignoradas: tuple[str, ...] = (),
    fundir_identidades: bool = False,
    completos: bool = False,
    **_: object,
) -> pd.DataFrame:
    """O motor duckdb mora em `adapters/coleta_csv/`, onde o SQL é permitido."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from adapters.coleta_csv import carga_duckdb

    fb.ESTATISTICAS_CARGA.pop(fb.LING.atual.slug, None)
    fb._stats_erros_coleta()
    repos = marca_elegiveis(le_alvos(fonte))
    repos.insert(0, "codigo", range(len(repos)))
    repos = repos.rename(columns={"mainLanguage": "principal", "createdAt": "criado"})
    pedido = carga_duckdb.Pedido(
        eventos=[(a.caminho, a.papel) for a in fonte.eventos],
        repos=repos,
        linguagem=fb.LING.atual.nome,
        extensoes=fb.LING.atual.extensoes,
        tipos=fb.MAPA_TIPO_R2,
        trabalho=trabalho,
        memoria=memoria,
        threads=threads,
        contar_brutas=contar_brutas,
        origem=origem,
        acoes_ignoradas=acoes_ignoradas,
        fundir_identidades=fundir_identidades,
        autores=fonte.autores,
        completos=completos,
    )
    if origem is not None:
        origem.mkdir(parents=True, exist_ok=True)
        repos[["codigo", "repo_id"]].to_parquet(origem / "repos.parquet", index=False)
    resultado = carga_duckdb.carrega(pedido)
    fb._stats().update(resultado.estatisticas)
    if len(resultado.fantasmas):
        fb._salva_fantasmas_por_ano(resultado.fantasmas)
    return resultado.eventos


MOTORES: dict[str, Callable[..., pd.DataFrame]] = {"pandas": _pandas, "duckdb": _duckdb}


def carrega(fonte: Fonte, motor: str = "pandas", **opcoes: object) -> pd.DataFrame:
    """Eventos [contributor_id, event_type, timestamp] da fonte, lidos pelo motor escolhido.

    Opções do `duckdb`: `trabalho` (pasta em disco para o derrame), `memoria` ("30GB"), `threads`,
    `contar_brutas` (relê o arquivo só para contar linhas), `origem` (pasta onde grava a origem de
    cada pessoa, ver `carga_duckdb._grava_origem`), `acoes_ignoradas` (ações de issue_event que
    saem, como `("mentioned",)`), `fundir_identidades` (nome de commit -> login, ver
    `carga_duckdb`), `completos` (um evento por linha com repositório, para o pipeline do motor).
    """
    if motor not in MOTORES:
        raise SystemExit(f"motor {motor!r} desconhecido: use {list(MOTORES)}.")
    if opcoes.get("acoes_ignoradas") and motor != "duckdb":
        raise SystemExit("acoes_ignoradas só existe no motor duckdb: use --set motor=duckdb.")
    if opcoes.get("fundir_identidades") and motor != "duckdb":
        raise SystemExit("fundir_identidades só existe no motor duckdb: use --set motor=duckdb.")
    if opcoes.get("completos") and motor != "duckdb":
        raise SystemExit("completos só existe no motor duckdb: use --set motor=duckdb.")
    if fonte.autores and motor != "duckdb":
        raise SystemExit("autores (vitalidade_fontes.yaml) só existe no motor duckdb.")
    return MOTORES[motor](fonte, **opcoes)
