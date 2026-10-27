"""Métricas de vitalidade de uma linguagem, com a régua do Plano de Experimento.

Funções puras sobre eventos canônicos (`contributor_id`, `event_type`,
`timestamp`). Não sabem de onde vieram os eventos nem gravam nada.

A régua difere da replicação do IEICE16 em três pontos, todos do plano:

  saída    12 meses sem contribuir (Avelino et al., ESEM 2019). O IEICE16 usa 3.
  faixas   0-1, 1-2, 2-3, 3-5, 5-8, 8+ anos na linguagem, contados como ano menos
           ano de entrada (quem entrou em Y está em 0-1 no ano Y).
  passo    anual.

Definições (cada uma é uma escolha registrada em docs/linguagem/vitalidade.md):

  ativo do ano Y   teve pelo menos um evento em Y
  novato de Y      primeiro evento da vida caiu em Y
  saída de Y       o último evento da vida da pessoa caiu em Y, e depois dele vieram
                   mais de 12 meses sem nada até o fim da coleta. É a última da vida
  pausa de Y       um período de atividade terminou em Y, e a pessoa voltou depois de
                   mais de 12 meses. Quem volta não saiu
  volta de Y       começo de período de atividade depois do primeiro caiu em Y
  moved de Y       primeiro commit/PR caiu em Y, depois de já ter discutido

Censura à direita: a saída de Y só se decide 12 meses depois de 31/12/Y. Ano
que a coleta não cobre até lá fica com saída `NaN`. Anualizar está proibido.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

from .classify import DAYS_PER_MONTH
from .projection import _wilcoxon, abre

GAP_DIAS = 12 * DAYS_PER_MONTH
DIAS_POR_ANO = 365.25
TIPOS_CODING = {"commits", "pull_requests"}

FAIXAS = ["0-1", "1-2", "2-3", "3-5", "5-8", "8+"]
_CORTES = [0, 1, 2, 3, 5, 8, math.inf]
FAIXAS_NOVATO = ["0-1"]
FAIXAS_CURTAS = ["0-1", "1-2", "2-3", "3-5"]  # a padronização curta, até 5 anos
FAIXAS_VETERANO = ["5-8", "8+"]


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


def compacta(eventos: pd.DataFrame) -> pd.DataFrame:
    """Reduz os eventos ao que as métricas deste módulo usam, sem mudar nenhum resultado.

    Guarda, de cada pessoa, o primeiro e o último evento de cada trimestre, o último evento
    de código e o último de discussão de cada trimestre, mais o primeiro evento de código e o
    primeiro de discussão da vida. As métricas só dependem de:

      - onde um período de atividade (separado por mais de 12 meses de silêncio)
        começa e termina: um silêncio desses nunca cabe dentro de um trimestre, então
        o primeiro e o último evento de cada trimestre bastam;
      - em que anos a pessoa apareceu e o primeiro e o último evento dela;
      - o primeiro evento de cada lado (código e discussão);
      - o último evento de cada lado, que `deixou_codigo` lê. Guardado por trimestre e não por
        vida, para o corte da coleta num fim de trimestre continuar exato.

    Os eventos que sobram são todos reais. Aplicar de novo ao resultado não muda
    nada, então coletas enormes podem ser compactadas em pedaços.
    """
    ev = eventos[["contributor_id", "event_type", "timestamp"]]
    ev = ev.sort_values(["contributor_id", "timestamp"], kind="stable")
    trimestre = ev["timestamp"].dt.year * 4 + (ev["timestamp"].dt.month - 1) // 3
    por_trimestre = ev.groupby([ev["contributor_id"], trimestre], sort=False)
    codou = ev["event_type"].isin(TIPOS_CODING)
    por_pessoa_codigo = ev[codou].groupby("contributor_id", sort=False)
    por_pessoa_discussao = ev[~codou].groupby("contributor_id", sort=False)
    codigo_por_trimestre = ev[codou].groupby(
        [ev["contributor_id"][codou], trimestre[codou]], sort=False
    )
    discussao_por_trimestre = ev[~codou].groupby(
        [ev["contributor_id"][~codou], trimestre[~codou]], sort=False
    )
    partes = [
        por_trimestre.head(1),
        por_trimestre.tail(1),
        codigo_por_trimestre.tail(1),
        discussao_por_trimestre.tail(1),
        por_pessoa_codigo.head(1),
        por_pessoa_discussao.head(1),
    ]
    out = pd.concat(partes).drop_duplicates()
    out["event_type"] = out["event_type"].astype(str)
    return out.sort_values(["contributor_id", "timestamp"], kind="stable").reset_index(drop=True)


def so_quem_codou(eventos: pd.DataFrame) -> pd.DataFrame:
    """Os eventos de quem fez ao menos um commit ou PR na vida, inclusive os de discussão.

    Tira o público que só abre issue ou comenta, que dá metade das pessoas de cada
    linguagem. A pessoa entra na população no primeiro evento dela, de qualquer tipo.
    """
    codou = eventos.loc[eventos["event_type"].isin(TIPOS_CODING), "contributor_id"].unique()
    return eventos[eventos["contributor_id"].isin(codou)]


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


NOVATO_DIAS = round(
    3 * DAYS_PER_MONTH
)  # 91, a banda de 3 meses do pipeline do figuras_linguagem_bruta
INATIVIDADE_CCR_DIAS = 3 * DAYS_PER_MONTH  # "did not give any contribution for more than 3 months"


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


# As quatro categorias da pirâmide no fim do ano. Esquerda: só discussão e quem codou e passou a
# discutir. Direita: quem discutiu primeiro e passou a codar (`moved`) e o resto de quem codou.
LADOS = ["non_coding", "moved_to_discussion", "moved", "coding"]

BAND_DIAS = 90  # trimestre de 90 dias, como o `band_days` da replicação do IEICE16


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


def ate_a_data(eventos: pd.DataFrame, fim: pd.Timestamp) -> pd.DataFrame:
    """Os eventos até `fim`, como se a coleta tivesse terminado ali.

    Quem só aparece depois some, e quem aparece nos dois lados fica com o último evento de antes.
    A compactação é exata quando `fim` cai no fim de um trimestre.
    """
    return eventos[eventos["timestamp"] <= fim]


def so_quem_passou_de(eventos: pd.DataFrame, dias: float = 90) -> pd.DataFrame:
    """Os eventos de quem tem ao menos uma contribuição `dias` ou mais depois da primeira.

    A pessoa só conta como viva depois de provar presença: um evento a pelo menos `dias` dias do
    primeiro. É o nascimento reconhecido com atraso, como a saída é reconhecida com 12 meses de
    silêncio. O corte olha o futuro da pessoa, então derruba a saída dos novatos e infla a
    retenção deles, e não serve para as taxas de saída da faixa 0-1. Serve para a composição
    (pirâmide).
    """
    por_pessoa = eventos.groupby("contributor_id")["timestamp"]
    vida = por_pessoa.max() - por_pessoa.min()
    passou = vida >= pd.Timedelta(days=dias)
    return eventos[eventos["contributor_id"].isin(passou[passou].index)]


def tira_pessoas_de_um_dia(eventos: pd.DataFrame) -> pd.DataFrame:
    """Os eventos de quem teve atividade em mais de um dia. Tira quem entrou e sumiu no mesmo dia.

    O corte olha o futuro da pessoa: ela só entra se voltou em outro dia. Por isso derruba a
    saída dos novatos e infla a retenção, e serve de sensibilidade, não de população principal.
    """
    por_pessoa = eventos.groupby("contributor_id")["timestamp"]
    mais_de_um = por_pessoa.max().dt.normalize() > por_pessoa.min().dt.normalize()
    return eventos[eventos["contributor_id"].isin(mais_de_um[mais_de_um].index)]


def composicao(pa: pd.DataFrame) -> pd.DataFrame:
    """Ativos por (ano, faixa) nas quatro categorias da pirâmide (ver `LADOS`)."""
    t = pa.groupby(["ano", "faixa", "categoria"], observed=False).size().unstack(fill_value=0)
    for coluna in LADOS:
        if coluna not in t.columns:
            t[coluna] = 0
    return t[LADOS].reset_index()


def indice_envelhecimento(pa: pd.DataFrame) -> pd.DataFrame:
    """Ativos com 5 anos ou mais na linguagem divididos pelos ativos com menos de 1, por ano."""
    veteranos = pa[pa["faixa"].isin(FAIXAS_VETERANO)].groupby("ano").size()
    novatos = pa[pa["faixa"].isin(FAIXAS_NOVATO)].groupby("ano").size()
    t = pd.DataFrame({"veteranos": veteranos, "novatos": novatos}).fillna(0).astype(int)
    t["indice"] = t["veteranos"] / t["novatos"].where(t["novatos"] > 0)
    t.index.name = "ano"
    return t.reset_index()


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


def tabuas_por_coorte(dur: pd.DataFrame) -> pd.DataFrame:
    """`tabua_de_vida` de cada coorte de entrada, empilhadas com a coluna `coorte`."""
    frames = []
    for coorte, grupo in dur.groupby("coorte"):
        t = tabua_de_vida(grupo)
        t.insert(0, "coorte", coorte)
        frames.append(t)
    return pd.concat(frames, ignore_index=True)


# Etapa 5: Kaplan-Meier e log-rank (RQ2).


def _amostra_censurada(dur: pd.DataFrame) -> stats.CensoredData:
    """Duração de `duracoes`, com quem não saiu marcado como censura à direita."""
    return stats.CensoredData.right_censored(
        dur["duracao_anos"].to_numpy(), ~dur["saiu"].to_numpy()
    )


# Acima disso a curva sai com um ponto por dia: milhões de pessoas dariam um ponto por pessoa.
MAX_PONTOS_KM = 2_000_000


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


# Etapa 6: taxa padronizada por faixa e SMR (RQ2).


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


# Etapa 7: projeção anual em bandas de 1 ano (RQ3).
#
# Banda = idade em anos de calendário, de 0 a 7, e a 8+ aberta no índice 8.
# Cada banda de 0 a 7 é uma coorte de entrada só, então a coorte da banda a em
# T está na banda a+1 em T+1. A 8+ recebe a banda 7 e guarda quem já estava nela:
#   P(8+, T+1) = SR(7) P(7, T) + SR(8+) P(8+, T)

BANDAS = 9
METODOS = ["ingenuo", "coorte", "pessimista", "conservador", "otimista"]
METODOS_COM_ERRO = ["ingenuo", "coorte", "conservador"]


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
