"""Registro de métricas e parâmetros de `scripts/vitalidade.py`."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
import vitalidade as script  # noqa: E402

# As linhas da tabela de variáveis dependentes do plano. O magnetismo existe, mas
# o plano o adia: fica fora da execução padrão.
ESPERADAS = {
    "tamanho",
    "composicao",
    "retencao",
    "saida_por_faixa",
    "cenarios",
    "ccr_ncr",
    "stickiness",
    "significancia",
    "comparacao_corrigida",
    "trajetoria",
    "ccr_ncr_comparado",
    "magnetismo",
}


def test_registro_tem_as_metricas_do_plano():
    assert set(script.METRICAS) == ESPERADAS


def test_toda_metrica_diz_o_que_faz_e_cita_a_referencia():
    for nome, funcao in script.METRICAS.items():
        assert "O que faz:" in funcao.__doc__, nome
        assert "Referência:" in funcao.__doc__, nome


def test_set_troca_um_parametro():
    p = script.carrega_parametros(["min_saidas=20", "teto=true", "linguagens_rq2=[clojure, zig]"])
    assert p.min_saidas == 20
    assert p.teto is True
    assert p.linguagens_rq2 == ["clojure", "zig"]
    assert p.horizonte == 5


def test_set_com_chave_desconhecida_falha_alto():
    with pytest.raises(SystemExit):
        script.carrega_parametros(["nao_existe=1"])


def test_magnetismo_fica_fora_da_execucao_padrao():
    assert not script.PADRAO["magnetismo"]
    assert all(script.PADRAO[n] for n in ESPERADAS - {"magnetismo"})


def test_toda_metrica_tem_figura_e_ao_menos_uma_por_padrao():
    for nome in script.METRICAS:
        assert script.FIGURAS[nome], nome
        padrao = [f for f in script.FIGURAS[nome] if (nome, f) in script.FIGURAS_PADRAO]
        assert padrao, nome


def test_toda_metrica_oferece_uma_figura_alternativa():
    for nome in script.METRICAS:
        assert len(script.FIGURAS[nome]) >= 2, nome


def test_escolha_de_figuras():
    nomes = ["tamanho", "composicao"]
    assert script.escolhe_figuras("nenhuma", nomes) == {"tamanho": [], "composicao": []}
    um = script.escolhe_figuras("tamanho.fluxo", nomes)
    assert um == {"tamanho": ["fluxo"], "composicao": []}
    todas = script.escolhe_figuras("todas", nomes)
    assert set(todas["tamanho"]) == set(script.FIGURAS["tamanho"])
    padrao = script.escolhe_figuras("padrao", nomes)
    assert "fluxo" not in padrao["tamanho"]
    assert "anual" in padrao["tamanho"]
    inteira = script.escolhe_figuras("composicao", nomes)
    assert set(inteira["composicao"]) == set(script.FIGURAS["composicao"])
    assert inteira["tamanho"] == []
    with pytest.raises(SystemExit):
        script.escolhe_figuras("tamanho.nao_existe", nomes)


def _figura_de_teste():
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(5, 3))
    ax.plot([0, 1], [0, 1], label="serie")
    ax.set_title("original")
    ax.set_xlabel("x original")
    ax.legend(loc="upper left")
    return fig, ax


def test_estilo_troca_titulo_rotulo_limite_e_tamanho():
    from vitalidade_figuras import aplica_estilo

    fig, ax = _figura_de_teste()
    aplica_estilo(
        fig,
        {
            "figsize": [8, 2],
            "titulo": "{linguagem}: novo",
            "rotulo_x": "ano",
            "ylim": [0, 5],
            "fontes": {"titulo": 20},
            "linha": {"largura": 4},
            "linhas_horizontais": [{"y": 2, "rotulo": "meta"}],
            "textos": [{"x": 0.5, "y": 0.5, "texto": "aqui"}],
        },
    )
    assert ax.get_title().endswith(": novo")
    assert "{linguagem}" not in ax.get_title()
    assert ax.get_xlabel() == "ano"
    assert ax.get_ylim() == (0, 5)
    assert list(fig.get_size_inches()) == [8, 2]
    assert ax.title.get_fontsize() == 20
    assert ax.get_lines()[0].get_linewidth() == 4
    assert len(ax.get_lines()) == 2  # a série e a linha horizontal
    assert [t.get_text() for t in ax.texts] == ["meta", "aqui"]


def test_estilo_sem_opcoes_nao_muda_nada():
    from vitalidade_figuras import aplica_estilo

    fig, ax = _figura_de_teste()
    aplica_estilo(fig, {"fontes": {"titulo": None}})
    assert ax.get_title() == "original"
    assert list(fig.get_size_inches()) == [5, 3]
    assert ax.get_legend() is not None


def test_estilo_move_e_esconde_a_legenda():
    from vitalidade_figuras import aplica_estilo

    fig, ax = _figura_de_teste()
    aplica_estilo(fig, {"legenda": {"posicao": "abaixo", "colunas": 2}})
    legenda = ax.get_legend()
    assert [t.get_text() for t in legenda.get_texts()] == ["serie"]
    aplica_estilo(fig, {"legenda": {"mostrar": False}})
    assert ax.get_legend() is None


def test_estilo_do_yaml_tem_so_figuras_e_opcoes_que_existem():
    import vitalidade_figuras as f

    f.carrega_estilo([])  # falha alto se o yaml cita figura ou opção inexistente
    assert f.estilo_da("tamanho.anual")["figsize"] == [9, 7]
    assert f.estilo_da("tamanho.fluxo")["dpi"] == 200  # herdado de global


def test_estilo_na_linha_de_comando_vence_o_yaml():
    import vitalidade_figuras as f

    try:
        f.carrega_estilo(["tamanho.anual:legenda.posicao=abaixo", "global:dpi=300"])
        e = f.estilo_da("tamanho.anual")
        assert e["legenda"]["posicao"] == "abaixo"
        assert e["dpi"] == 300
        with pytest.raises(SystemExit):
            f.carrega_estilo(["tamanho.anual:opcao_inventada=1"])
        with pytest.raises(SystemExit):
            f.carrega_estilo(["figura.que.nao.existe:dpi=1"])
    finally:
        f.carrega_estilo([])


def test_toda_figura_registrada_pertence_a_uma_metrica():
    import vitalidade_figuras as f

    assert set(f.FIGURAS) <= set(script.METRICAS)


def test_tabelas_gravadas_voltam_iguais(tmp_path, monkeypatch):
    import pandas as pd

    monkeypatch.setattr(script.fb.CFG, "saida", tmp_path, raising=False)
    tabelas = {
        "anual": pd.DataFrame({"ano": [2020, 2021], "ativos": [3, 4]}),
        "cenarios-x/projecao_backtest": pd.DataFrame({"faixa": pd.Categorical(["a", "b"])}),
        "periodos": pd.DataFrame(
            {"periodo": pd.period_range("2020Q1", periods=2), "v": [1.0, 2.0]}
        ),
    }
    script.salva_tabelas("linguagem", "tamanho", tabelas)
    lidas = script.carrega_tabelas("linguagem", "tamanho")
    assert set(lidas) == set(tabelas)
    for chave, tabela in tabelas.items():
        pd.testing.assert_frame_equal(lidas[chave], tabela)
    with pytest.raises(SystemExit):
        script.carrega_tabelas("linguagem", "metrica_sem_resultado")


def test_largura_de_linha_nao_engrossa_linha_de_referencia():
    from vitalidade_figuras import aplica_estilo

    fig, ax = _figura_de_teste()
    referencia = ax.axhline(0.5, linewidth=1)
    aplica_estilo(fig, {"linha": {"largura": 5}})
    assert ax.get_lines()[0].get_linewidth() == 5
    assert referencia.get_linewidth() == 1


def test_pacote_leva_so_as_tabelas_e_abre_em_outra_pasta(tmp_path):
    import vitalidade_pacote as pacote

    origem = tmp_path / "origem"
    for relativo in [
        "clojure/resultados/vitalidade/tamanho/anual.parquet",
        "clojure/resultados/vitalidade/meta.json",
        "clojure/csv/vitalidade/anual.csv",
        "geral/resultados/vitalidade/significancia/logrank.parquet",
        "clojure/cache/vitalidade_eventos.parquet",
        "clojure/vitalidade/anual.png",
        "clojure/trabalho/carga.duckdb",
    ]:
        arquivo = origem / relativo
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        arquivo.write_text(relativo)

    arquivo_pacote = pacote.empacota(origem, tmp_path / "tudo.tar.gz")
    destino = tmp_path / "destino"
    pacote.importa(arquivo_pacote, destino)

    abertos = sorted(str(p.relative_to(destino)) for p in destino.rglob("*") if p.is_file())
    assert abertos == [
        "MANIFESTO-vitalidade.json",
        "clojure/csv/vitalidade/anual.csv",
        "clojure/resultados/vitalidade/meta.json",
        "clojure/resultados/vitalidade/tamanho/anual.parquet",
        "geral/resultados/vitalidade/significancia/logrank.parquet",
    ]
    conteudo = (destino / "clojure/csv/vitalidade/anual.csv").read_text()
    assert conteudo == "clojure/csv/vitalidade/anual.csv"


def test_pacote_sem_resultados_falha_alto(tmp_path):
    import vitalidade_pacote as pacote

    with pytest.raises(SystemExit):
        pacote.empacota(tmp_path, tmp_path / "x.tar.gz")


def test_populacao_desconhecida_falha_alto():
    p = script.carrega_parametros(["populacao=ninguem"])
    with pytest.raises(SystemExit):
        script.aplica_populacao(p)


def test_populacao_de_codigo_grava_em_pasta_propria(tmp_path, monkeypatch):
    script.carga_fonte.aplica_linguagem("zig")
    monkeypatch.setattr(script.fb, "TMP_BASE", tmp_path)
    monkeypatch.setattr(script.fb.CFG, "saida", tmp_path / "zig", raising=False)
    monkeypatch.setattr(script.fb.ESTADO_PASTA_GERAL, "pasta", tmp_path / "geral")
    script.aplica_populacao(script.carrega_parametros(["populacao=codigo"]))
    assert script.fb.CFG.saida == tmp_path / "zig-codigo"
    assert script.fb.ESTADO_PASTA_GERAL.pasta == tmp_path / "geral-codigo"
    assert script.vitalidade_figuras.ESTADO.sufixo == " (só quem codou)"
    script.aplica_populacao(script.carrega_parametros([]))  # volta ao padrão
    assert script.vitalidade_figuras.ESTADO.sufixo == ""


def test_carencia_de_um_ano_nao_tracejou_nada_e_a_de_tres_traceja_dois_anos():
    import pandas as pd

    import vitalidade_figuras as f

    class Ctx:
        fim = pd.Timestamp("2026-10-12")

        class p:  # noqa: N801
            carencia_anos = 1

    assert f._ate_o_ano_decidido(Ctx) == 2025
    assert f._primeiro_provisorio(Ctx) == 2026  # 2025 já é firme, nada tracejado
    Ctx.p.carencia_anos = 3
    assert f._primeiro_provisorio(Ctx) == 2024  # 2024 e 2025 provisórios
