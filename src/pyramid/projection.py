"""Estágio 6: projeção coorte-componente (IEICE16 seção 4).

Isserman [15] projeta população por coorte etária usando taxa de sobrevivência:

    Pop(idade X+n, ano T+n) = Sobrevivência(X) × Pop(idade X, ano T)
    Sobrevivência(X)        = Pop(idade X+n, T) / Pop(idade X, T-n)

O IEICE16 (p.1310, col. dir.) troca cada variável explicitamente:

    "X is the activity period of the cohort being examined, n is an interval
     of time set at three months ... and 3 m in year T is the month of most
     recent contributors counting."

Ou seja: coorte = a banda de 3 meses da pirâmide (`band`), e n = 1 banda. Com
T = jun/2013 e T-n = mar/2013, projetando set/2013:

    SR(b)          = P(b+1, jun/2013) / P(b, mar/2013)
    P(b+1, set/13) = SR(b) × P(b, jun/2013)

A coorte de base (band 0) não vem de sobrevivência: é o análogo demográfico dos
nascimentos. O artigo não tem taxa de fecundidade, então usa a média das duas
contagens mais recentes (p.1311, col. esq.):

    newcomer = (P{T} + P{T−n})/2,  P{T} = "Population activity period 3 m in year T"

Migração líquida é zero por decisão explícita do artigo ("we do not consider
that contributors move to other projects in our study").

Baseline: "the baseline method, which assumes that the number of contributors
of September and June 2013 are the same": previsão = a contagem de jun/2013.

Erro: ABRE (Miyazaki et al. [19]), com denominador = min(real, previsto) nos
dois ramos. Ver `abre` e docs/discrepancias.md, seção 5.

Três populações projetadas separadamente ("Populations are projected for
non-coding, moved, and coding contributors, separately") + a coluna `all`.
"""

from __future__ import annotations

import logging
import math

import numpy as np
import pandas as pd

from . import logging_config as runlog
from .config import settings, stage_dir
from .extract import source
from .metrics import load_all as load_metrics
from .snapshots import CATEGORIES, load_all as load_snapshots, require_date_match

log = logging.getLogger(__name__)
STAGE = "projection"

# A UNIDADE DE ANÁLISE É A COORTE, NÃO O PROJETO.
#
# O artigo não diz isso em palavras, mas a Tabela 4 prova. Type D tem dois
# projetos e p-value 0.00000; Type A tem quatro e 0.00014. Um Wilcoxon pareado
# com n=2 não produz p abaixo de 0.5 (com n=4, o piso é 0.125): são só 2^n
# arranjos de sinal. Para p da ordem de 1e-5 são precisos ~18 pares no mínimo.
# Logo cada par é (projeto, categoria, coorte), e a mediana da Tabela 3 é sobre
# coortes.
#
# A magnitude confirma por outro caminho: as medianas da Tabela 3 são 0.2500,
# 0.3333, 0.5000, 0.6667, 0.7500, 1.0000: frações de inteiros pequenos, que só
# saem de contagens de banda individual (2→3 dá 0.5; 3→4 dá 0.3333). Agregar por
# projeto (100+ contribuidores) dá ABRE de 0.02, vinte vezes menor. Ver
# docs/discrepancias.md, seção 12.
#
# `all` é a população total da coorte (as três categorias somadas naquela banda),
# leitura direta de "projection of all contributors".
COLUMNS = [
    "scope_id",
    "type",
    "category",
    "band",
    "actual",
    "cohort_pred",
    "baseline_pred",
    "abre_cohort",
    "abre_baseline",
]


def abre(actual: float, predicted: float) -> float:
    """Absolute Balanced Relative Error.

    IEICE16 p.1311 escreve os dois ramos com o denominador trocando de lado
    conforme o sinal de (x̂ − x). Como o ramo de cima vale quando x̂ ≥ x e usa x,
    e o de baixo vale quando x̂ < x e usa x̂, o denominador é sempre o MENOR dos
    dois, que é o BRE de Miyazaki et al. tal como publicado. Escrito com `min`
    aqui de propósito: a forma de dois ramos convida a inverter um sinal em
    revisão e o teste não pegaria (os ramos coincidem quando x = x̂).

    Simétrico por construção: abre(a, b) == abre(b, a).

    `nan` em qualquer lado propaga: é o canal por onde `project` sinaliza que o
    método não tem resposta para a célula (coorte órfã). Tratado explicitamente
    porque `min(x, nan)` em Python devolve o primeiro argumento em vez de nan,
    então sem esta guarda o resultado dependeria da ordem dos parâmetros.
    """
    if math.isnan(actual) or math.isnan(predicted):
        return float("nan")
    if actual < 0 or predicted < 0:
        raise ValueError(f"ABRE em contagem negativa: actual={actual} pred={predicted}")
    denom = min(actual, predicted)
    if denom == 0:
        # Uma das duas contagens é zero: o erro relativo não existe (divisão por
        # zero) e cravar 0.0 ou 1.0 aqui inventaria um acerto ou um erro máximo.
        # A mediana do artigo é sobre projetos onde os dois lados existem.
        return float("nan")
    return abs(predicted - actual) / denom


def _counts_by_band(df: pd.DataFrame, n_bands: int) -> np.ndarray:
    """Vetor de contagem por banda, indexado de 0 a n_bands-1."""
    v = np.zeros(n_bands, dtype=float)
    if df.empty:
        return v
    c = df["band"].value_counts()
    idx = c.index.to_numpy(dtype=int)
    dentro = idx < n_bands
    v[idx[dentro]] = c.to_numpy(dtype=float)[dentro]
    return v


def project(p_base: np.ndarray, p_last: np.ndarray) -> tuple[np.ndarray, int]:
    """Projeta um passo de 3 meses. Devolve (vetor por banda, coortes órfãs).

    `p_base` = contagem por banda em T−n (mar/2013)
    `p_last` = contagem por banda em T   (jun/2013)

    Dois casos distintos quando o denominador `p_base[b]` é zero:

    - `p_last[b] == 0` também (banda vazia nos dois tempos): ninguém envelhece
      para b+1, e prever 0 é uma afirmação substantiva, não uma lacuna. No
      dataset são 3256 células e o alvo é de fato vazio em 98.9% delas.
    - `p_last[b] > 0` (coorte órfã): a banda apareceu povoada sem ter existido
      no tempo anterior. A taxa de sobrevivência é indefinida: 0/0 vezes algo.
      São 195 células, e o alvo tem gente de verdade em 73.8% delas, ou seja,
      cravar 0 ali seria errado na maioria das vezes. A célula fica `nan`
      (= "o método não responde") e sai do cálculo de erro, em vez de entrar
      como previsão de extinção. Prever 0 e deixar `abre` tratar seria um viés
      sistemático numa direção só, favorecendo artificialmente a baseline.
    """
    n = len(p_last)
    proj = np.zeros(n, dtype=float)

    # Nascimentos: média das duas contagens mais recentes da banda de base.
    proj[0] = (p_last[0] + p_base[0]) / 2.0

    orfas = 0
    for b in range(n - 1):
        if p_base[b] == 0:
            if p_last[b] > 0:
                orfas += 1
                proj[b + 1] = np.nan  # indefinido, não "morreu"
            continue
        proj[b + 1] = (p_last[b + 1] / p_base[b]) * p_last[b]

    return proj, orfas


def eligible_scopes(snaps: pd.DataFrame, base: pd.Timestamp) -> list[int]:
    """ "the 36 projects that have more than 100 contributors" (p.1311).

    O artigo não diz sobre qual snapshot nem se conta ativos ou acumulados.
    Variante escolhida em docs/discrepancias.md, seções 7 e 9.2: ativos no
    primeiro snapshot base. O resultado é 34; a diferença para os 36 do artigo
    é ruído de fronteira.

    O corte usa `> limiar`, seguindo "more than 100" ao pé da letra. A
    alternativa `>=` foi descartada: não é detalhe cosmético, porque o 35º
    projeto tem exatamente 100 contribuintes ativos, então ler "more than"
    como `>=` devolveria 35. Ver seção 9.2.
    """
    cfg = settings()["projection"]
    limiar = cfg["min_contributors"]
    basis = cfg["min_contributors_basis"]
    if basis not in ("active", "cumulative"):
        raise ValueError(
            f"projection.min_contributors_basis={basis!r}: só 'active' ou "
            "'cumulative'. Ver docs/discrepancias.md, seção 7."
        )

    at = snaps[snaps["snapshot"] == base]
    if basis == "active":
        at = at[at["active"]]
    n = at.groupby("scope_id")["contributor_id"].nunique()
    return sorted(int(s) for s in n[n > limiar].index)


def compute() -> pd.DataFrame:
    cfg = settings()
    bases = [pd.Timestamp(d) for d in cfg["snapshots"]["projection_base"]]
    target = pd.Timestamp(cfg["snapshots"]["projection_target"])
    if len(bases) != 2:
        raise ValueError(
            f"projection_base tem {len(bases)} datas; o método usa exatamente "
            "duas (T−n e T) para tirar a taxa de sobrevivência. IEICE16 seção 4.2."
        )
    base, last = bases

    snaps = load_snapshots(dates=[base, last, target])
    for d, nome in (
        (base, "projection_base[0]"),
        (last, "projection_base[1]"),
        (target, "projection_target"),
    ):
        require_date_match(snaps[snaps["snapshot"] == d], d, "snapshot", f"projection.{nome}")

    scopes = eligible_scopes(snaps, base)
    log.info(
        "%d projetos com mais de %d contribuidores (%s em %s)",
        len(scopes),
        settings()["projection"]["min_contributors"],
        settings()["projection"]["min_contributors_basis"],
        base.date(),
        extra={"stage": STAGE},
    )

    # O tipo A-D vem do snapshot de classificação, não do alvo da projeção: as
    # Tabelas 3 e 4 quebram por tipo e o tipo do artigo é o da Fig.5.
    snap_tipo = pd.Timestamp(checkpoint_snapshot())
    tipos = load_metrics()
    tipos = tipos[tipos["snapshot"] == snap_tipo].set_index("scope_id")["type"]

    n_bands = int(snaps["band"].max()) + 1
    # Só os vivos. A pirâmide é a população ativa no snapshot: "a contributor
    # left the project when he/she did not give any contribution for more than
    # three months". É o que metrics.py e plots.py já usam. Sem esse filtro a
    # população é o acumulado histórico, onde ninguém morre: a banda de todo
    # mundo avança um degrau a cada trimestre, a taxa de sobrevivência é 1 por
    # construção e a projeção acerta na mosca sem ter previsto nada.
    dentro = snaps[snaps["scope_id"].isin(scopes) & snaps["active"]]
    por_data = {d: dentro[dentro["snapshot"] == d] for d in (base, last, target)}

    linhas, orfas_total = [], 0
    for sid in scopes:
        tipo = tipos.get(sid)
        vetores = {}
        for d, df in por_data.items():
            g = df[df["scope_id"] == sid]
            vetores[d] = {c: _counts_by_band(g[g["category"] == c], n_bands) for c in CATEGORIES}

        # `all` = população total da coorte, projetada como as outras: soma as
        # três categorias por banda ANTES de projetar. Somar as três projeções
        # daria quase o mesmo, mas a taxa de sobrevivência da população inteira
        # é a que o artigo chama de "projection of all contributors".
        series = {c: (vetores[base][c], vetores[last][c], vetores[target][c]) for c in CATEGORIES}
        series["all"] = tuple(sum(vetores[d][c] for c in CATEGORIES) for d in (base, last, target))

        for cat, (p_base, p_last, p_alvo) in series.items():
            pred, orfas = project(p_base, p_last)
            if cat != "all":
                orfas_total += orfas
            for b in range(n_bands):
                a, cp, bp = float(p_alvo[b]), float(pred[b]), float(p_last[b])
                if min(a, cp) == 0 and min(a, bp) == 0:
                    # Coorte vazia dos dois lados nos dois métodos: não há erro
                    # relativo a medir e manter a linha só encheria a mediana de
                    # nan. A cauda da pirâmide é quase toda assim.
                    continue
                linhas.append(
                    {
                        "scope_id": sid,
                        "type": tipo,
                        "category": cat,
                        "band": b,
                        "actual": a,
                        "cohort_pred": cp,
                        "baseline_pred": bp,
                        "abre_cohort": abre(a, cp),
                        "abre_baseline": abre(a, bp),
                    }
                )

    if orfas_total:
        log.warning(
            "%d coortes sem denominador em %s (excluídas do erro, não "
            "projetadas como 0): a sobrevivência é indefinida quando a banda "
            "anterior está vazia",
            orfas_total,
            base.date(),
            extra={"stage": STAGE},
        )
    return pd.DataFrame(linhas, columns=COLUMNS)


def checkpoint_snapshot() -> str:
    from .config import checkpoints

    return checkpoints()["types"]["snapshot"]


def _wilcoxon(a: np.ndarray, b: np.ndarray) -> float:
    """Wilcoxon pareado, bilateral. `nan` quando a amostra não sustenta o teste."""
    from scipy.stats import wilcoxon

    par = np.isfinite(a) & np.isfinite(b)
    a, b = a[par], b[par]
    if len(a) < 1 or np.allclose(a, b):
        return float("nan")
    try:
        return float(wilcoxon(a, b).pvalue)
    except ValueError:
        # Todos os pares com diferença zero: o teste não tem o que ranquear.
        return float("nan")


def tables(df: pd.DataFrame | None = None) -> dict[str, pd.DataFrame]:
    """Tabelas 3 (mediana do ABRE) e 4 (Wilcoxon) do IEICE16."""
    df = load() if df is None else df
    ordem = [*CATEGORIES, "all"]
    tipos = ["A", "B", "C", "D", "All types"]

    # Só pares completos. O ABRE é nan quando uma das duas contagens é zero
    # (erro relativo sem denominador), e isso atinge os dois métodos em coortes
    # diferentes. Tirar a mediana de cada coluna sobre o que sobrou compararia
    # duas amostras distintas e o Wilcoxon, que é pareado, já usaria só a
    # interseção: as Tabelas 3 e 4 sairiam de populações diferentes.
    completos = df[df["abre_cohort"].notna() & df["abre_baseline"].notna()]

    med, pval = [], []
    for tipo in tipos:
        sub = completos if tipo == "All types" else completos[completos["type"] == tipo]
        linha_m = {
            "type": tipo,
            "projects": int(sub["scope_id"].nunique()),
            "pairs": len(sub[sub["category"] == "all"]),
        }
        linha_p = dict(linha_m)
        for cat in ordem:
            s = sub[sub["category"] == cat]
            linha_m[f"{cat}_cohort"] = s["abre_cohort"].median()
            linha_m[f"{cat}_baseline"] = s["abre_baseline"].median()
            linha_p[cat] = _wilcoxon(
                s["abre_cohort"].to_numpy(dtype=float),
                s["abre_baseline"].to_numpy(dtype=float),
            )
        med.append(linha_m)
        pval.append(linha_p)
    return {"abre": pd.DataFrame(med), "wilcoxon": pd.DataFrame(pval)}


def term_split(df: pd.DataFrame | None = None) -> dict:
    """Curto vs. longo prazo: corte em 1 ano de atividade (IEICE16 seção 4.2 fim).

    "The median of ABRE of short-term contributors is 0.4055, and median of
     ABRE of long-term contributors is 0.3333" (p-value = 0.0460).

    1 ano de período de atividade = banda 4 (bandas são de 3 meses, fechadas em
    cima: banda 0..3 cobre (0, 12m]). Curto = bandas 0-3, longo = 4+.

    Aqui o teste é de duas amostras independentes (rank-sum), não pareado: os
    dois grupos são conjuntos de coortes de tamanhos diferentes, não há par
    natural entre uma banda curta e uma longa. As medianas relatadas, 0.4055 e
    0.3333, são de novo frações de inteiro pequeno, coerentes com coorte.
    """
    from scipy.stats import ranksums

    df = load() if df is None else df
    sub = df[(df["category"] == "all") & df["abre_cohort"].notna()]
    curto = sub[sub["band"] < 4]["abre_cohort"].to_numpy(dtype=float)
    longo = sub[sub["band"] >= 4]["abre_cohort"].to_numpy(dtype=float)

    return {
        "short_term_abre_median": float(np.median(curto)) if len(curto) else float("nan"),
        "long_term_abre_median": float(np.median(longo)) if len(longo) else float("nan"),
        "short_n": len(curto),
        "long_n": len(longo),
        "wilcoxon_p": (
            float(ranksums(curto, longo).pvalue) if len(curto) and len(longo) else float("nan")
        ),
    }


def path():
    return stage_dir(STAGE) / "projection.parquet"


def load() -> pd.DataFrame:
    return pd.read_parquet(path())


def run(scopes: list[int] | None = None, force: bool = False, fail_fast: bool = False) -> dict:
    if scopes is not None:
        raise ValueError(
            "projection não aceita --project: a amostra é definida pelo limiar "
            "de 100 contribuidores (IEICE16 seção 4.2) e as Tabelas 3/4 são medianas "
            "sobre ela. Restringir o escopo devolveria uma mediana de outra "
            "população com a mesma cara."
        )

    man = runlog.load(STAGE)
    if force:
        man = {"stage": STAGE, "ok": {}, "failed": {}}
    if not force and man.get("ok") and path().exists():
        log.info("%s já calculado; use --force", STAGE)
        return man

    try:
        df = compute()
        df.to_parquet(path(), index=False)
    except Exception as e:  # noqa: BLE001
        man["failed"]["all"] = f"{type(e).__name__}: {e}"
        log.exception("falha no estágio %s", STAGE, extra={"stage": STAGE})
        runlog.save(STAGE, man)
        if fail_fast:
            raise
        return man

    t = tables(df)
    man["ok"]["projects"] = int(df["scope_id"].nunique())
    # Nome da classe, não o objeto: o repr default carrega o endereço de memória
    # e faria o manifesto diferir entre duas runs idênticas.
    man["ok"]["source"] = type(source()).__name__
    for _, r in t["abre"].iterrows():
        man["ok"][f"abre_{r['type']}"] = {
            c: None if pd.isna(r[f"{c}_cohort"]) else round(float(r[f"{c}_cohort"]), 4)
            for c in (*CATEGORIES, "all")
        }
        log.info(
            "%-9s %2d proj/%4d pares  non-coding %.4f/%.4f  moved %.4f/%.4f  "
            "coding %.4f/%.4f  all %.4f/%.4f",
            r["type"],
            r["projects"],
            r["pairs"],
            r["non_coding_cohort"],
            r["non_coding_baseline"],
            r["moved_cohort"],
            r["moved_baseline"],
            r["coding_cohort"],
            r["coding_baseline"],
            r["all_cohort"],
            r["all_baseline"],
            extra={"stage": STAGE},
        )
    man["failed"].pop("all", None)
    runlog.save(STAGE, man)
    return man
