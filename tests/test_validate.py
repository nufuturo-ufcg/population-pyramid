"""Testes do `pyramid validate`.

O valor deste comando está em rotular. Ele não calcula nada. Os dois
rótulos que mantêm a documentação honesta são justamente os que **nunca
aparecem numa rodada saudável**:

* `OBSOLETA`: divergência declarada que voltou a bater. Sem isto,
  `docs/replicacao/discrepancias.md` continuaria afirmando um desvio já corrigido.
* chave órfã: declaração apontando para um check que não existe mais. Sem
  isto, o yaml acumula perdão para nada.

Um bug em qualquer um dos dois é silencioso por construção: o comando segue
imprimindo "está no estado que a documentação descreve". Por isso a tabela de
status é testada célula a célula, e não por amostragem.
"""

from __future__ import annotations

import pytest

from pyramid import validate as v


def _check(**kw):
    base = dict(key="k", grupo="g", fonte=v.ARTIGO, esperado=1, obtido=1, bate=True)
    return v.Check(**{**base, **kw})


# --- tabela de status ---------------------------------------------------------


@pytest.mark.parametrize(
    "gate,bate,ref,esperado",
    [
        # gate: o que o artigo exige que bata
        (True, True, "", v.OK),
        (True, False, "", v.FALHA),
        (True, False, "seção 3.1", v.CONHECIDA),  # desvio declarado e analisado
        (True, True, "seção 3.1", v.OBSOLETA),  # declarado, mas voltou a bater
        # informativo: divergir não é falha, só ruído a olhar
        (False, True, "", v.OK),
        (False, False, "", "~"),
        (False, False, "seção 3.1", v.CONHECIDA),
        (False, True, "seção 3.1", v.OK),
    ],
)
def test_status(gate, bate, ref, esperado):
    assert _check(gate=gate, bate=bate, ref=ref).status == esperado


def test_indisponivel_ganha_de_tudo():
    """Artefato ausente não pode ser lido como acerto nem como desvio conhecido."""
    c = _check(bate=True, ref="seção 3.1", indisponivel=True)
    assert c.status == v.INDISPONIVEL


def test_indisponivel_e_obsoleta_sao_fatais():
    """Sair 0 com checkpoint não executado é o pior modo de falha possível:

    o comando diria que está tudo bem sobre um dado que ele não leu.
    """
    assert v.INDISPONIVEL in v.FATAIS
    assert v.OBSOLETA in v.FATAIS
    assert v.CONHECIDA not in v.FATAIS
    assert "~" not in v.FATAIS


# --- agregação ----------------------------------------------------------------


def test_relatorio_ok_ignora_conhecida_e_til():
    rep = v.Report(
        [
            _check(key="a"),
            _check(key="b", bate=False, ref="seção 7"),
            _check(key="c", gate=False, bate=False),
        ]
    )
    assert rep.ok
    assert rep.falhas == []
    assert rep.contagem() == {v.OK: 1, v.CONHECIDA: 1, "~": 1}


def test_uma_falha_derruba_o_relatorio():
    rep = v.Report([_check(key="a"), _check(key="b", bate=False)])
    assert not rep.ok
    assert [c.key for c in rep.falhas] == ["b"]


def test_obsoleta_derruba_o_relatorio():
    """Cenário: alguém conserta a seção 3.1 e esquece de tirar a declaração."""
    rep = v.Report([_check(key="types.counts.A", bate=True, ref="seção 3.1")])
    assert not rep.ok
    assert rep.falhas[0].status == v.OBSOLETA


# --- integração com o yaml ----------------------------------------------------


def test_chave_orfa_no_yaml_vira_falha(monkeypatch):
    """Declaração que não casa com nenhum check não protege nada."""
    monkeypatch.setattr(v, "checkpoints", lambda: {"known_divergences": {"nao.existe": "seção 99"}})
    monkeypatch.setattr(v, "GRUPOS", {"g": lambda cfg: [_check(key="existe")]})

    rep = v.run()
    orfas = [c for c in rep.checks if c.grupo == "known_divergences"]
    assert [c.key for c in orfas] == ["nao.existe"]
    assert not rep.ok


def test_orfa_nao_e_checada_em_rodada_parcial(monkeypatch):
    """`validate --grupo x` não vê os outros grupos: acusar órfã ali seria ruído."""
    monkeypatch.setattr(
        v, "checkpoints", lambda: {"known_divergences": {"outro.grupo": "seção 99"}}
    )
    monkeypatch.setattr(v, "GRUPOS", {"g": lambda cfg: [_check(key="existe")]})

    rep = v.run(["g"])
    assert [c.grupo for c in rep.checks] == ["g"]
    assert rep.ok


def test_grupo_desconhecido_e_erro(monkeypatch):
    monkeypatch.setattr(v, "checkpoints", lambda: {})
    monkeypatch.setattr(v, "GRUPOS", {"g": lambda cfg: []})
    with pytest.raises(ValueError, match="grupo desconhecido"):
        v.run(["naoexiste"])


def test_declaracao_do_yaml_chega_no_check(monkeypatch):
    monkeypatch.setattr(v, "checkpoints", lambda: {"known_divergences": {"existe": "seção 13"}})
    monkeypatch.setattr(v, "GRUPOS", {"g": lambda cfg: [_check(key="existe", bate=False)]})
    rep = v.run()
    assert rep.checks[0].ref == "seção 13"
    assert rep.checks[0].status == v.CONHECIDA
    assert rep.ok


# --- declaração por prefixo ---------------------------------------------------


def _cfg_prefixo():
    return {"known_divergences": {"tab.*": "seção 12"}}


def test_prefixo_cobre_todas_as_celulas_do_grupo(monkeypatch):
    monkeypatch.setattr(v, "checkpoints", _cfg_prefixo)
    monkeypatch.setattr(
        v,
        "GRUPOS",
        {"g": lambda cfg: [_check(key="tab.A.x", bate=False), _check(key="tab.B.y", bate=False)]},
    )
    rep = v.run()
    assert [c.status for c in rep.checks] == [v.CONHECIDA, v.CONHECIDA]
    assert rep.ok


def test_prefixo_nao_vaza_para_chave_de_fora(monkeypatch):
    """`tab.*` não pode pegar `tabela.x`. Divergência de fora fica FALHA."""
    monkeypatch.setattr(v, "checkpoints", _cfg_prefixo)
    monkeypatch.setattr(v, "GRUPOS", {"g": lambda cfg: [_check(key="tabela.x", bate=False)]})
    rep = v.run()
    assert rep.checks[0].status == v.FALHA
    assert not rep.ok


def test_chave_exata_ganha_do_prefixo(monkeypatch):
    monkeypatch.setattr(
        v,
        "checkpoints",
        lambda: {"known_divergences": {"tab.*": "seção 12", "tab.A.x": "seção 16"}},
    )
    monkeypatch.setattr(v, "GRUPOS", {"g": lambda cfg: [_check(key="tab.A.x", bate=False)]})
    assert v.run().checks[0].ref == "seção 16"


def test_grupo_inteiro_batendo_vira_obsoleta(monkeypatch):
    """Se todas as células reproduzem, a seção de docs virou mentira."""
    monkeypatch.setattr(v, "checkpoints", _cfg_prefixo)
    monkeypatch.setattr(
        v,
        "GRUPOS",
        {"g": lambda cfg: [_check(key="tab.A.x"), _check(key="tab.B.y")]},
    )
    rep = v.run()
    obs = [c for c in rep.checks if c.grupo == "known_divergences"]
    assert [c.key for c in obs] == ["tab.*"]
    assert obs[0].status == v.OBSOLETA
    assert obs[0].obtido == "2/2 batem"
    assert not rep.ok


def test_uma_celula_divergente_segura_o_grupo(monkeypatch):
    """Enquanto uma diverge, a explicação ainda descreve algo real."""
    monkeypatch.setattr(v, "checkpoints", _cfg_prefixo)
    monkeypatch.setattr(
        v,
        "GRUPOS",
        {"g": lambda cfg: [_check(key="tab.A.x"), _check(key="tab.B.y", bate=False)]},
    )
    rep = v.run()
    assert not [c for c in rep.checks if c.grupo == "known_divergences"]
    assert rep.ok


def test_prefixo_sem_nenhuma_celula_e_orfao(monkeypatch):
    monkeypatch.setattr(v, "checkpoints", _cfg_prefixo)
    monkeypatch.setattr(v, "GRUPOS", {"g": lambda cfg: [_check(key="outro.x")]})
    rep = v.run()
    orfas = [c for c in rep.checks if c.grupo == "known_divergences"]
    assert [(c.key, c.obtido) for c in orfas] == [("tab.*", "chave órfã no yaml")]
    assert not rep.ok


# --- comparação numérica ------------------------------------------------------


def test_perto_usa_tolerancia_relativa():
    assert v._perto(0.4055, 0.4000, 0.02)
    assert not v._perto(0.4500, 0.4000, 0.02)


def test_perto_no_zero_cai_para_o_absoluto():
    """D/non_coding/baseline é 0.0000 na Tabela 3: sem isto só o zero exato passa."""
    assert v._perto(0.01, 0.0, 0.02)
    assert not v._perto(0.05, 0.0, 0.02)


def test_perto_com_nan_nunca_bate():
    """NaN é dado ausente; tratar como igual esconderia coorte sem denominador."""
    assert not v._perto(float("nan"), 0.5, 0.02)
    assert not v._perto(0.5, float("nan"), 0.02)
    assert not v._perto(float("nan"), float("nan"), 0.02)
