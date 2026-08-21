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


# --- separação da saída por unidade de análise --------------------------------
# `<scope_id>.parquet` é o nome em todo estágio, e id de projeto colide com id de
# linguagem. Sem subpasta as duas populações se sobrescrevem, e `_ids_gravados`
# leria as duas como uma só. `project` continua sem subpasta, senão a replicação
# MSR14 muda de caminho.


@pytest.fixture
def saida(tmp_path, monkeypatch):
    """Redireciona a saída e fecha qualquer execução isolada aberta."""
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(config, "RUNS_DIR", tmp_path / "output" / "runs")
    config.end_run()
    yield tmp_path / "output"
    config.end_run()


def _unidade(monkeypatch, unit):
    monkeypatch.setattr(config, "UNITS_IMPLEMENTADAS", ("project", unit))
    monkeypatch.setattr(config, "settings", lambda: {"analysis": {"unit": unit}})


def test_project_grava_onde_sempre_gravou(saida, monkeypatch):
    _unidade(monkeypatch, "project")

    assert config.stage_dir("extract") == saida / "extract"
    assert config.artifact_dir("plots") == saida / "plots"


def test_unidade_nova_ganha_subpasta_propria(saida, monkeypatch):
    _unidade(monkeypatch, "language")

    assert config.stage_dir("extract") == saida / "by-language" / "extract"
    assert config.artifact_dir("plots") == saida / "by-language" / "plots"


def test_o_manifesto_segue_a_unidade(saida, monkeypatch):
    """O manifesto mora no `artifact_dir`. Sem a subpasta lá, a execução por
    linguagem sobrescreve o `_manifest.json` da execução por projeto."""
    from pyramid import logging_config as runlog

    _unidade(monkeypatch, "project")
    por_projeto = runlog._path("extract")
    _unidade(monkeypatch, "language")
    por_linguagem = runlog._path("extract")

    assert por_projeto == saida / "extract" / "_manifest.json"
    assert por_linguagem == saida / "by-language" / "extract" / "_manifest.json"


def test_execucao_isolada_tambem_separa_por_unidade(saida, monkeypatch):
    _unidade(monkeypatch, "language")
    destino = config.start_run("teste")

    assert config.artifact_dir("plots") == destino / "by-language" / "plots"
    # O parquet fica canônico mesmo com execução aberta, senão a cadeia
    # extract -> classify -> snapshots quebra.
    assert config.stage_dir("extract") == saida / "by-language" / "extract"


def test_parquet_de_unidades_diferentes_nao_colide(saida, monkeypatch):
    _unidade(monkeypatch, "project")
    (config.stage_dir("extract") / "1.parquet").write_text("projeto 1")
    _unidade(monkeypatch, "language")
    (config.stage_dir("extract") / "1.parquet").write_text("linguagem 1")

    _unidade(monkeypatch, "project")
    assert (config.stage_dir("extract") / "1.parquet").read_text() == "projeto 1"
