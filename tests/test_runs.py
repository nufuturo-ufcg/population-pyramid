"""Saída modular: execução isolada em `output/runs/<carimbo>/`.

A regra que estes testes prendem: entregável (figura, tabela, relatório) segue a
execução aberta, parquet de estágio continua na saída canônica. Mover parquet
quebraria a cadeia extract -> snapshots -> classify -> metrics, que lê de
`output/<estágio>/` por caminho fixo.
"""

import json

import pytest

from pyramid import config


@pytest.fixture
def saida(tmp_path, monkeypatch):
    """Redireciona output/ e runs/ para o tmp, e fecha a execução no fim."""
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(config, "RUNS_DIR", tmp_path / "output" / "runs")
    yield tmp_path / "output"
    config.end_run()


def test_sem_run_a_saida_e_a_canonica(saida):
    assert config.run_dir() is None
    assert config.artifact_dir("plots") == saida / "plots"
    assert config.stage_dir("plots") == saida / "plots"


def test_run_desvia_entregavel_e_preserva_parquet(saida):
    config.start_run("baseline", comando="pyramid plot --run")

    assert config.artifact_dir("plots").parent == config.run_dir()
    # O parquet do estágio fica na canônica: é entrada do estágio seguinte.
    assert config.stage_dir("plots") == saida / "plots"


def test_rotulo_entra_no_nome_e_carimbo_ordena(saida):
    d = config.start_run("hipotese-x")

    carimbo, _, rotulo = d.name.partition("-hipotese-x")
    assert rotulo == ""
    assert len(carimbo) == len("AAAAMMDD-HHMMSS")
    assert carimbo.replace("-", "").isdigit()


def test_metadados_da_execucao(saida, monkeypatch):
    monkeypatch.setenv("DATASET_SOURCE", "msr14")
    d = config.start_run("auditoria", comando="pyramid validate --run")

    meta = json.loads((d / "_run.json").read_text())
    assert meta["run"] == d.name
    assert meta["comando"] == "pyramid validate --run"
    assert meta["dataset_source"] == "msr14"
    assert "criado_em" in meta
    # commit vem do git do repo; fora de um clone o campo existe e fica vazio.
    assert "commit" in meta


def test_latest_aponta_para_a_ultima(saida):
    config.start_run("primeira")
    segunda = config.start_run("segunda")

    link = config.RUNS_DIR / "latest"
    if link.is_symlink():
        assert link.resolve().name == segunda.name
    else:
        assert (config.RUNS_DIR / "latest.txt").read_text().strip() == segunda.name


def test_end_run_devolve_a_saida_canonica(saida):
    config.start_run("temporaria")
    config.end_run()

    assert config.run_dir() is None
    assert config.artifact_dir("plots") == saida / "plots"


def test_manifesto_acompanha_a_execucao(saida):
    from pyramid import logging_config as runlog

    canonico = runlog._path("plots")
    config.start_run("comparacao")
    dentro = runlog._path("plots")

    assert canonico == saida / "plots" / "_manifest.json"
    assert dentro.parent.parent == config.run_dir()
