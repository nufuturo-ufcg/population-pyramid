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
