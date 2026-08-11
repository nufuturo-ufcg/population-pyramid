"""Janela de tempo pedida na linha de comando.

O que estes testes prendem: `--inicio`/`--fim` chegam ao estado do processo sem
tocar em `config/settings.yaml`, e data fora do formato ISO morre no parse,
antes de qualquer estágio abrir banco ou parquet.
"""

import pytest
from typer.testing import CliRunner

from pyramid import config
from pyramid.cli import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def janela_limpa():
    """Estado de janela é do processo. Sem isto um teste contamina o seguinte."""
    config.set_window(None, None)
    yield
    config.set_window(None, None)


@pytest.fixture
def espia(monkeypatch):
    """Troca o estágio por um registrador, para o teste rodar sem banco."""
    visto = {}

    def run(scopes, *, force=False, fail_fast=False):
        visto["scopes"] = scopes
        visto["janela"] = config.window_override()

    from pyramid import snapshots

    monkeypatch.setattr(snapshots, "run", run, raising=False)
    return visto


def test_janela_chega_no_estagio(espia):
    r = runner.invoke(app, ["--inicio", "2011-01-01", "--fim", "2012-12-31", "snapshots"])

    assert r.exit_code == 0, r.output
    assert espia["janela"] == ("2011-01-01", "2012-12-31")


def test_uma_ponta_so(espia):
    r = runner.invoke(app, ["--fim", "2012-12-31", "snapshots"])

    assert r.exit_code == 0, r.output
    assert espia["janela"] == (None, "2012-12-31")


def test_sem_flag_a_janela_e_a_da_config(espia):
    r = runner.invoke(app, ["snapshots"])

    assert r.exit_code == 0, r.output
    assert espia["janela"] == (None, None)


@pytest.mark.parametrize("valor", ["2011", "01/01/2011", "2011-13-01", "ontem"])
def test_data_fora_do_iso_morre_no_parse(valor, espia):
    r = runner.invoke(app, ["--inicio", valor, "snapshots"])

    assert r.exit_code != 0
    assert "AAAA-MM-DD" in r.output
    assert "janela" not in espia
