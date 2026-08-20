"""Leitura de `config/settings.yaml` que o resto do pipeline assume.

`analysis.unit` escolhe a unidade de análise da saída. O contrato de entrada já
exige `scope_meta.language`, então o dia em que existir agregador por linguagem
o valor entra aqui. Até lá o valor desconhecido tem que parar antes do banco.
"""

from __future__ import annotations

import pytest

from pyramid import config, extract


def test_unit_project_e_a_implementada(monkeypatch):
    monkeypatch.setattr(config, "settings", lambda: {"analysis": {"unit": "project"}})

    assert config.analysis_unit() == "project"


def test_settings_sem_analysis_cai_em_project(monkeypatch):
    monkeypatch.setattr(config, "settings", lambda: {})

    assert config.analysis_unit() == "project"


def test_unit_sem_agregador_falha_com_a_lista(monkeypatch):
    monkeypatch.setattr(config, "settings", lambda: {"analysis": {"unit": "language"}})

    with pytest.raises(ValueError, match=r"analysis\.unit='language'.*project"):
        config.analysis_unit()


def test_extract_para_antes_de_abrir_a_fonte(monkeypatch):
    """A validação roda antes de instanciar o adaptador, que abriria conexão."""
    monkeypatch.setattr(config, "settings", lambda: {"analysis": {"unit": "team"}})

    def explode() -> None:
        raise AssertionError("extract chegou a abrir a fonte")

    monkeypatch.setattr(extract, "source", explode)

    with pytest.raises(ValueError, match=r"analysis\.unit='team'"):
        extract.run()


# ---------------------------------------------------------------------------
# Leitura não abre banco
# ---------------------------------------------------------------------------
def test_estagios_de_leitura_nao_chamam_o_adaptador(monkeypatch):
    """`load_all`, `table` e o `validate` rodam com o MySQL desligado.

    O `plots` já prometia isso ("as figuras se regeram com o banco desligado") e
    os outros estágios de leitura não cumpriam: pediam a lista de projetos e o
    rótulo ao adaptador, que abre conexão. No CI, sem dump, quatro testes de
    checkpoint quebravam em vez de pular. O rótulo vem do manifesto do `extract`
    e a lista vem dos parquets no disco.
    """
    from pyramid import attractiveness, extract, metrics, snapshots

    def explode() -> None:
        raise AssertionError("estágio de leitura tentou abrir o banco")

    monkeypatch.setattr(extract, "source", explode)
    monkeypatch.setattr(metrics, "source", explode)
    monkeypatch.setattr(snapshots, "source", explode)
    monkeypatch.setattr(attractiveness, "source", explode)

    metrics.load_all()
    snapshots.load_all()
