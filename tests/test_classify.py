"""Exemplo didático do IEICE16 (Tabela 2 + Fig. 4), usado como caso de teste.

Os autores dão seis contribuidores fictícios C1..C6 e mostram, para dois
snapshots t1 e t2 (t2 = t1 + 3 meses), quantos meses de atividade cada um tem
de cada lado, mais o desenho das duas pirâmides resultantes:

    Tabela 2            t1                t2
    contribuidor  coding  non-coding  coding  non-coding
    C1              1         -          4         -
    C2              -         -          -         2
    C3              -         3          2         6
    C4              5         2          8         5
    C5              -         4          -         7
    C6              3         5          6         8

Isso amarra três decisões que o texto sozinho deixa ambíguas:

1. C3 em t2 tem 6 meses de non-coding e 2 de coding, e a Fig. 4(b) o desenha na
   banda "3 months". A idade de quem migrou (`moved`) é contada a
   partir do PRIMEIRO EVENTO DE CODING (`init_c`), não do início da atividade.
   Mesma coisa com C6 (8 non-coding / 6 coding, desenhado na banda "6 months").

2. C4 tem atividade dos dois lados mas é `coding`, não `moved`, porque o
   primeiro evento dele foi coding (init_c < init_d). `moved` exige ter
   discutido ANTES de codar.

3. C3 tem exatamente 3 meses em t1 e a Fig. 4(a) o coloca na banda "3 months",
   não na de 6: as bandas são fechadas em cima: (0,3], (3,6], (6,9].
   C6, com exatos 6 em t2, idem: banda "6 months".
"""

from __future__ import annotations

import pandas as pd
import pytest

from pyramid.classify import (
    DAYS_PER_MONTH,
    OVERVIEW_COLUMNS,
    _periodo_em_dias,
    coding_events,
    overview,
    profile,
)
from pyramid.config import settings
from pyramid.snapshots import band_days, pyramid_at

# O "mês" da Fig.4 do IEICE16 é o mês da BANDA (90/3 = 30 dias). O mês de
# calendário (365.25/12) fica de fora.
# O exemplo é sintético e afirma "C3 tem exatamente 3 meses e cai na banda
# '3 months'": só faz sentido se os 3 meses do enunciado forem a mesma unidade
# que a banda usa para cortar. Construir os eventos com 30.4375 punha C3 a 1,3
# dia ALÉM da fronteira, e o teste passava a medir a unidade, não a regra.
MES = band_days() / settings()["periods"]["band_months"]

T2 = pd.Timestamp("2013-01-01")
T1 = T2 - pd.Timedelta(days=3 * MES)

CODING, NON_CODING = "commits", "issue_comments"

# (contribuidor, meses de coding antes de t2, meses de non-coding antes de t2)
TABELA_2 = {
    "C1": (4, None),
    "C2": (None, 2),
    "C3": (2, 6),
    "C4": (8, 5),
    "C5": (None, 7),
    "C6": (6, 8),
}


def _events() -> pd.DataFrame:
    """Um evento por mês desde o início de cada lado até t2.

    A atividade é contínua (sem lacuna de 3 meses), então a idade é a mesma sob
    `calendar_tenure` e sob `accumulated_active`. O teste vale para as duas
    configurações de `periods.age_basis`.
    """
    rows = []
    for cid, (coding_m, non_coding_m) in TABELA_2.items():
        for months, kind in ((coding_m, CODING), (non_coding_m, NON_CODING)):
            if months is None:
                continue
            for k in range(months, -1, -1):
                rows.append((cid, T2 - pd.Timedelta(days=k * MES), kind))
    return pd.DataFrame(rows, columns=["contributor_id", "timestamp", "event_type"])


@pytest.fixture(scope="module")
def spans() -> pd.DataFrame:
    coding = coding_events()
    assert CODING in coding and NON_CODING not in coding, (
        "o teste assume a taxonomia da Tabela 1 do IEICE16"
    )
    gap = settings()["periods"]["inactivity_months"] * DAYS_PER_MONTH
    return profile(_events(), coding, gap)


@pytest.fixture(scope="module")
def gap_days() -> float:
    return settings()["periods"]["inactivity_months"] * DAYS_PER_MONTH


def _at(spans: pd.DataFrame, t: pd.Timestamp, gap_days: float) -> pd.DataFrame:
    return pyramid_at(spans, t, gap_days).set_index("contributor_id")


# ---------------------------------------------------------------- categorias


@pytest.mark.parametrize(
    ("cid", "categoria"),
    [
        ("C1", "coding"),  # só codou
        ("C3", "non_coding"),  # ainda não tinha codado em t1
        ("C4", "coding"),  # codou antes de discutir → coding, não moved
        ("C5", "non_coding"),
        ("C6", "moved"),  # discutiu antes de codar
    ],
)
def test_categoria_em_t1(spans, gap_days, cid, categoria):
    assert _at(spans, T1, gap_days).loc[cid, "category"] == categoria


@pytest.mark.parametrize(
    ("cid", "categoria"),
    [
        ("C1", "coding"),
        ("C2", "non_coding"),
        ("C3", "moved"),  # migrou entre t1 e t2, o ponto central da Fig. 4
        ("C4", "coding"),
        ("C5", "non_coding"),
        ("C6", "moved"),
    ],
)
def test_categoria_em_t2(spans, gap_days, cid, categoria):
    assert _at(spans, T2, gap_days).loc[cid, "category"] == categoria


def test_c2_ainda_nao_existe_em_t1(spans, gap_days):
    """C2 só aparece 2 meses antes de t2: não pode estar na pirâmide de t1."""
    assert "C2" not in _at(spans, T1, gap_days).index


# --------------------------------------------------------------- idade/banda


@pytest.mark.parametrize(
    ("cid", "idade", "banda"),
    [
        ("C1", 1, 0),
        ("C3", 3, 0),  # exatos 3 meses ficam na banda "3 months"
        ("C4", 5, 1),
        ("C5", 4, 1),
        ("C6", 3, 0),  # idade de `moved` = desde init_c (3), não desde init_d (5)
    ],
)
def test_idade_e_banda_em_t1(spans, gap_days, cid, idade, banda):
    p = _at(spans, T1, gap_days)
    assert p.loc[cid, "age_days"] / MES == pytest.approx(idade, abs=1e-6)
    assert p.loc[cid, "band"] == banda


@pytest.mark.parametrize(
    ("cid", "idade", "banda"),
    [
        ("C1", 4, 1),
        ("C2", 2, 0),
        ("C3", 2, 0),  # 6 meses de non-coding, mas a idade é a de coding
        ("C4", 8, 2),
        ("C5", 7, 2),
        ("C6", 6, 1),  # exatos 6 meses ficam na banda "6 months"
    ],
)
def test_idade_e_banda_em_t2(spans, gap_days, cid, idade, banda):
    p = _at(spans, T2, gap_days)
    assert p.loc[cid, "age_days"] / MES == pytest.approx(idade, abs=1e-6)
    assert p.loc[cid, "band"] == banda


# ------------------------------------------------- a pirâmide desenhada


def _desenho(spans, t, gap_days) -> dict[int, dict[str, set[str]]]:
    p = _at(spans, t, gap_days).reset_index()
    p = p[p["active"]]
    out: dict[int, dict[str, set[str]]] = {}
    for (band, cat), g in p.groupby(["band", "category"]):
        out.setdefault(int(band), {})[str(cat)] = set(g["contributor_id"])
    return out


def test_figura_4a(spans, gap_days):
    assert _desenho(spans, T1, gap_days) == {
        0: {"coding": {"C1"}, "moved": {"C6"}, "non_coding": {"C3"}},
        1: {"coding": {"C4"}, "non_coding": {"C5"}},
    }


def test_figura_4b(spans, gap_days):
    assert _desenho(spans, T2, gap_days) == {
        0: {"moved": {"C3"}, "non_coding": {"C2"}},
        1: {"coding": {"C1"}, "moved": {"C6"}},
        2: {"coding": {"C4"}, "non_coding": {"C5"}},
    }


# ---------------------------------------------------------------------------
# Tabela por projeto (IEICE16 seção 2.3, Fig.2 e Fig.3)
# ---------------------------------------------------------------------------
def _man() -> dict:
    """Manifesto com dois projetos completos e um gravado antes do resumo."""
    return {
        "stage": "classify",
        "ok": {
            "79163": {
                "contributors": 10,
                "ever_coded": 4,
                "coding_activities": 700,
                "non_coding_activities": 900,
                "development_days": 1528,
                "spans": 12,
            },
            "12": {
                "contributors": 3,
                "ever_coded": 3,
                "coding_activities": 5,
                "non_coding_activities": 0,
                "development_days": 40,
                "spans": 3,
            },
            "999": {"contributors": 1, "ever_coded": 1, "spans": 1},
        },
        "failed": {},
    }


def test_overview_soma_os_dois_lados_no_total():
    """Quem nunca codou é de não-código, então os dois lados fecham o total."""
    df = overview(_man())
    assert (df["coding_contributors"] + df["non_coding_contributors"] == df["contributors"]).all()
    linha = df[df["scope_id"] == 79163].iloc[0]
    assert int(linha["coding_contributors"]) == 4
    assert int(linha["non_coding_contributors"]) == 6
    assert int(linha["coding_activities"]) == 700
    assert int(linha["non_coding_activities"]) == 900
    assert int(linha["development_days"]) == 1528


def test_overview_ignora_entrada_sem_as_chaves_do_resumo():
    """Manifesto de execução antiga não vira linha furada na tabela.

    O projeto sem `coding_activities` fica fora, e o `run` o reprocessa por causa
    da mesma checagem. Linha com zero inventado seria pior: entraria na figura
    como projeto sem atividade nenhuma.
    """
    df = overview(_man())
    assert 999 not in set(df["scope_id"])
    assert len(df) == 2


def test_overview_sai_ordenado_por_id_e_inteiro():
    """Ordem e tipo fixos: o parquet tem de sair igual em duas execuções."""
    df = overview(_man())
    assert list(df["scope_id"]) == [12, 79163]
    assert list(df.columns) == OVERVIEW_COLUMNS
    assert all(str(t) == "int64" for t in df.dtypes)


def test_overview_vazio_mantem_as_colunas():
    df = overview({"ok": {}})
    assert list(df.columns) == OVERVIEW_COLUMNS
    assert df.empty


def test_periodo_vai_do_primeiro_ao_ultimo_evento_do_projeto():
    """Apêndice A: "from the first activity to the last activity", do projeto.

    Contribuidor nenhum cobre o intervalo inteiro sozinho aqui: o período sai do
    menor `span_start` contra o maior `span_end`, atravessando gente diferente.
    """
    df = pd.DataFrame(
        {
            "contributor_id": ["C1", "C1", "C2"],
            "span_start": pd.to_datetime(["2009-07-31", "2011-01-01", "2010-01-01"]),
            "span_end": pd.to_datetime(["2009-09-30", "2011-03-01", "2013-10-07"]),
            "span_idx": [0, 1, 0],
        }
    )
    assert _periodo_em_dias(df) == 1529


def test_projeto_sem_evento_tem_periodo_zero():
    vazio = pd.DataFrame(columns=["contributor_id", "span_start", "span_end", "span_idx"])
    assert _periodo_em_dias(vazio) == 0
