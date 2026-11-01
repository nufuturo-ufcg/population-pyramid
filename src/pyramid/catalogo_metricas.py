"""Catálogo das métricas da ferramenta: o que são, o que entra, o que sai e o cálculo.

Cada métrica tem um bloco de comentário (`# Métrica: nome`) com quatro partes: O que é,
Referência, Entrada e Resultado esperado. O código que calcula vem logo abaixo, na ordem do
Plano de Experimento. O arquivo roda sozinho, só com pandas, numpy e scipy. Não importa nada
do pacote `pyramid`.

Este código repete o do motor (`src/pyramid/vitalidade.py`, `projection.py` e
`attractiveness.py`). Um teste (`tests/test_catalogo_metricas.py`) roda o catálogo e o motor
nos mesmos eventos e exige o mesmo resultado, então uma mudança no motor quebra o teste até
este arquivo ser atualizado. `compacta`, a redução dos eventos para coletas de centenas de GB,
fica de fora: ela não muda nenhum resultado, e as funções daqui aceitam os eventos inteiros.

`CATALOGO` leva cada métrica à função que a calcula e à coluna do resultado onde ela aparece.
`REGISTRO` leva cada linha do registro `METRICAS` de `scripts/vitalidade.py` às métricas dela.

Entrada comum a todas: eventos canônicos, um DataFrame com três colunas.

    contributor_id  identificador estável da pessoa
    event_type      commits, pull_requests, commit_comments, issue_comments,
                    pull_request_comments, issue_events ou issues
    timestamp       data e hora do evento (datetime64)

Código é `commits` e `pull_requests` (`TIPOS_CODING`). Os outros cinco tipos são discussão.
O contrato completo está em `docs/ferramenta/FONTES.md`.

Do evento à métrica:

    fim = eventos["timestamp"].max()
    pa = pessoa_ano(eventos, fim, com_moved_to_discussion=False)
    dur = duracoes(eventos, fim)
    anual = tabela_anual(pa, fim)

`fim` é o último instante coberto pela coleta. O estudo para em `data_de_corte` (2025-12-31)
e os eventos de 2026 só decidem quem saiu e quem pausou.

Convenções do estudo, valem para todas as métricas:

    saída    12 meses sem contribuir (Avelino et al., ESEM 2019). A replicação do IEICE16 usa 3
    faixas   0-1, 1-2, 2-3, 3-5, 5-8 e 8+ anos na linguagem. A idade no ano Y é Y menos o ano da
             primeira contribuição, então quem entrou em Y está na faixa 0-1
    censura  a saída de Y só se decide 12 meses depois de 31/12/Y. Ano que a coleta não cobre
             até lá fica com saída vazia (NaN). Anualizar um ano aberto é proibido
    pessoa   a pirâmide conta os residentes (população `mais_de_uma_ocasiao`): quem tem mais de
             uma contribuição em ocasiões diferentes. O filtro lê `origem/pessoas.parquet` e mora
             em `scripts/vitalidade.py` (`filtra_populacao`). As funções daqui recebem os
             eventos que sobraram depois dele

As definições com todas as escolhas registradas estão em `docs/linguagem/vitalidade.md`.
"""

import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

DAYS_PER_MONTH = 365.25 / 12  # 30,4375
GAP_DIAS = 12 * DAYS_PER_MONTH
DIAS_POR_ANO = 365.25
TIPOS_CODING = {"commits", "pull_requests"}

FAIXAS = ["0-1", "1-2", "2-3", "3-5", "5-8", "8+"]
_CORTES = [0, 1, 2, 3, 5, 8, math.inf]
FAIXAS_NOVATO = ["0-1"]
FAIXAS_CURTAS = ["0-1", "1-2", "2-3", "3-5"]  # a padronização curta, até 5 anos
FAIXAS_VETERANO = ["5-8", "8+"]

# As quatro categorias da pirâmide no fim do ano. Esquerda: só discussão e quem codou e passou a
# discutir. Direita: quem discutiu primeiro e passou a codar (`moved`) e o resto de quem codou.
LADOS = ["non_coding", "moved_to_discussion", "moved", "coding"]
BAND_DIAS = 90  # trimestre de 90 dias, como o `band_days` da replicação do IEICE16

NOVATO_DIAS = round(3 * DAYS_PER_MONTH)  # 91, a banda de 3 meses do IEICE16
INATIVIDADE_CCR_DIAS = 3 * DAYS_PER_MONTH  # "did not give any contribution for more than 3 months"

BANDAS = 9
METODOS = ["ingenuo", "coorte", "pessimista", "conservador", "otimista"]
METODOS_COM_ERRO = ["ingenuo", "coorte", "conservador"]

# Acima disso a curva de Kaplan-Meier sai com um ponto por dia: milhões de pessoas dariam um
# ponto por pessoa.
MAX_PONTOS_KM = 2_000_000

QUADRANTES = {
    (True, True): "attractive",
    (True, False): "floating",
    (False, True): "stagnant",
    (False, False): "terminal",
}

CATALOGO: dict[str, tuple[Callable[..., Any], str | None]] = {}
REGISTRO: dict[str, tuple[str, ...]] = {}


# ================================================================================================
# Base: períodos de atividade e uma linha por pessoa e ano
# ================================================================================================

# Base, sem métrica própria. `pessoa_ano` é a tabela de onde saem os dados registrados por
# observação (ativos, novatos, saídas, pausas, voltas, moved) e a pirâmide. `periodos` parte a
# vida de cada pessoa em períodos de atividade, separados por mais de 12 meses de silêncio.


def faixa_de(anos: pd.Series) -> pd.Series:
    """Faixa de tempo na linguagem, fechada embaixo: 1 ano cai em 1-2."""
    return pd.cut(anos, bins=_CORTES, right=False, labels=FAIXAS)


def ano_fechado(ano: int, fim: pd.Timestamp) -> bool:
    """A coleta cobre 12 meses depois do fim de `ano`, então toda saída dele se decide."""
    return fim > pd.Timestamp(f"{ano + 1}-01-01") + pd.Timedelta(days=GAP_DIAS)


def ano_completo(ano: int, fim: pd.Timestamp) -> bool:
    """O ano de calendário acabou antes do fim da coleta. Só o ano da coleta fica de fora."""
    return ano < fim.year


def provisorio(ano: int, fim: pd.Timestamp) -> bool:
    """Ano completo cuja saída ainda não passou por 12 meses de coleta: vale como estimativa.

    Quem teve a última contribuição nele conta como saída, com menos de 12 meses de silêncio
    confirmados. Quem voltar depois do fim da coleta ainda aparece como saída.
    """
    return ano_completo(ano, fim) and not ano_fechado(ano, fim)


def periodos(eventos: pd.DataFrame) -> pd.DataFrame:
    """Um período de atividade por linha, com o primeiro evento de código e de discussão da pessoa.

    Mesma saída de `classify.profile(eventos, TIPOS_CODING, GAP_DIAS)`, numa
    passada vetorizada em vez de um laço Python por pessoa, com uma diferença: eventos do
    mesmo ano de calendário ficam no mesmo período, mesmo com mais de 365,25 dias entre eles
    (só acontece em ano bissexto). Um teste confere as duas nos demais casos.
    """
    ev = eventos.sort_values(["contributor_id", "timestamp"], kind="stable")
    ts = ev["timestamp"]
    pessoa = ev["contributor_id"]
    codou = ev["event_type"].isin(TIPOS_CODING)

    primeiros = (
        ev.assign(_c=ts.where(codou), _d=ts.where(~codou))
        .groupby("contributor_id", sort=False)
        .agg(
            init_c=("_c", "min"),
            init_d=("_d", "min"),
            last_c=("_c", "max"),
            last_d=("_d", "max"),
        )
    )

    pessoa_nova = pessoa != pessoa.shift()
    anterior = ts.shift()
    # Dois eventos do mesmo ano de calendário nunca são dois períodos: num ano bissexto, 1/jan e
    # 31/dez distam mais de 365,25 dias, e sem esta guarda a pessoa teria duas saídas no mesmo
    # ano, que a tabela anual não sabe contar. Em 4,2 milhões de pessoas do Python, uma só caiu aí.
    silencio = ((ts - anterior) / np.timedelta64(1, "D") > GAP_DIAS) & (
        ts.dt.year != anterior.dt.year
    )
    periodo = (pessoa_nova | silencio).cumsum()
    spans = ev.groupby(periodo, sort=False).agg(
        contributor_id=("contributor_id", "first"),
        span_start=("timestamp", "min"),
        span_end=("timestamp", "max"),
    )
    spans["span_idx"] = spans.groupby("contributor_id", sort=False).cumcount()
    return spans.reset_index(drop=True).merge(primeiros, on="contributor_id", how="left")


def pessoa_ano(
    eventos: pd.DataFrame, fim: pd.Timestamp | None = None, com_moved_to_discussion: bool = True
) -> pd.DataFrame:
    """Uma linha por (pessoa, ano em que contribuiu). Base de toda métrica anual.

    `fim` é o último instante coberto pela coleta. Padrão: o evento mais recente.
    Sem `com_moved_to_discussion` a categoria `moved_to_discussion` não existe: quem já codou e
    neste ano só discutiu fica onde a história dele o põe, em `moved` ou `coding`.
    """
    if fim is None:
        fim = eventos["timestamp"].max()
    ev = eventos[["contributor_id", "event_type", "timestamp"]]

    spans = periodos(ev)
    marcos = spans.groupby("contributor_id").agg(
        init_c=("init_c", "first"),
        init_d=("init_d", "first"),
        last_c=("last_c", "first"),
        last_d=("last_d", "first"),
        primeiro=("span_start", "min"),
    )

    pa = ev.assign(ano=ev["timestamp"].dt.year)[["contributor_id", "ano"]].drop_duplicates()
    pa = pa.join(marcos, on="contributor_id")

    # Quem fez commit ou PR em cada ano. A compactação guarda o último evento de código de cada
    # trimestre, então saber se houve código no ano é exato.
    com_codigo = ev[ev["event_type"].isin(TIPOS_CODING)]
    anos_com_codigo = com_codigo.assign(ano=com_codigo["timestamp"].dt.year)[
        ["contributor_id", "ano"]
    ].drop_duplicates()
    anos_com_codigo["codou_no_ano"] = True
    pa = pa.merge(anos_com_codigo, on=["contributor_id", "ano"], how="left")
    codou_no_ano = pa.pop("codou_no_ano").fillna(False).astype(bool)

    fim_ano = pd.to_datetime((pa["ano"] + 1).astype(str) + "-01-01")
    # Idade em anos de calendário: cada faixa de 1 ano é exatamente uma coorte
    # de entrada, que é o que a projeção por coorte precisa para envelhecer 1 por ano.
    pa["idade_anos"] = pa["ano"] - pa["primeiro"].dt.year
    # Idade em dias no fim do ano, para a pirâmide em faixas de trimestre (como no artigo).
    pa["idade_dias"] = (fim_ano.clip(upper=fim) - pa["primeiro"]).dt.days
    pa["faixa"] = faixa_de(pa["idade_anos"])
    pa["novato"] = pa["primeiro"].dt.year == pa["ano"]

    # Mesma regra de `snapshots.pyramid_at`, avaliada no fim do ano.
    codou = pa["init_c"].notna() & (pa["init_c"] < fim_ano)
    comecou_na_discussao = codou & pa["init_d"].notna() & (pa["init_d"] < pa["init_c"])
    # O lado de volta do `moved`: quem já codou e neste ano só discutiu. Quem fez algum commit ou PR
    # no ano fica do lado do código, mesmo que o último evento do ano seja um comentário.
    foi_para_discussao = codou & ~codou_no_ano & com_moved_to_discussion
    pa["categoria"] = np.select(
        [~codou, foi_para_discussao, comecou_na_discussao],
        ["non_coding", "moved_to_discussion", "moved"],
        default="coding",
    )
    # Fluxo: o ano em que quem começou pela discussão fez o primeiro commit/PR.
    pa["moved_no_ano"] = comecou_na_discussao & (pa["init_c"].dt.year == pa["ano"])
    # O caminho de volta: a pessoa para de codar e depois só discute. O ano é o do último
    # commit ou PR, e só existe olhando o futuro (quem codar de novo deixa de contar).
    deixou = pa["last_c"].notna() & pa["last_d"].notna() & (pa["last_d"] > pa["last_c"])
    pa["deixou_codigo_no_ano"] = deixou & (pa["last_c"].dt.year == pa["ano"])

    # Todo período que não é o último já termina com mais de 12 meses de silêncio
    # (é o que o separou do seguinte), então basta medir a distância até `fim`.
    # Saída é o fim do último período, o da vida inteira: quem para e depois volta
    # não saiu, só fez uma pausa.
    # O último ano completo entra com a regra provisória: o último evento nele já conta como saída.
    parou = ((fim - spans["span_end"]) > pd.Timedelta(days=GAP_DIAS)) | (
        spans["span_end"].dt.year == fim.year - 1
    )
    ultimo = spans["span_idx"] == spans.groupby("contributor_id")["span_idx"].transform("max")
    da_vida = parou & ultimo
    pausa = parou & ~ultimo
    saidas = spans.loc[da_vida, ["contributor_id"]].assign(
        ano=spans.loc[da_vida, "span_end"].dt.year, saida=True
    )
    pausas = spans.loc[pausa, ["contributor_id"]].assign(
        ano=spans.loc[pausa, "span_end"].dt.year, pausa=True
    )
    voltou = spans["span_idx"] > 0
    voltas = spans.loc[voltou, ["contributor_id"]].assign(
        ano=spans.loc[voltou, "span_start"].dt.year, volta=True
    )
    pa = pa.merge(saidas, on=["contributor_id", "ano"], how="left")
    pa = pa.merge(pausas, on=["contributor_id", "ano"], how="left")
    pa = pa.merge(voltas, on=["contributor_id", "ano"], how="left")
    pa["saida"] = pa["saida"].eq(True)
    pa["pausa"] = pa["pausa"].eq(True)
    pa["volta"] = pa["volta"].eq(True)

    # Dois períodos separados por 12 meses não terminam (nem começam) no mesmo ano.
    if pa.duplicated(["contributor_id", "ano"]).any():
        raise ValueError("pessoa_ano: (pessoa, ano) repetido; mais de uma saída ou volta no ano.")
    return pa.drop(columns=["init_c", "init_d", "last_c", "last_d"]).reset_index(drop=True)


# ================================================================================================
# Tamanho (RQ1.1): dados registrados por observação e crescimento natural
# ================================================================================================

# Métrica: ativos
#   O que é:
#     Pessoas que contribuíram naquele ano. Um evento no ano basta.
#   Referência:
#     Da pesquisa (Plano de Experimento).
#   Entrada:
#     `pa` (de `pessoa_ano`) e `fim`. `pa` traz contributor_id, ano, primeiro, idade_anos,
#     idade_dias, faixa, novato, categoria, moved_no_ano, deixou_codigo_no_ano, saida,
#     pausa e volta.
#   Resultado esperado:
#     Uma linha por ano na tabela de `tabela_anual`, coluna `ativos`. Inteiro, um por
#     pessoa que apareceu no ano.

# Métrica: novatos
#   O que é:
#     Pessoas cuja primeira contribuição da vida na linguagem caiu naquele ano. Entram na
#     faixa 0-1.
#   Referência:
#     Foucault et al., ESEC/FSE 2015. https://doi.org/10.1145/2786805.2786870
#   Entrada:
#     `pa` (de `pessoa_ano`) e `fim`. `pa` traz contributor_id, ano, primeiro, idade_anos,
#     idade_dias, faixa, novato, categoria, moved_no_ano, deixou_codigo_no_ano, saida,
#     pausa e volta.
#   Resultado esperado:
#     Uma linha por ano na tabela de `tabela_anual`, coluna `novatos`. Soma sobre o
#     primeiro evento de cada pessoa.

# Métrica: saidas
#   O que é:
#     Pessoas cuja última contribuição da vida caiu naquele ano e que ficaram mais de 12
#     meses sem contribuir depois dela. Quem para e volta tem uma pausa, que fica fora das
#     saídas.
#   Referência:
#     Foucault et al., ESEC/FSE 2015. https://doi.org/10.1145/2786805.2786870
#     Avelino et al., ESEM 2019 (limite de 12 meses). https://arxiv.org/abs/1906.08058
#   Entrada:
#     `pa` (de `pessoa_ano`) e `fim`. `pa` traz contributor_id, ano, primeiro, idade_anos,
#     idade_dias, faixa, novato, categoria, moved_no_ano, deixou_codigo_no_ano, saida,
#     pausa e volta.
#   Resultado esperado:
#     Uma linha por ano na tabela de `tabela_anual`, coluna `saidas`. Fica vazia (NaN) no
#     ano que a coleta ainda não cobre com 12 meses depois.

# Métrica: pausas
#   O que é:
#     Um período de atividade terminou naquele ano e a pessoa voltou depois de mais de 12
#     meses. Quem volta não saiu, então a pausa não entra na saída e a pessoa segue viva.
#   Referência:
#     Da pesquisa (Plano de Experimento).
#     Avelino et al., ESEM 2019 (limite de 12 meses). https://arxiv.org/abs/1906.08058
#   Entrada:
#     `pa` (de `pessoa_ano`) e `fim`. `pa` traz contributor_id, ano, primeiro, idade_anos,
#     idade_dias, faixa, novato, categoria, moved_no_ano, deixou_codigo_no_ano, saida,
#     pausa e volta.
#   Resultado esperado:
#     Uma linha por ano na tabela de `tabela_anual`, coluna `pausas`.

# Métrica: voltas
#   O que é:
#     Pessoas que retomam a atividade naquele ano, depois de um período sem contribuir.
#   Referência:
#     Da pesquisa (Plano de Experimento).
#   Entrada:
#     `pa` (de `pessoa_ano`) e `fim`. `pa` traz contributor_id, ano, primeiro, idade_anos,
#     idade_dias, faixa, novato, categoria, moved_no_ano, deixou_codigo_no_ano, saida,
#     pausa e volta.
#   Resultado esperado:
#     Uma linha por ano na tabela de `tabela_anual`, coluna `voltas`. Conta o começo de
#     todo período depois do primeiro.

# Métrica: moved
#   O que é:
#     Pessoas que só participavam sem escrever código (revisão, discussão) e passam a ter
#     atividade de código naquele ano. O ano é o do primeiro commit ou PR.
#   Referência:
#     Onoue et al., IEICE16. https://doi.org/10.1587/transinf.2015EDP7363
#   Entrada:
#     `pa` (de `pessoa_ano`) e `fim`. `pa` traz contributor_id, ano, primeiro, idade_anos,
#     idade_dias, faixa, novato, categoria, moved_no_ano, deixou_codigo_no_ano, saida,
#     pausa e volta.
#   Resultado esperado:
#     Uma linha por ano na tabela de `tabela_anual`, coluna `moved`.

# Métrica: deixou_codigo
#   O que é:
#     O caminho de volta do moved: a última atividade de discussão vem depois do último
#     commit ou PR. O ano é o do último commit ou PR.
#   Referência:
#     Da pesquisa (Plano de Experimento).
#   Entrada:
#     `pa` (de `pessoa_ano`) e `fim`. `pa` traz contributor_id, ano, primeiro, idade_anos,
#     idade_dias, faixa, novato, categoria, moved_no_ano, deixou_codigo_no_ano, saida,
#     pausa e volta.
#   Resultado esperado:
#     Uma linha por ano na tabela de `tabela_anual`, coluna `deixou_codigo`. Olha o
#     futuro: quem voltar a codar deixa de contar. No último ano da coleta o valor sobe,
#     porque quem ainda vai codar entra como quem deixou o código.

# Métrica: natalidade
#   O que é:
#     Tudo que entra no ano (novatos e voltas) sobre os ativos do mesmo ano, em %.
#   Referência:
#     Equação compensadora da demografia (IBGE, metodologia das projeções 1980-2050).
#     https://ftp.ibge.gov.br/Projecao_da_Populacao/Revisao_2004_Projecoes_1980_2050/metodologia.pdf
#   Entrada:
#     `pa` (de `pessoa_ano`) e `fim`. `pa` traz contributor_id, ano, primeiro, idade_anos,
#     idade_dias, faixa, novato, categoria, moved_no_ano, deixou_codigo_no_ano, saida,
#     pausa e volta.
#   Resultado esperado:
#     Coluna `natalidade_pct` de `tabela_anual`. Com 55, entraram 55 pessoas para cada 100
#     ativas no ano.

# Métrica: mortalidade
#   O que é:
#     Tudo que sai no ano (saídas e pausas) sobre os ativos do mesmo ano, em %.
#   Referência:
#     Equação compensadora da demografia (IBGE, metodologia das projeções 1980-2050).
#     https://ftp.ibge.gov.br/Projecao_da_Populacao/Revisao_2004_Projecoes_1980_2050/metodologia.pdf
#   Entrada:
#     `pa` (de `pessoa_ano`) e `fim`. `pa` traz contributor_id, ano, primeiro, idade_anos,
#     idade_dias, faixa, novato, categoria, moved_no_ano, deixou_codigo_no_ano, saida,
#     pausa e volta.
#   Resultado esperado:
#     Coluna `mortalidade_pct` de `tabela_anual`. Fica vazia no ano que a coleta ainda não
#     cobre.

# Métrica: crescimento_natural
#   O que é:
#     Tudo que entra menos tudo que sai, em % dos ativos do ano: (novatos + voltas -
#     saídas - pausas) / ativos. É a natalidade menos a mortalidade. Responde a RQ1.1.
#   Referência:
#     Equação compensadora da demografia (IBGE, metodologia das projeções 1980-2050).
#     https://ftp.ibge.gov.br/Projecao_da_Populacao/Revisao_2004_Projecoes_1980_2050/metodologia.pdf
#   Entrada:
#     `pa` (de `pessoa_ano`) e `fim`. `pa` traz contributor_id, ano, primeiro, idade_anos,
#     idade_dias, faixa, novato, categoria, moved_no_ano, deixou_codigo_no_ano, saida,
#     pausa e volta.
#   Resultado esperado:
#     Coluna `crescimento_natural_pct` de `tabela_anual`. Positivo: entrou mais gente do
#     que saiu. Negativo: saiu mais do que entrou.
#     A base é o próprio ano. A variação dos ativos sobre o ano anterior é outra conta.
#     `provisorio` verdadeiro marca o último ano completo, porque quem parou há pouco
#     ainda pode voltar.
#     A função falha alto se ativos(Y+1) não for ativos(Y) menos saídas e pausas, mais
#     novatos e voltas de Y+1.


def tabela_anual(pa: pd.DataFrame, fim: pd.Timestamp) -> pd.DataFrame:
    """Ativos, novatos, saídas, pausas, voltas, moved, deixou_codigo e crescimento natural, por ano.

    Saída é a última contribuição da vida. Quem para por mais de 12 meses e volta
    tem uma pausa no ano em que parou e uma volta no ano em que voltou, e deixa de ser ativo
    só entre os dois. Falha alto se a conta não fecha: ativos(Y+1) = ativos(Y) - saídas(Y) -
    pausas(Y) + novatos(Y+1) + voltas(Y+1), para todo Y com saída decidida.

    crescimento_natural_pct = (novatos + voltas - saídas - pausas) / ativos: tudo que entra menos
    tudo que sai, em % dos ativos do mesmo ano. natalidade_pct = (novatos + voltas) / ativos e
    mortalidade_pct = (saídas + pausas) / ativos, e a diferença entre elas é o crescimento natural.

    A base é o ano Y. Entra quem chegou em Y (novato ou volta) e sai quem tem a última contribuição
    de um período de atividade em Y (a saída só se confirma 12 meses depois). Não é a variação dos
    ativos sobre o ano anterior, ativos(Y) / ativos(Y-1) - 1, que usa Y-1 como base e as saídas e
    pausas de Y-1. Clojure 2024: crescimento natural -8,4%, variação dos ativos -18,8%.
    """
    g = pa.groupby("ano")
    t = pd.DataFrame(
        {
            "ativos": g.size(),
            "novatos": g["novato"].sum(),
            "saidas": g["saida"].sum().astype(float),
            "pausas": g["pausa"].sum(),
            "voltas": g["volta"].sum(),
            "moved": g["moved_no_ano"].sum(),
            "deixou_codigo": g["deixou_codigo_no_ano"].sum(),
        }
    )
    for ano in t.index:
        if not ano_completo(ano, fim):
            t.loc[ano, "saidas"] = np.nan
    t["provisorio"] = [provisorio(ano, fim) for ano in t.index]
    t["natalidade_pct"] = 100 * (t["novatos"] + t["voltas"]) / t["ativos"]
    t["mortalidade_pct"] = 100 * (t["saidas"] + t["pausas"]) / t["ativos"]
    t["crescimento_natural_pct"] = t["natalidade_pct"] - t["mortalidade_pct"]

    for ano in t.index:
        if ano + 1 not in t.index or pd.isna(t.loc[ano, "saidas"]):
            continue
        esperado = (
            t.loc[ano, "ativos"]
            - t.loc[ano, "saidas"]
            - t.loc[ano, "pausas"]
            + t.loc[ano + 1, "novatos"]
            + t.loc[ano + 1, "voltas"]
        )
        if esperado != t.loc[ano + 1, "ativos"]:
            raise ValueError(
                f"tabela_anual: conta não fecha em {ano}->{ano + 1}: "
                f"esperado {esperado}, ativos {t.loc[ano + 1, 'ativos']}."
            )
    t.index.name = "ano"
    return t.reset_index()


def trajetoria(anual: pd.DataFrame, ano_base_indice: int = 2019) -> pd.DataFrame:
    """Tamanho sem o efeito do tamanho: índice de ativos e taxas em % dos ativos do ano.

    Mesma conta de `metrica_trajetoria` em `scripts/vitalidade.py`.
    """
    t = anual.copy()
    t["saida_pct"] = 100 * t["saidas"] / t["ativos"]
    t["volta_pct"] = 100 * t["voltas"] / t["ativos"]
    t["novato_pct"] = 100 * t["novatos"] / t["ativos"]
    # Reposição: todo mundo que entrou (novatos e voltas) para cada pessoa que saiu (saídas e
    # pausas). Acima de 1 o crescimento natural é positivo.
    t["reposicao"] = (t["novatos"] + t["voltas"]) / (t["saidas"] + t["pausas"]).where(
        t["saidas"].notna()
    )
    ativos_na_base = t.set_index("ano")["ativos"].get(ano_base_indice)  # sem o ano base, sem índice
    t["indice"] = 100 * t["ativos"] / ativos_na_base if ativos_na_base else float("nan")
    return t


# shortcut: `scripts/vitalidade.py` ainda marca `provisorio` da trajetória pela regra de
# `carencia_anos` (os últimos anos completos). Aqui vale o `provisorio` de `tabela_anual`.
# Unificar quando o catálogo virar package.


# Métrica: saida_pct
#   O que é:
#     Saídas do ano em % dos ativos do mesmo ano. Tira o tamanho da linguagem da
#     comparação.
#   Referência:
#     Da pesquisa (Plano de Experimento).
#     Equação compensadora da demografia (IBGE, metodologia das projeções 1980-2050).
#     https://ftp.ibge.gov.br/Projecao_da_Populacao/Revisao_2004_Projecoes_1980_2050/metodologia.pdf
#   Entrada:
#     `anual` (de `tabela_anual`) e `ano_base_indice` (2019).
#   Resultado esperado:
#     Coluna `saida_pct` de `trajetoria`. Com 40, saíram 40 pessoas para cada 100 ativas.
#     Vazia no ano sem saída decidida.

# Métrica: volta_pct
#   O que é:
#     Voltas do ano em % dos ativos do mesmo ano.
#   Referência:
#     Da pesquisa (Plano de Experimento).
#     Equação compensadora da demografia (IBGE, metodologia das projeções 1980-2050).
#     https://ftp.ibge.gov.br/Projecao_da_Populacao/Revisao_2004_Projecoes_1980_2050/metodologia.pdf
#   Entrada:
#     `anual` (de `tabela_anual`) e `ano_base_indice` (2019).
#   Resultado esperado:
#     Coluna `volta_pct` de `trajetoria`. Com 8, voltaram 8 pessoas para cada 100 ativas.

# Métrica: novato_pct
#   O que é:
#     Novatos do ano em % dos ativos do mesmo ano.
#   Referência:
#     Da pesquisa (Plano de Experimento).
#     Equação compensadora da demografia (IBGE, metodologia das projeções 1980-2050).
#     https://ftp.ibge.gov.br/Projecao_da_Populacao/Revisao_2004_Projecoes_1980_2050/metodologia.pdf
#   Entrada:
#     `anual` (de `tabela_anual`) e `ano_base_indice` (2019).
#   Resultado esperado:
#     Coluna `novato_pct` de `trajetoria`. Com 30, 30 de cada 100 ativas são novatas.

# Métrica: reposicao
#   O que é:
#     O que entrou no ano (novatos e voltas) dividido pelo que saiu (saídas e pausas).
#   Referência:
#     Da pesquisa (Plano de Experimento).
#     Equação compensadora da demografia (IBGE, metodologia das projeções 1980-2050).
#     https://ftp.ibge.gov.br/Projecao_da_Populacao/Revisao_2004_Projecoes_1980_2050/metodologia.pdf
#   Entrada:
#     `anual` (de `tabela_anual`) e `ano_base_indice` (2019).
#   Resultado esperado:
#     Coluna `reposicao` de `trajetoria`. Acima de 1 o crescimento natural é positivo.
#     Abaixo de 1 o saldo é de perda. Vazia no ano sem saída decidida.

# Métrica: indice_de_ativos
#   O que é:
#     Ativos de cada ano divididos pelos ativos do ano base, vezes 100. O Python tem mil
#     vezes os ativos do Zig. Só o índice compara a trajetória das duas.
#   Referência:
#     Da pesquisa (Plano de Experimento).
#     Equação compensadora da demografia (IBGE, metodologia das projeções 1980-2050).
#     https://ftp.ibge.gov.br/Projecao_da_Populacao/Revisao_2004_Projecoes_1980_2050/metodologia.pdf
#   Entrada:
#     `anual` (de `tabela_anual`) e `ano_base_indice` (2019).
#   Resultado esperado:
#     Coluna `indice` de `trajetoria`. 100 no ano base (`ano_base_indice`). 80 quer dizer
#     20% menos ativos que no ano base. Sem ativos no ano base, sem índice.

# ================================================================================================
# Composição (RQ1.2): pirâmide e índice de envelhecimento
# ================================================================================================

# Métrica: piramide
#   O que é:
#     Ativos por faixa de tempo na linguagem (0-1, 1-2, 2-3, 3-5, 5-8, 8+ anos), separados
#     em quem faz código e quem só discute.
#     Categorias: non_coding (nunca fez commit nem PR), moved (começou pela discussão e
#     fez commit ou PR neste ano) e coding (começou pelo código). A quarta,
#     moved_to_discussion (já codou e neste ano só discutiu), só existe com
#     `com_moved_to_discussion=True`.
#   Referência:
#     Pirâmide etária e índice de envelhecimento (IBGE).
#     https://seriesestatisticas.ibge.gov.br/series.aspx?vcodigo=CD95
#     Hannemann e Klamma, OSS 2013. https://doi.org/10.1007/978-3-642-38928-3_6
#   Entrada:
#     `pa`, a tabela de `pessoa_ano`: uma linha por pessoa e ano em que ela contribuiu.
#   Resultado esperado:
#     Tabela de `composicao`: ano, faixa e uma coluna de contagem por categoria.
#     Quem fez commit ou PR no ano fica do lado do código, mesmo que o último evento seja
#     um comentário.

# Métrica: piramide_trimestral
#   O que é:
#     A pirâmide com idade em bandas de 90 dias no fim do ano, como no artigo, só para
#     olhar. As métricas usam as faixas de 1 ano.
#   Referência:
#     Onoue et al., IEICE16. https://doi.org/10.1587/transinf.2015EDP7363 (ESEM14 e
#     IEICE16).
#   Entrada:
#     `pa`, a tabela de `pessoa_ano`: uma linha por pessoa e ano em que ela contribuiu.
#   Resultado esperado:
#     Tabela de `composicao_trimestral`: ano, band (0 é até 90 dias de idade) e uma coluna
#     de contagem por categoria.


def composicao(pa: pd.DataFrame) -> pd.DataFrame:
    """Ativos por (ano, faixa) nas quatro categorias da pirâmide (ver `LADOS`)."""
    t = pa.groupby(["ano", "faixa", "categoria"], observed=False).size().unstack(fill_value=0)
    for coluna in LADOS:
        if coluna not in t.columns:
            t[coluna] = 0
    return t[LADOS].reset_index()


def composicao_trimestral(pa: pd.DataFrame, band_dias: int = BAND_DIAS) -> pd.DataFrame:
    """Ativos por (ano, banda de 3 meses de idade) em cada lado da pirâmide, como no artigo.

    A idade é o tempo desde a primeira contribuição até o fim do ano, em bandas de `band_dias`
    dias; a banda 0 vai de 0 a 90 dias. Os lados são os de `composicao`.
    """
    lados = LADOS
    banda = (np.ceil((pa["idade_dias"] / band_dias).round(9)) - 1).clip(lower=0).astype(int)
    t = pa.assign(band=banda).groupby(["ano", "band", "categoria"]).size().unstack(fill_value=0)
    for lado in lados:
        if lado not in t:
            t[lado] = 0
    return t[lados].reset_index()


# Métrica: piramide_em_pct
#   O que é:
#     A pirâmide com as contagens em % dos ativos do ano, para comparar linguagens de
#     tamanhos diferentes.
#   Referência:
#     Da pesquisa (Plano de Experimento).
#     Pirâmide etária e índice de envelhecimento (IBGE).
#     https://seriesestatisticas.ibge.gov.br/series.aspx?vcodigo=CD95
#   Entrada:
#     `pa`, a tabela de `pessoa_ano`: uma linha por pessoa e ano em que ela contribuiu.
#   Resultado esperado:
#     Tabela de `composicao_em_pct`: as colunas de `composicao`, cada uma em % do total do
#     ano. As quatro categorias de um ano somam 100.


def composicao_em_pct(pa: pd.DataFrame) -> pd.DataFrame:
    """`composicao` com as contagens em % dos ativos do ano (o `composicao_pct` da trajetória)."""
    c = composicao(pa)
    total_do_ano = c[LADOS].sum(axis=1).groupby(c["ano"]).transform("sum")
    c[LADOS] = 100 * c[LADOS].div(total_do_ano, axis=0)
    return c


# Métrica: indice_envelhecimento
#   O que é:
#     Ativos com 5 anos ou mais na linguagem (faixas 5-8 e 8+) divididos pelos ativos com
#     menos de 1 ano (faixa 0-1), por ano.
#   Referência:
#     Pirâmide etária e índice de envelhecimento (IBGE).
#     https://seriesestatisticas.ibge.gov.br/series.aspx?vcodigo=CD95
#     Hannemann e Klamma, OSS 2013. https://doi.org/10.1007/978-3-642-38928-3_6
#   Entrada:
#     `pa`, a tabela de `pessoa_ano`: uma linha por pessoa e ano em que ela contribuiu.
#   Resultado esperado:
#     Tabela de `indice_envelhecimento`: ano, veteranos, novatos e indice.
#     Índice 1: tantos veteranos quanto novatos. Quando sobe, a base encolhe mais rápido
#     que o topo. Fica vazio no ano sem novatos.


def indice_envelhecimento(pa: pd.DataFrame) -> pd.DataFrame:
    """Ativos com 5 anos ou mais na linguagem divididos pelos ativos com menos de 1, por ano."""
    veteranos = pa[pa["faixa"].isin(FAIXAS_VETERANO)].groupby("ano").size()
    novatos = pa[pa["faixa"].isin(FAIXAS_NOVATO)].groupby("ano").size()
    t = pd.DataFrame({"veteranos": veteranos, "novatos": novatos}).fillna(0).astype(int)
    t["indice"] = t["veteranos"] / t["novatos"].where(t["novatos"] > 0)
    t.index.name = "ano"
    return t.reset_index()


# ================================================================================================
# Retenção (RQ1.3): duração de cada pessoa e tábua de vida
# ================================================================================================

# Base, sem métrica própria. `duracoes` dá uma linha por pessoa: entrada, último evento, anos
# entre os dois, se saiu e a coorte de entrada. Quem tem o último evento a 12 meses ou menos
# de `fim` ainda pode voltar e fica censurado (`saiu` falso), com a duração observada até ali.


def duracoes(eventos: pd.DataFrame, fim: pd.Timestamp | None = None) -> pd.DataFrame:
    """Uma linha por pessoa: coorte de entrada, anos entre primeiro e último evento, e se saiu.

    Quem tem o último evento a 12 meses ou menos de `fim` ainda pode voltar a
    contribuir: fica censurado (`saiu` falso) na duração observada até ali.
    """
    if fim is None:
        fim = eventos["timestamp"].max()
    g = eventos.groupby("contributor_id")["timestamp"]
    p = pd.DataFrame({"entrada": g.min(), "ultimo": g.max()})
    dias = (p["ultimo"] - p["entrada"]).dt.total_seconds() / 86400
    p["duracao_anos"] = dias / DIAS_POR_ANO
    p["saiu"] = (fim - p["ultimo"]) > pd.Timedelta(days=GAP_DIAS)
    p["coorte"] = p["entrada"].dt.year
    return p.reset_index()


def _intervalo_de_wilson(eventos: float, n: float, z: float = 1.96) -> tuple[float, float]:
    """Intervalo de confiança de 95% de Wilson para uma proporção `eventos / n`.

    Vale para `n` fracionário (a exposição da tábua, com meio intervalo por censurado) e não
    estoura em 0 ou em 1, o que o intervalo normal faz quando o número de saídas é zero.
    """
    if not n > 0:
        return float("nan"), float("nan")
    p = eventos / n
    denominador = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / denominador
    meia = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominador
    return max(0.0, centro - meia), min(1.0, centro + meia)


# Métrica: sobreviventes
#   O que é:
#     l(x): pessoas ainda em observação ao chegar em x anos de contribuição.
#     Responde a RQ1.3. Quem entrou no mesmo ano forma uma coorte.
#   Referência:
#     IBGE, Tábua Completa de Mortalidade 2023.
#     https://biblioteca.ibge.gov.br/visualizacao/periodicos/3097/tcmb_2023.pdf
#     Hannemann e Klamma, OSS 2013. https://doi.org/10.1007/978-3-642-38928-3_6
#   Entrada:
#     `dur`, a tabela de `duracoes`: uma linha por pessoa, com contributor_id, entrada,
#     ultimo, duracao_anos, saiu (falso é censurado) e coorte.
#   Resultado esperado:
#     Coluna `l` da tabela de `tabua_de_vida`, uma linha por x. Começa no total da coorte
#     e só desce.

# Métrica: saidas_da_tabua
#   O que é:
#     d(x): saídas entre x e x+1 anos de contribuição.
#     Responde a RQ1.3. Quem entrou no mesmo ano forma uma coorte.
#   Referência:
#     IBGE, Tábua Completa de Mortalidade 2023.
#     https://biblioteca.ibge.gov.br/visualizacao/periodicos/3097/tcmb_2023.pdf
#     Hannemann e Klamma, OSS 2013. https://doi.org/10.1007/978-3-642-38928-3_6
#   Entrada:
#     `dur`, a tabela de `duracoes`: uma linha por pessoa, com contributor_id, entrada,
#     ultimo, duracao_anos, saiu (falso é censurado) e coorte.
#   Resultado esperado:
#     Coluna `d` da tabela de `tabua_de_vida`, uma linha por x. Contagem. Soma das saídas
#     de todos os x é o total de quem saiu.

# Métrica: chance_de_sair
#   O que é:
#     q(x) = d(x) / (l(x) - censurados(x) / 2): a chance de sair estando no ano x. O
#     censurado conta meio intervalo de exposição. É a taxa de saída da faixa, no nível do
#     ano.
#     Responde a RQ1.3. Quem entrou no mesmo ano forma uma coorte.
#   Referência:
#     IBGE, Tábua Completa de Mortalidade 2023.
#     https://biblioteca.ibge.gov.br/visualizacao/periodicos/3097/tcmb_2023.pdf
#     Hannemann e Klamma, OSS 2013. https://doi.org/10.1007/978-3-642-38928-3_6
#   Entrada:
#     `dur`, a tabela de `duracoes`: uma linha por pessoa, com contributor_id, entrada,
#     ultimo, duracao_anos, saiu (falso é censurado) e coorte.
#   Resultado esperado:
#     Coluna `q` da tabela de `tabua_de_vida`, uma linha por x. q vai de 0 a 1. Com q =
#     0,4 em x = 2, 40% de quem chegou a 2 anos sai antes de completar 3. `n_efetivo` é a
#     exposição de q: com poucas pessoas q oscila.

# Métrica: fracao_que_chega
#   O que é:
#     S(x): fração da coorte que chega a x. Produto de (1 - q) até x - 1.
#     Responde a RQ1.3. Quem entrou no mesmo ano forma uma coorte.
#   Referência:
#     IBGE, Tábua Completa de Mortalidade 2023.
#     https://biblioteca.ibge.gov.br/visualizacao/periodicos/3097/tcmb_2023.pdf
#     Hannemann e Klamma, OSS 2013. https://doi.org/10.1007/978-3-642-38928-3_6
#   Entrada:
#     `dur`, a tabela de `duracoes`: uma linha por pessoa, com contributor_id, entrada,
#     ultimo, duracao_anos, saiu (falso é censurado) e coorte.
#   Resultado esperado:
#     Coluna `S` da tabela de `tabua_de_vida`, uma linha por x. Começa em 1 e desce. S =
#     0,3 em x = 5: 30% da coorte chega a 5 anos.

# Métrica: esperanca_restante
#   O que é:
#     e(x): anos que ainda restam, em média, a quem chegou a x anos de contribuição.
#     Responde a pergunta de quem já está há x anos: quanto tempo ainda fica.
#     Responde a RQ1.3. Quem entrou no mesmo ano forma uma coorte.
#   Referência:
#     IBGE, Tábua Completa de Mortalidade 2023.
#     https://biblioteca.ibge.gov.br/visualizacao/periodicos/3097/tcmb_2023.pdf
#     Hannemann e Klamma, OSS 2013. https://doi.org/10.1007/978-3-642-38928-3_6
#   Entrada:
#     `dur`, a tabela de `duracoes`: uma linha por pessoa, com contributor_id, entrada,
#     ultimo, duracao_anos, saiu (falso é censurado) e coorte.
#   Resultado esperado:
#     Coluna `e` da tabela de `tabua_de_vida`, uma linha por x. Anos. `e_truncado`
#     verdadeiro: a cauda censurada fica de fora. Nesse caso e(x) é um valor mínimo.

# Métrica: intervalo_de_q
#   O que é:
#     Intervalo de 95% de Wilson para q(x), calculado com a exposição `n_efetivo`. Não
#     estoura em 0 ou em 1 quando não há saída.
#     Responde a RQ1.3. Quem entrou no mesmo ano forma uma coorte.
#   Referência:
#     IBGE, Tábua Completa de Mortalidade 2023.
#     https://biblioteca.ibge.gov.br/visualizacao/periodicos/3097/tcmb_2023.pdf
#     Hannemann e Klamma, OSS 2013. https://doi.org/10.1007/978-3-642-38928-3_6
#   Entrada:
#     `dur`, a tabela de `duracoes`: uma linha por pessoa, com contributor_id, entrada,
#     ultimo, duracao_anos, saiu (falso é censurado) e coorte.
#   Resultado esperado:
#     Coluna `q_inf` da tabela de `tabua_de_vida`, uma linha por x. `q_inf` e `q_sup`,
#     entre 0 e 1. Com 10 pessoas efetivas e 0 saídas o intervalo vai de 0 a 28%. Quem lê
#     q(x) deve olhar `n_efetivo` e o intervalo.


def tabua_de_vida(dur: pd.DataFrame) -> pd.DataFrame:
    """Tábua de vida atuarial em intervalos de 1 ano na linguagem.

    l(x)  pessoas ainda em observação ao chegar em x anos
    d(x)  saídas entre x e x+1
    q(x)  d(x) / (l(x) - censurados(x)/2): o censurado conta meio intervalo de exposição
    n_efetivo(x)  a exposição l(x) - censurados(x)/2, o denominador de q
    q_inf, q_sup  intervalo de confiança de 95% de Wilson para q(x) com `n_efetivo`
    S(x)  fração que chega em x, produto de (1 - q) até x-1
    e(x)  anos que ainda restam, em média, a quem chegou em x

    Com poucas pessoas efetivamente observadas q(x) oscila: 0 saídas em 10 pessoas efetivas dá
    q = 0 e um intervalo de 0 a 28%. Quem lê q(x) deve olhar `n_efetivo` e o intervalo.

    Quando a tábua termina com gente censurada (S final > 0), a cauda depois do
    último intervalo observado não entra, e e(x) é um piso. `e_truncado` marca.
    """
    colunas = [
        "x",
        "l",
        "d",
        "censurados",
        "n_efetivo",
        "q",
        "q_inf",
        "q_sup",
        "S",
        "e",
        "e_truncado",
    ]
    if dur.empty:
        return pd.DataFrame(columns=colunas)

    intervalo = np.floor(dur["duracao_anos"]).astype(int)
    em_risco = len(dur)
    sobrevivencia = 1.0
    linhas = []
    for x in range(int(intervalo.max()) + 1):
        aqui = intervalo == x
        d = int((aqui & dur["saiu"]).sum())
        c = int((aqui & ~dur["saiu"]).sum())
        exposicao = em_risco - c / 2
        q = d / exposicao if exposicao > 0 else np.nan
        q_inf, q_sup = _intervalo_de_wilson(d, exposicao)
        linhas.append(
            {
                "x": x,
                "l": em_risco,
                "d": d,
                "censurados": c,
                "n_efetivo": exposicao,
                "q": q,
                "q_inf": q_inf,
                "q_sup": q_sup,
                "S": sobrevivencia,
            }
        )
        if not np.isnan(q):
            sobrevivencia = sobrevivencia * (1 - q)
        em_risco = em_risco - d - c

    t = pd.DataFrame(linhas)
    s_seguinte = t["S"].shift(-1, fill_value=sobrevivencia)
    anos_vividos = (t["S"] + s_seguinte) / 2
    restante = anos_vividos[::-1].cumsum()[::-1]
    t["e"] = restante / t["S"].where(t["S"] > 0)
    t["e_truncado"] = sobrevivencia > 0
    return t[colunas]


# Métrica: tabua_por_coorte
#   O que é:
#     A tábua de vida de cada coorte de entrada. Comparando coortes, vê-se se cada geração
#     fica mais ou menos tempo que a anterior.
#   Referência:
#     IBGE, Tábua Completa de Mortalidade 2023.
#     https://biblioteca.ibge.gov.br/visualizacao/periodicos/3097/tcmb_2023.pdf
#     Hannemann e Klamma, OSS 2013. https://doi.org/10.1007/978-3-642-38928-3_6
#   Entrada:
#     `dur`, a tabela de `duracoes`: uma linha por pessoa, com contributor_id, entrada,
#     ultimo, duracao_anos, saiu (falso é censurado) e coorte.
#   Resultado esperado:
#     Tabela de `tabuas_por_coorte`: as colunas de `tabua_de_vida` com a coluna coorte na
#     frente. As coortes mais recentes ficam incompletas por causa da censura.


def tabuas_por_coorte(dur: pd.DataFrame) -> pd.DataFrame:
    """`tabua_de_vida` de cada coorte de entrada, empilhadas com a coluna `coorte`."""
    frames = []
    for coorte, grupo in dur.groupby("coorte"):
        t = tabua_de_vida(grupo)
        t.insert(0, "coorte", coorte)
        frames.append(t)
    return pd.concat(frames, ignore_index=True)


# Métrica: chance_de_seguir
#   O que é:
#     Chance de seguir mais 1 ano tendo chegado a x: 1 - q(x). Olha só o ano seguinte.
#   Referência:
#     Da pesquisa (Plano de Experimento).
#     IBGE, Tábua Completa de Mortalidade 2023.
#     https://biblioteca.ibge.gov.br/visualizacao/periodicos/3097/tcmb_2023.pdf
#   Entrada:
#     `tabua`, a tabela de `tabua_de_vida`.
#   Resultado esperado:
#     Uma série entre 0 e 1, uma por x. 0,6 em x = 3: 60% de quem chegou a 3 anos segue
#     mais um ano. Abaixo de 300 pessoas efetivas (`n_efetivo`) a chance oscila vários
#     pontos.


def chance_de_seguir(tabua: pd.DataFrame) -> pd.Series:
    """Chance de seguir mais 1 ano tendo chegado a x: 1 - q(x)."""
    return 1 - tabua["q"]


# ================================================================================================
# Saída por faixa (RQ1.3)
# ================================================================================================

# Métrica: taxa_saida_por_faixa
#   O que é:
#     Saídas da faixa dividido pelos ativos da faixa, por ano e faixa de tempo na
#     linguagem. É o q(x) da tábua de vida, faixa por faixa. Mostra em que fase a
#     comunidade perde mais gente, novatos ou veteranos.
#   Referência:
#     IBGE, Tábua Completa de Mortalidade 2023.
#     https://biblioteca.ibge.gov.br/visualizacao/periodicos/3097/tcmb_2023.pdf
#     CDC WONDER, Presentation Standards for Mortality Data, 2024.
#     https://wonder.cdc.gov/controller/pdf/presentation-standards-mortality-2024.pdf
#   Entrada:
#     `pa`, a tabela de `pessoa_ano`: uma linha por pessoa e ano em que ela contribuiu. E
#     `fim`.
#   Resultado esperado:
#     Tabela de `taxa_saida_por_faixa`: ano, faixa, ativos, saidas e taxa_saida.
#     taxa_saida vai de 0 a 1. Com 0,3, a cada 10 ativos da faixa 3 saíram no ano.
#     Ano que a coleta não cobre fica sem saídas e sem taxa. Faixa sem ativos fica sem
#     taxa. Os gráficos marcam como instável a célula com menos de 20 saídas
#     (`saidas_estavel`).


def taxa_saida_por_faixa(pa: pd.DataFrame, fim: pd.Timestamp) -> pd.DataFrame:
    """Saídas da faixa / ativos da faixa, por (ano, faixa). Ano aberto fica `NaN`."""
    t = (
        pa.groupby(["ano", "faixa"], observed=False)
        .agg(ativos=("contributor_id", "size"), saidas=("saida", "sum"))
        .reset_index()
    )
    t["saidas"] = t["saidas"].astype(float)
    for i in t.index:
        if not ano_completo(int(t.loc[i, "ano"]), fim):
            t.loc[i, "saidas"] = np.nan
    t["taxa_saida"] = t["saidas"] / t["ativos"].where(t["ativos"] > 0)
    return t


# ================================================================================================
# Comparação corrigida (RQ2): taxa padronizada e SMR
# ================================================================================================

# Métrica: taxa_bruta
#   O que é:
#     Saídas do ano sobre os ativos do ano da linguagem, sem corrigir a composição.
#     Responde a RQ2.
#   Referência:
#     Ahmad et al., Age Standardization of Rates: A New WHO Standard, OMS, 2001.
#     https://cdn.who.int/media/docs/default-source/gho-documents/global-health-estimates/gpe_discussion_paper_series_paper31_2001_age_standardization_rates.pdf
#   Entrada:
#     Um dict {linguagem: tabela de `taxa_saida_por_faixa`} e `ano_pesos` (2025). A
#     referência é a soma das linguagens do dict.
#   Resultado esperado:
#     Coluna `taxa_bruta` da tabela de `padronizacao`, uma linha por linguagem e ano. 0 a
#     1. Mistura a diferença real de retenção com a diferença de composição entre
#     linguagens.

# Métrica: taxa_padronizada
#   O que é:
#     Taxa direta: soma, por faixa, de (taxa de saída da faixa na linguagem x peso da
#     faixa na população de referência). Compara as linguagens como se todas tivessem a
#     mesma mistura de novatos e veteranos. O que sobra de diferença vem da retenção.
#     Responde a RQ2.
#   Referência:
#     Ahmad et al., Age Standardization of Rates: A New WHO Standard, OMS, 2001.
#     https://cdn.who.int/media/docs/default-source/gho-documents/global-health-estimates/gpe_discussion_paper_series_paper31_2001_age_standardization_rates.pdf
#   Entrada:
#     Um dict {linguagem: tabela de `taxa_saida_por_faixa`} e `ano_pesos` (2025). A
#     referência é a soma das linguagens do dict.
#   Resultado esperado:
#     Coluna `taxa_padronizada` da tabela de `padronizacao`, uma linha por linguagem e
#     ano. 0 a 1. Fica vazia no ano em que alguma faixa não tem ninguém (linguagem jovem).

# Métrica: taxa_padronizada_ate_5a
#   O que é:
#     A taxa direta só nas faixas de 0 a 5 anos, com os pesos renormalizados. Começa 5
#     anos depois do nascimento da comunidade e compara todas no mesmo intervalo de
#     idades.
#     Responde a RQ2.
#   Referência:
#     Ahmad et al., Age Standardization of Rates: A New WHO Standard, OMS, 2001.
#     https://cdn.who.int/media/docs/default-source/gho-documents/global-health-estimates/gpe_discussion_paper_series_paper31_2001_age_standardization_rates.pdf
#   Entrada:
#     Um dict {linguagem: tabela de `taxa_saida_por_faixa`} e `ano_pesos` (2025). A
#     referência é a soma das linguagens do dict.
#   Resultado esperado:
#     Coluna `taxa_padronizada_ate_5a` da tabela de `padronizacao`, uma linha por
#     linguagem e ano. 0 a 1. Existe em linguagens novas, que ainda não têm as faixas 5-8
#     e 8+.

# Métrica: saidas_esperadas
#   O que é:
#     Quantas saídas a linguagem teria se tivesse as taxas de saída da referência em cada
#     faixa: soma, por faixa, de (taxa da referência x ativos da linguagem).
#     Responde a RQ2.
#   Referência:
#     Ahmad et al., Age Standardization of Rates: A New WHO Standard, OMS, 2001.
#     https://cdn.who.int/media/docs/default-source/gho-documents/global-health-estimates/gpe_discussion_paper_series_paper31_2001_age_standardization_rates.pdf
#   Entrada:
#     Um dict {linguagem: tabela de `taxa_saida_por_faixa`} e `ano_pesos` (2025). A
#     referência é a soma das linguagens do dict.
#   Resultado esperado:
#     Coluna `saidas_esperadas` da tabela de `padronizacao`, uma linha por linguagem e
#     ano. Contagem fracionária. Fica vazia se a referência do ano tem faixa aberta.

# Métrica: smr
#   O que é:
#     Razão padronizada de saídas: saídas reais divididas pelas saídas esperadas.
#     Responde a RQ2.
#   Referência:
#     Ahmad et al., Age Standardization of Rates: A New WHO Standard, OMS, 2001.
#     https://cdn.who.int/media/docs/default-source/gho-documents/global-health-estimates/gpe_discussion_paper_series_paper31_2001_age_standardization_rates.pdf
#   Entrada:
#     Um dict {linguagem: tabela de `taxa_saida_por_faixa`} e `ano_pesos` (2025). A
#     referência é a soma das linguagens do dict.
#   Resultado esperado:
#     Coluna `smr` da tabela de `padronizacao`, uma linha por linguagem e ano. 1: saiu o
#     esperado. Acima de 1: saiu mais do que o esperado. Abaixo de 1: saiu menos. O
#     resultado depende da referência escolhida.


def padronizacao(taxas: dict[str, pd.DataFrame], ano_pesos: int) -> pd.DataFrame:
    """Taxa de saída bruta, padronizada (direta) e SMR (indireta), por linguagem e ano.

    `taxas` traz a saída de `taxa_saida_por_faixa` de cada linguagem. A
    referência é a soma das linguagens: os pesos vêm da composição por faixa de
    todas juntas em `ano_pesos`, e a taxa da referência em Y é a de todas juntas em Y.

      direta  soma, por faixa, de taxa da linguagem vezes peso da faixa
      SMR     saídas da linguagem / soma, por faixa, de taxa da referência vezes
              ativos da linguagem

    Faixa sem ativos na linguagem deixa a direta `NaN`, porque falta a taxa a
    pesar. Ano aberto em qualquer linguagem deixa a referência daquele ano `NaN`.

    `taxa_padronizada_ate_5a` é a direta só nas faixas `FAIXAS_CURTAS` (0 a 5 anos), com os pesos
    renormalizados. Uma linguagem nova não tem 8+ nem 5-8 nos primeiros anos, e a direta completa
    só começa quando todas as faixas existem (Zig em 2023). A curta começa 5 anos depois do
    nascimento da comunidade e compara todas no mesmo intervalo de idades.
    """
    frames = []
    for linguagem, t in taxas.items():
        frames.append(t.assign(linguagem=linguagem))
    todas = pd.concat(frames, ignore_index=True)
    todas["aberto"] = todas["saidas"].isna()

    ref = todas.groupby(["ano", "faixa"], observed=True).agg(
        ativos=("ativos", "sum"), saidas=("saidas", "sum"), abertos=("aberto", "sum")
    )
    ref["taxa"] = ref["saidas"] / ref["ativos"].where(ref["ativos"] > 0)
    ref.loc[ref["abertos"] > 0, "taxa"] = np.nan

    ativos_pesos = ref.xs(ano_pesos, level="ano")["ativos"]
    pesos = ativos_pesos / ativos_pesos.sum()
    pesos_curtos = ativos_pesos.reindex(FAIXAS_CURTAS)
    pesos_curtos = pesos_curtos / pesos_curtos.sum()

    linhas = []
    for (linguagem, ano), grupo in todas.groupby(["linguagem", "ano"]):
        g = grupo.set_index("faixa")
        taxa_ref = ref.xs(ano, level="ano")["taxa"]
        com_gente = g["ativos"] > 0
        saidas = g["saidas"].sum(skipna=False)
        esperadas = (taxa_ref[com_gente] * g.loc[com_gente, "ativos"]).sum(skipna=False)
        linhas.append(
            {
                "linguagem": linguagem,
                "ano": ano,
                "ativos": g["ativos"].sum(),
                "saidas": saidas,
                "taxa_bruta": saidas / g["ativos"].sum(),
                "taxa_padronizada": (g["taxa_saida"] * pesos).sum(skipna=False),
                "taxa_padronizada_ate_5a": (
                    g["taxa_saida"].reindex(FAIXAS_CURTAS) * pesos_curtos
                ).sum(skipna=False),
                "saidas_esperadas": esperadas,
                "smr": saidas / esperadas,
            }
        )
    return pd.DataFrame(linhas)


# ================================================================================================
# Significância (RQ2): Kaplan-Meier e log-rank
# ================================================================================================

# Métrica: kaplan_meier
#   O que é:
#     A probabilidade estimada de uma pessoa ainda estar ativa t anos depois de entrar.
#     Quem segue ativo no fim da coleta entra como ainda sem saída (censura à direita).
#   Referência:
#     Constantinou e Mens, Innovations in Systems and Software Engineering, 2017.
#     https://doi.org/10.1007/s11334-017-0303-4
#   Entrada:
#     `dur`, a tabela de `duracoes`: uma linha por pessoa, com contributor_id, entrada,
#     ultimo, duracao_anos, saiu (falso é censurado) e coorte.
#   Resultado esperado:
#     Tabela de `kaplan_meier`: anos, S (a fração ainda ativa, que começa em 1 e desce em
#     degraus) e em_risco (quantas pessoas têm duração de `anos` ou mais: quanto menos,
#     menos a curva vale).
#     Uma amostra com mais de 2 milhões de pontos sai com um ponto por dia, exato nesse
#     instante.

# Métrica: logrank
#   O que é:
#     Teste que diz se duas curvas de Kaplan-Meier diferem além do acaso. O plano compara
#     Clojure com cada outra linguagem.
#   Referência:
#     Constantinou e Mens, Innovations in Systems and Software Engineering, 2017.
#     https://doi.org/10.1007/s11334-017-0303-4
#   Entrada:
#     `dur_a` e `dur_b`, as tabelas de `duracoes` das duas linguagens.
#   Resultado esperado:
#     Uma tupla (estatística, p). P abaixo de 0,05: a diferença passa do acaso.
#     Com milhares de pessoas o p fica minúsculo para qualquer diferença. O que informa é
#     o tamanho dela, por exemplo 0,28 contra 0,36 de fração ativa depois de 5 anos.


def _amostra_censurada(dur: pd.DataFrame) -> stats.CensoredData:
    """Duração de `duracoes`, com quem não saiu marcado como censura à direita."""
    return stats.CensoredData.right_censored(
        dur["duracao_anos"].to_numpy(), ~dur["saiu"].to_numpy()
    )


def kaplan_meier(dur: pd.DataFrame) -> pd.DataFrame:
    """Fração estimada ainda ativa, `S`, depois de `anos` desde a primeira contribuição.

    `em_risco` é quantas pessoas têm duração de `anos` ou mais: quanto menor, menos a curva vale.
    Com mais de `MAX_PONTOS_KM` pontos fica o último de cada dia, que é exato nesse instante.
    """
    sf = stats.ecdf(_amostra_censurada(dur)).sf
    curva = pd.DataFrame({"anos": sf.quantiles, "S": sf.probabilities})
    if len(curva) > MAX_PONTOS_KM:
        dia = np.floor(curva["anos"] * DIAS_POR_ANO)
        curva = curva.groupby(dia, sort=True).last().reset_index(drop=True)
    duracoes_ordenadas = np.sort(dur["duracao_anos"].to_numpy())
    curva["em_risco"] = len(duracoes_ordenadas) - np.searchsorted(
        duracoes_ordenadas, curva["anos"].to_numpy(), side="left"
    )
    return curva


def logrank(dur_a: pd.DataFrame, dur_b: pd.DataFrame) -> tuple[float, float]:
    """Log-rank bilateral entre duas curvas de Kaplan-Meier: (estatística, p-valor)."""
    r = stats.logrank(_amostra_censurada(dur_a), _amostra_censurada(dur_b))
    return float(r.statistic), float(r.pvalue)


# ================================================================================================
# Cenários futuros (RQ3): projeção, erro e cobertura
# ================================================================================================

# Base, sem métrica própria. A projeção usa faixas de 1 ano de contribuição (0 a 7 e 8+) e
# avança um ano por vez. `populacao_por_idade` dá ativos por ano e idade. `saidas_por_banda`
# dá as saídas por ano e banda. `regra_da_variante` monta a regra de cenário a partir de
# `variantes` no yaml.


def populacao_por_idade(pa: pd.DataFrame) -> pd.DataFrame:
    """Ativos por ano (linhas) e idade exata em anos (colunas), sem fechar a 8+."""
    pop = pa.groupby(["ano", "idade_anos"]).size().unstack(fill_value=0)
    anos = range(int(pop.index.min()), int(pop.index.max()) + 1)
    idades = range(int(pop.columns.max()) + 1)
    return pop.reindex(index=anos, columns=idades, fill_value=0)


def _bandas(linha: pd.Series) -> np.ndarray:
    """Contagem por idade exata vira vetor de 0 a 7 e 8+."""
    v = np.zeros(BANDAS)
    for idade, n in linha.items():
        v[min(int(idade), BANDAS - 1)] += n
    return v


def saidas_por_banda(pa: pd.DataFrame, fim: pd.Timestamp) -> pd.DataFrame:
    """Saídas por ano (linhas) e banda de 0 a 8 (colunas). Ano aberto fica `NaN`."""
    saiu = pa[pa["saida"]].assign(banda=pa["idade_anos"].clip(upper=BANDAS - 1))
    t = saiu.groupby(["ano", "banda"]).size().unstack(fill_value=0)
    anos = range(int(pa["ano"].min()), int(pa["ano"].max()) + 1)
    t = t.reindex(index=anos, columns=range(BANDAS), fill_value=0).astype(float)
    for ano in t.index:
        if not ano_fechado(ano, fim):
            t.loc[ano] = np.nan
    return t


@dataclass(frozen=True)
class RegraCenario:
    """Como os cenários leem a série histórica.

    min_saidas        a permanência da banda a de Y-1 para Y só entra se a banda
                      teve pelo menos essas saídas em Y-1
    janela            só os últimos `janela` anos até a base; `None` usa a história toda
    novatos_por_taxa  novatos viram taxa (novatos de Y / ativos de Y-1), aplicada
                      à população do ano projetado; falso usa a contagem de novatos
    conservador       como o cenário conservador sai da janela: `extremos` é a média do menor
                      e do maior valor, `media` é a média de todos os anos da janela e
                      `recentes` é a média dos 2 últimos anos da janela
    """

    min_saidas: int = 0
    janela: int | None = None
    novatos_por_taxa: bool = False
    conservador: str = "extremos"


def regra_da_variante(valores: list, min_saidas: int) -> RegraCenario:
    """A regra de uma variante do yaml: [rótulo, janela, novatos por taxa, conservador].

    O quarto item é opcional e o padrão é `extremos`.
    """
    janela, por_taxa = valores[1], valores[2]
    conservador = valores[3] if len(valores) > 3 else "extremos"
    return RegraCenario(min_saidas, janela, por_taxa, conservador)


# Métrica: taxa_de_permanencia
#   O que é:
#     Para cada faixa de 1 ano, a população da faixa seguinte neste ano dividida pela da
#     faixa anterior no ano passado. Pode passar de 1, porque quem volta a contribuir
#     reaparece na faixa seguinte sem ter sido contado na anterior.
#   Referência:
#     Onoue et al., IEICE16. https://doi.org/10.1587/transinf.2015EDP7363 Adaptado do
#     método de componentes por coorte de Isserman.
#   Entrada:
#     `pop` (de `populacao_por_idade`) e o `ano`.
#   Resultado esperado:
#     Um vetor de 9 posições (faixas 0 a 7 e 8+). Banda de origem vazia deixa a taxa vazia
#     (NaN). 0,8 quer dizer que 80% da faixa chegou à seguinte.


def permanencia(pop: pd.DataFrame, ano: int) -> np.ndarray:
    """Taxa de permanência de `ano - 1` para `ano`, por banda de origem.

    sr[a], a de 0 a 7: P(idade a+1, ano) / P(idade a, ano - 1).
    sr[8]: P(idade 9 ou mais, ano) / P(idade 8 ou mais, ano - 1).
    Banda de origem vazia deixa a taxa `NaN`.
    """
    antes = pop.loc[ano - 1]
    agora = pop.loc[ano]
    sr = np.full(BANDAS, np.nan)
    for a in range(BANDAS - 1):
        if antes.get(a, 0) > 0:
            sr[a] = agora.get(a + 1, 0) / antes[a]
    na_aberta = antes[antes.index >= BANDAS - 1].sum()
    if na_aberta > 0:
        sr[BANDAS - 1] = agora[agora.index >= BANDAS].sum() / na_aberta
    return sr


def projeta_um_ano(p: np.ndarray, sr: np.ndarray, novatos: float, teto: bool) -> np.ndarray:
    """Pirâmide de T+1 a partir da de T. `teto` limita a permanência em 1.

    Banda vazia em T não leva ninguém adiante, mesmo com taxa `NaN`. Banda com
    gente e taxa `NaN` deixa o destino `NaN`: o método não tem resposta ali.
    """
    if teto:
        sr = np.minimum(sr, 1.0)
    proj = np.zeros(BANDAS)
    proj[0] = novatos
    for a in range(BANDAS):
        if p[a] == 0:
            continue
        destino = min(a + 1, BANDAS - 1)
        proj[destino] = proj[destino] + p[a] * sr[a]
    return proj


# Métrica: projecao_ingenua
#   O que é:
#     A pirâmide do próximo ano é igual à do último ano observado.
#     Responde a RQ3. O backtest usa só os anos anteriores ao ano previsto.
#   Referência:
#     Onoue et al., IEICE16. https://doi.org/10.1587/transinf.2015EDP7363
#     Variantes de projeção da ONU.
#     https://www.prb.org/resource/understanding-population-projections-assumptions-behind-the-numbers/
#     Bonifácio e Guimarães, Texto para Discussão 2698, Ipea, 2021.
#   Entrada:
#     `pa`, `fim`, o último ano com saída decidida (`fim.year - 1`), `teto` (limita a
#     permanência em 1) e `regra`, um `RegraCenario`.
#   Resultado esperado:
#     Coluna `ingenuo` da tabela de `backtest` (uma linha por ano e faixa, com a faixa
#     `total`) e linhas do `metodo` correspondente em `projeta_futuro`.

# Métrica: projecao_coorte
#   O que é:
#     Cada faixa do próximo ano recebe a população da faixa anterior vezes a taxa de
#     permanência do último par de anos. Os novatos são a média dos dois últimos anos.
#     Responde a RQ3. O backtest usa só os anos anteriores ao ano previsto.
#   Referência:
#     Onoue et al., IEICE16. https://doi.org/10.1587/transinf.2015EDP7363
#     Variantes de projeção da ONU.
#     https://www.prb.org/resource/understanding-population-projections-assumptions-behind-the-numbers/
#     Bonifácio e Guimarães, Texto para Discussão 2698, Ipea, 2021.
#   Entrada:
#     `pa`, `fim`, o último ano com saída decidida (`fim.year - 1`), `teto` (limita a
#     permanência em 1) e `regra`, um `RegraCenario`.
#   Resultado esperado:
#     Coluna `coorte` da tabela de `backtest` (uma linha por ano e faixa, com a faixa
#     `total`) e linhas do `metodo` correspondente em `projeta_futuro`.

# Métrica: cenario_pessimista
#   O que é:
#     A mesma conta do coorte com a permanência de cada faixa e os novatos no menor valor
#     da série histórica. Só entram anos em que a faixa teve o mínimo de saídas
#     (`min_saidas`).
#     Responde a RQ3. O backtest usa só os anos anteriores ao ano previsto.
#   Referência:
#     Onoue et al., IEICE16. https://doi.org/10.1587/transinf.2015EDP7363
#     Variantes de projeção da ONU.
#     https://www.prb.org/resource/understanding-population-projections-assumptions-behind-the-numbers/
#     Bonifácio e Guimarães, Texto para Discussão 2698, Ipea, 2021.
#   Entrada:
#     `pa`, `fim`, o último ano com saída decidida (`fim.year - 1`), `teto` (limita a
#     permanência em 1) e `regra`, um `RegraCenario`.
#   Resultado esperado:
#     Coluna `pessimista` da tabela de `backtest` (uma linha por ano e faixa, com a faixa
#     `total`) e linhas do `metodo` correspondente em `projeta_futuro`.

# Métrica: cenario_conservador
#   O que é:
#     A mesma conta do coorte com a média entre o maior e o menor valor histórico (regra
#     `extremos`) ou outra regra da variante: média da janela, ou dos 2 últimos anos.
#     Responde a RQ3. O backtest usa só os anos anteriores ao ano previsto.
#   Referência:
#     Onoue et al., IEICE16. https://doi.org/10.1587/transinf.2015EDP7363
#     Variantes de projeção da ONU.
#     https://www.prb.org/resource/understanding-population-projections-assumptions-behind-the-numbers/
#     Bonifácio e Guimarães, Texto para Discussão 2698, Ipea, 2021.
#   Entrada:
#     `pa`, `fim`, o último ano com saída decidida (`fim.year - 1`), `teto` (limita a
#     permanência em 1) e `regra`, um `RegraCenario`.
#   Resultado esperado:
#     Coluna `conservador` da tabela de `backtest` (uma linha por ano e faixa, com a faixa
#     `total`) e linhas do `metodo` correspondente em `projeta_futuro`.

# Métrica: cenario_otimista
#   O que é:
#     A mesma conta do coorte com a permanência de cada faixa e os novatos no maior valor
#     da série histórica. Junta o melhor ano de cada faixa, então funciona como limite
#     superior da projeção.
#     Responde a RQ3. O backtest usa só os anos anteriores ao ano previsto.
#   Referência:
#     Onoue et al., IEICE16. https://doi.org/10.1587/transinf.2015EDP7363
#     Variantes de projeção da ONU.
#     https://www.prb.org/resource/understanding-population-projections-assumptions-behind-the-numbers/
#     Bonifácio e Guimarães, Texto para Discussão 2698, Ipea, 2021.
#   Entrada:
#     `pa`, `fim`, o último ano com saída decidida (`fim.year - 1`), `teto` (limita a
#     permanência em 1) e `regra`, um `RegraCenario`.
#   Resultado esperado:
#     Coluna `otimista` da tabela de `backtest` (uma linha por ano e faixa, com a faixa
#     `total`) e linhas do `metodo` correspondente em `projeta_futuro`.


def cenarios(
    pop: pd.DataFrame, saidas: pd.DataFrame, ate_ano: int, regra: RegraCenario
) -> dict[str, tuple[np.ndarray, float]]:
    """(permanência, novatos) de cada cenário, só com a série até `ate_ano`.

    pessimista  menor valor da janela; otimista  maior; conservador  a média dos dois (`extremos`)
    ou a média da janela toda (`media`), conforme `regra.conservador`.
    Os novatos saem em contagem ou em taxa, conforme `regra.novatos_por_taxa`;
    `_novatos_do_cenario` converte. Banda sem nenhum ano válido usa a
    permanência do último ano nos três cenários, a mesma do coorte.
    """
    inicio = int(pop.index.min()) + 1
    if regra.janela is not None:
        inicio = max(inicio, ate_ano - regra.janela + 1)
    historico = []
    for ano in range(inicio, ate_ano + 1):
        sr = permanencia(pop, ano)
        for a in range(BANDAS):
            if not saidas.loc[ano - 1, a] >= regra.min_saidas:
                sr[a] = np.nan
        historico.append(sr)
    h = pd.DataFrame(historico)
    menor = np.array(h.min(), dtype=float)
    maior = np.array(h.max(), dtype=float)
    ultimo = permanencia(pop, ate_ano)
    for a in range(BANDAS):
        if np.isnan(menor[a]):
            menor[a] = ultimo[a]
            maior[a] = ultimo[a]
    novatos = pop.loc[inicio:ate_ano, 0]
    if regra.novatos_por_taxa:
        ativos_antes = pop.sum(axis=1).shift(1).loc[inicio:ate_ano]
        novatos = novatos / ativos_antes
    if regra.conservador in ("media", "recentes"):
        recorte = h if regra.conservador == "media" else h.tail(2)
        novatos_do_meio = novatos if regra.conservador == "media" else novatos.tail(2)
        meio = (np.array(recorte.mean(), dtype=float), float(novatos_do_meio.mean()))
        for a in range(BANDAS):
            if np.isnan(meio[0][a]):
                meio[0][a] = ultimo[a]
    elif regra.conservador == "extremos":
        meio = ((menor + maior) / 2, float(novatos.min() + novatos.max()) / 2)
    else:
        raise ValueError(
            f"conservador {regra.conservador!r}: use 'extremos', 'media' ou 'recentes'."
        )
    return {
        "pessimista": (menor, float(novatos.min())),
        "conservador": meio,
        "otimista": (maior, float(novatos.max())),
    }


def _novatos_do_cenario(valor: float, p: np.ndarray, regra: RegraCenario) -> float:
    """Novatos do ano projetado a partir da pirâmide `p` do ano anterior."""
    if regra.novatos_por_taxa:
        return valor * float(p.sum())
    return valor


def _projecoes(
    pop: pd.DataFrame, saidas: pd.DataFrame, base: int, teto: bool, regra: RegraCenario
) -> dict[str, np.ndarray]:
    """Pirâmide de `base + 1` por cada método, usando só a série até `base`."""
    p = _bandas(pop.loc[base])
    novatos_coorte = (pop.loc[base, 0] + pop.loc[base - 1, 0]) / 2
    proj = {
        "ingenuo": p,
        "coorte": projeta_um_ano(p, permanencia(pop, base), novatos_coorte, teto),
    }
    for nome, (sr, valor) in cenarios(pop, saidas, base, regra).items():
        proj[nome] = projeta_um_ano(p, sr, _novatos_do_cenario(valor, p, regra), teto)
    return proj


def _por_faixa(v: np.ndarray) -> dict[str, float]:
    """Vetor de bandas de 1 ano somado nas faixas de apresentação, mais o total."""
    faixas = faixa_de(pd.Series(range(BANDAS)))
    soma = dict.fromkeys(FAIXAS, 0.0)
    for banda in range(BANDAS):
        soma[faixas[banda]] = soma[faixas[banda]] + v[banda]
    soma["total"] = float(v.sum())
    return soma


# Métrica: abre
#   O que é:
#     Erro relativo equilibrado de uma previsão: a diferença absoluta dividida pelo menor
#     dos dois valores, o real e o previsto.
#   Referência:
#     Onoue et al., IEICE16. https://doi.org/10.1587/transinf.2015EDP7363 Miyazaki et al.
#     definem o BRE.
#   Entrada:
#     `actual` e `predicted`, duas contagens não negativas.
#   Resultado esperado:
#     Um número. 0 é acerto. 0,5 é um erro de metade do menor dos dois valores. Vale igual
#     para quem previu a mais e para quem previu a menos. Vazio (NaN) se qualquer lado é
#     vazio ou zero.


def abre(actual: float, predicted: float) -> float:
    """Absolute Balanced Relative Error.

    IEICE16 p.1311 escreve os dois ramos com o denominador trocando de lado
    conforme o sinal de (x̂ − x). Como o ramo de cima vale quando x̂ ≥ x e usa x,
    e o de baixo vale quando x̂ < x e usa x̂, o denominador é sempre o MENOR dos
    dois, que é o BRE de Miyazaki et al. tal como publicado. Escrito com `min`
    aqui de propósito: a forma de dois ramos convida a inverter um sinal em
    revisão e o teste não pegaria (os ramos coincidem quando x = x̂).

    Simétrico por construção: abre(a, b) == abre(b, a).

    `nan` em qualquer lado propaga: é o canal por onde `project` sinaliza que o
    método não tem resposta para a célula (coorte órfã). Tratado explicitamente
    porque `min(x, nan)` em Python devolve o primeiro argumento em vez de nan,
    então sem esta guarda o resultado dependeria da ordem dos parâmetros.
    """
    if math.isnan(actual) or math.isnan(predicted):
        return float("nan")
    if actual < 0 or predicted < 0:
        raise ValueError(f"ABRE em contagem negativa: actual={actual} pred={predicted}")
    denom = min(actual, predicted)
    if denom == 0:
        # Uma das duas contagens é zero: o erro relativo não existe (divisão por
        # zero) e cravar 0.0 ou 1.0 aqui inventaria um acerto ou um erro máximo.
        # A mediana do artigo é sobre projetos onde os dois lados existem.
        return float("nan")
    return abs(predicted - actual) / denom


# Métrica: cobertura
#   O que é:
#     Em quantos casos o valor real ficou entre o pessimista e o otimista do backtest.
#   Referência:
#     Da pesquisa (Plano de Experimento).
#   Entrada:
#     `pa`, `fim`, o último ano com saída decidida (`fim.year - 1`), `teto` (limita a
#     permanência em 1) e `regra`, um `RegraCenario`.
#   Resultado esperado:
#     Coluna `cobre` da tabela de `backtest`: 1 quando o real ficou entre os dois, 0
#     quando não, vazia se faltou cenário. `resumo_backtest` traz a média por faixa e por
#     total.

# Métrica: erro_mediano
#   O que é:
#     A mediana do ABRE de cada método (ingenuo, coorte e conservador), sobre as mesmas
#     células de faixa. Mede qual método acerta mais.
#   Referência:
#     Onoue et al., IEICE16. https://doi.org/10.1587/transinf.2015EDP7363
#   Entrada:
#     `bt`, a tabela de `backtest`.
#   Resultado esperado:
#     Tabela `abre` de `resumo_backtest`: teto, celulas, cobertura_faixas, cobertura_total
#     e uma coluna por método com a mediana do ABRE. Menor é melhor.

# Métrica: wilcoxon
#   O que é:
#     Teste pareado entre métodos sobre o ABRE de cada célula: coorte contra ingênuo,
#     conservador contra ingênuo e conservador contra coorte.
#   Referência:
#     Onoue et al., IEICE16. https://doi.org/10.1587/transinf.2015EDP7363
#   Entrada:
#     `bt`, a tabela de `backtest`.
#   Resultado esperado:
#     Tabela `wilcoxon` de `resumo_backtest`: teto, comparacao e p. P abaixo de 0,05: um
#     método erra menos que o outro além do acaso. Vazio (NaN) quando a amostra não
#     sustenta o teste.


def backtest(
    pa: pd.DataFrame, fim: pd.Timestamp, ultimo_ano: int, teto: bool, regra: RegraCenario
) -> pd.DataFrame:
    """Prevê cada ano até `ultimo_ano` com a série anterior a ele, e mede o erro.

    Uma linha por (ano previsto, faixa de apresentação ou `total`): o real, o
    previsto por cada método, o ABRE de `METODOS_COM_ERRO` e `cobre`: 1 se o
    real ficou entre o pessimista e o otimista, 0 se não, `NaN` se faltou cenário.
    """
    pop = populacao_por_idade(pa)
    saidas = saidas_por_banda(pa, fim)
    linhas = []
    for alvo in range(int(pop.index.min()) + 2, ultimo_ano + 1):
        previsto = {}
        for metodo, v in _projecoes(pop, saidas, alvo - 1, teto, regra).items():
            previsto[metodo] = _por_faixa(v)
        real = _por_faixa(_bandas(pop.loc[alvo]))
        for faixa, valor in real.items():
            linha: dict[str, object] = {"ano": alvo, "faixa": faixa, "real": valor}
            for metodo in METODOS:
                linha[metodo] = previsto[metodo][faixa]
            for metodo in METODOS_COM_ERRO:
                linha[f"abre_{metodo}"] = abre(valor, previsto[metodo][faixa])
            baixo = previsto["pessimista"][faixa]
            alto = previsto["otimista"][faixa]
            if np.isnan(baixo) or np.isnan(alto):
                linha["cobre"] = np.nan
            else:
                linha["cobre"] = float(baixo <= valor <= alto)
            linhas.append(linha)
    bt = pd.DataFrame(linhas)
    bt.insert(0, "teto", teto)
    return bt


def _wilcoxon(a: np.ndarray, b: np.ndarray) -> float:
    """Wilcoxon pareado, bilateral. `nan` quando a amostra não sustenta o teste."""
    from scipy.stats import wilcoxon

    par = np.isfinite(a) & np.isfinite(b)
    a, b = a[par], b[par]
    if len(a) < 1 or np.allclose(a, b):
        return float("nan")
    try:
        return float(wilcoxon(a, b).pvalue)
    except ValueError:
        # Todos os pares com diferença zero: o teste não tem o que ranquear.
        return float("nan")


def resumo_backtest(bt: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Mediana do ABRE e cobertura por método, e Wilcoxon pareado entre métodos.

    ABRE e Wilcoxon usam as células de faixa (a linha `total` fica de fora) e
    só onde os três métodos têm ABRE, para que todos sejam medidos nas mesmas
    células. A cobertura sai das faixas e, à parte, do total de cada ano.
    """
    medianas = []
    testes = []
    for teto, g in bt[bt["faixa"] != "total"].groupby("teto"):
        colunas = [f"abre_{m}" for m in METODOS_COM_ERRO]
        completos = g.dropna(subset=colunas)
        total = bt[(bt["faixa"] == "total") & (bt["teto"] == teto)]
        linha = {
            "teto": teto,
            "celulas": len(completos),
            "cobertura_faixas": g["cobre"].mean(),
            "cobertura_total": total["cobre"].mean(),
        }
        for m in METODOS_COM_ERRO:
            linha[m] = completos[f"abre_{m}"].median()
        medianas.append(linha)
        for a, b in [("coorte", "ingenuo"), ("conservador", "ingenuo"), ("conservador", "coorte")]:
            p = _wilcoxon(
                completos[f"abre_{a}"].to_numpy(dtype=float),
                completos[f"abre_{b}"].to_numpy(dtype=float),
            )
            testes.append({"teto": teto, "comparacao": f"{a} x {b}", "p": p})
    return {"abre": pd.DataFrame(medianas), "wilcoxon": pd.DataFrame(testes)}


# Métrica: projecao_futura
#   O que é:
#     A projeção dos próximos `anos` anos depois do último ano observado, um ano por vez,
#     por cada método.
#   Referência:
#     Onoue et al., IEICE16. https://doi.org/10.1587/transinf.2015EDP7363
#     Variantes de projeção da ONU.
#     https://www.prb.org/resource/understanding-population-projections-assumptions-behind-the-numbers/
#     Bonifácio e Guimarães, Texto para Discussão 2698, Ipea, 2021.
#   Entrada:
#     `pa`, `fim`, o último ano com saída decidida (`fim.year - 1`), `teto` (limita a
#     permanência em 1) e `regra`, um `RegraCenario`. E `anos`, o horizonte (5).
#   Resultado esperado:
#     Tabela de `projeta_futuro`: ano, metodo, faixa e previsto. A faixa `total` soma as
#     outras.


def projeta_futuro(  # noqa: PLR0913, PLR0917
    pa: pd.DataFrame,
    fim: pd.Timestamp,
    ultimo_ano: int,
    anos: int,
    teto: bool,
    regra: RegraCenario,
) -> pd.DataFrame:
    """Projeta `anos` anos depois de `ultimo_ano`, um ano por vez.

    O coorte usa a permanência do último par observado e, como novatos, a
    média dos dois anos anteriores (já projetados, depois do primeiro passo).
    Cada cenário fixa a sua permanência e os seus novatos.
    """
    pop = populacao_por_idade(pa)
    p_ultimo = _bandas(pop.loc[ultimo_ano])
    sr_coorte = permanencia(pop, ultimo_ano)
    fixos = cenarios(pop, saidas_por_banda(pa, fim), ultimo_ano, regra)

    atual = dict.fromkeys(METODOS, p_ultimo)
    anterior_coorte = _bandas(pop.loc[ultimo_ano - 1])
    linhas = []
    for ano in range(ultimo_ano + 1, ultimo_ano + anos + 1):
        novatos = (atual["coorte"][0] + anterior_coorte[0]) / 2
        anterior_coorte = atual["coorte"]
        atual["coorte"] = projeta_um_ano(atual["coorte"], sr_coorte, novatos, teto)
        for nome, (sr, valor) in fixos.items():
            novatos_cenario = _novatos_do_cenario(valor, atual[nome], regra)
            atual[nome] = projeta_um_ano(atual[nome], sr, novatos_cenario, teto)
        for metodo in METODOS:
            for faixa, valor in _por_faixa(atual[metodo]).items():
                linhas.append({"ano": ano, "metodo": metodo, "faixa": faixa, "previsto": valor})
    return pd.DataFrame(linhas)


# ================================================================================================
# CCR e NCR (RQ1 e RQ2): equilíbrio da população por trimestre
# ================================================================================================

# Métrica: ccr
#   O que é:
#     CCR = (código - discussão) / o maior dos dois. Compara quem faz código com quem só
#     discute. Lado do código: o primeiro commit ou PR é de antes do fim do trimestre.
#     População do trimestre: quem contribuiu na janela de inatividade até o fim dele.
#     A replicação faz a mesma conta sobre pirâmides em `metrics.from_pyramids`.
#   Referência:
#     Onoue et al., IEICE16. https://doi.org/10.1587/transinf.2015EDP7363
#   Entrada:
#     `eventos`, `inatividade_dias`, `novato_dias` e `fim`. O estudo usa 12 meses nos dois
#     cortes (`ccr_ncr_inatividade_meses` e `ccr_ncr_novato_meses`). Os padrões da função,
#     3 e 3 meses, reproduzem o IEICE16.
#   Resultado esperado:
#     Coluna `ccr` da tabela de `ccr_ncr_trimestral`, uma linha por trimestre (snapshot,
#     coding, non_coding, new, experienced, total, ccr, ncr e type). Entre -1 e 1. Perto
#     de 0: os dois lados são parecidos. Perto de 1: quase só código. Vazio se o trimestre
#     não tem ninguém ativo.

# Métrica: ncr
#   O que é:
#     NCR = (novatos - experientes) / o maior dos dois. Novato é quem tem até
#     `novato_dias` de idade, contada do primeiro commit ou PR (ou, sem ele, da primeira
#     discussão).
#     A replicação faz a mesma conta sobre pirâmides em `metrics.from_pyramids`.
#   Referência:
#     Onoue et al., IEICE16. https://doi.org/10.1587/transinf.2015EDP7363
#   Entrada:
#     `eventos`, `inatividade_dias`, `novato_dias` e `fim`. O estudo usa 12 meses nos dois
#     cortes (`ccr_ncr_inatividade_meses` e `ccr_ncr_novato_meses`). Os padrões da função,
#     3 e 3 meses, reproduzem o IEICE16.
#   Resultado esperado:
#     Coluna `ncr` da tabela de `ccr_ncr_trimestral`, uma linha por trimestre (snapshot,
#     coding, non_coding, new, experienced, total, ccr, ncr e type). Entre -1 e 1. Perto
#     de 1: quase só novatos. Perto de -1: quase só experientes.

# Métrica: tipo_ccr_ncr
#   O que é:
#     O tipo do trimestre pelo sinal dos dois: A, CCR > 0 e NCR > 0 (mais código e mais
#     novatos). B, CCR < 0 e NCR > 0 (mais discussão e mais novatos). C, CCR > 0 e NCR < 0
#     (mais código e mais experientes). D, CCR < 0 e NCR < 0 (mais discussão e mais
#     experientes). Zero exato cai do lado baixo.
#     A replicação faz a mesma conta sobre pirâmides em `metrics.from_pyramids`.
#   Referência:
#     Onoue et al., IEICE16. https://doi.org/10.1587/transinf.2015EDP7363
#   Entrada:
#     `eventos`, `inatividade_dias`, `novato_dias` e `fim`. O estudo usa 12 meses nos dois
#     cortes (`ccr_ncr_inatividade_meses` e `ccr_ncr_novato_meses`). Os padrões da função,
#     3 e 3 meses, reproduzem o IEICE16.
#   Resultado esperado:
#     Coluna `type` da tabela de `ccr_ncr_trimestral`, uma linha por trimestre (snapshot,
#     coding, non_coding, new, experienced, total, ccr, ncr e type). Uma letra de A a D.
#     Trimestre sem ninguém ativo fica de fora, sem tipo.


def _tipo_ccr_ncr(ccr: float, ncr: float) -> str | None:
    """Tipo A a D pelo sinal dos dois. Zero cai do lado baixo, como em `metrics._type_of`."""
    if not (np.isfinite(ccr) and np.isfinite(ncr)):
        return None
    return {(True, True): "A", (False, True): "B", (True, False): "C", (False, False): "D"}[
        (ccr > 0, ncr > 0)
    ]


def _razao(a: float, b: float) -> float:
    """(a - b) / max(a, b), como `metrics.ratio`. Indefinida sem ninguém."""
    maior = max(a, b)
    return float("nan") if maior == 0 else (a - b) / maior


def ccr_ncr_trimestral(
    eventos: pd.DataFrame,
    inatividade_dias: float = INATIVIDADE_CCR_DIAS,
    novato_dias: float = NOVATO_DIAS,
    fim: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """CCR e NCR por trimestre (IEICE16), direto dos eventos compactados.

    Mesma conta do motor (`snapshots.pyramid_at` e `metrics.from_pyramids`), sem o pipeline:

      população   quem contribuiu nos 3 meses até o fim do trimestre (`active`)
      lado        código se o primeiro commit ou PR é de antes do fim do trimestre
                  (inclui o `moved`), senão discussão
      novato      idade até 91 dias (3 meses), contada do primeiro commit ou PR (ou, sem ele, da
                  primeira discussão)
      CCR         (código - discussão) / o maior dos dois
      NCR         (novatos - experientes) / o maior dos dois

    O último evento de cada pessoa até o fim do trimestre é o último do trimestre dela, que a
    compactação guarda, então a conta é exata. `inatividade_dias` e `novato_dias` trocam os 3
    meses por outro corte, para a sensibilidade. Com `fim`, o último trimestre da série é o
    último que termina até `fim`; sem ele, vale a regra do motor, que para um trimestre antes
    do último evento.
    """
    ev = eventos[["contributor_id", "event_type", "timestamp"]].sort_values("timestamp")
    codou = ev["event_type"].isin(TIPOS_CODING)
    primeiro_codigo = ev[codou].groupby("contributor_id")["timestamp"].min()
    primeira_discussao = ev[~codou].groupby("contributor_id")["timestamp"].min()
    instantes = ev["timestamp"].to_numpy()
    pessoas = ev["contributor_id"].to_numpy()

    inicio = (ev["timestamp"].min() + pd.offsets.QuarterEnd(0)).normalize()
    if fim is None:
        ultimo = (ev["timestamp"].max() - pd.offsets.QuarterEnd(1)).normalize()
    else:
        ultimo = (fim + pd.offsets.QuarterEnd(0)).normalize()
        if ultimo > fim.normalize():
            ultimo = (ultimo - pd.offsets.QuarterEnd(1)).normalize()
    janela = np.timedelta64(int(inatividade_dias * 86400), "s")
    linhas = []
    for t in pd.date_range(inicio, ultimo, freq="QE"):
        de = np.searchsorted(instantes, (t - pd.Timedelta(janela)).to_datetime64(), side="left")
        ate = np.searchsorted(instantes, t.to_datetime64(), side="right")
        ativos = pd.unique(pessoas[de:ate])
        if len(ativos) == 0:
            continue
        codigo = primeiro_codigo.reindex(ativos)
        discussao = primeira_discussao.reindex(ativos)
        do_lado_do_codigo = (codigo <= t).to_numpy()
        origem = codigo.where(do_lado_do_codigo, discussao)
        idade_dias = ((t - origem).dt.total_seconds() / 86400.0).clip(lower=0.0)
        novatos = int((idade_dias <= novato_dias).sum())
        n_codigo = int(do_lado_do_codigo.sum())
        n_discussao = len(ativos) - n_codigo
        ccr = _razao(n_codigo, n_discussao)
        ncr = _razao(novatos, len(ativos) - novatos)
        linhas.append(
            {
                "snapshot": t,
                "coding": n_codigo,
                "non_coding": n_discussao,
                "new": novatos,
                "experienced": len(ativos) - novatos,
                "total": len(ativos),
                "ccr": ccr,
                "ncr": ncr,
                "type": _tipo_ccr_ncr(ccr, ncr),
            }
        )
    return pd.DataFrame(linhas)


# ================================================================================================
# Magnetismo e stickiness (RQ2)
# ================================================================================================


def pares_de_codigo(eventos: pd.DataFrame) -> pd.DataFrame:
    """(scope_id, contributor_id, year) único, só de commits e pull_requests.

    `eventos` traz a coluna `scope_id`: a linguagem (ou o projeto) de cada evento.
    """
    codigo = eventos[eventos["event_type"].isin(TIPOS_CODING)]
    pares = pd.DataFrame(
        {
            "scope_id": codigo["scope_id"].to_numpy(),
            "contributor_id": codigo["contributor_id"].to_numpy(),
            "year": codigo["timestamp"].dt.year.to_numpy(),
        }
    )
    return pares.drop_duplicates().reset_index(drop=True)


# Métrica: stickiness
#   O que é:
#     stickiness(P, Y) = devs de P em Y que contribuem em Y+1 / devs de P em Y. A fração
#     de quem contribuiu num ano e volta no ano seguinte, no mesmo escopo. Só commits e
#     PRs contam.
#   Referência:
#     Yamashita et al., MSR 2014. https://doi.org/10.1145/2597073.2597116
#     Ferreira, Silva e Valente, SBES 2020. https://doi.org/10.1145/3422392.3422433
#     ESEM14, seção 3.1.
#   Entrada:
#     `pairs`: uma linha única por (scope_id, contributor_id, year), só de commits e
#     pull_requests (`pares_de_codigo` monta a partir dos eventos). Para o magnetismo, com
#     todas as linguagens juntas.
#   Resultado esperado:
#     Coluna `stickiness` da tabela de `atratividade_anual`, uma linha por (scope_id,
#     year): devs, newcomers_here, newcomers_total, retained, magnetism, stickiness,
#     eligible, median_magnetism, median_stickiness, quadrant, left_censored e
#     right_censored. 0 a 1. Com 0,6, 6 de cada 10 pessoas do ano voltaram no seguinte. O
#     último ano fica sem stickiness, porque falta o ano seguinte. Se o último ano da
#     coleta é incompleto, o ano anterior subestima: quem volta depois do fim conta como
#     perdido.

# Métrica: magnetismo
#   O que é:
#     magnetismo(P, Y) = novatos de Y que contribuíram em P / novatos de Y em todos os
#     escopos. A fração dos novatos do ano que escolheram a linguagem. O plano adia o uso:
#     o denominador só representa o GitHub com todas as linguagens coletadas.
#   Referência:
#     Yamashita et al., MSR 2014. https://doi.org/10.1145/2597073.2597116
#     Ferreira, Silva e Valente, SBES 2020. https://doi.org/10.1145/3422392.3422433
#     ESEM14, seção 3.1.
#   Entrada:
#     `pairs`: uma linha única por (scope_id, contributor_id, year), só de commits e
#     pull_requests (`pares_de_codigo` monta a partir dos eventos). Para o magnetismo, com
#     todas as linguagens juntas.
#   Resultado esperado:
#     Coluna `magnetism` da tabela de `atratividade_anual`, uma linha por (scope_id,
#     year): devs, newcomers_here, newcomers_total, retained, magnetism, stickiness,
#     eligible, median_magnetism, median_stickiness, quadrant, left_censored e
#     right_censored. 0 a 1, com as colunas newcomers_here (novatos na linguagem no ano) e
#     newcomers_total (novatos de todas). Magnetismo 0,3: 3 de cada 10 novatos do ano
#     foram para ela. Fica fora da execução padrão (`--metricas magnetismo`).

# Métrica: quadrante
#   O que é:
#     Cruza magnetismo e stickiness com a mediana anual dos escopos elegíveis (mais de 10
#     ativos no ano): attractive (os dois acima da mediana), floating (magnetismo acima,
#     stickiness abaixo), stagnant (magnetismo abaixo, stickiness acima) e terminal (os
#     dois abaixo). Empate na mediana cai do lado baixo.
#   Referência:
#     Yamashita et al., MSR 2014. https://doi.org/10.1145/2597073.2597116
#     Ferreira, Silva e Valente, SBES 2020. https://doi.org/10.1145/3422392.3422433
#     ESEM14, seção 3.1.
#   Entrada:
#     `pairs`: uma linha única por (scope_id, contributor_id, year), só de commits e
#     pull_requests (`pares_de_codigo` monta a partir dos eventos). Para o magnetismo, com
#     todas as linguagens juntas.
#   Resultado esperado:
#     Coluna `quadrant` da tabela de `atratividade_anual`, uma linha por (scope_id, year):
#     devs, newcomers_here, newcomers_total, retained, magnetism, stickiness, eligible,
#     median_magnetism, median_stickiness, quadrant, left_censored e right_censored. Uma
#     das quatro palavras, ou vazio se o escopo não é elegível no ano.


def _voltaram_no_ano_seguinte(pairs: pd.DataFrame) -> pd.DataFrame:
    """Linhas (scope_id, contributor_id, year) em que a pessoa reaparece em Y+1 no mesmo escopo."""
    chaves = ["scope_id", "contributor_id", "year"]
    seguinte = pairs[chaves].assign(year=pairs["year"] - 1)
    return pairs.merge(seguinte, on=chaves, how="inner")


def atratividade_anual(pairs: pd.DataFrame, min_devs: int = 10) -> pd.DataFrame:
    """Uma linha por (escopo, ano) com magnetismo, stickiness e quadrante.

    `min_devs` é o `min_active_devs` do `settings.yaml`: o escopo só é elegível com mais devs que
    isso no ano. O corte é a mediana anual dos elegíveis.
    """
    colunas = [
        "scope_id",
        "year",
        "devs",
        "newcomers_here",
        "newcomers_total",
        "retained",
        "magnetism",
        "stickiness",
        "eligible",
        "median_magnetism",
        "median_stickiness",
        "quadrant",
        "left_censored",
        "right_censored",
    ]
    if pairs.empty:
        return pd.DataFrame(columns=colunas)

    pairs = pairs.drop_duplicates()
    first_year = pairs.groupby("contributor_id")["year"].min()
    novato = pairs["contributor_id"].map(first_year) == pairs["year"]

    per = (
        pairs.assign(_novato=novato)
        .groupby(["scope_id", "year"], as_index=False)
        .agg(devs=("contributor_id", "nunique"), newcomers_here=("_novato", "sum"))
    )

    # Denominador do magnetismo: novatos do ANO, no conjunto inteiro de escopos.
    novatos_ano = first_year.value_counts().rename("newcomers_total")
    per = per.merge(novatos_ano, left_on="year", right_index=True, how="left")
    per["newcomers_total"] = per["newcomers_total"].fillna(0).astype("int64")

    ret = (
        _voltaram_no_ano_seguinte(pairs)
        .groupby(["scope_id", "year"], as_index=False)
        .agg(retained=("contributor_id", "nunique"))
    )
    per = per.merge(ret, on=["scope_id", "year"], how="left")
    per["retained"] = per["retained"].fillna(0).astype("int64")

    per["magnetism"] = np.where(
        per["newcomers_total"] > 0, per["newcomers_here"] / per["newcomers_total"], np.nan
    )
    per["stickiness"] = np.where(per["devs"] > 0, per["retained"] / per["devs"], np.nan)

    anos = pairs["year"]
    y_min, y_max = int(anos.min()), int(anos.max())
    # Y == y_min: quem "estreia" ali pode ser veterano cuja história ficou fora dos dados.
    # Y == y_max: Y+1 não existe, a stickiness é indefinida (não zero).
    per["left_censored"] = per["year"] <= y_min
    per["right_censored"] = per["year"] >= y_max
    per.loc[per["right_censored"], "stickiness"] = np.nan

    per["eligible"] = (
        (per["devs"] > min_devs) & per["magnetism"].notna() & per["stickiness"].notna()
    )
    el = per[per["eligible"]]
    per["median_magnetism"] = per["year"].map(el.groupby("year")["magnetism"].median())
    per["median_stickiness"] = per["year"].map(el.groupby("year")["stickiness"].median())

    # Empate na mediana cai do lado BAIXO: alto = valor > corte.
    alto_m = per["magnetism"] > per["median_magnetism"]
    alto_s = per["stickiness"] > per["median_stickiness"]
    per["quadrant"] = [
        QUADRANTES[(bool(m), bool(s))] if e else None
        for m, s, e in zip(alto_m, alto_s, per["eligible"], strict=True)
    ]
    return per.sort_values(["year", "scope_id"])[colunas].reset_index(drop=True)


# ================================================================================================
# Índice: cada métrica, a função e a coluna; cada linha do registro e as métricas
# ================================================================================================

# nome da métrica -> (função que calcula, coluna do resultado onde ela aparece).
# Coluna `None`: a métrica é o resultado inteiro da função.
CATALOGO.update(
    {
        "ativos": (tabela_anual, "ativos"),
        "novatos": (tabela_anual, "novatos"),
        "saidas": (tabela_anual, "saidas"),
        "pausas": (tabela_anual, "pausas"),
        "voltas": (tabela_anual, "voltas"),
        "moved": (tabela_anual, "moved"),
        "deixou_codigo": (tabela_anual, "deixou_codigo"),
        "natalidade": (tabela_anual, "natalidade_pct"),
        "mortalidade": (tabela_anual, "mortalidade_pct"),
        "crescimento_natural": (tabela_anual, "crescimento_natural_pct"),
        "saida_pct": (trajetoria, "saida_pct"),
        "volta_pct": (trajetoria, "volta_pct"),
        "novato_pct": (trajetoria, "novato_pct"),
        "reposicao": (trajetoria, "reposicao"),
        "indice_de_ativos": (trajetoria, "indice"),
        "piramide": (composicao, None),
        "piramide_trimestral": (composicao_trimestral, None),
        "piramide_em_pct": (composicao_em_pct, None),
        "indice_envelhecimento": (indice_envelhecimento, "indice"),
        "sobreviventes": (tabua_de_vida, "l"),
        "saidas_da_tabua": (tabua_de_vida, "d"),
        "chance_de_sair": (tabua_de_vida, "q"),
        "fracao_que_chega": (tabua_de_vida, "S"),
        "esperanca_restante": (tabua_de_vida, "e"),
        "intervalo_de_q": (tabua_de_vida, "q_inf"),
        "tabua_por_coorte": (tabuas_por_coorte, None),
        "chance_de_seguir": (chance_de_seguir, None),
        "taxa_saida_por_faixa": (taxa_saida_por_faixa, "taxa_saida"),
        "taxa_bruta": (padronizacao, "taxa_bruta"),
        "taxa_padronizada": (padronizacao, "taxa_padronizada"),
        "taxa_padronizada_ate_5a": (padronizacao, "taxa_padronizada_ate_5a"),
        "saidas_esperadas": (padronizacao, "saidas_esperadas"),
        "smr": (padronizacao, "smr"),
        "kaplan_meier": (kaplan_meier, "S"),
        "logrank": (logrank, None),
        "taxa_de_permanencia": (permanencia, None),
        "projecao_ingenua": (backtest, "ingenuo"),
        "projecao_coorte": (backtest, "coorte"),
        "cenario_pessimista": (backtest, "pessimista"),
        "cenario_conservador": (backtest, "conservador"),
        "cenario_otimista": (backtest, "otimista"),
        "abre": (abre, None),
        "cobertura": (backtest, "cobre"),
        "erro_mediano": (resumo_backtest, "abre"),
        "wilcoxon": (resumo_backtest, "wilcoxon"),
        "projecao_futura": (projeta_futuro, "previsto"),
        "ccr": (ccr_ncr_trimestral, "ccr"),
        "ncr": (ccr_ncr_trimestral, "ncr"),
        "tipo_ccr_ncr": (ccr_ncr_trimestral, "type"),
        "stickiness": (atratividade_anual, "stickiness"),
        "magnetismo": (atratividade_anual, "magnetism"),
        "quadrante": (atratividade_anual, "quadrant"),
    }
)

# linha do registro `METRICAS` de scripts/vitalidade.py -> métricas dela.
REGISTRO.update(
    {
        "tamanho": (
            "ativos",
            "novatos",
            "saidas",
            "pausas",
            "voltas",
            "moved",
            "deixou_codigo",
            "natalidade",
            "mortalidade",
            "crescimento_natural",
        ),
        "composicao": ("piramide", "piramide_trimestral", "indice_envelhecimento"),
        "retencao": (
            "sobreviventes",
            "saidas_da_tabua",
            "chance_de_sair",
            "fracao_que_chega",
            "esperanca_restante",
            "intervalo_de_q",
            "tabua_por_coorte",
        ),
        "saida_por_faixa": ("taxa_saida_por_faixa",),
        "cenarios": (
            "taxa_de_permanencia",
            "projecao_ingenua",
            "projecao_coorte",
            "cenario_pessimista",
            "cenario_conservador",
            "cenario_otimista",
            "abre",
            "cobertura",
            "erro_mediano",
            "wilcoxon",
            "projecao_futura",
        ),
        "ccr_ncr": ("ccr", "ncr", "tipo_ccr_ncr"),
        "ccr_ncr_comparado": ("ccr", "ncr", "tipo_ccr_ncr"),
        "stickiness": ("stickiness",),
        "significancia": ("kaplan_meier", "logrank"),
        "tabua_comparada": (
            "sobreviventes",
            "saidas_da_tabua",
            "chance_de_sair",
            "fracao_que_chega",
            "esperanca_restante",
            "intervalo_de_q",
            "chance_de_seguir",
        ),
        "comparacao_corrigida": (
            "taxa_bruta",
            "taxa_padronizada",
            "taxa_padronizada_ate_5a",
            "saidas_esperadas",
            "smr",
        ),
        "trajetoria": (
            "saida_pct",
            "volta_pct",
            "novato_pct",
            "reposicao",
            "indice_de_ativos",
            "piramide_em_pct",
        ),
        "magnetismo": ("magnetismo", "quadrante"),
    }
)
