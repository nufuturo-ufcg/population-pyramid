"""Projeção coorte-componente (IEICE16 seção 4)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pyramid.projection import abre, ae, mer, mre, project, tables

# --------------------------------------------------------------------------- #
# ABRE
# --------------------------------------------------------------------------- #


def test_abre_usa_o_menor_denominador_nos_dois_sentidos():
    # Superestimar 2 -> 3 e subestimar 3 -> 2 têm o mesmo denominador (2), então
    # o mesmo erro. É o que torna o BRE "balanced"; um denominador fixo em
    # `actual` daria 0.5 e 0.333.
    assert abre(2, 3) == pytest.approx(0.5)
    assert abre(3, 2) == pytest.approx(0.5)


def test_abre_e_simetrico():
    for a, p in ((1, 7), (4, 9), (10, 3)):
        assert abre(a, p) == pytest.approx(abre(p, a))


def test_abre_zera_no_acerto_exato():
    assert abre(5, 5) == 0.0


def test_abre_indefinido_quando_um_lado_e_zero():
    # Sem denominador não há erro relativo; cravar 0 ou 1 inventaria resultado.
    assert np.isnan(abre(0, 4))
    assert np.isnan(abre(4, 0))
    assert np.isnan(abre(0, 0))


def test_abre_recusa_contagem_negativa():
    with pytest.raises(ValueError, match="negativa"):
        abre(-1, 3)


def test_abre_reproduz_as_fracoes_da_tabela_3():
    # As medianas publicadas são frações de inteiro pequeno. É o que denuncia
    # a unidade de análise: a coorte.
    assert abre(3, 4) == pytest.approx(0.3333, abs=1e-4)
    assert abre(3, 5) == pytest.approx(0.6667, abs=1e-4)
    assert abre(4, 7) == pytest.approx(0.7500)
    assert abre(2, 4) == pytest.approx(1.0000)


# --------------------------------------------------------------------------- #
# passo de projeção
# --------------------------------------------------------------------------- #


def test_projeta_cada_banda_pela_sobrevivencia_do_passo_anterior():
    # p_base = T-3m, p_last = T. SR da banda 0 = p_last[1]/p_base[0] = 5/10 = 0.5,
    # aplicado sobre p_last[0] = 20 -> 10 na banda 1.
    p_base = np.array([10.0, 8.0, 4.0])
    p_last = np.array([20.0, 5.0, 4.0])
    proj, orfas = project(p_base, p_last)

    assert proj[1] == pytest.approx(10.0)  # (5/10) * 20
    assert proj[2] == pytest.approx(4.0 / 8.0 * 5.0)
    assert orfas == 0


def test_nascimentos_sao_a_media_das_duas_bandas_de_entrada():
    proj, _ = project(np.array([10.0, 0.0]), np.array([20.0, 0.0]))
    assert proj[0] == pytest.approx(15.0)


def test_coorte_orfa_nao_inventa_sobrevivencia_e_e_contada():
    # Banda 0 povoada em T mas vazia em T-3m: a taxa é 0/0, indefinida. A célula
    # sai como nan ("sem resposta"). O valor 0 seria uma previsão de extinção,
    # e no dataset o alvo tem gente de verdade em 73.8% desses casos.
    proj, orfas = project(np.array([0.0, 4.0]), np.array([7.0, 4.0]))
    assert np.isnan(proj[1])
    assert orfas == 1


def test_coorte_orfa_nao_entra_no_erro_como_previsao_de_extincao():
    # Guarda de regressão do viés: se a órfã virasse 0, abre(4, 0) entraria como
    # erro e puniria o método coorte justamente onde ele não opinou. O caminho
    # nan->excluído precisa continuar valendo ponta a ponta.
    proj, _ = project(np.array([0.0, 4.0]), np.array([7.0, 4.0]))
    assert np.isnan(abre(4.0, proj[1]))


def test_abre_propaga_nan_nas_duas_ordens():
    # min(x, nan) em Python devolve x, então sem a guarda explícita o resultado
    # dependeria da ordem dos argumentos e o nan sumiria silenciosamente.
    assert np.isnan(abre(float("nan"), 3.0))
    assert np.isnan(abre(3.0, float("nan")))


def test_banda_vazia_dos_dois_lados_preve_zero_e_nao_e_orfa():
    # 0/0 com p_last também zero é afirmação substantiva ("ninguém envelhece"),
    # não lacuna: no dataset o alvo é de fato vazio em 98.9% dessas células.
    proj, orfas = project(np.array([0.0, 0.0]), np.array([0.0, 0.0]))
    assert proj[1] == 0.0
    assert orfas == 0


def test_projecao_nunca_e_negativa_onde_definida():
    # nan é permitido só na coorte órfã; onde há resposta, ela é não-negativa.
    # O teste confere as duas coisas para não virar um "assert que nan passa".
    rng = np.random.default_rng(0)
    for _ in range(50):
        p_base = rng.integers(0, 30, size=8).astype(float)
        p_last = rng.integers(0, 30, size=8).astype(float)
        proj, orfas = project(p_base, p_last)
        assert (proj[np.isfinite(proj)] >= 0).all()
        esperado_nan = {b + 1 for b in range(len(p_last) - 1) if p_base[b] == 0 and p_last[b] > 0}
        assert set(np.flatnonzero(np.isnan(proj))) == esperado_nan
        assert len(esperado_nan) == orfas


def test_populacao_imortal_e_projetada_sem_erro():
    """Regressão do bug que inflou a acurácia.

    Se a pirâmide for o acumulado histórico em vez da população ativa, ninguém
    morre: cada banda avança um degrau por trimestre e a sobrevivência é 1 por
    construção. A projeção acerta na mosca sem ter previsto nada. Foi assim que
    o ABRE saiu 0.006 contra os 0.4 do artigo. O teste fixa a aritmética que
    produz esse acerto, para que ele só possa aparecer se o filtro `active`
    tiver caído de novo.
    """
    p_base = np.array([10.0, 9.0, 8.0, 7.0])
    p_last = np.array([12.0, 10.0, 9.0, 8.0])  # p_last[b+1] == p_base[b]
    proj, _ = project(p_base, p_last)
    # SR = 1 em todas as bandas -> a projeção é o deslocamento puro de p_last.
    assert proj[1:] == pytest.approx(p_last[:-1])


# --------------------------------------------------------------------------- #
# tabelas
# --------------------------------------------------------------------------- #


def _df(linhas):
    """Frame do estágio a partir de (escopo, tipo, categoria, banda, medido, coorte,
    baseline, abre_coorte, abre_baseline).

    As colunas de MRE, MER e MAE saem das próprias funções: o teste declara só o
    ABRE, que é o que ele exercita, e as outras acompanham o dado em vez de virar
    número escrito à mão em dois lugares.
    """
    cols = [
        "scope_id",
        "type",
        "category",
        "band",
        "actual",
        "cohort_pred",
        "baseline_pred",
        "abre_cohort",
        "abre_baseline",
    ]
    df = pd.DataFrame(linhas, columns=cols)
    for nome, f in (("mre", mre), ("mer", mer), ("ae", ae)):
        for lado, coluna in (("cohort", "cohort_pred"), ("baseline", "baseline_pred")):
            df[f"{nome}_{lado}"] = [f(a, p) for a, p in zip(df["actual"], df[coluna], strict=True)]
    return df


def test_tabelas_usam_so_pares_completos():
    # A segunda linha tem baseline sem denominador: entra no parquet mas não
    # pode entrar na mediana, senão as Tabelas 3 e 4 sairiam de amostras
    # diferentes (o Wilcoxon é pareado e já usaria só a interseção).
    df = _df(
        [
            (1, "A", "all", 0, 4.0, 6.0, 5.0, 0.5, 0.25),
            (1, "A", "all", 1, 4.0, 6.0, 0.0, 0.5, float("nan")),
            (2, "A", "all", 0, 4.0, 8.0, 6.0, 1.0, 0.5),
        ]
    )
    t = tables(df)
    linha = t["abre"].set_index("type").loc["A"]
    assert linha["pairs"] == 2
    assert linha["all_cohort"] == pytest.approx(0.75)  # mediana de 0.5 e 1.0
    assert linha["all_baseline"] == pytest.approx(0.375)  # mediana de 0.25 e 0.5


def test_all_types_agrega_todos_os_tipos():
    df = _df(
        [
            (1, "A", "all", 0, 4.0, 6.0, 5.0, 0.5, 0.25),
            (2, "B", "all", 0, 4.0, 8.0, 6.0, 1.0, 0.5),
        ]
    )
    t = tables(df).__getitem__("abre").set_index("type")
    assert t.loc["All types", "projects"] == 2
    assert t.loc["All types", "all_cohort"] == pytest.approx(0.75)


def test_wilcoxon_e_nan_quando_os_metodos_empatam():
    # Sem diferença não há o que ranquear. O teste não pode devolver p=0.
    df = _df(
        [
            (1, "A", "all", 0, 4.0, 6.0, 6.0, 0.5, 0.5),
            (2, "A", "all", 0, 4.0, 8.0, 8.0, 1.0, 1.0),
        ]
    )
    assert np.isnan(tables(df)["wilcoxon"].set_index("type").loc["A", "all"])


# --------------------------------------------------------------------------- #
# checkpoints IEICE16 Tabelas 3 e 4
# --------------------------------------------------------------------------- #


def _abre_publicado():
    from pyramid.config import checkpoints

    return checkpoints()["projection_abre"]


def _tables():
    """Tabelas do estágio, ou skip explicando que falta rodar o estágio.

    Mesma regra do `_table()` de test_attractiveness: skip só quando o artefato
    não existe (clone limpo, antes do pipeline). Se ele existe e a leitura
    quebra, é bug e tem que falhar alto.
    """
    from pyramid.projection import path

    if not path().exists():
        pytest.skip(f"falta {path()}: rode `pyramid projection`")
    return tables()


@pytest.mark.checkpoint
def test_checkpoint_abre_na_ordem_de_grandeza_do_artigo():
    """O ABRE mediano do artigo vive em [0.18, 1.0]; o nosso tem que viver lá.

    Este é o teste que teria pegado o bug da pirâmide acumulada. Com a população
    imortal o ABRE saiu 0.006, duas ordens de grandeza abaixo de qualquer célula
    publicada, e nada no repositório reclamou. A faixa é frouxa de
    propósito: o dataset não é o do artigo (34 projetos contra 36) e as coortes
    não são as mesmas, então a comparação célula a célula não fecha (ver
    docs/replicacao/discrepancias.md seção 12). O que não pode acontecer é o erro sumir.
    """
    obs = _tables()["abre"].set_index("type")
    pub = _abre_publicado()["table"]

    minimo = min(v for cel in pub.values() for par in cel.values() for v in par if v > 0)
    maximo = max(v for cel in pub.values() for par in cel.values() for v in par)

    for cat in ("non_coding", "moved", "coding", "all"):
        v = obs.loc["All types", f"{cat}_cohort"]
        assert minimo / 3 <= v <= maximo * 1.5, (
            f"ABRE cohort de {cat} = {v:.4f} fora da ordem de grandeza publicada "
            f"[{minimo}, {maximo}]. Suspeite do filtro de população ativa"
        )


@pytest.mark.checkpoint
def test_checkpoint_coorte_bate_o_baseline_no_agregado():
    """A tese da seção 4: projetar por coorte erra menos que repetir a última medida.

    IEICE16 Tabela 4 marca All types/all como significativo (p<0.00001). É a
    única conclusão do artigo que não depende do dataset específico, então é a
    que exigimos aqui. As células por tipo divergem e estão documentadas.
    """
    t = _tables()
    linha = t["abre"].set_index("type").loc["All types"]
    assert linha["all_cohort"] < linha["all_baseline"]
    assert t["wilcoxon"].set_index("type").loc["All types", "all"] < 0.05


@pytest.mark.checkpoint
def test_checkpoint_projetos_elegiveis_perto_dos_36():
    """ "We used 36 projects that have more than 100 contributors" (IEICE16 seção 4).

    Temos 34: o corte é sobre contribuidores ativos no snapshot base, e o nosso
    dump tem dois projetos na fronteira dos 100. O teste trava a contagem para
    que ela não deslize em silêncio quando o filtro mudar.
    """
    n = _tables()["abre"].set_index("type").loc["All types", "projects"]
    assert n == 34, f"{n} projetos elegíveis; era 34 (artigo: 36)"


# ---------------------------------------------------------------------------
# As outras métricas de erro do IEICE16 p.1311 (seção 42)
# ---------------------------------------------------------------------------
def test_mre_divide_pelo_medido_e_mer_pelo_predito():
    """A diferença entre as duas é o denominador, e ela aparece quando erram.

    Medido 4, predito 6: o MRE divide por 4 e dá 0,5; o MER divide por 6 e dá
    0,333. O ABRE pega o menor denominador, então coincide com o MRE aqui.
    """
    assert mre(4, 6) == pytest.approx(0.5)
    assert mer(4, 6) == pytest.approx(2 / 6)
    assert abre(4, 6) == pytest.approx(0.5)


def test_mre_e_mer_trocam_de_lado_quando_a_previsao_e_baixa():
    """Prevendo 3 contra 4 medidos, o MER é que fica maior. O ABRE segue o maior."""
    assert mre(4, 3) == pytest.approx(0.25)
    assert mer(4, 3) == pytest.approx(1 / 3)
    assert abre(4, 3) == pytest.approx(1 / 3)


def test_metricas_relativas_nao_tem_denominador_no_zero():
    """Zero no denominador não vira acerto nem erro máximo: vira `nan`."""
    assert np.isnan(mre(0, 5))
    assert np.isnan(mer(5, 0))
    assert mre(5, 0) == pytest.approx(1.0)
    assert mer(0, 5) == pytest.approx(1.0)


def test_metricas_propagam_nan_da_coorte_orfa():
    for f in (mre, mer, ae):
        assert np.isnan(f(float("nan"), 3))
        assert np.isnan(f(3, float("nan")))


def test_mae_fica_em_contribuidores_e_nao_em_proporcao():
    """O erro absoluto é contagem: prever 6 onde havia 4 erra por 2 pessoas."""
    assert ae(4, 6) == pytest.approx(2.0)
    assert ae(6, 4) == pytest.approx(2.0)
    assert ae(4, 4) == pytest.approx(0.0)


def test_metricas_relativas_recusam_contagem_negativa():
    for f in (mre, mer):
        with pytest.raises(ValueError, match="negativa"):
            f(-1, 3)


def test_tabela_de_erros_tem_as_quatro_metricas_por_tipo_e_categoria():
    df = _df(
        [
            (1, "A", "all", 0, 4.0, 6.0, 5.0, 0.5, 0.25),
            (2, "A", "all", 0, 4.0, 8.0, 6.0, 1.0, 0.5),
        ]
    )
    erros = tables(df)["erros"]
    assert set(erros["metric"]) == {"ABRE", "MRE", "MER", "MAE"}
    # Relativa por mediana (é o que a Tabela 3 publica), absoluta por média.
    agg = dict(zip(erros["metric"], erros["aggregation"], strict=True))
    assert agg == {"ABRE": "mediana", "MRE": "mediana", "MER": "mediana", "MAE": "media"}
