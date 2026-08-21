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


# --- estágio que não vale na unidade configurada ------------------------------


@pytest.mark.parametrize("modulo", ["attractiveness", "projection"])
def test_estagio_calibrado_por_projeto_recusa_outra_unidade(monkeypatch, modulo):
    """Magnetismo compara com a mediana da amostra; projeção, com um limiar dela.

    Os dois mudam de significado quando a amostra deixa de ser projeto, e rodar
    assim mesmo devolveria número plausível e errado.
    """
    import importlib

    mod = importlib.import_module(f"pyramid.{modulo}")
    monkeypatch.setattr(config, "settings", lambda: {"analysis": {"unit": "language"}})

    with pytest.raises(ValueError, match=f"{modulo} não roda com"):
        mod.run()


@pytest.mark.parametrize("modulo", ["attractiveness", "projection"])
def test_a_unidade_suportada_esta_declarada(modulo):
    import importlib

    mod = importlib.import_module(f"pyramid.{modulo}")

    assert mod.UNIDADES == ("project",)


def test_run_all_pula_em_vez_de_morrer(monkeypatch):
    """Bloquear o estágio não pode inutilizar o `run-all` da unidade nova."""
    from pyramid import attractiveness, classify, cli

    monkeypatch.setattr(config, "settings", lambda: {"analysis": {"unit": "language"}})
    assert cli._pula_na_unidade(attractiveness)
    assert not cli._pula_na_unidade(classify)

    monkeypatch.setattr(config, "settings", lambda: {"analysis": {"unit": "project"}})
    assert not cli._pula_na_unidade(attractiveness)


def test_o_grupo_unknown_nao_vira_figura(por_linguagem):
    """`unknown` não é uma linguagem, e desenhar a pirâmide dele sugeriria que é."""
    escopos = {e.label: e for e in units.scopes_of_unit(por_linguagem)}

    assert not escopos["unknown"].plotavel
    assert escopos["Clojure"].plotavel


def test_com_project_todo_escopo_plota(por_projeto):
    """`language` nula aí é projeto de verdade sem linguagem registrada na origem."""
    escopos = {e.label: e for e in units.scopes_of_unit(por_projeto)}

    assert escopos["acme/quatro"].meta["language"] is None
    assert escopos["acme/quatro"].plotavel


# --- retomada não pode reusar dado de outra configuração ----------------------


def test_mudar_a_escolha_da_fonte_invalida_o_manifesto(tmp_path, monkeypatch):
    """O id do escopo não carrega a política que o produziu.

    Sob `unit: language` o id sai do nome da linguagem. Trocar uma chave que
    muda os MEMBROS do escopo não muda o id, então a retomada encontrava a chave
    no manifesto e o parquet no disco, pulava, e gravava a política nova por
    cima de dados da política velha. Número errado sem erro nenhum.
    """
    from pyramid import extract

    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr(config, "RUNS_DIR", tmp_path / "output" / "runs")
    monkeypatch.setattr(config, "settings", lambda: {"analysis": {"unit": "language"}})
    config.end_run()

    class ComEscolha(FonteFake):
        def __init__(self, escolha, escopos=None):
            super().__init__(escopos)
            self.escolha = escolha

        def provenance(self):
            return {"escolha": self.escolha}

    # Primeira execução: dois repositórios Clojure.
    monkeypatch.setattr(extract, "source", lambda: ComEscolha("a"))
    antes = extract.run()
    clojure = next(k for k, v in antes["ok"].items() if v["label"] == "Clojure")
    assert antes["ok"][clojure]["events"] == 4  # os dois repositórios Clojure

    # A escolha muda e o repositório 11 sai do grupo. O id de Clojure é o mesmo.
    so_um = {10: ESCOPOS[10], 12: ESCOPOS[12]}
    monkeypatch.setattr(extract, "source", lambda: ComEscolha("b", so_um))
    depois = extract.run()

    assert depois["ok"][clojure]["events"] == 2  # só o repositório 10 sobrou
    assert depois["escolha"] == "b"
