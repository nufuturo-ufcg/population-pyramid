"""Estágio 3: a pirâmide propriamente dita, snapshot a snapshot.

Para cada (projeto, snapshot T, contribuidor):
  category  coding | moved | non_coding: recalculada em cada snapshot T,
            pois depende do progresso do contribuidor até aquele instante
  age_days  tempo desde a origem até T (`periods.age_basis: calendar_tenure`;
            gaps de inatividade NÃO descontam. A leitura alternativa, que soma
            os spans, foi refutada, ver docs/replicacao/discrepancias.md, seção 3)
  band      faixa de 3 meses, fechada em cima (0 = (0,3m], 1 = (3,6m], ...)
  active    contribuiu nos últimos 3 meses antes de T

A categoria depende do snapshot de propósito: quem discute em 2011 e só vai
codar em 2012 aparece como `non_coding` nas pirâmides de 2011 e migra pro lado
coding (como `moved`) a partir de 2012. É essa migração que a Fig.3 do ESEM14
mostra ao longo dos anos.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from . import logging_config as runlog
from .classify import DAYS_PER_MONTH
from .classify import load as load_spans
from .config import settings, stage_dir
from .extract import source

log = logging.getLogger(__name__)
STAGE = "snapshots"

CATEGORIES = ["non_coding", "moved", "coding"]


def band_days(cfg: dict | None = None) -> float:
    """Largura da banda da pirâmide, em dias.

    Fica atrás de função (e não solta no YAML) por causa da checagem: `band_days`
    e `band_months` descrevem a MESMA banda em unidades diferentes, e se alguém
    mexer num sem mexer no outro o eixo y passa a rotular uma banda que o corte
    não usa: a figura mentiria em silêncio. 10% é folga para o desencontro
    medido (90 vs 91.3125, 1.4%); uma banda de tamanho diferente cai fora
    dessa margem e deve disparar o erro acima.
    """
    cfg = cfg or settings()
    bd = float(cfg["periods"]["band_days"])
    bm = float(cfg["periods"]["band_months"])
    nominal = bm * DAYS_PER_MONTH
    if not (0.9 * nominal <= bd <= 1.1 * nominal):
        raise ValueError(
            f"periods.band_days={bd} não descreve a mesma banda que "
            f"periods.band_months={bm} (~{nominal:.2f} dias). "
            "Mexeu num, mexa no outro."
        )
    return bd


def snapshot_dates(cfg: dict | None = None) -> list[pd.Timestamp]:
    """Série de snapshots em fins de trimestre civil.

    Usa `QuarterEnd` para ancorar a série. A alternativa, `DateOffset(months=3)`
    acumulado a partir do `start`, foi descartada: o pandas aplica um DateOffset
    iterativamente, então o dia-do-mês é truncado no primeiro mês curto e nunca
    se recupera: de 2010-03-31 saía 2010-06-30, depois 2010-12-30, 2011-12-30,
    2013-03-30, e todo o resto da série ficava grudado no dia 30. Jun/set
    pareciam corretos só por coincidência (esses meses acabam mesmo no dia 30),
    o que escondia o bug. Ver docs/replicacao/discrepancias.md, seção 8.

    `freq_months` continua respeitado, mas só em múltiplos de trimestre, que é o
    que o método usa (IEICE16 seção 4.1: March, June, September). Qualquer outro
    valor conta como erro de config.
    """
    s = (cfg or settings())["snapshots"]
    months = s["freq_months"]
    if months % 3 != 0:
        raise ValueError(
            f"snapshots.freq_months={months}: a série é ancorada em fim de "
            "trimestre civil, então só múltiplos de 3 são suportados."
        )
    dates = pd.date_range(s["start"], s["end"], freq=pd.offsets.QuarterEnd())
    return list(dates[:: months // 3])


def require_date_match(
    result: pd.DataFrame, wanted: pd.Timestamp, column: str, ctx: str
) -> pd.DataFrame:
    """Falha alto quando um filtro por data de snapshot não casa nada.

    Regra geral do projeto: nenhum filtro/join contra a série de datas pode
    seguir com resultado vazio em silêncio. Uma data que não existe na série é
    sempre erro de config ou de geração da série. A leitura "esse snapshot
    está vazio" fica descartada, porque a série é gerada inteira antes do
    filtro: uma data ausente denuncia um problema de configuração.
    Foi exatamente esse silêncio que deixou o bug do QuarterEnd passar
    despercebido até 2026-08 (docs/replicacao/discrepancias.md, seção 8).
    """
    if not result.empty:
        return result
    series = [str(t.date()) for t in snapshot_dates()]
    raise ValueError(
        f"{ctx}: filtro {column} == {pd.Timestamp(wanted).date()} não casou "
        "nenhuma linha. Datas válidas na série: " + ", ".join(series) + ". "
        "Se a data pedida parece certa, o erro está na geração da série "
        "(snapshots.start/freq_months em config/settings.yaml), não nos dados."
    )


def check_dates(cfg: dict | None = None) -> None:
    """Falha alto se uma data pedida na config não existe na série.

    Sem isso, `projection_base: 2013-03-31` (data que a série não gera) filtra
    zero linhas em silêncio e a projeção roda sobre um DataFrame vazio.
    """
    cfg = cfg or settings()
    s = cfg["snapshots"]
    series = set(snapshot_dates(cfg))
    wanted: list[tuple[str, str]] = [
        ("snapshots.classification_snapshot", s["classification_snapshot"]),
        ("snapshots.projection_target", s["projection_target"]),
    ]
    wanted += [(f"snapshots.projection_base[{i}]", d) for i, d in enumerate(s["projection_base"])]
    bad = [(k, d) for k, d in wanted if pd.Timestamp(d) not in series]
    if bad:
        near = sorted(series)[-6:]
        raise ValueError(
            "datas de config ausentes da série de snapshots: "
            + ", ".join(f"{k}={d}" for k, d in bad)
            + ". A série termina em: "
            + ", ".join(str(t.date()) for t in near)
            + ". A série é ancorada em fim de trimestre CIVIL (QuarterEnd), "
            "então dez/mar caem no dia 31 e jun/set no dia 30 "
            "(ver docs/replicacao/discrepancias.md, seção 8)."
        )


def pyramid_at(spans: pd.DataFrame, t: pd.Timestamp, gap_days: float) -> pd.DataFrame:
    """Estado de todos os contribuidores de um projeto no instante t."""
    if spans.empty:
        return pd.DataFrame(columns=["contributor_id", "category", "age_days", "band", "active"])

    s = spans[spans["span_start"] <= t].copy()
    if s.empty:
        return pd.DataFrame(columns=["contributor_id", "category", "age_days", "band", "active"])

    # span truncado em t: quem ainda está no meio de um período só conta até aqui
    s["eff_end"] = s["span_end"].clip(upper=t)

    per = s.groupby("contributor_id").agg(
        last_event=("eff_end", "max"), init_c=("init_c", "first"), init_d=("init_d", "first")
    )

    # o lado coding só vale a partir de init_c; antes disso a pessoa é non_coding
    coded = per["init_c"].notna() & (per["init_c"] <= t)
    # moved = já tinha discutido ANTES do primeiro commit/PR
    moved = coded & per["init_d"].notna() & (per["init_d"] < per["init_c"])

    per["category"] = np.where(coded, np.where(moved, "moved", "coding"), "non_coding")
    per["start_ref"] = per["init_c"].where(coded, per["init_d"])

    basis = settings()["periods"]["age_basis"]
    if basis == "calendar_tenure":
        # idade = tempo decorrido desde a origem, como a idade de uma pirâmide
        # demográfica. Gaps de inatividade NÃO descontam.
        per["age_days"] = (t - per["start_ref"]).dt.total_seconds() / 86400.0
    elif basis == "accumulated_active":
        # idade = soma dos pedaços de período de atividade a partir de start_ref
        s = s.join(per["start_ref"], on="contributor_id")
        lo = s[["span_start", "start_ref"]].max(axis=1)
        overlap = (s["eff_end"] - lo).dt.total_seconds() / 86400.0
        per["age_days"] = overlap.clip(lower=0).groupby(s["contributor_id"]).sum()
    else:
        raise ValueError(f"periods.age_basis desconhecido: {basis!r}")
    per["age_days"] = per["age_days"].clip(lower=0.0)

    per["age_months"] = per["age_days"] / DAYS_PER_MONTH
    # Bandas fechadas em cima: (0,90] -> 0, (90,180] -> 1, ...  O rótulo do eixo
    # é (band+1)*`band_months`. Conferido contra IEICE16 Tab.2/Fig.4(b): C3 com
    # exatos 3 meses em t1 aparece na banda "3 months", e C6 com 6 na banda
    # "6 months"; `floor` jogaria os dois para a banda seguinte. O arredondamento
    # evita que ruído de ponto flutuante mova alguém de banda.
    #
    # O corte usa DIAS (`band_days`) como unidade. A unidade `age_months` foi
    # descartada: um mês de 365.25/12 empurrava para baixo quem estava a menos
    # de um dia da fronteira. Ver `config/settings.yaml` e `discrepancias.md`,
    # seção 21.
    bd = float(band_days())
    per["band"] = (np.ceil((per["age_days"] / bd).round(9)).astype(int) - 1).clip(lower=0)
    # "left the project when he/she did not give any contribution for more than
    #  three months". A pirâmide mostra a população viva no snapshot
    per["idle_days"] = (t - per["last_event"]).dt.total_seconds() / 86400.0
    per["active"] = per["idle_days"] <= gap_days

    # `idle_days` fica persistido para o consumidor escolher a janela sem
    # reconstruir o estágio: `metrics` usa `active` (3 meses, IEICE16 p.1306) e
    # a pirâmide da Fig.2 usa 12 meses (medição da figura, discrepancias seção 19).
    return per.reset_index()[
        [
            "contributor_id",
            "category",
            "age_days",
            "age_months",
            "band",
            "idle_days",
            "active",
        ]
    ]


def path(scope_id: int) -> Path:
    """Arquivo de snapshots de um projeto."""
    return stage_dir(STAGE) / f"{scope_id}.parquet"


def load(scope_id: int) -> pd.DataFrame:
    """Lê os snapshots de um projeto."""
    return pd.read_parquet(path(scope_id))


def load_all(
    scopes: list[int] | None = None, dates: list[pd.Timestamp] | None = None
) -> pd.DataFrame:
    """Empilha os snapshots de vários projetos.

    `dates` filtra na leitura de cada arquivo. A série inteira são ~19 bandas
    × 90 projetos × 16 trimestres e a projeção só precisa de 3 datas; filtrar
    depois do empilhamento carregaria tudo à toa.
    """
    ids = scopes if scopes is not None else source().list_scopes()
    want = None if dates is None else {pd.Timestamp(d) for d in dates}
    frames = []
    for s in ids:
        if not path(s).exists():
            continue
        df = pd.read_parquet(path(s))
        frames.append(df if want is None else df[df["snapshot"].isin(want)])
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def run(scopes: list[int] | None = None, force: bool = False, fail_fast: bool = False) -> dict:
    """Executa o estágio snapshots nos projetos pedidos.

    `scopes=None` roda os 90 projetos do dump. `force` recalcula o que já
    está gravado. `fail_fast` interrompe no primeiro projeto que falhar; o
    padrão anota a falha no manifesto e segue para o próximo. Devolve o
    manifesto.
    """
    cfg = settings()
    check_dates(cfg)
    gap_days = cfg["periods"]["inactivity_months"] * DAYS_PER_MONTH
    dates = snapshot_dates(cfg)

    src = source()
    targets = scopes if scopes is not None else src.list_scopes()

    man = runlog.load(STAGE)
    if force:
        man = {"stage": STAGE, "ok": {}, "failed": {}}
    man["snapshots"] = [str(d.date()) for d in dates]

    for sid in targets:
        key = str(sid)
        if not force and key in man["ok"] and path(sid).exists():
            continue
        try:
            spans = load_spans(sid)
            frames = []
            for t in dates:
                p = pyramid_at(spans, t, gap_days)
                if not p.empty:
                    p.insert(0, "snapshot", t)
                    frames.append(p)
            df = (
                pd.concat(frames, ignore_index=True)
                if frames
                else pd.DataFrame(
                    columns=["snapshot", "contributor_id", "category", "band", "active"]
                )
            )
            df.insert(0, "scope_id", sid)
            df.to_parquet(path(sid), index=False)

            act = df[df["active"]] if len(df) else df
            man["ok"][key] = {
                "rows": len(df),
                "active_at_last_snapshot": int(
                    (act["snapshot"] == dates[-1]).sum() if len(act) else 0
                ),
            }
            man["failed"].pop(key, None)
            log.info(
                "%-38s %6d linhas  %4d ativos em %s",
                src.scope_label(sid),
                len(df),
                man["ok"][key]["active_at_last_snapshot"],
                dates[-1].date(),
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
