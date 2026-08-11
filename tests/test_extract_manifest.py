"""O manifesto do extract como cache do `scope_meta` do adaptador.

A promessa do contrato de entrada é agregar os MESMOS eventos por outro eixo
sem reextrair nada. Ela só vale se os atributos do escopo ficarem gravados
junto do parquet. Estes testes prendem esse trânsito: adaptador -> manifesto ->
`extract.scope_meta()`, com o banco desligado.
"""

from __future__ import annotations

import pandas as pd
import pytest

from pyramid import config, extract
from pyramid import logging_config as runlog


@pytest.fixture
def saida(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(config, "RUNS_DIR", tmp_path / "output" / "runs")
    (tmp_path / "output" / "extract").mkdir(parents=True)
    yield tmp_path / "output"
    config.end_run()


def sem_fonte(monkeypatch) -> None:
    """Qualquer toque no adaptador vira erro: o teste é sobre ler do disco."""

    def explode() -> None:
        raise AssertionError("leu do manifesto, não deveria abrir a fonte")

    monkeypatch.setattr(extract, "source", explode)


def test_manifesto_devolve_os_atributos_sem_as_contagens(saida, monkeypatch):
    runlog.save(
        "extract",
        {
            "stage": "extract",
            "ok": {
                "25875": {
                    "label": "rails/rails",
                    "language": "Ruby",
                    "created_at": "2008-04-11 15:53:01",
                    "events": 12,
                    "contributors": 3,
                    "first": "2012-03-01 10:00:00",
                    "last": "2013-01-04 08:15:00",
                }
            },
            "failed": {},
        },
    )
    sem_fonte(monkeypatch)

    assert extract.scope_meta() == {
        25875: {
            "label": "rails/rails",
            "language": "Ruby",
            "created_at": "2008-04-11 15:53:01",
        }
    }
    assert extract.labels() == {25875: "rails/rails"}


def test_language_do_manifesto_agrupa_escopos(saida, monkeypatch):
    runlog.save(
        "extract",
        {
            "stage": "extract",
            "ok": {
                "1": {"label": "a/a", "language": "Ruby", "created_at": None, "events": 1},
                "2": {"label": "b/b", "language": "Ruby", "created_at": None, "events": 1},
                "3": {"label": "c/c", "language": "Java", "created_at": None, "events": 1},
            },
            "failed": {},
        },
    )
    sem_fonte(monkeypatch)

    por_lingua: dict[str, list[int]] = {}
    for sid, meta in extract.scope_meta().items():
        por_lingua.setdefault(meta["language"], []).append(sid)

    assert por_lingua == {"Ruby": [1, 2], "Java": [3]}


def test_manifesto_vazio_cai_no_contrato_publico(saida, monkeypatch):
    class Fonte:
        def list_scopes(self) -> list[int]:
            return [7]

        def scope_meta(self, scope_id: int) -> dict:
            return {
                "label": "x/y",
                "language": None,
                "created_at": pd.Timestamp("2010-01-02 03:04:05"),
            }

    monkeypatch.setattr(extract, "source", Fonte)

    assert extract.scope_meta() == {
        7: {"label": "x/y", "language": None, "created_at": "2010-01-02 03:04:05"}
    }


def test_serializa_meta_preserva_chave_extra_do_adaptador():
    meta = {
        "label": "x/y",
        "language": "C",
        "created_at": pd.Timestamp("2010-01-02"),
        "forked_from": 3,
    }

    assert extract.serializa_meta(meta) == {
        "label": "x/y",
        "language": "C",
        "created_at": "2010-01-02 00:00:00",
        "forked_from": 3,
    }
