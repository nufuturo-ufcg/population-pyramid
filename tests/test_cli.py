"""Superfície da linha de comando.

O que estes testes prendem: `--inicio`/`--fim` chegam ao estado do processo sem
tocar em `config/settings.yaml`, data fora do formato ISO morre no parse antes
de qualquer estágio abrir banco ou parquet, e todo comando que o Makefile chama
existe na CLI. O README citou `pyramid project` por um tempo, comando que não
existe, e o erro só aparecia na hora de rodar.
"""

import re

import pytest
from typer.testing import CliRunner

from pyramid import config
from pyramid.cli import app
from pyramid.config import ROOT

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


def _comandos_da_cli() -> set[str]:
    return {c.name or c.callback.__name__ for c in app.registered_commands}


def _comandos_do_makefile() -> set[str]:
    txt = (ROOT / "Makefile").read_text()
    return set(re.findall(r"pyramid\s+([a-z][a-z-]*)", txt))


def test_makefile_so_chama_comando_que_existe():
    faltam = _comandos_do_makefile() - _comandos_da_cli()

    assert not faltam, f"Makefile chama comando inexistente: {sorted(faltam)}"


def test_make_help_cita_todo_alvo_do_phony():
    txt = (ROOT / "Makefile").read_text()
    phony = set(re.search(r"^\.PHONY:(.*)$", txt, re.M).group(1).split()) - {"help"}
    corpo = txt[txt.index("help:") : txt.index("setup:")]
    citados = set(re.findall(r"[a-z][a-z-]*", corpo))

    assert not phony - citados, f"alvo fora do make help: {sorted(phony - citados)}"
