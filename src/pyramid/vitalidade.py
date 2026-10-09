"""Métricas de vitalidade de uma linguagem, com a régua do Plano de Experimento.

Funções puras sobre eventos canônicos (`contributor_id`, `event_type`,
`timestamp`). Não sabem de onde vieram os eventos nem gravam nada.

A régua difere da replicação do IEICE16 em três pontos, todos do plano:

  saída    12 meses sem contribuir (Avelino et al., ESEM 2019). O IEICE16 usa 3.
  faixas   0-1, 1-2, 2-3, 3-5, 5-8, 8+ anos de casa, contados como ano menos
           ano de entrada (quem entrou em Y está em 0-1 no ano Y).
  passo    anual.

Definições (cada uma é uma escolha registrada em docs/linguagem/vitalidade.md):

  ativo do ano Y   teve pelo menos um evento em Y
  novato de Y      primeiro evento da vida caiu em Y
  saída de Y       último evento de um período de atividade caiu em Y, e depois
                   dele vieram mais de 12 meses sem nada
  volta de Y       começo de período de atividade depois do primeiro caiu em Y
  moved de Y       primeiro commit/PR caiu em Y, depois de já ter discutido

Censura à direita: a saída de Y só se decide 12 meses depois de 31/12/Y. Ano
que a coleta não cobre até lá fica com saída `NaN`. Anualizar está proibido.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy import stats

from .classify import DAYS_PER_MONTH, profile
from .projection import _wilcoxon, abre

GAP_DIAS = 12 * DAYS_PER_MONTH
DIAS_POR_ANO = 365.25
TIPOS_CODING = {"commits", "pull_requests"}

FAIXAS = ["0-1", "1-2", "2-3", "3-5", "5-8", "8+"]
_CORTES = [0, 1, 2, 3, 5, 8, math.inf]
FAIXAS_NOVATO = ["0-1"]
FAIXAS_VETERANO = ["5-8", "8+"]


def faixa_de(anos: pd.Series) -> pd.Series:
    """Faixa de tempo de casa, fechada embaixo: 1 ano cai em 1-2."""
    return pd.cut(anos, bins=_CORTES, right=False, labels=FAIXAS)


def ano_fechado(ano: int, fim: pd.Timestamp) -> bool:
    """A coleta cobre 12 meses depois do fim de `ano`, então toda saída dele se decide."""
    return fim > pd.Timestamp(f"{ano + 1}-01-01") + pd.Timedelta(days=GAP_DIAS)


def pessoa_ano(eventos: pd.DataFrame, fim: pd.Timestamp | None = None) -> pd.DataFrame:
    """Uma linha por (pessoa, ano em que contribuiu). Base de toda métrica anual.

    `fim` é o último instante coberto pela coleta. Padrão: o evento mais recente.
    """
    if fim is None:
        fim = eventos["timestamp"].max()
    ev = eventos[["contributor_id", "event_type", "timestamp"]]

    spans = profile(ev, TIPOS_CODING, GAP_DIAS)
    marcos = spans.groupby("contributor_id").agg(
        init_c=("init_c", "first"), init_d=("init_d", "first"), primeiro=("span_start", "min")
    )

    pa = ev.assign(ano=ev["timestamp"].dt.year)[["contributor_id", "ano"]].drop_duplicates()
    pa = pa.join(marcos, on="contributor_id")

    fim_ano = pd.to_datetime((pa["ano"] + 1).astype(str) + "-01-01")
    # Idade em anos de calendário: cada faixa de 1 ano é exatamente uma coorte
    # de entrada, que é o que a projeção por coorte precisa para envelhecer 1 por ano.
    pa["idade_anos"] = pa["ano"] - pa["primeiro"].dt.year
    pa["faixa"] = faixa_de(pa["idade_anos"])
    pa["novato"] = pa["primeiro"].dt.year == pa["ano"]

    # Mesma regra de `snapshots.pyramid_at`, avaliada no fim do ano.
    codou = pa["init_c"].notna() & (pa["init_c"] < fim_ano)
    moved = codou & pa["init_d"].notna() & (pa["init_d"] < pa["init_c"])
    pa["categoria"] = np.where(codou, np.where(moved, "moved", "coding"), "non_coding")
    pa["moved_no_ano"] = moved & (pa["init_c"].dt.year == pa["ano"])

    # Todo período que não é o último já termina com mais de 12 meses de silêncio
    # (é o que o separou do seguinte), então basta medir a distância até `fim`.
    parou = (fim - spans["span_end"]) > pd.Timedelta(days=GAP_DIAS)
    saidas = spans.loc[parou, ["contributor_id"]].assign(
        ano=spans.loc[parou, "span_end"].dt.year, saida=True
    )
    voltou = spans["span_idx"] > 0
    voltas = spans.loc[voltou, ["contributor_id"]].assign(
        ano=spans.loc[voltou, "span_start"].dt.year, volta=True
    )
    pa = pa.merge(saidas, on=["contributor_id", "ano"], how="left")
    pa = pa.merge(voltas, on=["contributor_id", "ano"], how="left")
    pa["saida"] = pa["saida"].eq(True)
    pa["volta"] = pa["volta"].eq(True)

    # Dois períodos separados por 12 meses não terminam (nem começam) no mesmo ano.
    if pa.duplicated(["contributor_id", "ano"]).any():
        raise ValueError("pessoa_ano: (pessoa, ano) repetido; mais de uma saída ou volta no ano.")
    return pa.drop(columns=["init_c", "init_d"]).reset_index(drop=True)


def tabela_anual(pa: pd.DataFrame, fim: pd.Timestamp) -> pd.DataFrame:
    """Ativos, novatos, saídas, voltas, moved e crescimento natural, por ano.

    Falha alto se a conta não fecha: ativos(Y+1) = ativos(Y) - saídas(Y) +
    novatos(Y+1) + voltas(Y+1), para todo Y com saída decidida.
    """
    g = pa.groupby("ano")
    t = pd.DataFrame(
        {
            "ativos": g.size(),
            "novatos": g["novato"].sum(),
            "saidas": g["saida"].sum().astype(float),
            "voltas": g["volta"].sum(),
            "moved": g["moved_no_ano"].sum(),
        }
    )
    for ano in t.index:
        if not ano_fechado(ano, fim):
            t.loc[ano, "saidas"] = np.nan
    t["crescimento_natural_pct"] = 100 * (t["novatos"] - t["saidas"]) / t["ativos"]

    for ano in t.index:
        if ano + 1 not in t.index or pd.isna(t.loc[ano, "saidas"]):
            continue
        esperado = (
            t.loc[ano, "ativos"]
            - t.loc[ano, "saidas"]
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


def composicao(pa: pd.DataFrame) -> pd.DataFrame:
    """Ativos por (ano, faixa) em cada lado da pirâmide: non_coding, moved, coding."""
    t = pa.groupby(["ano", "faixa", "categoria"], observed=False).size().unstack(fill_value=0)
    for coluna in ("non_coding", "moved", "coding"):
        if coluna not in t.columns:
            t[coluna] = 0
    return t[["non_coding", "moved", "coding"]].reset_index()


def indice_envelhecimento(pa: pd.DataFrame) -> pd.DataFrame:
    """Ativos com 5 anos ou mais de casa divididos pelos ativos com menos de 1, por ano."""
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
        if not ano_fechado(int(t.loc[i, "ano"]), fim):
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


def tabua_de_vida(dur: pd.DataFrame) -> pd.DataFrame:
    """Tábua de vida atuarial em intervalos de 1 ano de casa.

    l(x)  pessoas ainda em observação ao chegar em x anos
    d(x)  saídas entre x e x+1
    q(x)  d(x) / (l(x) - censurados(x)/2): o censurado conta meio intervalo de exposição
    S(x)  fração que chega em x, produto de (1 - q) até x-1
    e(x)  anos que ainda restam, em média, a quem chegou em x

    Quando a tábua termina com gente censurada (S final > 0), a cauda depois do
    último intervalo observado não entra, e e(x) é um piso. `e_truncado` marca.
    """
    colunas = ["x", "l", "d", "censurados", "q", "S", "e", "e_truncado"]
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
        linhas.append({"x": x, "l": em_risco, "d": d, "censurados": c, "q": q, "S": sobrevivencia})
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


def kaplan_meier(dur: pd.DataFrame) -> pd.DataFrame:
    """Fração estimada ainda ativa, `S`, depois de `anos` desde a primeira contribuição."""
    sf = stats.ecdf(_amostra_censurada(dur)).sf
    return pd.DataFrame({"anos": sf.quantiles, "S": sf.probabilities})


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


def cenarios(
    pop: pd.DataFrame, saidas: pd.DataFrame, ate_ano: int, min_saidas: int
) -> dict[str, tuple[np.ndarray, float]]:
    """(permanência, novatos) de cada cenário, só com a série até `ate_ano`.

    pessimista  menor valor histórico; otimista  maior; conservador  a média dos dois.
    A permanência de a de Y-1 para Y só entra quando a banda a teve pelo menos
    `min_saidas` saídas em Y-1. Banda sem nenhum ano válido usa a permanência do
    último ano nos três cenários, a mesma do coorte.
    """
    historico = []
    for ano in range(int(pop.index.min()) + 1, ate_ano + 1):
        sr = permanencia(pop, ano)
        for a in range(BANDAS):
            if not saidas.loc[ano - 1, a] >= min_saidas:
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
    novatos = pop.loc[:ate_ano, 0]
    return {
        "pessimista": (menor, float(novatos.min())),
        "conservador": ((menor + maior) / 2, float(novatos.min() + novatos.max()) / 2),
        "otimista": (maior, float(novatos.max())),
    }


def _projecoes(
    pop: pd.DataFrame, saidas: pd.DataFrame, base: int, teto: bool, min_saidas: int
) -> dict[str, np.ndarray]:
    """Pirâmide de `base + 1` por cada método, usando só a série até `base`."""
    p = _bandas(pop.loc[base])
    novatos_coorte = (pop.loc[base, 0] + pop.loc[base - 1, 0]) / 2
    proj = {
        "ingenuo": p,
        "coorte": projeta_um_ano(p, permanencia(pop, base), novatos_coorte, teto),
    }
    for nome, (sr, novatos) in cenarios(pop, saidas, base, min_saidas).items():
        proj[nome] = projeta_um_ano(p, sr, novatos, teto)
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
    pa: pd.DataFrame, fim: pd.Timestamp, ultimo_ano: int, teto: bool, min_saidas: int
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
        for metodo, v in _projecoes(pop, saidas, alvo - 1, teto, min_saidas).items():
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
    pa: pd.DataFrame, fim: pd.Timestamp, ultimo_ano: int, anos: int, teto: bool, min_saidas: int
) -> pd.DataFrame:
    """Projeta `anos` anos depois de `ultimo_ano`, um ano por vez.

    O coorte usa a permanência do último par observado e, como novatos, a
    média dos dois anos anteriores (já projetados, depois do primeiro passo).
    Cada cenário fixa a sua permanência e os seus novatos.
    """
    pop = populacao_por_idade(pa)
    p_ultimo = _bandas(pop.loc[ultimo_ano])
    sr_coorte = permanencia(pop, ultimo_ano)
    fixos = cenarios(pop, saidas_por_banda(pa, fim), ultimo_ano, min_saidas)

    atual = dict.fromkeys(METODOS, p_ultimo)
    anterior_coorte = _bandas(pop.loc[ultimo_ano - 1])
    linhas = []
    for ano in range(ultimo_ano + 1, ultimo_ano + anos + 1):
        novatos = (atual["coorte"][0] + anterior_coorte[0]) / 2
        anterior_coorte = atual["coorte"]
        atual["coorte"] = projeta_um_ano(atual["coorte"], sr_coorte, novatos, teto)
        for nome, (sr, novatos_cenario) in fixos.items():
            atual[nome] = projeta_um_ano(atual[nome], sr, novatos_cenario, teto)
        for metodo in METODOS:
            for faixa, valor in _por_faixa(atual[metodo]).items():
                linhas.append({"ano": ano, "metodo": metodo, "faixa": faixa, "previsto": valor})
    return pd.DataFrame(linhas)
