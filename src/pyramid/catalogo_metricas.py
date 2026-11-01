"""Catálogo das métricas de vitalidade de uma comunidade de software.

Este arquivo reúne tudo que se calcula sobre uma comunidade de desenvolvedores: quantas pessoas
entram e saem por ano, qual a idade da comunidade, quanto tempo cada pessoa fica e como a
população deve evoluir nos próximos anos. Quem nunca viu o estudo consegue ler aqui o que cada
métrica mede, de onde a ideia vem e como a conta é feita.

Perguntas do estudo (Plano de Experimento):

- RQ1: Como evoluíram as entradas e saídas de desenvolvedores de uma linguagem ao longo dos anos?
- RQ2: A linguagem atrai e retém desenvolvedores melhor ou pior que outras?
- RQ3: Qual método de projeção estima com mais acerto a população futura?

Como ler este arquivo

Cada métrica tem um bloco de comentário que começa com `# Métrica: nome` e traz quatro partes:

- O que é: a definição em palavras simples.
- Referência: o artigo ou a norma de onde a ideia vem.
- Entrada: o que a função recebe.
- Resultado esperado: o que ela devolve e como ler o número.

O código que calcula vem logo abaixo do bloco, na ordem do Plano de Experimento. O arquivo roda
sozinho, só com pandas, numpy e scipy, e não importa nada do pacote `pyramid`.

O código repete o do motor (`src/pyramid/vitalidade.py`, `projection.py` e `attractiveness.py`).
O teste `tests/test_catalogo_metricas.py` roda o catálogo e o motor sobre os mesmos eventos e exige
o mesmo resultado. Se o motor mudar, o teste falha até este arquivo ser atualizado. Uma etapa do
motor fica de fora: a `compacta`, que reduz os eventos de coletas de centenas de GB para caber na
memória. Ela não muda nenhum resultado, e as funções daqui aceitam os eventos inteiros.

`CATALOGO` liga cada métrica à função que a calcula e à coluna do resultado onde ela aparece.
`REGISTRO` agrupa as métricas do mesmo jeito que o registro `METRICAS` de `scripts/vitalidade.py`.

O que entra: os eventos

Entrada comum a todas as métricas. É um DataFrame em que cada linha é uma ação de uma pessoa (um
commit, um comentário numa issue e assim por diante), com três colunas:

    contributor_id  identificador estável da pessoa
    event_type      commits, pull_requests, commit_comments, issue_comments,
                    pull_request_comments, issue_events ou issues
    timestamp       data e hora do evento (datetime64)

Eventos de código são `commits` e `pull_requests` (`TIPOS_CODING`). Os outros cinco tipos são
discussão. O contrato completo da entrada está em `docs/ferramenta/FONTES.md`.

Do evento à métrica:

    fim = eventos["timestamp"].max()
    pa = pessoa_ano(eventos, fim, com_moved_to_discussion=False)
    dur = duracoes(eventos, fim)
    anual = tabela_anual(pa, fim)

`fim` é a data e hora do último evento da coleta. O estudo analisa até 31/12/2025
(`data_de_corte`). Os eventos de 2026 só servem para saber quem saiu e quem fez pausa em 2025.

Tabelas que passam de uma função para outra:

- `pa` (de `pessoa_ano`): uma linha por pessoa e por ano em que ela contribuiu. Traz a idade na
  linguagem, a faixa de idade e se a pessoa é novata, saiu, fez pausa ou voltou naquele ano.
- `anual` (de `tabela_anual`): uma linha por ano, com os totais.
- `dur` (de `duracoes`): uma linha por pessoa, com quando entrou, quando fez o último evento,
  quantos anos ficou e se já saiu.
- `tabua` (de `tabua_de_vida`): como um grupo que entrou junto vai diminuindo com os anos.
- `bt` (de `backtest`): a previsão de anos que já passaram, comparada ao que aconteceu.
- `pairs` (de `pares_de_codigo`): a lista de (escopo, pessoa, ano) em que houve commit ou PR.
  Escopo é a unidade analisada: uma linguagem ou um projeto.

Vocabulário emprestado da demografia, usado como analogia:

- Idade: o tempo desde a primeira contribuição na linguagem.
- Nascimento: a primeira contribuição.
- Saída (óbito): 12 meses sem contribuir.
- Coorte: o grupo de pessoas que entrou no mesmo ano.

Convenções do estudo, valem para todas as métricas:

- Saída: 12 meses sem contribuir (Avelino et al., ESEM 2019). A replicação do IEICE16 usa 3
  meses.
- Faixas de idade: 0-1, 1-2, 2-3, 3-5, 5-8 e 8+ anos na linguagem. A idade no ano Y é Y menos o
  ano da primeira contribuição. Quem entrou em Y está na faixa 0-1.
- Ano em aberto: a saída do ano Y só se decide 12 meses depois de 31/12/Y, porque é preciso
  esperar para ver se a pessoa volta. Se a coleta termina antes, a saída desse ano fica vazia
  (NaN). Estimar o ano inteiro a partir de um ano incompleto é proibido.
- Quem entra na conta: a pirâmide conta os residentes (população `mais_de_uma_ocasiao`), que são
  as pessoas com mais de uma contribuição em ocasiões diferentes. O filtro lê
  `origem/pessoas.parquet` e mora em `scripts/vitalidade.py` (`filtra_populacao`). As funções
  daqui recebem os eventos que sobraram depois dele.

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

# As quatro categorias da pirâmide no fim do ano. Lado esquerdo: quem só discute (`non_coding`)
# e quem já fez código e passou a só discutir (`moved_to_discussion`). Lado direito: quem
# começou pela discussão e passou a fazer código (`moved`) e quem começou pelo código
# (`coding`).
LADOS = ["non_coding", "moved_to_discussion", "moved", "coding"]
BAND_DIAS = 90  # fatia de idade de 90 dias (um trimestre), como o `band_days` do IEICE16

NOVATO_DIAS = round(3 * DAYS_PER_MONTH)  # 91 dias: novato tem até 3 meses de idade (IEICE16)
# Quem passa mais de 3 meses sem contribuir sai do trimestre (IEICE16: "did not give any
# contribution for more than 3 months").
INATIVIDADE_CCR_DIAS = 3 * DAYS_PER_MONTH

BANDAS = 9  # idades 0 a 7 e 8 ou mais, uma posição por idade
METODOS = ["ingenuo", "coorte", "pessimista", "conservador", "otimista"]
METODOS_COM_ERRO = ["ingenuo", "coorte", "conservador"]

# Acima desse número de pontos, a curva de Kaplan-Meier guarda um ponto por dia. Sem isso,
# milhões de pessoas dariam um ponto por pessoa.
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
# Base: períodos de atividade de cada pessoa e uma linha por pessoa e ano
# ================================================================================================

# Base, sem métrica própria. `pessoa_ano` é a tabela de onde saem os totais por ano (ativos,
# novatos, saídas, pausas, voltas e moved) e a pirâmide. `periodos` parte a vida de cada pessoa
# em períodos de atividade, separados por mais de 12 meses sem contribuir.


def faixa_de(anos: pd.Series) -> pd.Series:
    """Faixa de idade na linguagem. Quem tem exatamente 1 ano cai em 1-2."""
    return pd.cut(anos, bins=_CORTES, right=False, labels=FAIXAS)


def ano_fechado(ano: int, fim: pd.Timestamp) -> bool:
    """Verdadeiro se a coleta cobre os 12 meses seguintes ao fim de `ano`.

    Nesse caso já dá para saber quem saiu naquele ano.
    """
    return fim > pd.Timestamp(f"{ano + 1}-01-01") + pd.Timedelta(days=GAP_DIAS)


def ano_completo(ano: int, fim: pd.Timestamp) -> bool:
    """Verdadeiro se `ano` terminou antes do fim da coleta. O ano da coleta fica de fora."""
    return ano < fim.year


def provisorio(ano: int, fim: pd.Timestamp) -> bool:
    """Ano que já acabou, mas sem os 12 meses de coleta depois dele. Vale como estimativa.

    Quem fez a última contribuição nesse ano conta como saída, mesmo sem 12 meses de silêncio
    confirmados. Quem voltar depois do fim da coleta continua contado como saída.
    """
    return ano_completo(ano, fim) and not ano_fechado(ano, fim)


def periodos(eventos: pd.DataFrame) -> pd.DataFrame:
    """Parte a vida de cada pessoa em períodos de atividade, um período por linha.

    Um período termina quando a pessoa passa mais de 12 meses sem contribuir. Quem volta depois
    começa outro período. Cada linha traz também o primeiro e o último evento de código e de
    discussão da pessoa.

    Dá o mesmo resultado de `classify.profile(eventos, TIPOS_CODING, GAP_DIAS)`, em uma passada
    só, sem laço por pessoa. Há uma diferença: dois eventos do mesmo ano de calendário ficam
    sempre no mesmo período, mesmo com mais de 365,25 dias entre eles. Isso só acontece em ano
    bissexto. Um teste confere as duas versões nos demais casos.
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
    # Dois eventos do mesmo ano de calendário ficam sempre no mesmo período. Num ano bissexto,
    # 1/jan e 31/dez distam mais de 365,25 dias. Sem esta regra a pessoa teria duas saídas no
    # mesmo ano, e a tabela anual não sabe contar isso. Entre 4,2 milhões de pessoas do Python,
    # só uma caiu nesse caso.
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
    """Uma linha por pessoa e por ano em que ela contribuiu. Toda métrica anual sai daqui.

    `fim` é a data e hora do último evento coletado. Sem ele, vale o evento mais recente.
    Com `com_moved_to_discussion=False` a categoria `moved_to_discussion` some. Quem já fez
    commit ou PR e neste ano só discutiu fica na categoria que a história dele indica, `moved`
    ou `coding`.
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

    # Marca quem fez commit ou PR em cada ano. A redução dos eventos guarda o último evento de
    # código de cada trimestre, então saber se houve código no ano continua exato.
    com_codigo = ev[ev["event_type"].isin(TIPOS_CODING)]
    anos_com_codigo = com_codigo.assign(ano=com_codigo["timestamp"].dt.year)[
        ["contributor_id", "ano"]
    ].drop_duplicates()
    anos_com_codigo["codou_no_ano"] = True
    pa = pa.merge(anos_com_codigo, on=["contributor_id", "ano"], how="left")
    codou_no_ano = pa.pop("codou_no_ano").fillna(False).astype(bool)

    fim_ano = pd.to_datetime((pa["ano"] + 1).astype(str) + "-01-01")
    # Idade em anos de calendário: ano da contribuição menos ano da primeira contribuição. Cada
    # idade é uma coorte de entrada, e a projeção por coorte precisa disso para envelhecer a
    # população 1 ano por vez.
    pa["idade_anos"] = pa["ano"] - pa["primeiro"].dt.year
    # Idade em dias no fim do ano, usada na pirâmide de fatias de 90 dias do artigo.
    pa["idade_dias"] = (fim_ano.clip(upper=fim) - pa["primeiro"]).dt.days
    pa["faixa"] = faixa_de(pa["idade_anos"])
    pa["novato"] = pa["primeiro"].dt.year == pa["ano"]

    # O lado da pirâmide sai da mesma regra de `snapshots.pyramid_at`, aplicada no fim do ano.
    # `codou`: já fez commit ou PR até o fim do ano. `comecou_na_discussao`: o primeiro evento
    # de discussão veio antes do primeiro commit ou PR.
    codou = pa["init_c"].notna() & (pa["init_c"] < fim_ano)
    comecou_na_discussao = codou & pa["init_d"].notna() & (pa["init_d"] < pa["init_c"])
    # O caminho de volta do `moved`: quem já fez código antes e neste ano só discutiu. Quem fez
    # algum commit ou PR no ano fica do lado do código, mesmo que o último evento do ano seja
    # um comentário.
    foi_para_discussao = codou & ~codou_no_ano & com_moved_to_discussion
    pa["categoria"] = np.select(
        [~codou, foi_para_discussao, comecou_na_discussao],
        ["non_coding", "moved_to_discussion", "moved"],
        default="coding",
    )
    # O ano em que quem começou pela discussão fez o primeiro commit ou PR.
    pa["moved_no_ano"] = comecou_na_discussao & (pa["init_c"].dt.year == pa["ano"])
    # A pessoa para de fazer código e depois só discute. O ano é o do último commit ou PR. Isso
    # só se sabe olhando o futuro, porque quem voltar a fazer commit deixa de contar.
    deixou = pa["last_c"].notna() & pa["last_d"].notna() & (pa["last_d"] > pa["last_c"])
    pa["deixou_codigo_no_ano"] = deixou & (pa["last_c"].dt.year == pa["ano"])

    # Todo período que não é o último já termina com mais de 12 meses de silêncio (foi isso que o
    # separou do seguinte), então basta medir a distância até `fim`.
    # Saída é o fim do último período, o da vida inteira. Quem para e depois volta fez uma pausa.
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

    # Dois períodos separados por mais de 12 meses não terminam nem começam no mesmo ano.
    if pa.duplicated(["contributor_id", "ano"]).any():
        raise ValueError("pessoa_ano: (pessoa, ano) repetido; mais de uma saída ou volta no ano.")
    return pa.drop(columns=["init_c", "init_d", "last_c", "last_d"]).reset_index(drop=True)


# ================================================================================================
# Tamanho (RQ1.1): quantas pessoas entram e saem por ano
# ================================================================================================

# Métrica: ativos
#   O que é:
#     Quantas pessoas contribuíram na linguagem naquele ano. Uma contribuição basta para a pessoa
#     contar.
#   Referência:
#     Da pesquisa (Plano de Experimento).
#   Entrada:
#     `pa`, a tabela de pessoas por ano (`pessoa_ano`), e `fim`, a data e hora do último evento
#     coletado.
#   Resultado esperado:
#     Coluna `ativos` da `tabela_anual`, um número inteiro por ano.
#     Exemplo: 1.200 em 2021 quer dizer que 1.200 pessoas diferentes contribuíram em 2021.

# Métrica: novatos
#   O que é:
#     Quantas pessoas fizeram, naquele ano, a primeira contribuição da vida na linguagem. Elas
#     ficam na faixa de idade 0-1.
#   Referência:
#     Foucault et al., ESEC/FSE 2015.
#     https://doi.org/10.1145/2786805.2786870
#   Entrada:
#     `pa`, a tabela de pessoas por ano (`pessoa_ano`), e `fim`, a data e hora do último evento
#     coletado.
#   Resultado esperado:
#     Coluna `novatos` da `tabela_anual`, um número inteiro por ano.
#     Exemplo: 300 em 2021 quer dizer que 300 pessoas contribuíram pela primeira vez em 2021.

# Métrica: saidas
#   O que é:
#     Quantas pessoas fizeram a última contribuição da vida naquele ano e passaram mais de 12
#     meses sem contribuir depois dela.
#     Quem para e volta mais tarde fez uma pausa (veja `pausas`) e fica fora das saídas.
#   Referência:
#     Foucault et al., ESEC/FSE 2015.
#     https://doi.org/10.1145/2786805.2786870
#     Avelino et al., ESEM 2019 (limite de 12 meses).
#     https://arxiv.org/abs/1906.08058
#   Entrada:
#     `pa`, a tabela de pessoas por ano (`pessoa_ano`), e `fim`, a data e hora do último evento
#     coletado.
#   Resultado esperado:
#     Coluna `saidas` da `tabela_anual`.
#     Exemplo: 450 em 2021 quer dizer que 450 pessoas pararam em 2021 e passaram mais de 12 meses
#     sem contribuir.
#     Fica vazia (NaN) no ano em que a coleta ainda não cobre os 12 meses seguintes, porque ainda
#     não dá para saber se a pessoa vai voltar.

# Métrica: pausas
#   O que é:
#     Quantas pessoas pararam de contribuir naquele ano, ficaram mais de 12 meses sem contribuir e
#     depois voltaram.
#     Quem volta não saiu, então a pausa fica fora das saídas. Entre o ano da pausa e o ano da
#     volta, a pessoa não conta como ativa.
#   Referência:
#     Da pesquisa (Plano de Experimento).
#     Avelino et al., ESEM 2019 (limite de 12 meses).
#     https://arxiv.org/abs/1906.08058
#   Entrada:
#     `pa`, a tabela de pessoas por ano (`pessoa_ano`), e `fim`, a data e hora do último evento
#     coletado.
#   Resultado esperado:
#     Coluna `pausas` da `tabela_anual`.
#     Exemplo: 40 em 2019 quer dizer que 40 pessoas pararam em 2019 e voltaram depois de mais de
#     12 meses.

# Métrica: voltas
#   O que é:
#     Quantas pessoas voltaram a contribuir naquele ano, depois de mais de 12 meses sem
#     contribuir.
#   Referência:
#     Da pesquisa (Plano de Experimento).
#   Entrada:
#     `pa`, a tabela de pessoas por ano (`pessoa_ano`), e `fim`, a data e hora do último evento
#     coletado.
#   Resultado esperado:
#     Coluna `voltas` da `tabela_anual`. Cada volta é o começo de um período de atividade que não
#     é o primeiro da pessoa.
#     Exemplo: 25 em 2022 quer dizer que 25 pessoas retomaram a atividade em 2022.

# Métrica: moved
#   O que é:
#     Quantas pessoas só participavam da discussão (revisão, comentários) e fizeram o primeiro
#     commit ou PR naquele ano.
#     O nome vem do artigo e quer dizer que a pessoa mudou do lado da discussão para o lado do
#     código. O ano é o do primeiro commit ou PR.
#   Referência:
#     Onoue et al., IEICE16.
#     https://doi.org/10.1587/transinf.2015EDP7363
#   Entrada:
#     `pa`, a tabela de pessoas por ano (`pessoa_ano`), e `fim`, a data e hora do último evento
#     coletado.
#   Resultado esperado:
#     Coluna `moved` da `tabela_anual`.
#     Exemplo: 60 em 2020 quer dizer que 60 pessoas que antes só discutiam fizeram o primeiro
#     commit ou PR em 2020.

# Métrica: deixou_codigo
#   O que é:
#     O caminho de volta do `moved`: pessoas cuja última atividade foi de discussão, depois do
#     último commit ou PR.
#     O ano é o do último commit ou PR.
#   Referência:
#     Da pesquisa (Plano de Experimento).
#   Entrada:
#     `pa`, a tabela de pessoas por ano (`pessoa_ano`), e `fim`, a data e hora do último evento
#     coletado.
#   Resultado esperado:
#     Coluna `deixou_codigo` da `tabela_anual`.
#     O valor depende do futuro: quem voltar a fazer commit ou PR deixa de contar. Por isso, no
#     último ano da coleta o valor sobe. Quem ainda vai voltar a fazer código entra como quem
#     deixou o código.

# Métrica: natalidade
#   O que é:
#     Quantas pessoas entraram no ano (novatos e voltas) para cada 100 pessoas ativas no mesmo
#     ano. Na demografia, é a taxa de natalidade.
#   Referência:
#     Equação compensadora da demografia (IBGE, metodologia das projeções 1980-2050).
#     https://ftp.ibge.gov.br/Projecao_da_Populacao/Revisao_2004_Projecoes_1980_2050/metodologia.pdf
#   Entrada:
#     `pa`, a tabela de pessoas por ano (`pessoa_ano`), e `fim`, a data e hora do último evento
#     coletado.
#   Resultado esperado:
#     Coluna `natalidade_pct` da `tabela_anual`.
#     Exemplo: 55 quer dizer que entraram 55 pessoas para cada 100 ativas no ano.

# Métrica: mortalidade
#   O que é:
#     Quantas pessoas saíram no ano (saídas e pausas) para cada 100 pessoas ativas no mesmo ano.
#     Na demografia, é a taxa de mortalidade.
#   Referência:
#     Equação compensadora da demografia (IBGE, metodologia das projeções 1980-2050).
#     https://ftp.ibge.gov.br/Projecao_da_Populacao/Revisao_2004_Projecoes_1980_2050/metodologia.pdf
#   Entrada:
#     `pa`, a tabela de pessoas por ano (`pessoa_ano`), e `fim`, a data e hora do último evento
#     coletado.
#   Resultado esperado:
#     Coluna `mortalidade_pct` da `tabela_anual`.
#     Exemplo: 40 quer dizer que saíram 40 pessoas para cada 100 ativas no ano.
#     Fica vazia no ano que a coleta ainda não cobre.

# Métrica: crescimento_natural
#   O que é:
#     Tudo que entra menos tudo que sai, em % das pessoas ativas do ano:
#     (novatos + voltas - saídas - pausas) / ativos.
#     É a natalidade menos a mortalidade. Responde a RQ1.1 (quantos entraram e saíram por ano e
#     qual foi o saldo).
#   Referência:
#     Equação compensadora da demografia (IBGE, metodologia das projeções 1980-2050).
#     https://ftp.ibge.gov.br/Projecao_da_Populacao/Revisao_2004_Projecoes_1980_2050/metodologia.pdf
#   Entrada:
#     `pa`, a tabela de pessoas por ano (`pessoa_ano`), e `fim`, a data e hora do último evento
#     coletado.
#   Resultado esperado:
#     Coluna `crescimento_natural_pct` da `tabela_anual`.
#     - Positivo: entrou mais gente do que saiu.
#     - Negativo: saiu mais gente do que entrou.
#     A base é o próprio ano. A variação dos ativos sobre o ano anterior é outra conta.
#     A coluna `provisorio` verdadeira marca o último ano completo, porque quem parou há pouco
#     ainda pode voltar.
#     A função para com erro se a conta de ativos não fechar: os ativos de Y+1 precisam ser os
#     ativos de Y, menos as saídas e pausas de Y, mais os novatos e voltas de Y+1.


def tabela_anual(pa: pd.DataFrame, fim: pd.Timestamp) -> pd.DataFrame:
    """Os totais de cada ano: quem estava ativo, quem entrou, quem saiu e o crescimento natural.

    Colunas: ativos, novatos, saídas, pausas, voltas, moved e deixou_codigo (contagens) e as três
    taxas em % dos ativos do mesmo ano.

    Saída é a última contribuição da vida da pessoa. Quem para por mais de 12 meses e volta
    tem uma pausa no ano em que parou e uma volta no ano em que voltou. Entre os dois anos ela
    não conta como ativa.

    A conta de ativos precisa fechar, e a função para com erro se ela não fechar:
    ativos(Y+1) = ativos(Y) - saídas(Y) - pausas(Y) + novatos(Y+1) + voltas(Y+1),
    para todo ano Y com saída decidida.

    As taxas:
      natalidade_pct           (novatos + voltas) / ativos
      mortalidade_pct          (saídas + pausas) / ativos
      crescimento_natural_pct  natalidade menos mortalidade, ou seja, tudo que entra menos tudo
                               que sai

    A base é o próprio ano Y. Entra quem chegou em Y (novato ou volta). Sai quem fez em Y a
    última contribuição de um período de atividade (a saída só se confirma 12 meses depois).
    Esta conta é diferente da variação dos ativos sobre o ano anterior, ativos(Y) / ativos(Y-1)
    - 1, que usa Y-1 como base e as saídas e pausas de Y-1.
    Exemplo, Clojure 2024: crescimento natural de -8,4% e variação dos ativos de -18,8%.
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
    """Compara linguagens de tamanhos diferentes: taxas em % dos ativos do ano e índice de ativos.

    Mesma conta de `metrica_trajetoria` em `scripts/vitalidade.py`.
    """
    t = anual.copy()
    t["saida_pct"] = 100 * t["saidas"] / t["ativos"]
    t["volta_pct"] = 100 * t["voltas"] / t["ativos"]
    t["novato_pct"] = 100 * t["novatos"] / t["ativos"]
    # Reposição: todo mundo que entrou (novatos e voltas) para cada pessoa que saiu (saídas e
    # pausas). Acima de 1, o crescimento natural é positivo.
    t["reposicao"] = (t["novatos"] + t["voltas"]) / (t["saidas"] + t["pausas"]).where(
        t["saidas"].notna()
    )
    # Sem ativos no ano base, não há índice.
    ativos_na_base = t.set_index("ano")["ativos"].get(ano_base_indice)
    t["indice"] = 100 * t["ativos"] / ativos_na_base if ativos_na_base else float("nan")
    return t


# shortcut: `scripts/vitalidade.py` ainda marca `provisorio` da trajetória pela regra de
# `carencia_anos` (os últimos anos completos). Aqui vale o `provisorio` de `tabela_anual`.
# Unificar quando o catálogo virar package.


# Métrica: saida_pct
#   O que é:
#     Saídas do ano para cada 100 pessoas ativas no mesmo ano. Tira o tamanho da linguagem da
#     comparação.
#   Referência:
#     Da pesquisa (Plano de Experimento).
#     Equação compensadora da demografia (IBGE, metodologia das projeções 1980-2050).
#     https://ftp.ibge.gov.br/Projecao_da_Populacao/Revisao_2004_Projecoes_1980_2050/metodologia.pdf
#   Entrada:
#     `anual`, a tabela de totais por ano (`tabela_anual`), e `ano_base_indice` (2019).
#   Resultado esperado:
#     Coluna `saida_pct` da `trajetoria`. Exemplo: 40 quer dizer que saíram 40 pessoas para cada
#     100 ativas.
#     Fica vazia no ano sem saída decidida.

# Métrica: volta_pct
#   O que é:
#     Voltas do ano para cada 100 pessoas ativas no mesmo ano.
#   Referência:
#     Da pesquisa (Plano de Experimento).
#     Equação compensadora da demografia (IBGE, metodologia das projeções 1980-2050).
#     https://ftp.ibge.gov.br/Projecao_da_Populacao/Revisao_2004_Projecoes_1980_2050/metodologia.pdf
#   Entrada:
#     `anual`, a tabela de totais por ano (`tabela_anual`), e `ano_base_indice` (2019).
#   Resultado esperado:
#     Coluna `volta_pct` da `trajetoria`. Exemplo: 8 quer dizer que voltaram 8 pessoas para cada
#     100 ativas.

# Métrica: novato_pct
#   O que é:
#     Novatos do ano para cada 100 pessoas ativas no mesmo ano.
#   Referência:
#     Da pesquisa (Plano de Experimento).
#     Equação compensadora da demografia (IBGE, metodologia das projeções 1980-2050).
#     https://ftp.ibge.gov.br/Projecao_da_Populacao/Revisao_2004_Projecoes_1980_2050/metodologia.pdf
#   Entrada:
#     `anual`, a tabela de totais por ano (`tabela_anual`), e `ano_base_indice` (2019).
#   Resultado esperado:
#     Coluna `novato_pct` da `trajetoria`. Exemplo: 30 quer dizer que 30 de cada 100 ativas são
#     novatas.

# Métrica: reposicao
#   O que é:
#     Quantas pessoas entraram no ano (novatos e voltas) para cada pessoa que saiu (saídas e
#     pausas).
#   Referência:
#     Da pesquisa (Plano de Experimento).
#     Equação compensadora da demografia (IBGE, metodologia das projeções 1980-2050).
#     https://ftp.ibge.gov.br/Projecao_da_Populacao/Revisao_2004_Projecoes_1980_2050/metodologia.pdf
#   Entrada:
#     `anual`, a tabela de totais por ano (`tabela_anual`), e `ano_base_indice` (2019).
#   Resultado esperado:
#     Coluna `reposicao` da `trajetoria`.
#     - Acima de 1: entrou mais gente do que saiu, e o crescimento natural é positivo.
#     - Abaixo de 1: saiu mais gente do que entrou.
#     Exemplo: 0,8 quer dizer 8 entradas para cada 10 saídas.
#     Fica vazia no ano sem saída decidida.

# Métrica: indice_de_ativos
#   O que é:
#     Ativos de cada ano divididos pelos ativos do ano base, vezes 100.
#     O Python tem cerca de mil vezes os ativos do Zig. Só o índice permite comparar a evolução
#     das duas.
#   Referência:
#     Da pesquisa (Plano de Experimento).
#     Equação compensadora da demografia (IBGE, metodologia das projeções 1980-2050).
#     https://ftp.ibge.gov.br/Projecao_da_Populacao/Revisao_2004_Projecoes_1980_2050/metodologia.pdf
#   Entrada:
#     `anual`, a tabela de totais por ano (`tabela_anual`), e `ano_base_indice` (2019).
#   Resultado esperado:
#     Coluna `indice` da `trajetoria`. Vale 100 no ano base (`ano_base_indice`).
#     Exemplo: 80 quer dizer 20% menos ativos do que no ano base.
#     Sem ativos no ano base, não há índice.

# ================================================================================================
# Composição (RQ1.2): novatos e veteranos, pirâmide e índice de envelhecimento
# ================================================================================================

# Métrica: piramide
#   O que é:
#     Uma tabela que conta os ativos de cada ano por faixa de idade na linguagem (0-1, 1-2, 2-3,
#     3-5, 5-8 e 8+ anos) e por categoria. As categorias separam quem escreve código de quem só
#     participa da discussão:
#     - Quem nunca fez commit nem PR (`non_coding`).
#     - Quem começou pela discussão e fez commit ou PR neste ano (`moved`).
#     - Quem começou pelo código (`coding`).
#     - Quem já fez código antes e neste ano só discutiu (`moved_to_discussion`). Esta categoria
#       só existe com `com_moved_to_discussion=True`.
#   Referência:
#     Pirâmide etária e índice de envelhecimento (IBGE).
#     https://seriesestatisticas.ibge.gov.br/series.aspx?vcodigo=CD95
#     Hannemann e Klamma, OSS 2013.
#     https://doi.org/10.1007/978-3-642-38928-3_6
#   Entrada:
#     `pa`, a tabela de pessoas por ano (`pessoa_ano`): uma linha por pessoa e por ano em que ela
#     contribuiu.
#   Resultado esperado:
#     Tabela `composicao`: ano, faixa e uma coluna de contagem por categoria.
#     Quem fez commit ou PR no ano fica do lado do código, mesmo que o último evento do ano seja
#     um comentário.

# Métrica: piramide_trimestral
#   O que é:
#     A mesma pirâmide, com a idade em fatias de 90 dias (cerca de um trimestre) no lugar de anos,
#     como no artigo. Serve para olhar a forma da pirâmide. As métricas usam as faixas de 1 ano.
#   Referência:
#     Onoue et al., IEICE16.
#     https://doi.org/10.1587/transinf.2015EDP7363 (ESEM14 e IEICE16)
#   Entrada:
#     `pa`, a tabela de pessoas por ano (`pessoa_ano`): uma linha por pessoa e por ano em que ela
#     contribuiu.
#   Resultado esperado:
#     Tabela `composicao_trimestral`: ano, `band` e uma coluna de contagem por categoria.
#     A fatia 0 vai de 0 a 90 dias de idade, a fatia 1 de 91 a 180 dias, e assim por diante.


def composicao(pa: pd.DataFrame) -> pd.DataFrame:
    """Quantos ativos há por ano e faixa de idade, nas quatro categorias da pirâmide (`LADOS`)."""
    t = pa.groupby(["ano", "faixa", "categoria"], observed=False).size().unstack(fill_value=0)
    for coluna in LADOS:
        if coluna not in t.columns:
            t[coluna] = 0
    return t[LADOS].reset_index()


def composicao_trimestral(pa: pd.DataFrame, band_dias: int = BAND_DIAS) -> pd.DataFrame:
    """Ativos por ano e por fatia de 90 dias de idade, em cada categoria da pirâmide.

    A idade é o tempo desde a primeira contribuição até o fim do ano, em fatias de `band_dias`
    dias. A fatia 0 vai de 0 a 90 dias, a fatia 1 de 91 a 180, e assim por diante. As categorias
    são as de `composicao`.
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
#     A pirâmide com cada número em % do total de ativos do ano. Serve para comparar linguagens de
#     tamanhos diferentes.
#   Referência:
#     Da pesquisa (Plano de Experimento).
#     Pirâmide etária e índice de envelhecimento (IBGE).
#     https://seriesestatisticas.ibge.gov.br/series.aspx?vcodigo=CD95
#   Entrada:
#     `pa`, a tabela de pessoas por ano (`pessoa_ano`): uma linha por pessoa e por ano em que ela
#     contribuiu.
#   Resultado esperado:
#     Tabela `composicao_em_pct`: as mesmas colunas da `composicao`, cada uma em % do total do
#     ano.
#     Somando todas as faixas e categorias de um ano, o resultado é 100.


def composicao_em_pct(pa: pd.DataFrame) -> pd.DataFrame:
    """`composicao` com cada contagem em % dos ativos do ano (o `composicao_pct` da trajetória)."""
    c = composicao(pa)
    total_do_ano = c[LADOS].sum(axis=1).groupby(c["ano"]).transform("sum")
    c[LADOS] = 100 * c[LADOS].div(total_do_ano, axis=0)
    return c


# Métrica: indice_envelhecimento
#   O que é:
#     Ativos com 5 anos ou mais na linguagem (faixas 5-8 e 8+) divididos pelos ativos com menos de
#     1 ano (faixa 0-1), por ano.
#     Na demografia, mede quantos idosos existem para cada jovem.
#   Referência:
#     Pirâmide etária e índice de envelhecimento (IBGE).
#     https://seriesestatisticas.ibge.gov.br/series.aspx?vcodigo=CD95
#     Hannemann e Klamma, OSS 2013.
#     https://doi.org/10.1007/978-3-642-38928-3_6
#   Entrada:
#     `pa`, a tabela de pessoas por ano (`pessoa_ano`): uma linha por pessoa e por ano em que ela
#     contribuiu.
#   Resultado esperado:
#     Tabela `indice_envelhecimento`: ano, veteranos, novatos e indice.
#     - Índice 1: tantos veteranos quanto novatos.
#     - Índice subindo: a base da pirâmide (os novatos) encolhe mais rápido que o topo.
#     Fica vazio no ano sem novatos.


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

# Base, sem métrica própria. `duracoes` dá uma linha por pessoa: quando entrou, o último evento,
# os anos entre os dois, se já saiu e a coorte de entrada. Quem fez o último evento há 12 meses
# ou menos de `fim` ainda pode voltar. Essa pessoa fica em observação (`saiu` falso), com a
# duração medida até ali. Na estatística, isso se chama censura à direita.


def duracoes(eventos: pd.DataFrame, fim: pd.Timestamp | None = None) -> pd.DataFrame:
    """Uma linha por pessoa: coorte de entrada, anos entre o primeiro e o último evento e se saiu.

    Quem fez o último evento há 12 meses ou menos de `fim` ainda pode voltar a contribuir. Essa
    pessoa fica em observação (`saiu` falso), com a duração medida até o último evento.
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
    """Faixa de 95% de confiança (método de Wilson) para a proporção `eventos / n`.

    Aceita `n` fracionário, porque na tábua quem está em observação conta meio ano. A faixa
    nunca passa de 0 nem de 1. O intervalo normal passa quando o número de saídas é zero.
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
#     l(x): quantas pessoas da coorte ainda estão em observação ao chegar em x anos de
#     contribuição. Quem entrou no mesmo ano forma uma coorte.
#     Em observação quer dizer que a pessoa não saiu antes de x e a coleta ainda a acompanhava.
#     Faz parte da tábua de vida, que responde a RQ1.3 (em que ponto da vida na linguagem as
#     pessoas saem).
#   Referência:
#     IBGE, Tábua Completa de Mortalidade 2023.
#     https://biblioteca.ibge.gov.br/visualizacao/periodicos/3097/tcmb_2023.pdf
#     Hannemann e Klamma, OSS 2013.
#     https://doi.org/10.1007/978-3-642-38928-3_6
#   Entrada:
#     `dur`, a tabela de durações (`duracoes`): uma linha por pessoa, com quando entrou, quando
#     fez o último evento, quantos anos ficou, se já saiu e a coorte de entrada.
#   Resultado esperado:
#     Coluna `l` da `tabua_de_vida`, uma linha por x (0 é o primeiro ano de contribuição).
#     Começa no total da coorte e só desce.

# Métrica: saidas_da_tabua
#   O que é:
#     d(x): quantas pessoas saíram entre x e x+1 anos de contribuição.
#     Faz parte da tábua de vida, que responde a RQ1.3 (em que ponto da vida na linguagem as
#     pessoas saem).
#   Referência:
#     IBGE, Tábua Completa de Mortalidade 2023.
#     https://biblioteca.ibge.gov.br/visualizacao/periodicos/3097/tcmb_2023.pdf
#     Hannemann e Klamma, OSS 2013.
#     https://doi.org/10.1007/978-3-642-38928-3_6
#   Entrada:
#     `dur`, a tabela de durações (`duracoes`): uma linha por pessoa, com quando entrou, quando
#     fez o último evento, quantos anos ficou, se já saiu e a coorte de entrada.
#   Resultado esperado:
#     Coluna `d` da `tabua_de_vida`, uma linha por x. É uma contagem.
#     Somando todos os x, o resultado é o total de quem saiu.

# Métrica: chance_de_sair
#   O que é:
#     q(x): a chance de uma pessoa sair no ano x, sabendo que ela chegou até ele. Na demografia, é
#     a probabilidade de morte.
#     A conta é q(x) = d(x) / (l(x) - censurados(x) / 2). Censurado é quem ainda pode voltar (o
#     último evento foi há 12 meses ou menos do fim da coleta). Essa pessoa conta como meio ano de
#     observação em vez de um ano inteiro.
#     É a taxa de saída da faixa, no nível do ano. Faz parte da tábua de vida, que responde a
#     RQ1.3 (em que ponto da vida na linguagem as pessoas saem).
#   Referência:
#     IBGE, Tábua Completa de Mortalidade 2023.
#     https://biblioteca.ibge.gov.br/visualizacao/periodicos/3097/tcmb_2023.pdf
#     Hannemann e Klamma, OSS 2013.
#     https://doi.org/10.1007/978-3-642-38928-3_6
#   Entrada:
#     `dur`, a tabela de durações (`duracoes`): uma linha por pessoa, com quando entrou, quando
#     fez o último evento, quantos anos ficou, se já saiu e a coorte de entrada.
#   Resultado esperado:
#     Coluna `q` da `tabua_de_vida`, uma linha por x, de 0 a 1.
#     Exemplo: q = 0,4 em x = 2 quer dizer que 40% de quem chegou a 2 anos sai antes de completar
#     3.
#     A coluna `n_efetivo` mostra quantas pessoas pesam na conta. Com poucas, q oscila muito.

# Métrica: fracao_que_chega
#   O que é:
#     S(x): a fração da coorte que chega a x anos de contribuição. É o produto de (1 - q) de todos
#     os anos antes de x. Faz parte da tábua de vida, que responde a RQ1.3 (em que ponto da vida
#     na linguagem as pessoas saem).
#   Referência:
#     IBGE, Tábua Completa de Mortalidade 2023.
#     https://biblioteca.ibge.gov.br/visualizacao/periodicos/3097/tcmb_2023.pdf
#     Hannemann e Klamma, OSS 2013.
#     https://doi.org/10.1007/978-3-642-38928-3_6
#   Entrada:
#     `dur`, a tabela de durações (`duracoes`): uma linha por pessoa, com quando entrou, quando
#     fez o último evento, quantos anos ficou, se já saiu e a coorte de entrada.
#   Resultado esperado:
#     Coluna `S` da `tabua_de_vida`, uma linha por x. Começa em 1 e desce.
#     Exemplo: S = 0,3 em x = 5 quer dizer que 30% da coorte chega a 5 anos.

# Métrica: esperanca_restante
#   O que é:
#     e(x): quantos anos a mais, em média, ainda contribui uma pessoa que chegou a x anos.
#     Responde: quem já está há x anos ainda fica quanto tempo?
#     Faz parte da tábua de vida, que responde a RQ1.3 (em que ponto da vida na linguagem as
#     pessoas saem).
#   Referência:
#     IBGE, Tábua Completa de Mortalidade 2023.
#     https://biblioteca.ibge.gov.br/visualizacao/periodicos/3097/tcmb_2023.pdf
#     Hannemann e Klamma, OSS 2013.
#     https://doi.org/10.1007/978-3-642-38928-3_6
#   Entrada:
#     `dur`, a tabela de durações (`duracoes`): uma linha por pessoa, com quando entrou, quando
#     fez o último evento, quantos anos ficou, se já saiu e a coorte de entrada.
#   Resultado esperado:
#     Coluna `e` da `tabua_de_vida`, uma linha por x, em anos.
#     Quando `e_truncado` é verdadeiro, ainda há gente em observação no fim da tábua. A parte da
#     vida depois do último ano observado não entra na conta, e e(x) vale como valor mínimo.

# Métrica: intervalo_de_q
#   O que é:
#     A faixa de valores em que q(x) provavelmente está: um intervalo de confiança de 95%, pelo
#     método de Wilson, calculado com `n_efetivo`.
#     Com poucas pessoas a faixa é larga. Ela nunca passa de 0 nem de 1, mesmo quando ninguém
#     saiu. Faz parte da tábua de vida, que responde a RQ1.3 (em que ponto da vida na linguagem as
#     pessoas saem).
#   Referência:
#     IBGE, Tábua Completa de Mortalidade 2023.
#     https://biblioteca.ibge.gov.br/visualizacao/periodicos/3097/tcmb_2023.pdf
#     Hannemann e Klamma, OSS 2013.
#     https://doi.org/10.1007/978-3-642-38928-3_6
#   Entrada:
#     `dur`, a tabela de durações (`duracoes`): uma linha por pessoa, com quando entrou, quando
#     fez o último evento, quantos anos ficou, se já saiu e a coorte de entrada.
#   Resultado esperado:
#     Colunas `q_inf` e `q_sup` da `tabua_de_vida`, uma linha por x, entre 0 e 1.
#     Exemplo: com 10 pessoas e nenhuma saída, q vale 0 e a faixa vai de 0 a 28%.
#     Quem lê q(x) deve olhar também `n_efetivo` e a faixa.


def tabua_de_vida(dur: pd.DataFrame) -> pd.DataFrame:
    """Tábua de vida: como um grupo que entrou junto vai diminuindo a cada ano de contribuição.

    Colunas (x é o ano de contribuição, e 0 é o primeiro):
      l(x)          pessoas em observação ao chegar em x anos
      d(x)          saídas entre x e x+1
      censurados    pessoas que ainda podem voltar e saem da observação em x
      q(x)          chance de sair: d(x) / (l(x) - censurados(x)/2). Quem está em observação
                    conta meio ano
      n_efetivo(x)  o denominador de q: l(x) - censurados(x)/2
      q_inf, q_sup  faixa de 95% de confiança (Wilson) para q(x), calculada com `n_efetivo`
      S(x)          fração da coorte que chega a x: produto de (1 - q) até x-1
      e(x)          anos que ainda restam, em média, a quem chegou a x

    Com poucas pessoas, q(x) oscila: 0 saídas em 10 pessoas dá q = 0 e uma faixa de 0 a 28%.
    Quem lê q(x) deve olhar `n_efetivo` e a faixa.

    Se a tábua termina com gente em observação (S final > 0), a parte da vida depois do último
    ano observado fica de fora, e e(x) vale como valor mínimo. A coluna `e_truncado` avisa.
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
#     A tábua de vida de cada coorte de entrada. Comparando as coortes, dá para ver se cada
#     geração fica mais ou menos tempo que a anterior.
#   Referência:
#     IBGE, Tábua Completa de Mortalidade 2023.
#     https://biblioteca.ibge.gov.br/visualizacao/periodicos/3097/tcmb_2023.pdf
#     Hannemann e Klamma, OSS 2013.
#     https://doi.org/10.1007/978-3-642-38928-3_6
#   Entrada:
#     `dur`, a tabela de durações (`duracoes`): uma linha por pessoa, com quando entrou, quando
#     fez o último evento, quantos anos ficou, se já saiu e a coorte de entrada.
#   Resultado esperado:
#     Tabela `tabuas_por_coorte`: as colunas da `tabua_de_vida` com a coluna `coorte` na frente.
#     As coortes mais recentes ficam incompletas, porque a coleta ainda não viu o que acontece com
#     elas depois.


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
#     A chance de seguir contribuindo por mais 1 ano, para quem chegou a x anos: 1 - q(x). Olha só
#     o ano seguinte.
#   Referência:
#     Da pesquisa (Plano de Experimento).
#     IBGE, Tábua Completa de Mortalidade 2023.
#     https://biblioteca.ibge.gov.br/visualizacao/periodicos/3097/tcmb_2023.pdf
#   Entrada:
#     `tabua`, a tabela de `tabua_de_vida`.
#   Resultado esperado:
#     Uma série de 0 a 1, uma por x.
#     Exemplo: 0,6 em x = 3 quer dizer que 60% de quem chegou a 3 anos segue por mais um ano.
#     Com menos de 300 pessoas em `n_efetivo`, o valor oscila vários pontos.


def chance_de_seguir(tabua: pd.DataFrame) -> pd.Series:
    """Chance de seguir mais 1 ano tendo chegado a x: 1 - q(x)."""
    return 1 - tabua["q"]


# ================================================================================================
# Saída por faixa de idade (RQ1.3)
# ================================================================================================

# Métrica: taxa_saida_por_faixa
#   O que é:
#     De cada faixa de idade na linguagem, que fração saiu no ano: saídas da faixa divididas pelos
#     ativos da faixa.
#     É o q(x) da tábua de vida, calculado por faixa. Mostra em que fase a comunidade perde mais
#     gente: entre os novatos ou entre os veteranos.
#   Referência:
#     IBGE, Tábua Completa de Mortalidade 2023.
#     https://biblioteca.ibge.gov.br/visualizacao/periodicos/3097/tcmb_2023.pdf
#     CDC WONDER, Presentation Standards for Mortality Data, 2024.
#     https://wonder.cdc.gov/controller/pdf/presentation-standards-mortality-2024.pdf
#   Entrada:
#     `pa`, a tabela de pessoas por ano (`pessoa_ano`), e `fim`, a data e hora do último evento
#     coletado.
#   Resultado esperado:
#     Tabela `taxa_saida_por_faixa`: ano, faixa, ativos, saidas e taxa_saida.
#     A `taxa_saida` vai de 0 a 1. Exemplo: 0,3 quer dizer que, a cada 10 ativos da faixa, 3
#     saíram no ano.
#     Ano que a coleta não cobre fica sem saídas e sem taxa. Faixa sem ativos fica sem taxa.
#     Os gráficos do estudo marcam como instável a célula com menos de 20 saídas.


def taxa_saida_por_faixa(pa: pd.DataFrame, fim: pd.Timestamp) -> pd.DataFrame:
    """Saídas da faixa divididas pelos ativos da faixa, por ano. Ano em aberto fica `NaN`."""
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
#     Saídas do ano divididas pelos ativos do ano na linguagem, sem corrigir a composição.
#     Responde a RQ2 (a linguagem retém melhor ou pior que outras).
#     Quem é novo sai mais. Uma linguagem com muita gente nova tem taxa bruta alta mesmo que
#     retenha tão bem quanto as outras. A taxa padronizada corrige isso.
#   Referência:
#     Ahmad et al., Age Standardization of Rates: A New WHO Standard, OMS, 2001.
#     https://cdn.who.int/media/docs/default-source/gho-documents/global-health-estimates/gpe_discussion_paper_series_paper31_2001_age_standardization_rates.pdf
#   Entrada:
#     Um dict {linguagem: tabela de `taxa_saida_por_faixa`} e `ano_pesos` (2025), o ano cuja
#     mistura de faixas de idade serve de peso. A população de referência é a soma de todas as
#     linguagens do dict.
#   Resultado esperado:
#     Coluna `taxa_bruta` da tabela `padronizacao`, uma linha por linguagem e ano, de 0 a 1.
#     O número mistura a diferença real de retenção com a diferença de composição entre as
#     linguagens.

# Métrica: taxa_padronizada
#   O que é:
#     A taxa de saída da linguagem refeita como se ela tivesse a mesma mistura de faixas de idade
#     da população de referência. Para cada faixa, multiplica a taxa de saída da linguagem pelo
#     peso da faixa na referência e soma tudo (taxa direta).
#     A diferença que sobra entre as linguagens vem da retenção. Responde a RQ2.
#   Referência:
#     Ahmad et al., Age Standardization of Rates: A New WHO Standard, OMS, 2001.
#     https://cdn.who.int/media/docs/default-source/gho-documents/global-health-estimates/gpe_discussion_paper_series_paper31_2001_age_standardization_rates.pdf
#   Entrada:
#     Um dict {linguagem: tabela de `taxa_saida_por_faixa`} e `ano_pesos` (2025), o ano cuja
#     mistura de faixas de idade serve de peso. A população de referência é a soma de todas as
#     linguagens do dict.
#   Resultado esperado:
#     Coluna `taxa_padronizada` da tabela `padronizacao`, uma linha por linguagem e ano, de 0 a 1.
#     Fica vazia no ano em que alguma faixa não tem ninguém na linguagem (linguagem jovem), porque
#     falta a taxa para pesar.

# Métrica: taxa_padronizada_ate_5a
#   O que é:
#     A taxa direta só nas faixas de 0 a 5 anos, com os pesos reajustados para somar 1.
#     Uma linguagem nova ainda não tem as faixas 5-8 e 8+, e a taxa padronizada completa só começa
#     quando todas as faixas existem. Esta começa 5 anos depois do nascimento da comunidade e
#     compara todas no mesmo intervalo de idades. Responde a RQ2.
#   Referência:
#     Ahmad et al., Age Standardization of Rates: A New WHO Standard, OMS, 2001.
#     https://cdn.who.int/media/docs/default-source/gho-documents/global-health-estimates/gpe_discussion_paper_series_paper31_2001_age_standardization_rates.pdf
#   Entrada:
#     Um dict {linguagem: tabela de `taxa_saida_por_faixa`} e `ano_pesos` (2025), o ano cuja
#     mistura de faixas de idade serve de peso. A população de referência é a soma de todas as
#     linguagens do dict.
#   Resultado esperado:
#     Coluna `taxa_padronizada_ate_5a` da tabela `padronizacao`, uma linha por linguagem e ano, de
#     0 a 1.
#     Existe em linguagens novas, que ainda não têm as faixas 5-8 e 8+.

# Métrica: saidas_esperadas
#   O que é:
#     Quantas saídas a linguagem teria se cada faixa dela saísse na taxa da população de
#     referência: soma, por faixa, de (taxa da referência x ativos da linguagem). Responde a RQ2.
#   Referência:
#     Ahmad et al., Age Standardization of Rates: A New WHO Standard, OMS, 2001.
#     https://cdn.who.int/media/docs/default-source/gho-documents/global-health-estimates/gpe_discussion_paper_series_paper31_2001_age_standardization_rates.pdf
#   Entrada:
#     Um dict {linguagem: tabela de `taxa_saida_por_faixa`} e `ano_pesos` (2025), o ano cuja
#     mistura de faixas de idade serve de peso. A população de referência é a soma de todas as
#     linguagens do dict.
#   Resultado esperado:
#     Coluna `saidas_esperadas` da tabela `padronizacao`, uma linha por linguagem e ano.
#     É uma contagem com casas decimais.
#     Fica vazia se a referência do ano tem alguma faixa em aberto (coleta incompleta).

# Métrica: smr
#   O que é:
#     Razão padronizada de saídas (SMR, do inglês Standardized Mortality Ratio): as saídas reais
#     divididas pelas saídas esperadas. Responde a RQ2.
#   Referência:
#     Ahmad et al., Age Standardization of Rates: A New WHO Standard, OMS, 2001.
#     https://cdn.who.int/media/docs/default-source/gho-documents/global-health-estimates/gpe_discussion_paper_series_paper31_2001_age_standardization_rates.pdf
#   Entrada:
#     Um dict {linguagem: tabela de `taxa_saida_por_faixa`} e `ano_pesos` (2025), o ano cuja
#     mistura de faixas de idade serve de peso. A população de referência é a soma de todas as
#     linguagens do dict.
#   Resultado esperado:
#     Coluna `smr` da tabela `padronizacao`, uma linha por linguagem e ano.
#     - 1: saiu o esperado.
#     - Acima de 1: saiu mais do que o esperado. Exemplo: 1,2 quer dizer 20% mais saídas.
#     - Abaixo de 1: saiu menos do que o esperado.
#     O resultado depende da referência escolhida.


def padronizacao(taxas: dict[str, pd.DataFrame], ano_pesos: int) -> pd.DataFrame:
    """Taxa de saída bruta, padronizada (direta) e SMR (indireta), por linguagem e ano.

    `taxas` traz a saída de `taxa_saida_por_faixa` de cada linguagem. A população de referência
    é a soma das linguagens: os pesos vêm da composição por faixa de todas juntas em
    `ano_pesos`, e a taxa da referência em Y é a de todas juntas em Y.

      direta  soma, por faixa, de taxa da linguagem vezes peso da faixa
      SMR     saídas da linguagem / soma, por faixa, de taxa da referência vezes
              ativos da linguagem

    Faixa sem ativos na linguagem deixa a direta `NaN`, porque falta a taxa para pesar. Ano em
    aberto em qualquer linguagem deixa a referência daquele ano `NaN`.

    `taxa_padronizada_ate_5a` é a direta só nas faixas `FAIXAS_CURTAS` (0 a 5 anos), com os pesos
    reajustados. Uma linguagem nova não tem as faixas 5-8 e 8+ nos primeiros anos, e a direta
    completa só começa quando todas as faixas existem (Zig em 2023). A curta começa 5 anos
    depois do nascimento da comunidade e compara todas no mesmo intervalo de idades.
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
# Diferença entre linguagens além do acaso (RQ2): Kaplan-Meier e log-rank
# ================================================================================================

# Métrica: kaplan_meier
#   O que é:
#     A estimativa da chance de uma pessoa ainda estar ativa t anos depois de entrar.
#     Quem ainda está ativo no fim da coleta entra na conta como ainda sem saída, porque não se
#     sabe quando vai sair. Na estatística, isso se chama censura à direita.
#   Referência:
#     Constantinou e Mens, Innovations in Systems and Software Engineering, 2017.
#     https://doi.org/10.1007/s11334-017-0303-4
#   Entrada:
#     `dur`, a tabela de durações (`duracoes`): uma linha por pessoa, com quando entrou, quando
#     fez o último evento, quantos anos ficou, se já saiu e a coorte de entrada.
#   Resultado esperado:
#     Tabela `kaplan_meier` com três colunas:
#     - `anos`: o tempo desde a primeira contribuição.
#     - `S`: a fração ainda ativa. Começa em 1 e desce em degraus.
#     - `em_risco`: quantas pessoas têm duração de `anos` ou mais. Quanto menor, menos a curva
#       vale.
#     Uma amostra com mais de 2 milhões de pontos sai com um ponto por dia, exato nesse instante.

# Métrica: logrank
#   O que é:
#     Teste que diz se duas curvas de Kaplan-Meier diferem além do acaso. O plano compara Clojure
#     com cada outra linguagem.
#   Referência:
#     Constantinou e Mens, Innovations in Systems and Software Engineering, 2017.
#     https://doi.org/10.1007/s11334-017-0303-4
#   Entrada:
#     `dur_a` e `dur_b`, as tabelas de durações (`duracoes`) das duas linguagens.
#   Resultado esperado:
#     Uma tupla (estatística, p).
#     - p abaixo de 0,05: a diferença passa do acaso.
#     Com milhares de pessoas, p fica minúsculo para qualquer diferença. O que informa é o tamanho
#     dela, por exemplo 0,28 contra 0,36 de fração ativa depois de 5 anos.


def _amostra_censurada(dur: pd.DataFrame) -> stats.CensoredData:
    """Durações de `duracoes`. Quem ainda não saiu entra marcado como em observação."""
    return stats.CensoredData.right_censored(
        dur["duracao_anos"].to_numpy(), ~dur["saiu"].to_numpy()
    )


def kaplan_meier(dur: pd.DataFrame) -> pd.DataFrame:
    """Fração estimada ainda ativa, `S`, `anos` depois da primeira contribuição.

    `em_risco` é quantas pessoas têm duração de `anos` ou mais: quanto menor, menos a curva vale.
    Com mais de `MAX_PONTOS_KM` pontos, fica o último de cada dia, que é exato nesse instante.
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
    """Teste log-rank entre duas curvas de Kaplan-Meier. Devolve (estatística, p)."""
    r = stats.logrank(_amostra_censurada(dur_a), _amostra_censurada(dur_b))
    return float(r.statistic), float(r.pvalue)


# ================================================================================================
# Cenários futuros (RQ3): projeção, erro e cobertura
# ================================================================================================

# Base, sem métrica própria. A projeção trabalha com a idade em anos de contribuição (0 a 7 e
# 8 ou mais) e avança um ano por vez. Banda é uma dessas idades. `populacao_por_idade` conta os
# ativos por ano e idade. `saidas_por_banda` conta as saídas por ano e banda.
# `regra_da_variante` monta a regra de um cenário a partir de `variantes` no yaml.


def populacao_por_idade(pa: pd.DataFrame) -> pd.DataFrame:
    """Ativos por ano (linhas) e por idade exata em anos (colunas), sem agrupar o 8+."""
    pop = pa.groupby(["ano", "idade_anos"]).size().unstack(fill_value=0)
    anos = range(int(pop.index.min()), int(pop.index.max()) + 1)
    idades = range(int(pop.columns.max()) + 1)
    return pop.reindex(index=anos, columns=idades, fill_value=0)


def _bandas(linha: pd.Series) -> np.ndarray:
    """Transforma a contagem por idade exata num vetor de 9 posições: idades 0 a 7 e 8 ou mais."""
    v = np.zeros(BANDAS)
    for idade, n in linha.items():
        v[min(int(idade), BANDAS - 1)] += n
    return v


def saidas_por_banda(pa: pd.DataFrame, fim: pd.Timestamp) -> pd.DataFrame:
    """Saídas por ano (linhas) e banda de 0 a 8 (colunas). Ano em aberto fica `NaN`."""
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
    """Como os cenários leem a história.

    min_saidas        a taxa de permanência de uma banda de Y-1 para Y só entra na conta se a
                      banda teve pelo menos essas saídas em Y-1
    janela            usa só os últimos `janela` anos até o ano base; `None` usa a história toda
    novatos_por_taxa  verdadeiro: os novatos viram taxa (novatos de Y / ativos de Y-1), aplicada
                      à população do ano projetado. Falso: usa a contagem de novatos
    conservador       como o cenário conservador é calculado: `extremos` é a média do menor e
                      do maior valor, `media` é a média de todos os anos da janela e `recentes`
                      é a média dos 2 últimos anos da janela
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
#     Para cada idade de 0 a 7 anos e para 8 ou mais: quantas pessoas aparecem neste ano na idade
#     seguinte para cada pessoa que estava na idade anterior no ano passado.
#     O valor pode passar de 1, porque quem volta a contribuir reaparece na idade seguinte sem ter
#     sido contado na anterior.
#   Referência:
#     Onoue et al., IEICE16.
#     https://doi.org/10.1587/transinf.2015EDP7363
#     Adaptado do método de componentes por coorte de Isserman.
#   Entrada:
#     `pop` (de `populacao_por_idade`) e o `ano`.
#   Resultado esperado:
#     Um vetor de 9 posições (idades 0 a 7 e 8 ou mais).
#     Exemplo: 0,8 quer dizer que 80% da faixa chegou à faixa seguinte.
#     Faixa de origem vazia deixa a taxa vazia (NaN).


def permanencia(pop: pd.DataFrame, ano: int) -> np.ndarray:
    """Taxa de permanência de `ano - 1` para `ano`, por banda de origem.

    P(idade, ano) é o número de ativos daquela idade naquele ano.
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
    """Calcula a pirâmide de T+1 a partir da de T. Com `teto`, a taxa de permanência não passa de 1.

    Banda vazia em T não leva ninguém adiante, mesmo com taxa `NaN`. Banda com gente e taxa
    `NaN` deixa o destino `NaN`: o método não tem resposta ali.
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
#     A pirâmide do próximo ano é igual à do último ano observado. É a base de comparação:
#     qualquer método útil precisa errar menos que ela.
#     Responde a RQ3. O teste de previsão (`backtest`) usa só os anos anteriores ao ano previsto.
#   Referência:
#     Onoue et al., IEICE16.
#     https://doi.org/10.1587/transinf.2015EDP7363
#     Variantes de projeção da ONU.
#     https://www.prb.org/resource/understanding-population-projections-assumptions-behind-the-numbers/
#     Bonifácio e Guimarães, Texto para Discussão 2698, Ipea, 2021.
#   Entrada:
#     `pa`, `fim`, `ultimo_ano` (o último ano com saída decidida, `fim.year - 1`), `teto`
#     (verdadeiro limita a taxa de permanência em 1) e `regra` (um `RegraCenario`).
#   Resultado esperado:
#     Coluna `ingenuo` da tabela `backtest` (uma linha por ano e faixa, com a faixa extra `total`)
#     e, para o futuro, as linhas desse método em `projeta_futuro`.

# Métrica: projecao_coorte
#   O que é:
#     Cada faixa do próximo ano recebe a população da faixa anterior vezes a taxa de permanência
#     do último par de anos. Os novatos são a média dos dois últimos anos.
#     Coorte é o grupo que entrou no mesmo ano e envelhece junto. Responde a RQ3. O teste de
#     previsão (`backtest`) usa só os anos anteriores ao ano previsto.
#   Referência:
#     Onoue et al., IEICE16.
#     https://doi.org/10.1587/transinf.2015EDP7363
#     Variantes de projeção da ONU.
#     https://www.prb.org/resource/understanding-population-projections-assumptions-behind-the-numbers/
#     Bonifácio e Guimarães, Texto para Discussão 2698, Ipea, 2021.
#   Entrada:
#     `pa`, `fim`, `ultimo_ano` (o último ano com saída decidida, `fim.year - 1`), `teto`
#     (verdadeiro limita a taxa de permanência em 1) e `regra` (um `RegraCenario`).
#   Resultado esperado:
#     Coluna `coorte` da tabela `backtest` (uma linha por ano e faixa, com a faixa extra `total`)
#     e, para o futuro, as linhas desse método em `projeta_futuro`.

# Métrica: cenario_pessimista
#   O que é:
#     A mesma conta do coorte, com a taxa de permanência de cada faixa e o número de novatos no
#     menor valor da história. Só entram anos em que a faixa teve o mínimo de saídas
#     (`min_saidas`).
#     Responde a RQ3. O teste de previsão (`backtest`) usa só os anos anteriores ao ano previsto.
#   Referência:
#     Onoue et al., IEICE16.
#     https://doi.org/10.1587/transinf.2015EDP7363
#     Variantes de projeção da ONU.
#     https://www.prb.org/resource/understanding-population-projections-assumptions-behind-the-numbers/
#     Bonifácio e Guimarães, Texto para Discussão 2698, Ipea, 2021.
#   Entrada:
#     `pa`, `fim`, `ultimo_ano` (o último ano com saída decidida, `fim.year - 1`), `teto`
#     (verdadeiro limita a taxa de permanência em 1) e `regra` (um `RegraCenario`).
#   Resultado esperado:
#     Coluna `pessimista` da tabela `backtest` (uma linha por ano e faixa, com a faixa extra
#     `total`) e, para o futuro, as linhas desse método em `projeta_futuro`.

# Métrica: cenario_conservador
#   O que é:
#     A mesma conta do coorte, com o valor do meio: a média entre o maior e o menor valor da
#     história (regra `extremos`). A variante pode usar a média da janela (`media`) ou a média dos
#     2 últimos anos (`recentes`).
#     Responde a RQ3. O teste de previsão (`backtest`) usa só os anos anteriores ao ano previsto.
#   Referência:
#     Onoue et al., IEICE16.
#     https://doi.org/10.1587/transinf.2015EDP7363
#     Variantes de projeção da ONU.
#     https://www.prb.org/resource/understanding-population-projections-assumptions-behind-the-numbers/
#     Bonifácio e Guimarães, Texto para Discussão 2698, Ipea, 2021.
#   Entrada:
#     `pa`, `fim`, `ultimo_ano` (o último ano com saída decidida, `fim.year - 1`), `teto`
#     (verdadeiro limita a taxa de permanência em 1) e `regra` (um `RegraCenario`).
#   Resultado esperado:
#     Coluna `conservador` da tabela `backtest` (uma linha por ano e faixa, com a faixa extra
#     `total`) e, para o futuro, as linhas desse método em `projeta_futuro`.

# Métrica: cenario_otimista
#   O que é:
#     A mesma conta do coorte, com a taxa de permanência de cada faixa e o número de novatos no
#     maior valor da história. Junta o melhor ano de cada faixa, então funciona como limite
#     superior da projeção.
#     Responde a RQ3. O teste de previsão (`backtest`) usa só os anos anteriores ao ano previsto.
#   Referência:
#     Onoue et al., IEICE16.
#     https://doi.org/10.1587/transinf.2015EDP7363
#     Variantes de projeção da ONU.
#     https://www.prb.org/resource/understanding-population-projections-assumptions-behind-the-numbers/
#     Bonifácio e Guimarães, Texto para Discussão 2698, Ipea, 2021.
#   Entrada:
#     `pa`, `fim`, `ultimo_ano` (o último ano com saída decidida, `fim.year - 1`), `teto`
#     (verdadeiro limita a taxa de permanência em 1) e `regra` (um `RegraCenario`).
#   Resultado esperado:
#     Coluna `otimista` da tabela `backtest` (uma linha por ano e faixa, com a faixa extra
#     `total`) e, para o futuro, as linhas desse método em `projeta_futuro`.


def cenarios(
    pop: pd.DataFrame, saidas: pd.DataFrame, ate_ano: int, regra: RegraCenario
) -> dict[str, tuple[np.ndarray, float]]:
    """(taxa de permanência, novatos) de cada cenário, usando só a história até `ate_ano`.

      pessimista   menor valor da janela
      otimista     maior valor da janela
      conservador  a média dos dois (`extremos`) ou a média da janela toda (`media`), conforme
                   `regra.conservador`

    Os novatos saem em contagem ou em taxa, conforme `regra.novatos_por_taxa`, e
    `_novatos_do_cenario` converte. Banda sem nenhum ano válido usa nos três cenários a taxa de
    permanência do último ano, a mesma do coorte.
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
    """Soma o vetor de bandas de 1 ano nas faixas de 0-1 a 8+ e acrescenta o total."""
    faixas = faixa_de(pd.Series(range(BANDAS)))
    soma = dict.fromkeys(FAIXAS, 0.0)
    for banda in range(BANDAS):
        soma[faixas[banda]] = soma[faixas[banda]] + v[banda]
    soma["total"] = float(v.sum())
    return soma


# Métrica: abre
#   O que é:
#     ABRE (Absolute Balanced Relative Error), o erro relativo equilibrado de uma previsão: a
#     diferença absoluta entre o previsto e o real, dividida pelo menor dos dois valores.
#   Referência:
#     Onoue et al., IEICE16.
#     https://doi.org/10.1587/transinf.2015EDP7363
#     Miyazaki et al. definem o BRE.
#   Entrada:
#     `actual` (o valor real) e `predicted` (o previsto), duas contagens não negativas.
#   Resultado esperado:
#     Um número.
#     - 0: acerto.
#     - 0,5: erro de metade do menor dos dois valores.
#     Vale igual para quem previu a mais e para quem previu a menos.
#     Fica vazio (NaN) se qualquer lado é vazio ou zero.


def abre(actual: float, predicted: float) -> float:
    """ABRE (Absolute Balanced Relative Error): erro relativo equilibrado de uma previsão.

    É a diferença absoluta entre o previsto e o real, dividida pelo MENOR dos dois valores.
    O IEICE16 (p.1311) escreve a fórmula em dois ramos, com o denominador trocando de lado
    conforme o sinal de (previsto - real). Juntos, os dois ramos usam sempre o menor valor, que
    é o BRE de Miyazaki et al. tal como publicado. Aqui a conta usa `min` de propósito: a
    forma de dois ramos convida a inverter um sinal numa revisão, e o teste não pegaria,
    porque os ramos coincidem quando previsto e real são iguais.

    A conta é simétrica: abre(a, b) == abre(b, a).

    `nan` em qualquer lado propaga. É assim que `project` avisa que o método não tem resposta
    para a célula (coorte órfã). O caso é tratado de forma explícita porque `min(x, nan)` em
    Python devolve x, o primeiro argumento. Sem a guarda, o resultado dependeria da ordem dos
    parâmetros.
    """
    if math.isnan(actual) or math.isnan(predicted):
        return float("nan")
    if actual < 0 or predicted < 0:
        raise ValueError(f"ABRE em contagem negativa: actual={actual} pred={predicted}")
    denom = min(actual, predicted)
    if denom == 0:
        # Uma das duas contagens é zero, então a divisão não existe. Devolver 0.0 inventaria um
        # acerto e devolver 1.0 inventaria um erro máximo. A mediana do artigo considera só
        # projetos onde os dois lados existem.
        return float("nan")
    return abs(predicted - actual) / denom


# Métrica: cobertura
#   O que é:
#     Em quantos casos o valor real ficou entre o pessimista e o otimista da previsão.
#   Referência:
#     Da pesquisa (Plano de Experimento).
#   Entrada:
#     `pa`, `fim`, `ultimo_ano` (o último ano com saída decidida, `fim.year - 1`), `teto`
#     (verdadeiro limita a taxa de permanência em 1) e `regra` (um `RegraCenario`).
#   Resultado esperado:
#     Coluna `cobre` da tabela `backtest`: 1 quando o real ficou entre os dois, 0 quando ficou
#     fora e vazia se faltou cenário.
#     `resumo_backtest` traz a média por faixa e por total. Exemplo: 0,8 quer dizer que o real
#     ficou entre os dois cenários em 80% dos casos.

# Métrica: erro_mediano
#   O que é:
#     A mediana (o valor do meio) do ABRE de cada método (ingênuo, coorte e conservador), sobre as
#     mesmas células de faixa. Mede qual método acerta mais.
#   Referência:
#     Onoue et al., IEICE16.
#     https://doi.org/10.1587/transinf.2015EDP7363
#   Entrada:
#     `bt`, a tabela `backtest`.
#   Resultado esperado:
#     Tabela `abre` de `resumo_backtest`: teto, celulas, cobertura_faixas, cobertura_total e uma
#     coluna por método com a mediana do ABRE.
#     Menor é melhor.

# Métrica: wilcoxon
#   O que é:
#     Teste que compara dois métodos pelo ABRE de cada célula, emparelhando os dois erros da mesma
#     célula. As comparações são coorte contra ingênuo, conservador contra ingênuo e conservador
#     contra coorte.
#   Referência:
#     Onoue et al., IEICE16.
#     https://doi.org/10.1587/transinf.2015EDP7363
#   Entrada:
#     `bt`, a tabela `backtest`.
#   Resultado esperado:
#     Tabela `wilcoxon` de `resumo_backtest`: teto, comparacao e p.
#     - p abaixo de 0,05: um método erra menos que o outro além do acaso.
#     Fica vazio (NaN) quando a amostra não sustenta o teste.


def backtest(
    pa: pd.DataFrame, fim: pd.Timestamp, ultimo_ano: int, teto: bool, regra: RegraCenario
) -> pd.DataFrame:
    """Prevê cada ano até `ultimo_ano` usando só os anos anteriores a ele e mede o erro.

    Uma linha por ano previsto e faixa (ou `total`). Colunas: o valor real, o previsto por cada
    método, o ABRE de `METODOS_COM_ERRO` e `cobre`. A coluna `cobre` vale 1 se o real ficou
    entre o pessimista e o otimista, 0 se ficou fora e `NaN` se faltou cenário.
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
    """Wilcoxon pareado: compara os dois erros da mesma célula. `nan` se a amostra não basta."""
    from scipy.stats import wilcoxon

    par = np.isfinite(a) & np.isfinite(b)
    a, b = a[par], b[par]
    if len(a) < 1 or np.allclose(a, b):
        return float("nan")
    try:
        return float(wilcoxon(a, b).pvalue)
    except ValueError:
        # Todos os pares têm diferença zero: o teste não tem o que ordenar.
        return float("nan")


def resumo_backtest(bt: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Mediana do ABRE e cobertura por método, e Wilcoxon pareado entre métodos.

    O ABRE e o Wilcoxon usam as células de faixa (a linha `total` fica de fora) e só onde os
    três métodos têm ABRE, para que todos sejam medidos nas mesmas células. A cobertura sai
    das faixas e, separada, do total de cada ano.
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
#     A projeção dos próximos `anos` anos depois do último ano observado, um ano por vez, por cada
#     método.
#   Referência:
#     Onoue et al., IEICE16.
#     https://doi.org/10.1587/transinf.2015EDP7363
#     Variantes de projeção da ONU.
#     https://www.prb.org/resource/understanding-population-projections-assumptions-behind-the-numbers/
#     Bonifácio e Guimarães, Texto para Discussão 2698, Ipea, 2021.
#   Entrada:
#     `pa`, `fim`, `ultimo_ano` (o último ano com saída decidida, `fim.year - 1`), `teto`
#     (verdadeiro limita a taxa de permanência em 1) e `regra` (um `RegraCenario`). E `anos`, o
#     horizonte (5).
#   Resultado esperado:
#     Tabela de `projeta_futuro`: ano, metodo, faixa e previsto. A faixa `total` soma as outras.


def projeta_futuro(  # noqa: PLR0913, PLR0917
    pa: pd.DataFrame,
    fim: pd.Timestamp,
    ultimo_ano: int,
    anos: int,
    teto: bool,
    regra: RegraCenario,
) -> pd.DataFrame:
    """Projeta `anos` anos depois de `ultimo_ano`, um ano por vez.

    O coorte usa a taxa de permanência do último par de anos observado e, como novatos, a média
    dos dois anos anteriores (já projetados, depois do primeiro passo). Cada cenário fixa a sua
    taxa de permanência e os seus novatos.
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
# CCR e NCR (RQ1 e RQ2): código contra discussão e novatos contra experientes, por trimestre
# ================================================================================================

# Métrica: ccr
#   O que é:
#     CCR é o índice do IEICE16 que compara quem faz código com quem só discute:
#     CCR = (código - discussão) / o maior dos dois.
#     Lado do código: a pessoa fez o primeiro commit ou PR antes do fim do trimestre. População do
#     trimestre: quem contribuiu na janela de inatividade (3 meses por padrão) até o fim dele.
#     A replicação faz a mesma conta sobre pirâmides em `metrics.from_pyramids`.
#   Referência:
#     Onoue et al., IEICE16.
#     https://doi.org/10.1587/transinf.2015EDP7363
#   Entrada:
#     `eventos`, `inatividade_dias` (quanto tempo sem contribuir tira a pessoa do trimestre),
#     `novato_dias` (idade máxima de um novato) e `fim`. O estudo usa 12 meses nos dois cortes
#     (`ccr_ncr_inatividade_meses` e `ccr_ncr_novato_meses`). Os padrões da função, 3 e 3 meses,
#     reproduzem o IEICE16.
#   Resultado esperado:
#     Coluna `ccr` da tabela `ccr_ncr_trimestral`, uma linha por trimestre. As colunas da tabela
#     são snapshot (o fim do trimestre), coding, non_coding, new, experienced, total, ccr, ncr e
#     type.
#     O CCR vai de -1 a 1.
#     - Perto de 1: quase só código.
#     - Perto de 0: os dois lados são parecidos.
#     - Perto de -1: quase só discussão.
#     Trimestre sem ninguém ativo não aparece na tabela.

# Métrica: ncr
#   O que é:
#     NCR compara novatos com experientes:
#     NCR = (novatos - experientes) / o maior dos dois.
#     Novato é quem tem até `novato_dias` de idade, contada do primeiro commit ou PR (ou, sem ele,
#     da primeira discussão).
#     A replicação faz a mesma conta sobre pirâmides em `metrics.from_pyramids`.
#   Referência:
#     Onoue et al., IEICE16.
#     https://doi.org/10.1587/transinf.2015EDP7363
#   Entrada:
#     `eventos`, `inatividade_dias` (quanto tempo sem contribuir tira a pessoa do trimestre),
#     `novato_dias` (idade máxima de um novato) e `fim`. O estudo usa 12 meses nos dois cortes
#     (`ccr_ncr_inatividade_meses` e `ccr_ncr_novato_meses`). Os padrões da função, 3 e 3 meses,
#     reproduzem o IEICE16.
#   Resultado esperado:
#     Coluna `ncr` da tabela `ccr_ncr_trimestral`, uma linha por trimestre (as colunas estão
#     listadas em `ccr`).
#     O NCR vai de -1 a 1.
#     - Perto de 1: quase só novatos.
#     - Perto de -1: quase só experientes.

# Métrica: tipo_ccr_ncr
#   O que é:
#     O tipo do trimestre, dado pelo sinal do CCR e do NCR:
#     - Tipo A: CCR maior que 0 e NCR maior que 0 (mais código e mais novatos).
#     - Tipo B: CCR menor que 0 e NCR maior que 0 (mais discussão e mais novatos).
#     - Tipo C: CCR maior que 0 e NCR menor que 0 (mais código e mais experientes).
#     - Tipo D: CCR menor que 0 e NCR menor que 0 (mais discussão e mais experientes).
#     Zero exato cai do lado baixo.
#     A replicação faz a mesma conta sobre pirâmides em `metrics.from_pyramids`.
#   Referência:
#     Onoue et al., IEICE16.
#     https://doi.org/10.1587/transinf.2015EDP7363
#   Entrada:
#     `eventos`, `inatividade_dias` (quanto tempo sem contribuir tira a pessoa do trimestre),
#     `novato_dias` (idade máxima de um novato) e `fim`. O estudo usa 12 meses nos dois cortes
#     (`ccr_ncr_inatividade_meses` e `ccr_ncr_novato_meses`). Os padrões da função, 3 e 3 meses,
#     reproduzem o IEICE16.
#   Resultado esperado:
#     Coluna `type` da tabela `ccr_ncr_trimestral`, uma linha por trimestre (as colunas estão
#     listadas em `ccr`). É uma letra de A a D.
#     Trimestre sem ninguém ativo não aparece na tabela, então fica sem tipo.


def _tipo_ccr_ncr(ccr: float, ncr: float) -> str | None:
    """Tipo A a D pelo sinal dos dois. Zero cai do lado baixo, como em `metrics._type_of`."""
    if not (np.isfinite(ccr) and np.isfinite(ncr)):
        return None
    return {(True, True): "A", (False, True): "B", (True, False): "C", (False, False): "D"}[
        (ccr > 0, ncr > 0)
    ]


def _razao(a: float, b: float) -> float:
    """(a - b) / max(a, b), como `metrics.ratio`. Se os dois são zero, a razão não existe (NaN)."""
    maior = max(a, b)
    return float("nan") if maior == 0 else (a - b) / maior


def ccr_ncr_trimestral(
    eventos: pd.DataFrame,
    inatividade_dias: float = INATIVIDADE_CCR_DIAS,
    novato_dias: float = NOVATO_DIAS,
    fim: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """CCR e NCR de cada trimestre (IEICE16), calculados direto dos eventos reduzidos.

    Dá a mesma conta do motor (`snapshots.pyramid_at` e `metrics.from_pyramids`), sem passar
    pelas etapas do pipeline:

      população   quem contribuiu nos 3 meses até o fim do trimestre (`active`)
      lado        código se o primeiro commit ou PR é de antes do fim do trimestre (inclui o
                  `moved`). Do contrário, discussão
      novato      idade até 91 dias (3 meses), contada do primeiro commit ou PR (ou, sem ele, da
                  primeira discussão)
      CCR         (código - discussão) / o maior dos dois
      NCR         (novatos - experientes) / o maior dos dois

    O último evento de cada pessoa até o fim do trimestre é o último dela naquele trimestre, e
    a redução dos eventos o guarda, então a conta é exata. `inatividade_dias` e `novato_dias`
    trocam os 3 meses por outro corte, para testar a sensibilidade. Com `fim`, o último
    trimestre da série é o último que termina até `fim`. Sem `fim`, vale a regra do motor, que
    para um trimestre antes do último evento.
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
# Magnetismo e stickiness (RQ2): atrair e reter
# ================================================================================================


def pares_de_codigo(eventos: pd.DataFrame) -> pd.DataFrame:
    """Lista única de (scope_id, contributor_id, year), só com commits e pull_requests.

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
#     A fração de quem fez commit ou PR num ano e volta a fazer no ano seguinte, no mesmo escopo.
#     Stickiness quer dizer grude.
#     stickiness(P, Y) = devs de P em Y que contribuem em Y+1 / devs de P em Y.
#     Só commits e PRs contam.
#   Referência:
#     Yamashita et al., MSR 2014.
#     https://doi.org/10.1145/2597073.2597116
#     Ferreira, Silva e Valente, SBES 2020.
#     https://doi.org/10.1145/3422392.3422433
#     ESEM14, seção 3.1.
#   Entrada:
#     `pairs`: a lista única de (scope_id, contributor_id, year), só com commits e pull_requests
#     (`pares_de_codigo` monta a lista a partir dos eventos). Scope é a linguagem ou o projeto.
#     Para o magnetismo, as linguagens entram todas juntas.
#   Resultado esperado:
#     Coluna `stickiness` da tabela `atratividade_anual`, uma linha por (scope_id, year). As
#     colunas da tabela são devs, newcomers_here, newcomers_total, retained, magnetism,
#     stickiness, eligible, median_magnetism, median_stickiness, quadrant, left_censored e
#     right_censored.
#     A stickiness vai de 0 a 1. Exemplo: 0,6 quer dizer que 6 de cada 10 pessoas do ano voltaram
#     no seguinte.
#     O último ano fica sem stickiness, porque falta o ano seguinte.
#     Se o último ano da coleta é incompleto, o ano anterior fica subestimado: quem volta depois
#     do fim da coleta conta como perdido.

# Métrica: magnetismo
#   O que é:
#     Dos novatos do ano em todas as linguagens, a fração que escolheu esta. Magnetismo é o poder
#     de atrair gente nova.
#     magnetismo(P, Y) = novatos de Y que contribuíram em P / novatos de Y em todos os escopos.
#     O plano adia o uso: o denominador só representa o GitHub inteiro se todas as linguagens
#     forem coletadas.
#   Referência:
#     Yamashita et al., MSR 2014.
#     https://doi.org/10.1145/2597073.2597116
#     Ferreira, Silva e Valente, SBES 2020.
#     https://doi.org/10.1145/3422392.3422433
#     ESEM14, seção 3.1.
#   Entrada:
#     `pairs`: a lista única de (scope_id, contributor_id, year), só com commits e pull_requests
#     (`pares_de_codigo` monta a lista a partir dos eventos). Scope é a linguagem ou o projeto.
#     Para o magnetismo, as linguagens entram todas juntas.
#   Resultado esperado:
#     Coluna `magnetism` da tabela `atratividade_anual` (as colunas estão listadas em
#     `stickiness`), de 0 a 1. As colunas `newcomers_here` e `newcomers_total` trazem os novatos
#     da linguagem no ano e os novatos de todas.
#     Exemplo: 0,3 quer dizer que 3 de cada 10 novatos do ano foram para esta linguagem.
#     Fica fora da execução padrão (`--metricas magnetismo`).

# Métrica: quadrante
#   O que é:
#     Cruza magnetismo e stickiness com a mediana (o valor do meio) do ano entre os escopos
#     elegíveis, que são os com mais de 10 ativos no ano. São quatro quadrantes:
#     - `attractive`: os dois acima da mediana.
#     - `floating`: magnetismo acima e stickiness abaixo.
#     - `stagnant`: magnetismo abaixo e stickiness acima.
#     - `terminal`: os dois abaixo.
#     Empate na mediana cai do lado baixo.
#   Referência:
#     Yamashita et al., MSR 2014.
#     https://doi.org/10.1145/2597073.2597116
#     Ferreira, Silva e Valente, SBES 2020.
#     https://doi.org/10.1145/3422392.3422433
#     ESEM14, seção 3.1.
#   Entrada:
#     `pairs`: a lista única de (scope_id, contributor_id, year), só com commits e pull_requests
#     (`pares_de_codigo` monta a lista a partir dos eventos). Scope é a linguagem ou o projeto.
#     Para o magnetismo, as linguagens entram todas juntas.
#   Resultado esperado:
#     Coluna `quadrant` da tabela `atratividade_anual` (as colunas estão listadas em
#     `stickiness`), uma linha por (scope_id, year).
#     É uma das quatro palavras, ou vazio se o escopo não é elegível no ano.


def _voltaram_no_ano_seguinte(pairs: pd.DataFrame) -> pd.DataFrame:
    """Linhas (scope_id, contributor_id, year) em que a pessoa reaparece em Y+1 no mesmo escopo."""
    chaves = ["scope_id", "contributor_id", "year"]
    seguinte = pairs[chaves].assign(year=pairs["year"] - 1)
    return pairs.merge(seguinte, on=chaves, how="inner")


def atratividade_anual(pairs: pd.DataFrame, min_devs: int = 10) -> pd.DataFrame:
    """Uma linha por (escopo, ano) com magnetismo, stickiness e quadrante.

    `min_devs` é o `min_active_devs` do `settings.yaml`: o escopo só é elegível se tiver mais
    pessoas que isso no ano. O corte entre alto e baixo é a mediana anual dos escopos elegíveis.
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

    # Denominador do magnetismo: os novatos do ano em todos os escopos juntos.
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
    # No primeiro ano dos dados (y_min), quem estreia pode ser veterano cuja história ficou fora
    # da coleta. No último ano (y_max), o ano seguinte não existe e a stickiness fica indefinida
    # (NaN). Zero diria que ninguém voltou.
    per["left_censored"] = per["year"] <= y_min
    per["right_censored"] = per["year"] >= y_max
    per.loc[per["right_censored"], "stickiness"] = np.nan

    per["eligible"] = (
        (per["devs"] > min_devs) & per["magnetism"].notna() & per["stickiness"].notna()
    )
    el = per[per["eligible"]]
    per["median_magnetism"] = per["year"].map(el.groupby("year")["magnetism"].median())
    per["median_stickiness"] = per["year"].map(el.groupby("year")["stickiness"].median())

    # Empate na mediana cai do lado baixo: alto quer dizer valor maior que o corte.
    alto_m = per["magnetism"] > per["median_magnetism"]
    alto_s = per["stickiness"] > per["median_stickiness"]
    per["quadrant"] = [
        QUADRANTES[(bool(m), bool(s))] if e else None
        for m, s, e in zip(alto_m, alto_s, per["eligible"], strict=True)
    ]
    return per.sort_values(["year", "scope_id"])[colunas].reset_index(drop=True)


# ================================================================================================
# Índice: de cada métrica à função e à coluna; de cada linha do registro às suas métricas
# ================================================================================================

# Nome da métrica -> (função que calcula, coluna do resultado onde ela aparece).
# Coluna `None`: o resultado inteiro da função é a métrica.
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

# Linha do registro `METRICAS` de scripts/vitalidade.py -> métricas dela.
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
