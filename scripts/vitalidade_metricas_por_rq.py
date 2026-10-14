"""Escreve METRICAS_POR_RQ.md: as métricas de cada pergunta de pesquisa, na ordem do plano.

    uv run python scripts/vitalidade_metricas_por_rq.py --saida ~/Documents/pyramid-vitalidade

A ordem e as definições vêm da tabela "Variáveis dependentes" do Plano de Experimento. Cada
métrica mostra o que o plano pede, como está aqui, a tabela com os números e a figura. Todo número
vem dos CSV; a seção de diferenças lista onde a implementação saiu do plano.
"""

import argparse
import json
from pathlib import Path

import pandas as pd

import carga_fonte
import vitalidade as v
from vitalidade_relatorio import por_linguagem, tabela_md

RQ1 = "RQ1: Como a população de Clojure mudou entre 2008 e 2026?"
RQ2 = (
    "RQ2: Como está Clojure quando comparado com (a) linguagens de nicho (Elixir, Zig e OCaml) "
    "e (b) Python?"
)
RQ3 = "RQ3: Quais os cenários (otimista, pessimista e conservador) para Clojure nos próximos anos?"


class Pastas:
    """Onde estão os CSV e as figuras de cada linguagem e do comparativo."""

    def __init__(self, base: Path, populacao: str):
        sufixo = "" if populacao == "todos" else f"-{populacao}"
        self.base = base
        self.sufixo = sufixo

    def linguagem(self, slug: str) -> str:
        return f"{slug}{self.sufixo}"

    def csv(self, pasta: str, nome: str) -> pd.DataFrame:
        return pd.read_csv(self.base / pasta / "csv" / "vitalidade" / nome)


def figura(base: Path, caminho: str, legenda: str) -> str:
    """Imagem embutida. Figura que não existe vira aviso, para o documento não mentir."""
    if not (base / caminho).exists():
        return f"*Figura ausente: `{caminho}`. Rode `vitalidade.py --so-figuras`.*"
    return f"![{legenda}]({caminho})"


def glossario() -> str:
    linhas = [
        "## Como ler cada métrica, em palavras",
        "",
        "- **Ativos**: pessoas com pelo menos um evento (commit, PR, issue ou comentário) no ano.",
        "- **Novatos**: pessoas cuja primeira contribuição na vida cai no ano.",
        "- **Saída**: a última contribuição da vida, seguida de 12 meses sem nada. Quem para por "
        "12 meses e volta tem uma pausa. Para confirmar os 12 meses é preciso acompanhar a pessoa "
        "depois do ano. O estudo vai até 31/12/2025, e os eventos de 2026 só servem para decidir "
        "quem saiu, quem pausou e quem pertence à população. Quem parou há menos de 12 meses do "
        "fim da coleta ainda pode voltar, então a saída de 2025 pode estar um pouco alta.",
        "- **Natalidade e mortalidade**: natalidade é o que entra no ano (novatos e voltas) e "
        "mortalidade é o que sai (saídas e pausas), as duas em % dos ativos do ano.",
        "- **Crescimento natural**: tudo que entra menos tudo que sai, em % dos ativos do ano. "
        "É a natalidade menos a mortalidade. A base é o próprio ano, e não os ativos do ano "
        "anterior.",
        "- **Reposição**: novatos do ano divididos pelas saídas do ano. Abaixo de 1 a "
        "comunidade não repõe quem sai.",
        "- **Índice de envelhecimento**: ativos com 5 anos ou mais de casa divididos pelos ativos "
        "com menos de 1 ano de casa. A idade é o tempo na linguagem, não a idade da pessoa. "
        "Com índice 1 há tantos veteranos quanto novatos. Quando sobe, a base da pirâmide "
        "encolhe mais rápido que o topo.",
        "- **Coorte**: o grupo que entrou no mesmo ano. **Sobrevivência por coorte** é a fração "
        "desse grupo ainda ativa x anos depois. Coorte 2010 de Clojure com 0,83 depois de 1 ano "
        "quer dizer que de cada 100 pessoas que entraram em 2010, 83 seguiam ativas um ano "
        "depois.",
        "- **Pessoas ainda ativas no fim da coleta**: não dá para saber se vão sair. Elas não "
        "entram como saída, e só contam como observadas na metade do tempo. Contá-las como saída "
        "inflaria as saídas, e ignorá-las inflaria a retenção. Em estatística isso se chama "
        "censura à direita, o termo do plano.",
        "- **Tábua de vida**: para cada ano de casa x, quantas pessoas chegaram a x, quantas "
        "saíram no ano x, a chance de sair no ano x, a fração que chega a x e quantos anos ainda "
        "restam em média.",
        "- **Chance de seguir mais 1 ano**: 1 menos a chance de sair no ano x, entre quem chegou "
        "a x. Olha só o ano seguinte.",
        "- **Margem de erro de 95%**: a faixa em que o valor verdadeiro provavelmente está, dado "
        "quantas pessoas foram observadas. Com poucas pessoas a faixa fica larga. Não olha mais "
        "anos à frente. Funciona como a margem de erro de uma pesquisa eleitoral.",
        "- **Taxa padronizada**: a taxa de saída de cada faixa de tempo de casa, combinada com os "
        "pesos de uma composição de referência única. Cada linguagem é calculada como se tivesse "
        "a mesma mistura de novatos e veteranos, e assim a diferença que sobra é de retenção. "
        "Aqui só as faixas de 0 a 5 anos, que existem em todas as linguagens cinco anos depois "
        "do nascimento delas.",
        "- **SMR**: saídas observadas divididas pelas saídas esperadas, se a linguagem tivesse as "
        "taxas de saída da referência em cada faixa. Acima de 1: saiu mais gente que o esperado.",
        "- **Kaplan-Meier**: estima a probabilidade de uma pessoa ainda estar ativa t anos "
        "depois de entrar, usando a duração de cada pessoa (do primeiro ao último evento) e "
        "tratando quem segue ativo como ainda sem saída. A curva desce em degraus.",
        "- **Log-rank**: teste de que duas curvas de Kaplan-Meier são iguais. Com milhares de "
        "pessoas o p fica minúsculo para qualquer diferença. O que informa é o tamanho dela, "
        "por exemplo 0,28 contra 0,36 de fração ativa depois de 5 anos.",
        "- **CCR e NCR**: (código - discussão) / o maior dos dois, e (novatos - experientes) / o "
        "maior dos dois. O sinal dos dois dá o tipo: A mais código e mais novatos, B mais "
        "discussão e mais novatos, C mais código e mais experientes, D mais discussão e mais "
        "experientes.",
        "",
        "## Cuidados ao ler os números",
        "",
        "- **Poucas pessoas, números instáveis.** Uma taxa calculada sobre dez pessoas pode "
        "dar 0% ou 30% só por acaso. Os pontos do gráfico com menos de 30 pessoas observadas "
        "aparecem vazados, e a tabela do relatório traz a margem de erro.",
        "- **Quem tem muitos anos de casa é o primeiro grupo a entrar.** Em qualquer linguagem, "
        "os veteranos de 8 anos são quem chegou cedo, e isso pode diferenciá-los dos demais. "
        "Em linguagem jovem, como o Zig, são poucas pessoas.",
        "",
    ]
    return "\n".join(linhas)


def amostra(pastas: Pastas, p: v.Parametros) -> str:
    """Repositórios e pessoas de cada linguagem, lidos da carga gravada junto dos resultados."""
    linhas = []
    for slug in p.linguagens_rq2:
        pasta = pastas.linguagem(slug)
        meta = json.loads(
            (pastas.base / pasta / "resultados" / "vitalidade" / "meta.json").read_text()
        )
        a = meta.get("amostra", {})
        if "repos_finais" not in a:
            return (
                "## Amostra\n\nSem as contagens da carga: rode `vitalidade.py --sem-cache` "
                "em cada linguagem uma vez.\n"
            )
        linhas.append(
            {
                "linguagem": carga_fonte.LINGUAGENS[slug].nome,
                "repositórios candidatos": a["repos_total"],
                "excluídos, 50% do código ou menos": a["repos_excluidos_share"],
                "elegíveis": a["repos_elegiveis"],
                "com algum evento": a["repos_finais"],
                "pessoas com algum evento": a["contribuidores_finais"],
                f"pessoas na população {p.populacao}": a["pessoas_na_populacao"],
            }
        )
    tabela = pd.DataFrame(linhas).set_index("linguagem")
    texto = [
        "## Amostra",
        "",
        "- Candidatos: repositórios com 10 estrelas ou mais, listados pela SEART.",
        "- Elegíveis: mais de 50% do código do repositório na linguagem.",
        "- Com algum evento: elegíveis que sobram com pelo menos um evento depois dos filtros "
        "de autor, bot, data e commit copiado.",
        "- Pessoas: quem tem algum evento nesses repositórios, e quem entra na população do "
        "estudo.",
        "",
        tabela_md(tabela),
        "",
    ]
    return "\n".join(texto)


def marca_provisorios(t: pd.DataFrame, primeiro_provisorio: int) -> pd.DataFrame:
    """Põe um asterisco no ano das linhas com saída provisória."""
    t = t.copy()
    rotulos = []
    for ano in t.index:
        rotulos.append(f"{ano}*" if ano >= primeiro_provisorio else str(ano))
    t.index = rotulos
    return t


def renovacao(pastas: Pastas, p: v.Parametros, ano_ref: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Medidas de renovação de Clojure por ano e das cinco linguagens no ano de referência."""
    por_linguagem_e_ano = {}
    for slug in p.linguagens_rq2:
        lingua = pastas.linguagem(slug)
        a = pastas.csv(lingua, "anual.csv").set_index("ano")
        i = pastas.csv(lingua, "indice_envelhecimento.csv").set_index("ano")
        t = pd.DataFrame(index=a.index)
        t["ativos"] = a["ativos"]
        t["novatos"] = a["novatos"]
        t["saídas"] = a["saidas"]
        t["novatos por saída"] = a["novatos"] / a["saidas"].where(a["saidas"] > 0)
        t["% com menos de 1 ano"] = 100 * i["novatos"] / a["ativos"]
        t["% com 5 anos ou mais"] = 100 * i["veteranos"] / a["ativos"]
        t["índice de envelhecimento"] = i["indice"]
        por_linguagem_e_ano[slug] = t

    clojure = por_linguagem_e_ano["clojure"]
    clojure = clojure[(clojure.index >= 2012) & (clojure.index <= ano_ref)]
    clojure.index.name = "ano"

    comparacao = []
    for slug, t in por_linguagem_e_ano.items():
        if ano_ref in t.index and t.loc[ano_ref, "ativos"] >= 100:
            linha = t.loc[ano_ref, ["ativos", "novatos por saída", "% com menos de 1 ano"]].copy()
            linha["% com 5 anos ou mais"] = t.loc[ano_ref, "% com 5 anos ou mais"]
            linha["índice de envelhecimento"] = t.loc[ano_ref, "índice de envelhecimento"]
            linha.name = carga_fonte.LINGUAGENS[slug].nome
            comparacao.append(linha)
    comparacao = pd.DataFrame(comparacao)
    comparacao.index.name = "linguagem"
    return clojure, comparacao


def rq1(pastas: Pastas, p: v.Parametros) -> str:
    c = pastas.linguagem("clojure")
    ultimo = pd.Timestamp(p.data_de_corte).year
    ano_ref = ultimo - 1
    meta = json.loads((pastas.base / c / "resultados" / "vitalidade" / "meta.json").read_text())
    fim_acompanhamento = pd.Timestamp(meta.get("fim_acompanhamento") or meta["fim"])
    primeiro_provisorio = fim_acompanhamento.year - p.carencia_anos + 1

    anual = pastas.csv(c, "anual.csv").set_index("ano")
    tamanho = anual[
        [
            "ativos",
            "novatos",
            "voltas",
            "saidas",
            "pausas",
            "natalidade_pct",
            "mortalidade_pct",
            "crescimento_natural_pct",
        ]
    ].copy()
    tamanho.index.name = "ano"
    tamanho = tamanho.rename(
        columns={
            "saidas": "saídas",
            "natalidade_pct": "natalidade %",
            "mortalidade_pct": "mortalidade %",
            "crescimento_natural_pct": "crescimento natural %",
        }
    )

    envelhecimento = pastas.csv(c, "indice_envelhecimento.csv").set_index("ano")
    envelhecimento = envelhecimento[envelhecimento["veteranos"] > 0]
    envelhecimento = envelhecimento.rename(columns={"indice": "índice de envelhecimento"})

    clojure_renovacao, comparacao = renovacao(pastas, p, ano_ref)
    ref = clojure_renovacao.loc[ano_ref]
    ano_1 = clojure_renovacao[clojure_renovacao["novatos por saída"] >= 1].index.max()
    outras = comparacao.drop(index="Clojure")
    por_saida = "; ".join(f"{n} {num_f(v)}" for n, v in outras["novatos por saída"].items())
    por_topo = "; ".join(f"{n} {num_f(v, 0)}%" for n, v in outras["% com 5 anos ou mais"].items())
    menor_reposicao = ref["novatos por saída"] < outras["novatos por saída"].min()
    maior_topo = ref["% com 5 anos ou mais"] > outras["% com 5 anos ou mais"].max()

    coortes = pastas.csv(c, "tabua_coortes.csv")
    retencao = pd.DataFrame()
    for x in (1, 3, 5):
        parte = coortes[coortes["x"] == x].set_index("coorte")["S"]
        retencao[f"depois de {x} anos"] = parte
    retencao = retencao[retencao.index >= 2010]
    retencao.index.name = "coorte"
    primeira = retencao.index.min()
    # A última coorte cujos 3 anos já passaram inteiros dentro do acompanhamento.
    ultima_com_x3 = min(
        retencao["depois de 3 anos"].dropna().index.max(), fim_acompanhamento.year - 5
    )

    ccr = pastas.csv("geral" + pastas.sufixo, "ccr_ncr_comparado.csv")
    ccr = ccr[ccr["slug"] == "clojure"].copy()
    ccr["snapshot"] = pd.to_datetime(ccr["snapshot"])
    ccr = ccr[(ccr["snapshot"].dt.month == 12) & (ccr["total"] >= 100)]
    ccr["ano"] = ccr["snapshot"].dt.year
    ccr_tabela = ccr.set_index("ano")[["total", "ccr", "ncr", "type"]]
    ccr_tabela = ccr_tabela.rename(columns={"total": "ativos", "type": "tipo"})

    linhas = [
        f"## {RQ1}",
        "",
        f"O estudo vai até {ultimo}. Os eventos de 2026 não entram nas contagens.",
        "",
        "### 1.1 Tamanho: natalidade, mortalidade e crescimento natural",
        "",
        "- Plano: crescimento natural = (novatos - saídas) / ativos, em %.",
        "- Aqui: crescimento natural é tudo que entra menos tudo que sai, em % dos ativos do ano. "
        "Entram os novatos e as voltas, saem as saídas e as pausas.",
        "- Natalidade é o que entra sobre os ativos, mortalidade é o que sai sobre os ativos, "
        "e a diferença entre as duas é o crescimento natural.",
        f"- A saída de {ultimo} pode estar um pouco alta: quem parou há menos de 12 meses do fim "
        "da coleta ainda pode voltar.",
        "",
        tabela_md(marca_provisorios(tamanho, primeiro_provisorio), 1),
        "",
        "**Natalidade e mortalidade, sem os ativos ao fundo**",
        "",
        figura(
            pastas.base, f"{c}/vitalidade/natalidade_mortalidade.png", "natalidade e mortalidade"
        ),
        "",
        "**O mesmo gráfico, com os ativos de cada ano ao fundo**",
        "",
        figura(
            pastas.base,
            f"{c}/vitalidade/natalidade_mortalidade_com_ativos.png",
            "natalidade e mortalidade com os ativos",
        ),
        "",
        figura(pastas.base, f"{c}/vitalidade/crescimento.png", "crescimento natural"),
        "",
        figura(pastas.base, f"{c}/vitalidade/anual.png", "ativos, novatos, saídas e voltas"),
        "",
        "### 1.2 Composição: estrutura etária e índice de envelhecimento",
        "",
        "- Plano: pessoas ativas por faixa de tempo de contribuição (a pirâmide) e índice de "
        "envelhecimento.",
        "- Aqui: faixas 0-1, 1-2, 2-3, 3-5, 5-8 e 8+. Índice = ativos com 5 anos ou mais de casa "
        "dividido pelos ativos com menos de 1.",
        "",
        tabela_md(envelhecimento, 2),
        "",
        figura(pastas.base, f"{c}/vitalidade/piramides_faixa_pct.png", "pirâmides"),
        "",
        figura(pastas.base, f"{c}/vitalidade/indice_envelhecimento.png", "índice"),
        "",
        "### 1.3 Retenção: sobrevivência por coorte",
        "",
        "- Plano: fração de quem entrou junto que ainda está ativa 12 meses depois, por ano de "
        "entrada.",
        "- Aqui: a mesma fração para 1, 3 e 5 anos depois. A coluna de 1 ano é a do plano.",
        "- As coortes mais recentes ainda têm gente ativa no fim da coleta, sem saída "
        "confirmada. Os valores delas se leem com cautela.",
        "",
        tabela_md(retencao, 2),
        "",
        figura(pastas.base, f"{c}/vitalidade/tabua_coortes.png", "coortes"),
        "",
        "### 1.4 CCR e NCR (RQ1 e RQ2)",
        "",
        "- Plano: CCR = (código - discussão) / o maior dos dois. NCR = (novatos - experientes) / o "
        "maior dos dois. O sinal dos dois classifica o trimestre nos tipos A a D.",
        f"- Aqui: quem contribuiu em {p.ccr_ncr_inatividade_meses:g} meses, novato com até "
        f"{p.ccr_ncr_novato_meses:g} meses de casa. Valores no fim de cada ano.",
        "",
        tabela_md(ccr_tabela, 2),
        "",
        "### 1.5 Clojure é uma comunidade envelhecida que não se renova?",
        "",
        "A pergunta, em termos demográficos: a comunidade repõe quem sai, e o tempo de casa de "
        f"quem fica sobe? As medidas abaixo usam {ano_ref}, o último ano com saída confirmada. "
        "A idade é o tempo na linguagem.",
        "",
        f"1. **Reposição.** Em {ano_ref} entraram {num_i(ref['novatos'])} novatos para "
        f"{num_i(ref['saídas'])} saídas: {num_f(ref['novatos por saída'])} novato para cada "
        f"saída. Desde {ano_1 + 1} a reposição fica abaixo de 1. Nas outras linguagens em "
        f"{ano_ref}: {por_saida}.",
        f"2. **Base da pirâmide.** Os ativos com menos de 1 ano de casa eram "
        f"{num_f(clojure_renovacao['% com menos de 1 ano'].iloc[0], 0)}% em "
        f"{clojure_renovacao.index.min()} e são {num_f(ref['% com menos de 1 ano'], 0)}% em "
        f"{ano_ref}.",
        f"3. **Topo da pirâmide.** Os ativos com 5 anos ou mais de casa são "
        f"{num_f(ref['% com 5 anos ou mais'], 0)}% em {ano_ref}. Nas outras: {por_topo}.",
        f"4. **Quem entra agora fica menos.** Depois de 3 anos seguiam ativos "
        f"{num_f(retencao.loc[primeira, 'depois de 3 anos'])} da coorte {primeira} e "
        f"{num_f(retencao.loc[ultima_com_x3, 'depois de 3 anos'])} da coorte {ultima_com_x3}.",
        "",
        "Leitura: os itens 1 e 2 dizem que a renovação é baixa, o 3 que o tempo de casa de quem "
        "fica é alto, e o 4 que quem entra sai mais cedo que quem entrou antes. Clojure tem "
        + ("a menor reposição" if menor_reposicao else "uma reposição baixa")
        + " e "
        + (
            "a maior parcela de 5 anos ou mais"
            if maior_topo
            else "uma parcela alta de 5 anos ou mais"
        )
        + f" entre as cinco em {ano_ref}.",
        "",
        "Limites:",
        "",
        "- O tempo de casa dos ativos sobe em toda comunidade que amadurece. O que distingue "
        "Clojure é o nível e a velocidade, comparados com as outras linguagens no mesmo ano.",
        "- Os números contam todas as pessoas da amostra coletada. Não há margem de erro de "
        "amostragem. O que pode mudar o resultado são as definições: saída de 12 meses e "
        "população `passou_30_dias`.",
        "",
        "**Clojure por ano**",
        "",
        tabela_md(clojure_renovacao, 2),
        "",
        f"**Cinco linguagens em {ano_ref}**",
        "",
        tabela_md(comparacao, 2),
        "",
        figura(
            pastas.base, f"geral{pastas.sufixo}/vitalidade/trajetoria_reposicao.png", "reposição"
        ),
        "",
    ]
    return "\n".join(linhas)


def num_i(valor: float) -> str:
    """Inteiro com ponto de milhar, como 1.918."""
    return f"{valor:,.0f}".replace(",", ".")


def num_f(valor: float, casas: int = 2) -> str:
    """Número com vírgula decimal."""
    return f"{valor:.{casas}f}".replace(".", ",")


def rq2(pastas: Pastas, p: v.Parametros) -> str:
    geral = "geral" + pastas.sufixo
    ordem = p.linguagens_rq2
    pad = pastas.csv(geral, "padronizacao.csv")
    anos = [2019, 2020, 2021, 2022, 2023, 2024]
    blocos_smr = []
    for rodada, linguagens in p.rodadas_padronizacao.items():
        d = pad[(pad["rodada"] == rodada) & pad["ano"].isin(anos) & (pad["ativos"] >= 100)]
        smr = por_linguagem(d, "smr", "ano", linguagens)
        taxa = por_linguagem(d, "taxa_padronizada_ate_5a", "ano", linguagens)
        blocos_smr.append(
            "\n".join(
                [
                    f"**Rodada {rodada}**: referência é a soma de "
                    f"{', '.join(carga_fonte.LINGUAGENS[s].nome for s in linguagens)} em "
                    f"{p.ano_pesos}.",
                    "",
                    "SMR (acima de 1: perdeu mais que o esperado):",
                    "",
                    tabela_md(smr, 2),
                    "",
                    "Taxa de saída padronizada, 0 a 5 anos:",
                    "",
                    tabela_md(taxa, 2),
                    "",
                ]
            )
        )

    logrank = pastas.csv(geral, "logrank.csv")
    logrank = logrank.set_index("comparacao")
    logrank["p"] = logrank["p"].map(lambda valor: f"{valor:.1e}")
    logrank = logrank.rename(columns={"estatistica": "estatística"})
    tabua = pastas.csv(geral, "tabua_comparada.csv")
    sobrevida = pd.DataFrame()
    for x in (1, 3, 5):
        sobrevida[f"S({x})"] = por_linguagem(tabua, "S", "x", ordem).loc[x]
    sobrevida.index.name = "linguagem"

    ncr = pastas.csv(geral, "ccr_ncr_comparado.csv")
    ncr["snapshot"] = pd.to_datetime(ncr["snapshot"])
    ncr = ncr.rename(columns={"slug": "linguagem"})
    fim_de_ano = ncr[(ncr["snapshot"].dt.month == 12) & (ncr["total"] >= 100)].copy()
    fim_de_ano["ano"] = fim_de_ano["snapshot"].dt.year
    anos_ccr = [2015, 2018, 2020, 2022, 2025]
    fim_de_ano = fim_de_ano[fim_de_ano["ano"].isin(anos_ccr)]
    ccr_ano = por_linguagem(fim_de_ano, "ccr", "ano", ordem)
    ncr_ano = por_linguagem(fim_de_ano, "ncr", "ano", ordem)

    linhas = [
        f"## {RQ2}",
        "",
        "### 2.1 Comparação corrigida: taxa padronizada por idade e SMR",
        "",
        "- Plano: taxa de saída por faixa de experiência de cada linguagem com os pesos de uma "
        "composição de referência. SMR = saídas reais / saídas esperadas.",
        "- Aqui: uma rodada entre as linguagens de nicho (RQ2a) e outra de Clojure com Python "
        "(RQ2b), para o Python não pesar na referência das de nicho.",
        "- A taxa padronizada usa só as faixas de 0 a 5 anos (0-1, 1-2, 2-3, 3-5). Com as seis "
        "faixas ela só começa quando a linguagem tem 8+, e o Zig ficaria em 2023. Cada linha "
        "começa quando a linguagem tem 100 ativos.",
        "",
        *blocos_smr,
        figura(pastas.base, f"{geral}/vitalidade/padronizacao_nicho.png", "nicho"),
        "",
        figura(pastas.base, f"{geral}/vitalidade/padronizacao_python.png", "python"),
        "",
        "### 2.2 Significância da diferença: Kaplan-Meier e log-rank",
        "",
        "- Plano: curva de sobrevivência por linguagem, com quem seguia ativo ao fim da coleta "
        "tratado como ainda sem saída, e teste de log-rank entre as curvas.",
        f"- Aqui: o log-rank compara {carga_fonte.LINGUAGENS[ordem[0]].nome} com cada outra.",
        "",
        tabela_md(logrank, 2),
        "",
        "Fração que chega a x anos, da tábua de vida:",
        "",
        tabela_md(sobrevida, 2),
        "",
        figura(pastas.base, f"{geral}/vitalidade/kaplan_meier.png", "Kaplan-Meier"),
        "",
        "### 2.3 CCR e NCR (RQ1 e RQ2)",
        "",
        "Mesma definição da seção 1.4, agora nas cinco linguagens.",
        "",
        "CCR no fim do ano:",
        "",
        tabela_md(ccr_ano),
        "",
        "NCR no fim do ano:",
        "",
        tabela_md(ncr_ano),
        "",
        figura(pastas.base, f"{geral}/vitalidade/ccr_ncr_dispersao.png", "dispersão"),
        "",
        "### 2.4 Magnetismo e stickiness",
        "",
        "- Plano: magnetismo = novatos que entraram na linguagem / total de novatos das "
        "linguagens do estudo no ano. Stickiness = quem continua ativo no ano seguinte / total "
        "da linguagem no ano.",
        "- Aqui: implementados, fora da execução padrão por decisão. Sem número neste documento. "
        "Rodam com `--metricas magnetismo` e `--metricas stickiness`, nas linguagens que cabem na "
        "memória do pipeline do motor (Python não cabe).",
        "",
    ]
    return "\n".join(linhas)


def rq3(pastas: Pastas, p: v.Parametros) -> str:
    c = pastas.linguagem("clojure")
    chave = next(iter(p.variantes))
    rotulo = p.variantes[chave][0]
    base = pastas.base / c / "csv" / "vitalidade" / f"cenarios-{chave}"
    resumo = pd.read_csv(base / "projecao_resumo.csv")
    resumo = resumo[~resumo["teto"]].drop(columns=["teto"])
    erro = pd.DataFrame(
        {
            "ingênuo": [resumo["ingenuo"].iloc[0]],
            "coorte": [resumo["coorte"].iloc[0]],
            "conservador": [resumo["conservador"].iloc[0]],
        },
        index=["erro relativo absoluto médio (ABRE)"],
    )
    futuro = pd.read_csv(base / "projecao_futuro.csv")
    futuro = futuro[(~futuro["teto"]) & (futuro["faixa"] == "total")]
    ordem = ["pessimista", "conservador", "otimista"]
    projecao = futuro.pivot(index="ano", columns="metodo", values="previsto")
    projecao = projecao[ordem]
    wilcoxon = pd.read_csv(base / "projecao_wilcoxon.csv")
    wilcoxon = wilcoxon[~wilcoxon["teto"]].drop(columns=["teto"]).set_index("comparacao")
    wilcoxon["p"] = wilcoxon["p"].map(lambda valor: f"{valor:.1e}")

    linhas = [
        f"## {RQ3}",
        "",
        "### 3.1 Cenários futuros: projeção por variantes",
        "",
        "- Plano: da população de hoje por tempo de contribuição, projeta um ano por vez: parte "
        "continua ativa (permanência) e chega gente nova. Cada cenário varia as duas taxas. A "
        "direção projetada se checa rodando o modelo em anos passados.",
        f"- Aqui: regra do plano, `{chave}` ({rotulo}). Outras ficam em `variantes` no yaml.",
        f"- Horizonte: {p.horizonte} anos. Cenários por banda de idade: pessimista usa o menor "
        "valor dos dois últimos anos, otimista o maior e conservador a média dos dois. Os "
        "novatos seguem a mesma regra.",
        "",
        "Projeção do total de ativos de Clojure:",
        "",
        tabela_md(projecao, 0),
        "",
        "Erro do backtest (anos passados, um ano à frente):",
        "",
        tabela_md(erro, 3),
        "",
        "Teste de Wilcoxon entre os erros por célula:",
        "",
        tabela_md(wilcoxon, 2),
        "",
        figura(pastas.base, f"{c}/vitalidade/cenarios_comparados.png", "backtest"),
        "",
        figura(
            pastas.base, f"{c}/vitalidade/cenarios-{chave}/projecao_futuro.png", "projeção futura"
        ),
        "",
    ]
    return "\n".join(linhas)


def diferencas(p: v.Parametros) -> str:
    linhas = [
        "## Onde a implementação saiu do plano",
        "",
        "| item | plano | aqui |",
        "|---|---|---|",
        "| Saída | 3 meses sem contribuir (IEICE16) | 12 meses, o limite de Avelino et al. "
        "(ESEM 2019) |",
        f"| Período | 2008 a 2026 | estudo de 2008 a {pd.Timestamp(p.data_de_corte).year}. "
        "2026 só acompanha quem já estava na população |",
        "| Crescimento natural | (novatos - saídas) / ativos | tudo que entra menos tudo que sai, "
        "(novatos + voltas - saídas - pausas) / ativos |",
        "| Saída de 2025 | não prevista | calculada com o acompanhamento até 2026 e pode estar "
        "um pouco alta |",
        f"| População | todas as pessoas que contribuíram | `{p.populacao}`: 30 dias ou mais "
        "entre o primeiro e o último evento |",
        "| Retenção | fração ativa 12 meses depois, por coorte | tábua de vida por coorte, S(x) "
        "para x = 0 a 15 |",
        "| População de referência da padronização | soma das quatro linguagens em 2025 | soma "
        "da rodada em 2025: nicho (4 linguagens) e Clojure com Python |",
        f"| CCR e NCR | janela e novato do IEICE16 | janela de {p.ccr_ncr_inatividade_meses:g} "
        f"meses e novato com até {p.ccr_ncr_novato_meses:g} meses |",
        "| Faixas da taxa padronizada | as seis faixas | 0 a 5 anos, para todas começarem cedo |",
        "| Magnetismo e stickiness | métricas da RQ2 | implementados, fora da execução padrão |",
        "| Observação válida | 50% da linguagem no repositório e 10 estrelas | igual |",
        "",
    ]
    return "\n".join(linhas)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--saida", default=str(v.PADRAO_SAIDA))
    parser.add_argument("--set", dest="sobrepostos", action="append", default=[])
    args = parser.parse_args()

    p = v.carrega_parametros(args.sobrepostos)
    base = Path(args.saida).expanduser()
    pastas = Pastas(base, p.populacao)
    partes = [
        "# Métricas por pergunta de pesquisa\n",
        "Ordem e definições do Plano de Experimento. Cada métrica traz o que o plano pede, "
        "como está aqui, os números e a figura.\n",
        glossario(),
        amostra(pastas, p),
        rq1(pastas, p),
        rq2(pastas, p),
        rq3(pastas, p),
        diferencas(p),
    ]
    destino = base / "METRICAS_POR_RQ.md"
    destino.write_text("\n".join(partes))
    print(f"documento: {destino}")


if __name__ == "__main__":
    main()
