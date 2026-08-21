"""Estágio 4: CCR, NCR e os Tipos A-D, por (projeto, snapshot).

Fórmulas verificadas palavra por palavra contra o PDF do IEICE16 (s3, p.1308-1309):

    CCR = (coding - non) / coding      se coding >= non
        = (coding - non) / non         se coding <  non

    NCR = (new - experienced) / new          se new >= experienced
        = (new - experienced) / experienced  se new <  experienced

Ambos em [-1, 1]. O denominador é sempre o MAIOR dos dois lados, o que mantém a
razão limitada. Essa escolha é fiel à fórmula do artigo, tal como publicada.

Lados (IEICE16 s3 + spec s2):
  coding      = category in {coding, moved}: quem já codou alguma vez até T
  non         = category == non_coding
  new         = band 0  (idade < 3 meses de atividade acumulada)
  experienced = band >= 1

Quadrantes, citando o artigo (p.1309), que descreve cada tipo em palavras.
A tradução para sinal, feita abaixo, é a única leitura possível:

  "Type A: more newcomers than experienced ... more coding than non-coding"
  "Type B: more newcomers than experienced ... more non-coding than coding"
  "Type C: more experienced than newcomers ... more coding than non-coding"
  "Type D: more experienced than newcomers ... more non-coding than coding"

    Tipo | CCR | NCR
    A    | > 0 | > 0
    B    | < 0 | > 0
    C    | > 0 | < 0
    D    | < 0 | < 0

O corte usa ZERO como referência de sinal. A mediana não entra nessa comparação.
Projeto sem nenhum contribuidor no snapshot não é classificado: é literalmente
o que derruba 4 dos 90 na Fig.5 do IEICE16
("because four projects did not have any contributors in this period ... there
are 86 projects displayed in Fig. 5").

Empate exato (CCR == 0 ou NCR == 0) o artigo não cobre: ele só diz que valores
perto de zero significam lados "similares". Fica como `None` e é CONTADO no
manifesto, para aparecer no relatório em vez de ser absorvido em silêncio num
dos quadrantes. A regra de desempate para zero exato é fixa em `_type_of`,
deliberadamente não configurável.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from . import logging_config as runlog
from . import snapshots
from .config import stage_dir
from .extract import label_of, source
from .units import scopes_of_unit

log = logging.getLogger(__name__)
STAGE = "metrics"

CODING_SIDE = ("coding", "moved")


def ratio(a: float, b: float) -> float:
    """(a - b) / max(a, b): a forma fechada das duas ramificações do artigo.

    Indefinido quando os dois lados são zero: o projeto não tem população.
    """
    hi = max(a, b)
    if hi == 0:
        return float("nan")
    return (a - b) / hi


def _type_of(ccr: float, ncr: float) -> str | None:
    """Tipo A-D. Regra de desempate fixa: alto = (valor > 0).

    Os artigos só definem "positivo é alto, negativo é baixo" e nunca falam de
    zero. A leitura menos arbitrária é a literal: zero não é positivo, logo cai
    do lado baixo. Não é configurável de propósito: deixar isso como knob
    convidava a girar o parâmetro até o checkpoint bater, que é exatamente o
    que `CONTRIBUTING.md` proíbe em "Mudança que mexe em número".

    Em set/2013 isso afeta 2 projetos, ambos com CCR exatamente 0 por terem
    coding == non_coding (MiniProfiler 19/19 -> B, ccv 2/2 -> D). Não muda o
    erro L1 (11 em qualquer das duas convenções); muda só a contagem de
    classificados, de 83 para 85.
    """
    if not np.isfinite(ccr) or not np.isfinite(ncr):
        return None
    c_pos, n_pos = ccr > 0, ncr > 0
    return {(True, True): "A", (False, True): "B", (True, False): "C", (False, False): "D"}[
        (c_pos, n_pos)
    ]


def from_pyramids(df: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por snapshot a partir da pirâmide de UM projeto.

    Só a população viva entra: `active` é o "did not give any contribution for
    more than three months" do artigo. Quem já saiu não é mais contribuidor do
    projeto naquele instante e não pode pesar no CCR/NCR.
    """
    cols = [
        "scope_id",
        "snapshot",
        "coding",
        "non_coding",
        "new",
        "experienced",
        "total",
        "ccr",
        "ncr",
        "type",
    ]
    if df.empty:
        return pd.DataFrame(columns=cols)

    act = df[df["active"]]
    if act.empty:
        return pd.DataFrame(columns=cols)

    g = act.assign(
        _coding=act["category"].isin(CODING_SIDE),
        _new=act["band"] == 0,
    ).groupby(["scope_id", "snapshot"], as_index=False)

    out = g.agg(
        coding=("_coding", "sum"),
        non_coding=("_coding", lambda s: (~s).sum()),
        new=("_new", "sum"),
        experienced=("_new", lambda s: (~s).sum()),
        total=("contributor_id", "size"),
    )
    out["ccr"] = [ratio(c, n) for c, n in zip(out["coding"], out["non_coding"], strict=True)]
    out["ncr"] = [ratio(n, e) for n, e in zip(out["new"], out["experienced"], strict=True)]
    out["type"] = [_type_of(c, n) for c, n in zip(out["ccr"], out["ncr"], strict=True)]
    return out[cols]


def path(scope_id: int) -> Path:
    """Arquivo de métricas de um projeto."""
    return stage_dir(STAGE) / f"{scope_id}.parquet"


def load(scope_id: int) -> pd.DataFrame:
    """Lê as métricas de um projeto."""
    return pd.read_parquet(path(scope_id))


def _ids_gravados() -> list[int]:
    """Ids que este estágio já gravou, lidos do disco.

    Leitura não pergunta o escopo ao banco. `load_all` empilha o que existe, e o
    que existe está no disco: perguntar a lista ao MySQL só para depois filtrar
    por `path(s).exists()` amarrava `pyramid types`, `pyramid validate` e os
    testes de checkpoint a um banco de pé. Arquivo que não é `<id>.parquet` fica
    de fora (o manifesto e as tabelas do estágio começam com `_`).
    """
    return sorted(int(p.stem) for p in stage_dir(STAGE).glob("*.parquet") if p.stem.isdigit())


def load_all(scopes: list[int] | None = None) -> pd.DataFrame:
    """Empilha as métricas dos projetos pedidos, pulando o que ainda não rodou."""
    ids = scopes if scopes is not None else _ids_gravados()
    frames = [load(s) for s in ids if path(s).exists()]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def table(snapshot: str | pd.Timestamp, scopes: list[int] | None = None) -> pd.DataFrame:
    """Corte de um snapshot com o nome do projeto: a matéria-prima da Fig.5."""
    df = load_all(scopes)
    if df.empty:
        return df
    t = pd.Timestamp(snapshot)
    cut = snapshots.require_date_match(
        df[df["snapshot"] == t], t, "snapshot", "metrics.table"
    ).copy()
    # Rótulo vem do cache que o `extract` gravou no manifesto, não do banco: é a
    # mesma regra que `plots` já seguia.
    cut["project"] = [label_of(s) for s in cut["scope_id"]]
    return cut.sort_values(["type", "project"], na_position="last").reset_index(drop=True)


def run(scopes: list[int] | None = None, force: bool = False, fail_fast: bool = False) -> dict:
    """Executa o estágio metrics nos projetos pedidos.

    `scopes=None` roda os 90 projetos do dump. `force` recalcula o que já
    está gravado. `fail_fast` interrompe no primeiro projeto que falhar; o
    padrão anota a falha no manifesto e segue para o próximo. Devolve o
    manifesto.
    """
    src = source()
    targets = scopes if scopes is not None else [e.id for e in scopes_of_unit(src)]

    man = runlog.load(STAGE)
    if force:
        man = {"stage": STAGE, "ok": {}, "failed": {}}

    for sid in targets:
        key = str(sid)
        if not force and key in man["ok"] and path(sid).exists():
            continue
        try:
            out = from_pyramids(snapshots.load(sid))
            out.to_parquet(path(sid), index=False)

            last = out.iloc[-1] if len(out) else None
            man["ok"][key] = {
                "snapshots": len(out),
                "unclassified": int(out["type"].isna().sum()) if len(out) else 0,
                "last": None
                if last is None
                else {
                    "snapshot": str(pd.Timestamp(last["snapshot"]).date()),
                    "ccr": round(float(last["ccr"]), 4),
                    "ncr": round(float(last["ncr"]), 4),
                    "type": last["type"],
                },
            }
            man["failed"].pop(key, None)
            if last is None:
                log.warning(
                    "%-38s sem população ativa em nenhum snapshot",
                    src.scope_label(sid),
                    extra={"scope_id": sid, "stage": STAGE},
                )
            else:
                log.info(
                    "%-38s %3d snapshots  último: CCR %+.3f  NCR %+.3f  Tipo %s",
                    src.scope_label(sid),
                    len(out),
                    last["ccr"],
                    last["ncr"],
                    last["type"] or "-",
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
