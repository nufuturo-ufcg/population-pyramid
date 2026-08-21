"""Unidade de análise: quando N escopos do adaptador viram uma pirâmide só.

A fonte aqui é sintética e cabe na cabeça, para o que está sob teste ser o
agrupamento, e não o adaptador. Três repositórios, duas linguagens, e uma pessoa
que aparece em mais de um repositório, que é o caso que a pirâmide por linguagem
existe para tratar.
"""

from __future__ import annotations

import pandas as pd
import pytest

from pyramid import classify, config, units
from pyramid.sources.base import EVENT_COLUMNS

# (scope_id, rótulo, linguagem, nascimento) e os eventos de cada um.
#
# ANA está em 10 e em 11, os dois Clojure. Ela é a razão de tudo: sob `project`
# ela é duas pessoas, uma nascendo em 2019 e outra em 2021.
# BIA está em 10 (Clojure) e em 12 (Java), e tem de aparecer nas duas pirâmides.
ANA, BIA, CID = 1, 2, 3
ESCOPOS = {
    10: ("acme/um", "Clojure", "2019-01-01"),
    11: ("acme/dois", "Clojure", "2021-01-01"),
    12: ("acme/tres", "Java", "2020-01-01"),
    13: ("acme/quatro", None, "2022-01-01"),
}
EVENTOS = {
    10: [(ANA, "commits", "2019-03-01"), (BIA, "commits", "2019-04-01")],
    11: [(ANA, "commits", "2021-05-01"), (CID, "issues", "2021-06-01")],
    12: [(BIA, "commits", "2020-07-01")],
    13: [(CID, "commits", "2022-08-01")],
}


class FonteFake:
    """Só o que o contrato exige, com os eventos vindo de um dicionário."""

    def __init__(self, escopos=None, eventos=None):
        self.escopos = escopos or ESCOPOS
        self.eventos = eventos or EVENTOS

    def list_scopes(self) -> list[int]:
        return sorted(self.escopos)

    def scope_meta(self, scope_id: int) -> dict:
        rotulo, lang, nascimento = self.escopos[scope_id]
        return {"label": rotulo, "language": lang, "created_at": pd.Timestamp(nascimento)}

    def scope_label(self, scope_id: int) -> str:
        return self.escopos[scope_id][0]

    def get_events(self, scope_id: int) -> pd.DataFrame:
        linhas = [
            (scope_id, quem, tipo, pd.Timestamp(quando))
            for quem, tipo, quando in self.eventos.get(scope_id, [])
        ]
        return pd.DataFrame(linhas, columns=EVENT_COLUMNS)


@pytest.fixture
def por_linguagem(monkeypatch):
    monkeypatch.setattr(config, "settings", lambda: {"analysis": {"unit": "language"}})
    return FonteFake()


@pytest.fixture
def por_projeto(monkeypatch):
    monkeypatch.setattr(config, "settings", lambda: {"analysis": {"unit": "project"}})
    return FonteFake()


def _escopo(fonte, rotulo):
    return next(e for e in units.scopes_of_unit(fonte) if e.label == rotulo)


def _uniao(fonte, escopo):
    return pd.concat([fonte.get_events(m) for m in escopo.membros], ignore_index=True)


# --- project não muda de comportamento ----------------------------------------


def test_project_devolve_um_escopo_por_escopo_do_adaptador(por_projeto):
    escopos = units.scopes_of_unit(por_projeto)

    assert [e.id for e in escopos] == [10, 11, 12, 13]
    assert all(e.membros == (e.id,) for e in escopos)
    assert [e.label for e in escopos] == ["acme/um", "acme/dois", "acme/tres", "acme/quatro"]


# --- language agrupa ----------------------------------------------------------


def test_language_junta_os_repositorios_da_mesma_linguagem(por_linguagem):
    escopos = {e.label: e for e in units.scopes_of_unit(por_linguagem)}

    assert set(escopos) == {"Clojure", "Java", "unknown"}
    assert escopos["Clojure"].membros == (10, 11)
    assert escopos["Java"].membros == (12,)


def test_o_nascimento_da_linguagem_e_o_do_repositorio_mais_velho(por_linguagem):
    assert _escopo(por_linguagem, "Clojure").meta["created_at"] == pd.Timestamp("2019-01-01")


def test_escopo_sem_linguagem_e_contado_e_nao_plota(por_linguagem):
    unknown = _escopo(por_linguagem, "unknown")

    assert unknown.meta["language"] is None
    assert not unknown.plotavel
    assert _escopo(por_linguagem, "Clojure").plotavel


# --- o id da linguagem --------------------------------------------------------


def test_o_id_da_linguagem_sai_so_do_nome():
    """Índice numa lista ordenada mudaria o id de todas ao incluir uma linguagem."""
    assert units.id_da_linguagem("Clojure") == units.id_da_linguagem("Clojure")
    assert units.id_da_linguagem("Clojure") != units.id_da_linguagem("Java")


def test_incluir_linguagem_nova_nao_move_o_id_das_outras(monkeypatch):
    monkeypatch.setattr(config, "settings", lambda: {"analysis": {"unit": "language"}})
    antes = {e.label: e.id for e in units.scopes_of_unit(FonteFake())}
    # `Ada` ordena antes de todas, e é justamente esse o caso que quebraria um
    # id derivado de posição em lista ordenada.
    escopos = {**ESCOPOS, 14: ("acme/cinco", "Ada", "2023-01-01")}
    depois = {e.label: e.id for e in units.scopes_of_unit(FonteFake(escopos, {**EVENTOS, 14: []}))}

    assert all(depois[nome] == valor for nome, valor in antes.items())


def test_colisao_de_id_falha_alto(monkeypatch):
    monkeypatch.setattr(config, "settings", lambda: {"analysis": {"unit": "language"}})
    monkeypatch.setattr(units, "id_da_linguagem", lambda _nome: 42)

    with pytest.raises(ValueError, match="mesmo id"):
        units.scopes_of_unit(FonteFake())


# --- invariantes de soma ------------------------------------------------------


def test_a_soma_de_eventos_fecha(por_linguagem):
    clojure = _escopo(por_linguagem, "Clojure")
    soma = sum(len(por_linguagem.get_events(m)) for m in clojure.membros)

    assert len(_uniao(por_linguagem, clojure)) == soma


def test_contribuidor_unico_da_linguagem_nao_passa_da_soma(por_linguagem):
    clojure = _escopo(por_linguagem, "Clojure")
    soma = sum(por_linguagem.get_events(m)["contributor_id"].nunique() for m in clojure.membros)
    uniao = _uniao(por_linguagem, clojure)["contributor_id"].nunique()

    assert uniao <= soma
    assert uniao == 3 and soma == 4  # ANA conta uma vez, e estava em dois


def test_pessoa_em_dois_repositorios_nasce_no_evento_mais_antigo(por_linguagem):
    """Sob `project` ANA é duas pessoas, e a segunda nasce em 2021."""
    clojure = _escopo(por_linguagem, "Clojure")
    uniao = _uniao(por_linguagem, clojure)
    dela = uniao[uniao["contributor_id"] == ANA]

    assert len(dela) == 2
    assert dela["timestamp"].min() == pd.Timestamp("2019-03-01")


def test_quem_toca_duas_linguagens_aparece_nas_duas_piramides(por_linguagem):
    def pessoas(rotulo):
        return set(_uniao(por_linguagem, _escopo(por_linguagem, rotulo))["contributor_id"])

    assert BIA in pessoas("Clojure")
    assert BIA in pessoas("Java")


def test_o_span_atravessa_repositorio(por_linguagem):
    """Silêncio no repositório A que a atividade no B preenche não quebra o período.

    É o que "vitalidade sobre múltiplos projetos" quer dizer. Sob `project` a
    mesma sequência vira dois períodos, um por repositório.
    """
    eventos = {
        10: [(ANA, "commits", "2021-01-01")],
        11: [(ANA, "commits", "2021-02-01"), (ANA, "commits", "2021-03-01")],
    }
    fonte = FonteFake({10: ESCOPOS[10], 11: ESCOPOS[11]}, eventos)
    clojure = _escopo(fonte, "Clojure")

    juntos = classify.profile(_uniao(fonte, clojure), {"commits"}, gap_days=91.3125)
    separados = sum(
        len(classify.profile(fonte.get_events(m), {"commits"}, gap_days=91.3125))
        for m in clojure.membros
    )

    assert len(juntos) == 1
    assert separados == 2
