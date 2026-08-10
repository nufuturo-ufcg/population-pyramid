"""Estágio 2: perfil de cada contribuidor dentro de um projeto.

Produz, por (projeto, contribuidor):
  init_c   primeiro evento de CODING          (NaT se nunca codou)
  init_d   primeiro evento de NON-CODING      (NaT se nunca discutiu)
  spans    períodos de atividade contínuos, quebrados por 3 meses de silêncio

A categoria (coding / moved / non_coding) e a idade NÃO são fixas: dependem do
snapshot, e são resolvidas no estágio 3. Aqui só destilamos a linha do tempo.

Idade NÃO é decidida aqui, e a regra em vigor não é a leitura literal do artigo.
Os spans deste estágio alimentam as duas leituras possíveis de "less than three
months of activity periods" (IEICE16 p.1308), escolhidas em
`periods.age_basis`:

  calendar_tenure     (EM VIGOR) idade = tempo desde a origem; gaps não
                      descontam, como idade numa pirâmide demográfica.
  accumulated_active  (REFUTADA) idade = soma dos spans. Produz 41/42/0/0 nos
                      Tipos A-D de set/2013 contra 23/42/18/3 do artigo: sem
                      atividade contínua ninguém chega a 3 meses e C+D ficam
                      VAZIOS. Ver docs/discrepancias.md, seções 3 e 19.5.

O que os spans decidem de fato é quem está VIVO no snapshot ("we consider that a
contributor left a project when he/she did not give any contribution for more
than three months") e a frase "we consider them as experienced contributors when
they come back", que sob `calendar_tenure` sai de graça: quem volta tem tenure
grande e já cai fora da banda de novato.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from . import logging_config as runlog
from .config import settings, stage_dir
from .extract import load_events, source

log = logging.getLogger(__name__)
STAGE = "classify"

DAYS_PER_MONTH = 365.25 / 12  # 30.4375


def coding_events() -> set[str]:
    s = settings()["taxonomy"]
    return set(s["variants"][s["variant"]]["coding"])


def _spans(ts: np.ndarray, gap_days: float) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Quebra timestamps ordenados em períodos separados por gaps > gap_days."""
    if len(ts) == 0:
        return []
    out = []
    start = prev = ts[0]
    for t in ts[1:]:
        if (t - prev) / np.timedelta64(1, "D") > gap_days:
            out.append((start, prev))
            start = t
        prev = t
    out.append((start, prev))
    return out


def profile(events: pd.DataFrame, coding: set[str], gap_days: float) -> pd.DataFrame:
    """Um DataFrame longo: uma linha por (contribuidor, span)."""
    if events.empty:
        return pd.DataFrame(
            columns=["contributor_id", "init_c", "init_d", "span_start", "span_end", "span_idx"]
        )

    ev = events.sort_values(["contributor_id", "timestamp"], kind="stable")
    is_coding = ev["event_type"].isin(coding)

    firsts = (
        ev.assign(_c=ev["timestamp"].where(is_coding), _d=ev["timestamp"].where(~is_coding))
        .groupby("contributor_id", sort=False)
        .agg(init_c=("_c", "min"), init_d=("_d", "min"))
    )

    rows = []
    for cid, g in ev.groupby("contributor_id", sort=False):
        for i, (a, b) in enumerate(_spans(g["timestamp"].to_numpy(), gap_days)):
            rows.append((cid, a, b, i))

    spans = pd.DataFrame(rows, columns=["contributor_id", "span_start", "span_end", "span_idx"])
    return spans.merge(firsts, on="contributor_id", how="left")


def path(scope_id: int):
    return stage_dir(STAGE) / f"{scope_id}.parquet"


def load(scope_id: int) -> pd.DataFrame:
    return pd.read_parquet(path(scope_id))


def run(scopes: list[int] | None = None, force: bool = False, fail_fast: bool = False) -> dict:
    cfg = settings()
    gap_days = cfg["periods"]["inactivity_months"] * DAYS_PER_MONTH
    coding = coding_events()

    src = source()
    targets = scopes if scopes is not None else src.list_scopes()

    man = runlog.load(STAGE)
    if force:
        man = {"stage": STAGE, "ok": {}, "failed": {}}
    man["taxonomy_variant"] = cfg["taxonomy"]["variant"]
    man["gap_days"] = gap_days

    for sid in targets:
        key = str(sid)
        if not force and key in man["ok"] and path(sid).exists():
            continue
        try:
            df = profile(load_events(sid), coding, gap_days)
            df.to_parquet(path(sid), index=False)
            n_c = int(df.loc[df["init_c"].notna(), "contributor_id"].nunique())
            n_total = int(df["contributor_id"].nunique())
            man["ok"][key] = {
                "contributors": n_total,
                "ever_coded": n_c,
                "spans": len(df),
                "multi_span": int((df["span_idx"] > 0).sum()),
            }
            man["failed"].pop(key, None)
            log.info(
                "%-38s %5d contribuidores (%4d codaram)  %5d spans",
                src.scope_label(sid),
                n_total,
                n_c,
                len(df),
                extra={"scope_id": sid, "stage": STAGE},
            )
        except Exception as e:  # noqa: BLE001
            man["failed"][key] = f"{type(e).__name__}: {e}"
            log.exception("falha em %s", sid, extra={"scope_id": sid, "stage": STAGE})
            if fail_fast:
                runlog.save(STAGE, man)
                raise
        runlog.save(STAGE, man)

    runlog.save(STAGE, man)
    log.info(runlog.summarize(STAGE, man))
    return man
