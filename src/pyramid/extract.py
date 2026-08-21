"""Estágio 1: extração. Um parquet de eventos por projeto."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from . import logging_config as runlog
from . import sources
from .config import analysis_unit, settings, stage_dir
from .sources.base import EVENT_COLUMNS, ActivityDataSource
from .units import Escopo, scopes_of_unit

log = logging.getLogger(__name__)
STAGE = "extract"

# Contagem que o próprio extract escreve na entrada do manifesto. O que sobra
# na entrada veio do `scope_meta()` do adaptador.
_CONTAGEM = ("events", "contributors", "first", "last")


def source() -> ActivityDataSource:
    """Fonte de dados configurada, do adaptador em `input.adapter`.

    A fonte abre a própria conexão. O motor de cálculo trabalha sobre
    DataFrame e desconhece origem.
    """
    return sources.load()(settings())


def events_path(scope_id: int) -> Path:
    """Arquivo de eventos brutos de um projeto."""
    return stage_dir(STAGE) / f"{scope_id}.parquet"


def serializa_meta(meta: dict) -> dict:
    """`scope_meta` em tipos que o JSON do manifesto aguenta.

    `created_at` vira string ISO. O resto passa como está, inclusive chave que
    só aquele adaptador tem.
    """
    saida = dict(meta)
    nascimento = saida.get("created_at")
    if nascimento is not None:
        saida["created_at"] = str(nascimento)
    return saida


def scope_meta() -> dict[int, dict]:
    """`{scope_id: scope_meta}` a partir do manifesto do extract.

    O manifesto é cache em disco do que o adaptador já respondeu. Existe para
    que os estágios de leitura (plots, agregação por outro eixo) rodem sem o
    banco de pé. Manifesto vazio cai no adaptador, pelo contrato público.
    """
    man = runlog.load(STAGE)
    out = {
        int(k): {c: valor for c, valor in v.items() if c not in _CONTAGEM}
        for k, v in man.get("ok", {}).items()
        if v.get("label")
    }
    if not out:
        src = source()
        return {e.id: serializa_meta(e.meta) for e in scopes_of_unit(src)}
    return out


def labels() -> dict[int, str]:
    """`{scope_id: "owner/name"}`, do mesmo cache que `scope_meta()`."""
    return {sid: meta["label"] for sid, meta in scope_meta().items() if meta.get("label")}


def label_of(scope_id: int) -> str:
    """Rótulo legível do escopo. Devolve o próprio id quando o adaptador não dá nome."""
    return labels().get(int(scope_id), str(scope_id))


def load_events(scope_id: int) -> pd.DataFrame:
    """Lê os eventos extraídos de um projeto."""
    return pd.read_parquet(events_path(scope_id))


def _eventos_do_escopo(src: ActivityDataSource, sid: int, escopo: Escopo | None) -> pd.DataFrame:
    """Eventos de um escopo lógico, já com o `scope_id` dele.

    Com um membro só, é o que o adaptador devolveu. Com vários, é a união, e o
    `scope_id` de cada linha passa a ser o do escopo lógico, senão o `classify`
    agruparia por repositório e desfaria a soma.
    """
    if escopo is None or escopo.membros == (sid,):
        return src.get_events(sid)
    partes = [src.get_events(m) for m in escopo.membros]
    df = pd.concat(partes, ignore_index=True) if partes else pd.DataFrame(columns=EVENT_COLUMNS)
    df["scope_id"] = sid
    return df


def run(scopes: list[int] | None = None, force: bool = False, fail_fast: bool = False) -> dict:
    """Executa o estágio extract nos projetos pedidos.

    `scopes=None` roda todos os escopos que o adaptador expõe. `force` recalcula o que já
    está gravado. `fail_fast` interrompe no primeiro projeto que falhar; o
    padrão anota a falha no manifesto e segue para o próximo. Devolve o
    manifesto.
    """
    analysis_unit()  # unidade sem agregador para aqui, antes de tocar no banco
    src = source()
    man = runlog.load(STAGE)
    if force:
        man = {"stage": STAGE, "ok": {}, "failed": {}}

    man.update(src.provenance())

    # Um escopo lógico é uma pirâmide. Com `unit: project` ele é um escopo do
    # adaptador. Com `unit: language` ele soma os escopos que compartilham a
    # linguagem, e essa soma acontece AQUI, antes do `classify`, porque é o
    # `profile` que decide quem nasceu quando.
    logicos = {e.id: e for e in scopes_of_unit(src)}
    targets = scopes if scopes is not None else list(logicos)
    if scopes is not None:
        src.list_scopes()  # popula rótulos e roda o sanity check do adaptador

    for sid in targets:
        key = str(sid)
        if not force and key in man["ok"] and events_path(sid).exists():
            log.debug("pulando %s (ja extraido)", sid)
            continue
        escopo = logicos.get(sid)
        try:
            df = _eventos_do_escopo(src, sid, escopo)
            # Ordem canonica: o SGBD nao garante ordem sem ORDER BY (as linhas
            # saem na ordem fisica do InnoDB, que muda entre importacoes do
            # dump). Sem isso o parquet de um mesmo projeto muda de md5 entre
            # execucoes, quebrando a verificacao por hash. Ver discrepancias.md.
            df = df.sort_values(
                ["scope_id", "contributor_id", "timestamp", "event_type"],
                kind="mergesort",
            ).reset_index(drop=True)
            df.to_parquet(events_path(sid), index=False)
            meta = escopo.meta if escopo is not None else src.scope_meta(sid)
            man["ok"][key] = {
                **serializa_meta(meta),
                "events": len(df),
                "contributors": int(df["contributor_id"].nunique()),
                "first": str(df["timestamp"].min()),
                "last": str(df["timestamp"].max()),
            }
            man["failed"].pop(key, None)
            log.info(
                "%-38s %7d eventos  %5d contribuidores",
                escopo.label if escopo is not None else src.scope_label(sid),
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
