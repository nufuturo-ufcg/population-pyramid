import pandas as pd
import pytest

from pyramid import attractiveness as attr
from pyramid.config import checkpoints

# --- unidade: retenção por escopo (ambiguidade 4) -----------------------------


def _pairs(rows):
    return pd.DataFrame(rows, columns=["scope_id", "contributor_id", "year"])


def _keys(df):
    return {tuple(r) for r in df[["scope_id", "contributor_id", "year"]].to_numpy()}


def test_retained_project_nao_conta_quem_migrou():
    """Dev sai do projeto 1 e vai para o 2 em Y+1: o projeto 1 NÃO reteve.

    É a diferença que separa `stickiness_scope: project` de `dataset`. Um
    projeto não fica sticky porque o dev que ele perdeu foi commitar noutro
    lugar. Com escopo `dataset` ficaria.
    """
    pairs = _pairs([(1, "a", 2011), (2, "a", 2012)])

    assert _keys(attr._retained(pairs, "project")) == set()
    assert _keys(attr._retained(pairs, "dataset")) == {(1, "a", 2011)}


def test_retained_project_conta_quem_ficou():
    pairs = _pairs([(1, "a", 2011), (1, "a", 2012), (1, "b", 2011)])
    assert _keys(attr._retained(pairs, "project")) == {(1, "a", 2011)}


def test_retained_ignora_volta_com_buraco():
    """Sumiu em 2012 e voltou em 2013 cai fora da retenção de 2011: é ano SEGUINTE."""
    pairs = _pairs([(1, "a", 2011), (1, "a", 2013)])
    assert _keys(attr._retained(pairs, "project")) == set()


def test_retained_rejeita_escopo_desconhecido():
    with pytest.raises(ValueError, match="stickiness_scope"):
        attr._retained(_pairs([(1, "a", 2011)]), "global")


# --- GATE: exemplo trabalhado da Fig.1 do MSR'14 ------------------------------


def test_msr14_fig1_exemplo_dos_autores():
    """Os autores publicaram os números do próprio exemplo; a replicação os devolve.

    MSR'14 seção 2, Fig. 1, período 2011: cinco desenvolvedores (A-E) e dois
    projetos. "There are three new developers (B, C and D), and two of them
    contribute to project 1 (B and C), while one developer (D) contributes to
    project 2. In this case, Magnet value of project 1 is 2/3 and project 2 is
    1/3." Para o sticky: projeto 1 tem A, B, C em 2011 e A, B seguem em 2012
    (2/3); no projeto 2 só D contribui em 2011 e segue em 2012. "Sticky value
    of project 2 is not 2/1, but rather 1/1", porque E entra em 2012 e não
    conta no denominador.

    O exemplo trava a aritmética e a armadilha do sticky, mas sozinho ele NÃO
    separa novato global de novato por projeto: não há ninguém que seja
    veterano do dataset e estreante em um projeto. Esse eixo é o do teste
    seguinte. Ver seção 15 de docs/replicacao/discrepancias.md.
    """
    pairs = _pairs(
        [
            (1, "A", 2010),  # A não é novato em 2011
            (1, "A", 2011),
            (1, "A", 2012),
            (1, "B", 2011),
            (1, "B", 2012),
            (1, "C", 2011),  # estreia e some
            (2, "D", 2011),
            (2, "D", 2012),
            (2, "E", 2012),  # entra só depois: fora do sticky
        ]
    )
    got = attr.annual(pairs).set_index(["scope_id", "year"])

    assert got.loc[(1, 2011), "newcomers_total"] == 3  # B, C e D
    assert got.loc[(1, 2011), "magnetism"] == pytest.approx(2 / 3)
    assert got.loc[(2, 2011), "magnetism"] == pytest.approx(1 / 3)
    assert got.loc[(1, 2011), "stickiness"] == pytest.approx(2 / 3)
    assert got.loc[(2, 2011), "stickiness"] == pytest.approx(1.0)


def test_novato_e_do_dataset_nao_do_projeto():
    """Veterano que troca de projeto continua veterano, também no projeto novo.

    O artigo diz "the proportion of contributors who made their first
    contribution in the time period under study who contribute to a given
    project": o "first contribution" qualifica a pessoa no dataset, e o
    projeto só filtra quem conta. Aqui V contribui desde 2010 no projeto 1 e
    aparece no projeto 2 em 2011; N estreia no projeto 1 em 2011. O único
    novato do ano é N, então o projeto 2 tem magnetismo ZERO apesar de ter
    ganhado um contribuidor. Ele não atraiu ninguém para o ecossistema.

    Sob a leitura "novato = primeira aparição NESTE projeto", V contaria e o
    projeto 2 daria 1/2. É a variante P da seção 15: rodada nos 12 projetos da
    Tabela 2 do MSR'14, ela não corrige nenhuma célula e quebra três.
    """
    pairs = _pairs(
        [
            (1, "V", 2010),
            (1, "V", 2011),
            (2, "V", 2011),  # veterano estreando no projeto 2
            (1, "N", 2011),  # o único novato do dataset em 2011
        ]
    )
    got = attr.annual(pairs).set_index(["scope_id", "year"])

    assert got.loc[(1, 2011), "newcomers_total"] == 1
    assert got.loc[(1, 2011), "magnetism"] == pytest.approx(1.0)
    assert got.loc[(2, 2011), "magnetism"] == pytest.approx(0.0)


# --- GATE: Fig.2 do ESEM14, snapshot dez/2011 ---------------------------------


def _table(year):
    """Corte do ano, ou skip explicando que falta rodar o estágio.

    Skip só quando o artefato não existe. Se ele existe e o ano sumiu, é bug.
    Aí `table()` levanta ValueError, que não vira skip.
    """
    if not attr.path().exists():
        pytest.skip(f"falta {attr.path()}: rode `pyramid attractiveness`")
    return attr.table(year)


@pytest.mark.checkpoint
def test_checkpoint_quadrantes_dez_2011():
    """Os 4 projetos nomeados na Fig.2 têm de cair nos 4 quadrantes do paper.

    Um por quadrante, então não há como acertar por sorte: qualquer troca de
    corte (mediana), de escopo de retenção ou do filtro de devs ativos derruba
    pelo menos um. Se este teste quebrar, a mudança precisa ir para
    docs/replicacao/discrepancias.md antes de ser aceita.
    """
    esperado = checkpoints()["attractiveness"]["2011-12-31"]
    df = _table(2011)
    got = df.set_index("scope_id")["quadrant"].to_dict()
    faltando = [s for s in esperado if s not in got]
    assert not faltando, f"projetos do checkpoint fora do output: {faltando}"

    errados = {s: (got[s], q) for s, q in esperado.items() if got[s] != q}
    assert not errados, f"quadrante != paper (got, esperado): {errados}"


@pytest.mark.checkpoint
def test_checkpoint_2011_usa_os_quatro_quadrantes():
    """Guarda de sanidade do gate acima: os 4 rótulos existem mesmo em 2011.

    Sem isto, um bug que colapsasse tudo num quadrante só passaria despercebido
    caso o checkpoint fosse afrouxado no futuro.
    """
    df = _table(2011)
    assert set(df[df["eligible"]]["quadrant"]) == set(attr.QUADRANTS.values())


@pytest.mark.checkpoint
def test_checkpoint_jekyll_2011_diverge():
    """jekyll é o 5º projeto rotulado para 2011, e a replicação NÃO o reproduz.

    O ESEM14 chama jekyll de "also a terminal project in 2011" (p.5, discussão
    da Fig.3). Aqui ele sai `floating` em 2011 e `terminal` em 2010. A causa
    provável é a mesma da seção 3.1 (novato demais, e o magnetismo é contagem de
    novato), então este teste trava o valor **medido**, sem travar o do artigo: o
    ponto é detectar deriva enquanto a divergência estiver aberta.

    Se ele quebrar porque jekyll virou `terminal` em 2011, não conserte o
    teste: o checkpoint da Fig.2 passou a bater 5/5 e a seção 13 fecha. `pyramid
    validate` avisa a mesma coisa marcando a divergência como OBSOLETA.
    """
    jekyll = 79166
    declarado = checkpoints()["attractiveness"]["transitions"][jekyll]["classified"]
    assert declarado[2011] == "terminal", "o rótulo do artigo mudou no yaml"

    df = _table(2011).set_index("scope_id")
    assert jekyll in df.index, "jekyll sumiu do output"
    assert df.loc[jekyll, "quadrant"] == "floating", (
        "jekyll saiu de `floating` em 2011. Ver docs/replicacao/discrepancias.md seção 13 "
        "antes de mexer neste teste"
    )
    assert _table(2010).set_index("scope_id").loc[jekyll, "quadrant"] == "terminal"


# --- bordas do dataset --------------------------------------------------------


def test_ultimo_ano_nao_e_classificado():
    """2013 não tem Y+1 no dataset: stickiness é NaN e ninguém é elegível."""
    df = _table(2013)
    assert not df["eligible"].any()
    assert df["stickiness"].isna().all()


def test_year_of_aceita_as_tres_formas():
    assert attr.year_of(2011) == 2011
    assert attr.year_of("2011") == 2011
    assert attr.year_of("2011-12-31") == 2011
    assert attr.year_of(pd.Timestamp("2011-12-31")) == 2011


# ---------------------------------------------------------------------------
# Matriz de transição de quadrante (MSR14 Fig.3, seção 44)
# ---------------------------------------------------------------------------
def _historia(linhas):
    """(projeto, ano, quadrante, elegível, devs) -> frame do estágio."""
    return pd.DataFrame(
        linhas, columns=["scope_id", "year", "quadrant", "eligible", "devs"]
    ).astype({"year": int, "devs": int})


def test_transicao_conta_o_par_de_anos_consecutivos():
    df = _historia(
        [
            (1, 2004, "attractive", True, 20),
            (1, 2005, "terminal", True, 15),
            (1, 2006, "terminal", True, 12),
        ]
    )
    m = attr.transitions(range(2004, 2007), df)
    assert m.loc["attractive", "terminal"] == 1
    assert m.loc["terminal", "terminal"] == 1
    assert m.to_numpy().sum() == 2


def test_projeto_pequeno_demais_vira_estado_asterisco():
    """O `*` do artigo é "existe e não passa no filtro de dez desenvolvedores"."""
    df = _historia(
        [
            (1, 2004, None, False, 4),
            (1, 2005, "terminal", True, 11),
        ]
    )
    m = attr.transitions(range(2004, 2006), df)
    assert m.loc["*", "terminal"] == 1


def test_ano_sem_projeto_nao_gera_transicao():
    """O "-" da Tabela 2 não é estado: projeto que ainda não existia não tem seta."""
    df = _historia(
        [
            (1, 2004, None, False, 0),
            (1, 2005, "terminal", True, 11),
            (1, 2006, "terminal", True, 11),
        ]
    )
    m = attr.transitions(range(2004, 2007), df)
    assert m.to_numpy().sum() == 1
    assert m.loc["terminal", "terminal"] == 1


def test_transicao_respeita_a_janela_pedida():
    """A janela do artigo é 2004-2011; ano fora dela não entra nem como origem."""
    df = _historia(
        [
            (1, 2011, "attractive", True, 20),
            (1, 2012, "terminal", True, 15),
        ]
    )
    assert attr.transitions(range(2004, 2012), df).to_numpy().sum() == 0
    assert attr.transitions(range(2011, 2013), df).loc["attractive", "terminal"] == 1
