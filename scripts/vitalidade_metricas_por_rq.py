"""Escreve METRICAS_POR_RQ.md: as métricas de cada pergunta de pesquisa, na ordem do plano.

    uv run python scripts/vitalidade_metricas_por_rq.py --saida ~/Documents/pyramid-vitalidade

A ordem e as definições vêm da tabela "Variáveis dependentes" do Plano de Experimento. Cada
métrica mostra o que o plano pede, como está aqui, a tabela com os números e a figura. Todo número
vem dos CSV; a seção de diferenças lista onde a implementação saiu do plano.
"""

import argparse
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
        "- **Saída definitiva**: a última contribuição da vida, seguida de 12 meses sem nada. "
        "Como precisa dos 12 meses seguintes, a saída de 2025 não existe: eles cairiam em 2026, "
        "e o estudo termina em 31/12/2025.",
        "- **População viva**: quem está entre o primeiro e o último evento da vida, pausas "
        "incluídas. É a base da natalidade e da mortalidade. Os ativos são só quem contribuiu no "
        "ano, por isso a população viva é maior.",
        "- **Natalidade e mortalidade**: novatos do ano e saídas do ano, em % da população viva. "
        "A diferença é o crescimento natural.",
        "- **Crescimento natural**: (novatos - saídas) / ativos do mesmo ano.",
        "- **Índice de envelhecimento**: ativos com 5 anos ou mais de casa dividido pelos ativos "
        "com menos de 1 ano de casa. A idade é o tempo na linguagem, não a idade da pessoa. "
        "Com índice 1 há tantos veteranos quanto novatos. Quando sobe, a base da pirâmide "
        "encolhe mais rápido que o topo.",
        "- **Coorte**: o grupo que entrou no mesmo ano. **Sobrevivência por coorte**, S(x), é a "
        "fração desse grupo ainda ativa x anos depois. Coorte 2010 de Clojure com S(1) = 0,83 "
        "quer dizer que de cada 100 pessoas que entraram em 2010, 83 seguiam ativas um ano depois.",
        "- **Censura à direita**: quem ainda está ativo no fim da coleta não tem data de saída. "
        "Conta como censurado, e não como alguém que saiu. Ignorar isso inflaria as saídas.",
        "- **Tábua de vida**: para cada ano de casa x, l(x) pessoas em observação, d(x) saídas, "
        "q(x) = d(x) / exposição a chance de sair no ano, S(x) a fração que chega a x e e(x) os "
        "anos que ainda restam. A exposição desconta meio ano por pessoa censurada.",
        "- **Taxa padronizada**: a taxa de saída de cada faixa de tempo de casa, combinada com os "
        "pesos de uma composição de referência única. Tira o efeito de uma linguagem ter mais "
        "novatos do que outra. Aqui só as faixas de 0 a 5 anos, que existem em todas as "
        "linguagens cinco anos depois do nascimento delas.",
        "- **SMR**: saídas reais divididas pelas esperadas, se a linguagem tivesse as taxas de "
        "saída da referência em cada faixa. Acima de 1: perdeu mais gente que o esperado.",
        "- **Kaplan-Meier**: estima a probabilidade S(t) de uma pessoa ainda estar ativa t anos "
        "depois de entrar, usando a duração de cada pessoa (do primeiro ao último evento) e "
        "tratando quem segue ativo como censurado. A curva desce em degraus.",
        "- **Log-rank**: teste de que duas curvas de Kaplan-Meier são iguais. Com milhares de "
        "pessoas o p fica minúsculo para qualquer diferença. O que informa é o tamanho dela, "
        "por exemplo S(5) = 0,28 contra 0,36.",
        "- **CCR e NCR**: (código - discussão) / o maior dos dois, e (novatos - experientes) / o "
        "maior dos dois. O sinal dos dois dá o tipo: A mais código e mais novatos, B mais "
        "discussão e mais novatos, C mais código e mais experientes, D mais discussão e mais "
        "experientes.",
        "",
    ]
    return "\n".join(linhas)


def rq1(pastas: Pastas, p: v.Parametros) -> str:
    c = pastas.linguagem("clojure")
    ultimo = pd.Timestamp(p.data_de_corte).year

    anual = pastas.csv(c, "anual.csv").set_index("ano")
    tamanho = anual[["ativos", "novatos", "saidas", "crescimento_natural_pct"]].copy()
    tamanho.index.name = "ano"
    tamanho = tamanho.rename(
        columns={
            "ativos": "ativos",
            "novatos": "novatos",
            "saidas": "saídas",
            "crescimento_natural_pct": "crescimento natural %",
        }
    )

    envelhecimento = pastas.csv(c, "indice_envelhecimento.csv").set_index("ano")
    envelhecimento = envelhecimento[envelhecimento.index >= 2010]
    envelhecimento = envelhecimento.rename(columns={"indice": "índice de envelhecimento"})

    renovacao = []
    for slug in p.linguagens_rq2:
        lingua = pastas.linguagem(slug)
        i = pastas.csv(lingua, "indice_envelhecimento.csv").set_index("ano")
        a = pastas.csv(lingua, "anual.csv").set_index("ano")
        for ano in (2015, 2020, 2024, 2025):
            if ano in i.index and a.loc[ano, "ativos"] >= 100:
                renovacao.append(
                    {
                        "linguagem": carga_fonte.LINGUAGENS[slug].nome,
                        "ano": ano,
                        "ativos": a.loc[ano, "ativos"],
                        "novatos % dos ativos": 100 * i.loc[ano, "novatos"] / a.loc[ano, "ativos"],
                        "índice de envelhecimento": i.loc[ano, "indice"],
                    }
                )
    renovacao = pd.DataFrame(renovacao).set_index("linguagem")

    transicao = pastas.csv(c, "transicao_anual.csv").set_index("periodo")
    transicao = transicao[(transicao.index >= 2010) & transicao["mortalidade_pct"].notna()]
    transicao = transicao[["populacao", "natalidade_pct", "mortalidade_pct"]]
    transicao["natural pontos"] = transicao["natalidade_pct"] - transicao["mortalidade_pct"]
    transicao = transicao.rename(
        columns={
            "populacao": "população viva",
            "natalidade_pct": "natalidade %",
            "mortalidade_pct": "mortalidade %",
        }
    )
    transicao.index.name = "ano"

    coortes = pastas.csv(c, "tabua_coortes.csv")
    retencao = pd.DataFrame()
    for x in (1, 3, 5):
        parte = coortes[coortes["x"] == x].set_index("coorte")["S"]
        retencao[f"S({x})"] = parte
    retencao = retencao[retencao.index >= 2010]
    retencao.index.name = "coorte"

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
        f"Os dados vão até {ultimo} (`data_de_corte`). 2026 não entra.",
        "",
        "### 1.1 Tamanho: crescimento natural por ano",
        "",
        "- Plano: (novatos - saídas) / ativos, em %. Positivo: entrou mais gente do que saiu.",
        "- Aqui: a base são os ativos do mesmo ano. A saída é definitiva, 12 meses sem contribuir.",
        f"- Saída só existe até {ultimo - 1}: a de {ultimo} cairia em 2026.",
        "",
        tabela_md(tamanho, 1),
        "",
        figura(pastas.base, f"{c}/vitalidade/anual.png", "tamanho"),
        "",
        figura(pastas.base, f"{c}/vitalidade/crescimento.png", "crescimento"),
        "",
        "Natalidade e mortalidade, que dão o crescimento natural em outra base: a população viva "
        "(do primeiro ao último evento da vida, pausas incluídas), não os ativos do ano.",
        "",
        tabela_md(transicao, 1),
        "",
        figura(pastas.base, f"{c}/vitalidade/transicao_anual.png", "natalidade e mortalidade"),
        "",
        "### 1.2 Composição: estrutura etária e índice de envelhecimento",
        "",
        "- Plano: pessoas ativas por faixa de tempo de contribuição (a pirâmide) e índice de "
        "envelhecimento.",
        "- Aqui: faixas 0-1, 1-2, 2-3, 3-5, 5-8 e 8+. Índice = ativos com 5+ anos de casa / ativos "
        "com menos de 1. Subindo, a base encolhe mais rápido que o topo.",
        "",
        tabela_md(envelhecimento, 2),
        "",
        figura(pastas.base, f"{c}/vitalidade/piramides_faixa_pct.png", "pirâmides"),
        "",
        figura(pastas.base, f"{c}/vitalidade/indice_envelhecimento.png", "índice"),
        "",
        "**Clojure é uma população envelhecida que se renova pouco?** O que a tabela diz:",
        "",
        "- Em 2025 Clojure tem o maior índice de envelhecimento das cinco e a menor parcela de "
        "novatos entre os ativos, entre as linguagens que já têm 100 ativos ou mais.",
        "- A natalidade ficou abaixo da mortalidade a partir de 2018 e a distância cresce "
        "(tabela de natalidade e mortalidade, seção 1.1).",
        "- O índice sobe em todas as linguagens à medida que a comunidade amadurece. O que "
        "separa Clojure é o nível: a de 2025 é a mais alta, e o número de novatos por ano caiu "
        "de 2.287 (2015) para 654 (2024) enquanto os veteranos de 5 anos ou mais passaram de 284 "
        "para 1.748.",
        "- Os novatos de 2025 saem subestimados: com `passou_30_dias`, quem entrou depois de "
        "1º/dez/2025 não teve 30 dias de seguimento e fica de fora. O efeito vale para as cinco "
        "linguagens e infla o índice de 2025 em todas. Por isso 2024 é o ano mais seguro para "
        "comparar.",
        "",
        tabela_md(renovacao, 2),
        "",
        "### 1.3 Retenção: sobrevivência por coorte",
        "",
        "- Plano: fração de quem entrou junto que ainda está ativa 12 meses depois, por ano de "
        "entrada.",
        "- Aqui: tábua de vida por coorte. S(x) é a fração da coorte que chega a x anos. S(1) é o "
        "valor do plano.",
        "- As coortes mais recentes têm censura à direita: quem tem o último evento a 12 meses ou "
        "menos do fim conta como censurado, então S(1) das últimas coortes se lê com cautela.",
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
        figura(pastas.base, f"geral{pastas.sufixo}/vitalidade/ccr_ncr_serie.png", "série"),
        "",
    ]
    return "\n".join(linhas)


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
        "tratado como censura, e teste de log-rank entre as curvas.",
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
        f"| Período | 2008 a 2026 | 2008 a {pd.Timestamp(p.data_de_corte).year}, "
        "2026 está incompleto |",
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
