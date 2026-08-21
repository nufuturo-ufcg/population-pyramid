"""Estágio 5: atratividade anual, magnetismo × stickiness (ESEM14 seção 3.1).

Yamashita et al. (MSR'14), que o ESEM14 adota inteiro, medem duas coisas
independentes:

    magnetismo(P, Y) = |novatos do ano Y que contribuíram em P| / |novatos do ano Y|
    stickiness(P, Y) = |devs de P em Y que voltam em Y+1|       / |devs de P em Y|

"Novato do ano Y" é uma propriedade GLOBAL da pessoa: a primeira contribuição
dela em todo o dataset caiu em Y. Isso é o que torna este estágio diferente dos
anteriores: ele não é calculado por projeto. O denominador do magnetismo é o
dataset inteiro, e o corte alto/baixo é a mediana entre os projetos elegíveis
daquele ano. Rodar num subconjunto de projetos muda os dois e devolve número
errado sem avisar; por isso `run(scopes=...)` recusa em vez de obedecer.

Só commits e pull requests contam (ESEM14 seção 3.1: a tipologia do Yamashita
é sobre código; discussão não entra). Configurável em `attractiveness.events`.

Quadrantes (ESEM14 Fig.2):

                  sticky alto      sticky baixo
    magnet alto   attractive       floating
    magnet baixo  stagnant         terminal
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from . import logging_config as runlog
from .config import settings, stage_dir, unidade_suportada
from .extract import events_path, label_of, load_events, source
from .units import scopes_of_unit

log = logging.getLogger(__name__)
STAGE = "attractiveness"

# Unidades de análise em que este estágio faz sentido. Magnetismo e stickiness
# comparam cada escopo com a MEDIANA anual dos escopos elegíveis, e a mediana de
# 90 projetos não quer dizer a mesma coisa que a mediana de 13 linguagens: o
# quadrante de um escopo passaria a depender de quantas linguagens entraram na
# amostra. Isso é outra pergunta de pesquisa, e ela ainda não foi feita.
UNIDADES = ("project",)

QUADRANTS = {
    (True, True): "attractive",
    (True, False): "floating",
    (False, True): "stagnant",
    (False, False): "terminal",
}

COLUMNS = [
    "scope_id",
    "year",
    "devs",
    "newcomers_here",
    "newcomers_total",
    "retained",
    "magnetism",
    "stickiness",
    "eligible",
    "median_magnetism",
    "median_stickiness",
    "quadrant",
    "left_censored",
    "right_censored",
]


def coding_events() -> list[str]:
    """Eventos que contam como atividade de código, na ordem do `settings.yaml`."""
    return list(settings()["attractiveness"]["events"])


def activity(
    scopes: list[int] | None = None, events: list[str] | None = None
) -> tuple[pd.DataFrame, pd.Timestamp | None]:
    """(scope_id, contributor_id, year) único, + a última data coberta.

    Lê os parquets do estágio 1. Um parquet faltando é erro: com 89 dos 90
    projetos o denominador do magnetismo já sai errado, e errado por um valor
    que ninguém consegue enxergar olhando o resultado.
    """
    src = source()
    ids = scopes if scopes is not None else [e.id for e in scopes_of_unit(src)]
    ev = events if events is not None else coding_events()

    faltando = [s for s in ids if not events_path(s).exists()]
    if faltando:
        raise FileNotFoundError(
            f"{len(faltando)} projeto(s) sem eventos extraídos "
            f"({', '.join(str(s) for s in faltando[:5])}"
            f"{'...' if len(faltando) > 5 else ''}). "
            "O magnetismo é uma fração sobre TODOS os novatos do dataset: "
            "rodar com projeto faltando dá número plausível e errado. "
            "Rode `pyramid extract` antes."
        )

    frames, coverage = [], None
    for sid in ids:
        df = load_events(sid)
        df = df[df["event_type"].isin(ev)]
        if df.empty:
            continue
        ts = df["timestamp"]
        coverage = ts.max() if coverage is None else max(coverage, ts.max())
        frames.append(
            pd.DataFrame(
                {
                    "scope_id": sid,
                    "contributor_id": df["contributor_id"].to_numpy(),
                    "year": ts.dt.year.to_numpy(),
                }
            )
        )

    if not frames:
        return pd.DataFrame(columns=["scope_id", "contributor_id", "year"]), None
    out = pd.concat(frames, ignore_index=True).drop_duplicates()
    return out.reset_index(drop=True), coverage


def _retained(pairs: pd.DataFrame, scope: str) -> pd.DataFrame:
    """Linhas (scope_id, contributor_id, year) em que a pessoa reaparece em Y+1.

    `scope=project` (default): reaparecer NO MESMO projeto. É a definição do
    Yamashita: "sticky" descreve o projeto segurar o dev. A leitura de que o
    dev continua vivo em qualquer lugar foi descartada, porque não é o que o
    Yamashita mede. `scope=dataset` existe só para medir o tamanho da
    ambiguidade; ver settings.yaml.
    """
    if scope == "project":
        keys = ["scope_id", "contributor_id", "year"]
        nxt = pairs[keys].assign(year=pairs["year"] - 1)
        return pairs.merge(nxt, on=keys, how="inner")
    if scope == "dataset":
        dev_years = pairs[["contributor_id", "year"]].drop_duplicates()
        nxt = dev_years.assign(year=dev_years["year"] - 1)
        return pairs.merge(nxt, on=["contributor_id", "year"], how="inner")
    raise ValueError(f"attractiveness.stickiness_scope desconhecido: {scope!r}")


def annual(
    pairs: pd.DataFrame,
    coverage_end: pd.Timestamp | None = None,
    cfg: dict | None = None,
) -> pd.DataFrame:
    """Uma linha por (projeto, ano) com magnetismo, stickiness e quadrante."""
    c = (cfg or settings())["attractiveness"]
    min_devs = c["min_active_devs"]
    sticky_scope = c.get("stickiness_scope", "project")
    if c["cutoff"] != "median":
        raise ValueError(
            f"attractiveness.cutoff={c['cutoff']!r}: o ESEM14 usa mediana e só "
            "mediana. Outro corte precisa de fonte, não de config."
        )

    if pairs.empty:
        return pd.DataFrame(columns=COLUMNS)

    pairs = pairs.drop_duplicates()
    first_year = pairs.groupby("contributor_id")["year"].min()
    novato = pairs["contributor_id"].map(first_year) == pairs["year"]

    per = (
        pairs.assign(_novato=novato)
        .groupby(["scope_id", "year"], as_index=False)
        .agg(devs=("contributor_id", "nunique"), newcomers_here=("_novato", "sum"))
    )

    # denominador do magnetismo: novatos do ANO, no dataset inteiro
    novatos_ano = first_year.value_counts().rename("newcomers_total")
    per = per.merge(novatos_ano, left_on="year", right_index=True, how="left")
    per["newcomers_total"] = per["newcomers_total"].fillna(0).astype("int64")

    ret = (
        _retained(pairs, sticky_scope)
        .groupby(["scope_id", "year"], as_index=False)
        .agg(retained=("contributor_id", "nunique"))
    )
    per = per.merge(ret, on=["scope_id", "year"], how="left")
    per["retained"] = per["retained"].fillna(0).astype("int64")

    per["magnetism"] = np.where(
        per["newcomers_total"] > 0, per["newcomers_here"] / per["newcomers_total"], np.nan
    )
    per["stickiness"] = np.where(per["devs"] > 0, per["retained"] / per["devs"], np.nan)

    anos = pairs["year"]
    y_min, y_max = int(anos.min()), int(anos.max())
    # Y == y_min: quem "estreia" ali pode ser veterano cuja história ficou fora
    # do dump. Y == y_max: Y+1 não existe, stickiness é indefinida (não zero).
    per["left_censored"] = per["year"] <= y_min
    per["right_censored"] = per["year"] >= y_max
    per.loc[per["right_censored"], "stickiness"] = np.nan

    if coverage_end is not None:
        fim = pd.Timestamp(coverage_end)
        if fim < pd.Timestamp(year=fim.year, month=12, day=31):
            log.warning(
                "o ano %d está incompleto (dataset acaba em %s): a stickiness "
                "de %d subestima, porque quem voltaria depois de %s conta como "
                "perdido",
                fim.year,
                fim.date(),
                fim.year - 1,
                fim.date(),
                extra={"stage": STAGE},
            )

    per["eligible"] = (
        (per["devs"] > min_devs) & per["magnetism"].notna() & per["stickiness"].notna()
    )

    el = per[per["eligible"]]
    med_m = el.groupby("year")["magnetism"].median()
    med_s = el.groupby("year")["stickiness"].median()
    per["median_magnetism"] = per["year"].map(med_m)
    per["median_stickiness"] = per["year"].map(med_s)

    # Empate na mediana cai do lado BAIXO: mesma convenção de metrics._type_of
    # ("alto = valor > corte"). Com n ímpar de elegíveis o projeto que É a
    # mediana cai em baixo/baixo; é arbitrário, mas fixo e explícito, e não
    # ajustável para não virar botão de girar até o checkpoint bater.
    alto_m = per["magnetism"] > per["median_magnetism"]
    alto_s = per["stickiness"] > per["median_stickiness"]
    per["quadrant"] = [
        QUADRANTS[(bool(m), bool(s))] if e else None
        for m, s, e in zip(alto_m, alto_s, per["eligible"], strict=True)
    ]

    return per.sort_values(["year", "scope_id"])[COLUMNS].reset_index(drop=True)


def path() -> Path:
    """Arquivo único do estágio: a tabela anual dos 90 projetos."""
    return stage_dir(STAGE) / "attractiveness.parquet"


def load() -> pd.DataFrame:
    """Lê a tabela anual gravada pelo estágio."""
    return pd.read_parquet(path())


def table(year: int | str | pd.Timestamp | None = None) -> pd.DataFrame:
    """Corte de um ano com o nome do projeto: a matéria-prima da Fig.2."""
    df = load()
    if year is not None:
        y = year_of(year)
        got = df[df["year"] == y]
        if got.empty:
            anos = ", ".join(str(a) for a in sorted(df["year"].unique()))
            raise ValueError(
                f"attractiveness.table: ano {y} não existe no resultado. Anos disponíveis: {anos}."
            )
        df = got
    out = df.copy()
    # Rótulo do manifesto do `extract`, não do banco: `table()` é leitura, e
    # leitura tem de funcionar com o MySQL desligado.
    out["project"] = [label_of(s) for s in out["scope_id"]]
    return out.sort_values(["year", "quadrant", "project"], na_position="last").reset_index(
        drop=True
    )


def year_of(v: int | str | pd.Timestamp) -> int:
    """Aceita 2011, "2011" ou "2011-12-31" (a chave do checkpoints.yaml)."""
    if isinstance(v, int):
        return v
    s = str(v)
    if s.isdigit():
        return int(s)
    return int(pd.Timestamp(s).year)


def run(
    scopes: list[int] | None = None,
    force: bool = False,
    fail_fast: bool = False,
    years: list[int] | None = None,
) -> dict:
    """Calcula sempre o dataset inteiro; `years` só filtra o que é reportado."""
    unidade_suportada(STAGE, UNIDADES)
    if scopes is not None:
        raise ValueError(
            "attractiveness não aceita --project: o magnetismo é uma fração "
            "sobre os novatos de TODO o dataset e o corte é a mediana entre os "
            "90 projetos. Restringir o escopo muda denominador e mediana, e o "
            "resultado sairia errado sem parecer errado."
        )

    man = runlog.load(STAGE)
    if force:
        man = {"stage": STAGE, "ok": {}, "failed": {}}
    if not force and man.get("ok") and path().exists():
        log.info("%s já calculado (%d anos); use --force", STAGE, len(man["ok"]))
        return man

    cfg = settings()["attractiveness"]
    man["events"] = list(cfg["events"])
    man["stickiness_scope"] = cfg.get("stickiness_scope", "project")
    man["min_active_devs"] = cfg["min_active_devs"]

    try:
        pairs, coverage = activity()
        out = annual(pairs, coverage)
        out.to_parquet(path(), index=False)
    except Exception as e:
        man["failed"]["all"] = f"{type(e).__name__}: {e}"
        log.exception("falha no estágio %s", STAGE, extra={"stage": STAGE})
        runlog.save(STAGE, man)
        if fail_fast:
            raise
        return man

    for y, g in out.groupby("year"):
        if years is not None and int(y) not in years:
            continue
        el = g[g["eligible"]]
        counts = el["quadrant"].value_counts().to_dict()
        man["ok"][str(int(y))] = {
            "projects": len(g),
            "eligible": len(el),
            "median_magnetism": None
            if el.empty
            else round(float(el["median_magnetism"].iloc[0]), 6),
            "median_stickiness": None
            if el.empty
            else round(float(el["median_stickiness"].iloc[0]), 6),
            **{
                k: int(counts.get(k, 0)) for k in ("attractive", "floating", "stagnant", "terminal")
            },
        }
        man["failed"].pop(str(int(y)), None)
        log.info(
            "%d  %2d/%2d elegíveis  atrativo=%d flutuante=%d estagnado=%d terminal=%d",
            int(y),
            len(el),
            len(g),
            counts.get("attractive", 0),
            counts.get("floating", 0),
            counts.get("stagnant", 0),
            counts.get("terminal", 0),
            extra={"stage": STAGE},
        )
        if g["right_censored"].all():
            log.warning(
                "%d é o último ano do dataset: sem Y+1 não há stickiness, "
                "nenhum projeto é classificado",
                int(y),
                extra={"stage": STAGE},
            )

    runlog.save(STAGE, man)
    log.info(runlog.summarize(STAGE, man))
    return man
