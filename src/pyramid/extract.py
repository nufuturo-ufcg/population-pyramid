"""Estágio 1: extração. Um parquet de eventos por projeto."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from . import logging_config as runlog
from .config import settings, stage_dir
from .sources.msr14 import MSR14Source

log = logging.getLogger(__name__)
STAGE = "extract"


def source() -> MSR14Source:
    """Fonte de dados configurada.

    A fonte abre a própria conexão. O motor de cálculo trabalha sobre
    DataFrame e desconhece banco.
    """
    return MSR14Source(settings())


def events_path(scope_id: int) -> Path:
    """Arquivo de eventos brutos de um projeto."""
    return stage_dir(STAGE) / f"{scope_id}.parquet"


def labels() -> dict[int, str]:
    """`{scope_id: "owner/name"}` a partir do manifesto do extract.

    Os rótulos são os mesmos que `MSR14Source.list_scopes()` gravou: este é um
    cache em disco, não uma segunda fonte de verdade. Existe para que os
    estágios de leitura (plots) rodem sem o MySQL de pé. Se o manifesto não
    tiver o projeto, cai no banco.
    """
    man = runlog.load(STAGE)
    out = {int(k): v["label"] for k, v in man.get("ok", {}).items() if v.get("label")}
    if not out:
        src = source()
        src.list_scopes()
        return dict(src._labels)
    return out


def label_of(scope_id: int) -> str:
    """Nome `owner/name` do projeto. Devolve o próprio id quando não houver nome."""
    return labels().get(int(scope_id), str(scope_id))


def load_events(scope_id: int) -> pd.DataFrame:
    """Lê os eventos extraídos de um projeto."""
    return pd.read_parquet(events_path(scope_id))


def run(scopes: list[int] | None = None, force: bool = False, fail_fast: bool = False) -> dict:
    """Executa o estágio extract nos projetos pedidos.

    `scopes=None` roda os 90 projetos do dump. `force` recalcula o que já
    está gravado. `fail_fast` interrompe no primeiro projeto que falhar; o
    padrão anota a falha no manifesto e segue para o próximo. Devolve o
    manifesto.
    """
    src = source()
    man = runlog.load(STAGE)
    if force:
        man = {"stage": STAGE, "ok": {}, "failed": {}}

    man["taxonomy_variant"] = src.variant
    man["commit_scope"] = src.commit_scope

    targets = scopes if scopes is not None else src.list_scopes()
    if scopes is not None:
        src.list_scopes()  # popula rótulos e roda o sanity check dos 90

    for sid in targets:
        key = str(sid)
        if not force and key in man["ok"] and events_path(sid).exists():
            log.debug("pulando %s (ja extraido)", sid)
            continue
        try:
            df = src.get_events(sid)
            # Ordem canonica: o SGBD nao garante ordem sem ORDER BY (as linhas
            # saem na ordem fisica do InnoDB, que muda entre importacoes do
            # dump). Sem isso o parquet de um mesmo projeto muda de md5 entre
            # execucoes, quebrando a verificacao por hash. Ver discrepancias.md.
            df = df.sort_values(
                ["scope_id", "contributor_id", "timestamp", "event_type"],
                kind="mergesort",
            ).reset_index(drop=True)
            df.to_parquet(events_path(sid), index=False)
            man["ok"][key] = {
                "label": src.scope_label(sid),
                "events": len(df),
                "contributors": int(df["contributor_id"].nunique()),
                "first": str(df["timestamp"].min()),
                "last": str(df["timestamp"].max()),
            }
            man["failed"].pop(key, None)
            log.info(
                "%-38s %7d eventos  %5d contribuidores",
                src.scope_label(sid),
                len(df),
                df["contributor_id"].nunique(),
                extra={"scope_id": sid, "stage": STAGE},
            )
        except Exception as e:
            man["failed"][key] = f"{type(e).__name__}: {e}"
            log.exception("falha em %s", sid, extra={"scope_id": sid, "stage": STAGE})
            if fail_fast:
                runlog.save(STAGE, man)
                raise
        runlog.save(STAGE, man)

    runlog.save(STAGE, man)
    log.info(runlog.summarize(STAGE, man))
    return man
