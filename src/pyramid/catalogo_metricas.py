"""Catálogo das métricas da ferramenta, com o que entra e o que sai de cada uma.

Cada métrica tem um bloco de comentário com quatro partes (O que é, Referência, Entrada e
Resultado esperado) e, logo abaixo, a linha que a registra em `CATALOGO`: o nome da métrica e as
funções do motor que a calculam. Nada é recalculado aqui. As funções chegam por import, então o
catálogo acompanha o motor quando ele muda.

Os nomes são as linhas da tabela de variáveis dependentes do Plano de Experimento e os mesmos do
registro `METRICAS` de `scripts/vitalidade.py`. Um teste compara os dois.

Entrada comum a todas as métricas: eventos canônicos, um DataFrame com três colunas.

    contributor_id  identificador estável da pessoa
    event_type      commits, pull_requests, commit_comments, issue_comments,
                    pull_request_comments, issue_events ou issues
    timestamp       data e hora do evento (datetime64)

Código é `commits` e `pull_requests` (`vitalidade.TIPOS_CODING`). Os outros cinco tipos são
discussão. O contrato completo está em `docs/ferramenta/FONTES.md`.

Do evento à métrica, em cinco linhas (o teste `test_catalogo_metricas.py` roda estas mesmas):

    compactos = vitalidade.compacta(eventos)
    fim = compactos["timestamp"].max()
    pa = vitalidade.pessoa_ano(compactos, fim, com_moved_to_discussion=False)
    dur = vitalidade.duracoes(compactos, fim)
    anual = vitalidade.tabela_anual(pa, fim)

Os nomes que os blocos abaixo usam:

    compactos  os eventos reduzidos ao que as métricas leem, sem mudar nenhum resultado
    fim        o último instante coberto pela coleta. O estudo para em `data_de_corte`
               (2025-12-31) e os eventos de 2026 só decidem quem saiu e quem pausou
    pa         `pessoa_ano`: uma linha por pessoa e ano em que ela contribuiu
    dur        `duracoes`: uma linha por pessoa, do primeiro ao último evento

Convenções do estudo, valem para todos os blocos:

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

from collections.abc import Callable
from typing import Any

from . import attractiveness, metrics, projection, vitalidade

CATALOGO: dict[str, tuple[Callable[..., Any], ...]] = {}


# --- tamanho ---------------------------------------------------------------------------------
# O que é:
#   Quanto a população cresce ou encolhe por ano. Responde a RQ1.1.
#   Crescimento natural = tudo que entra (novatos e voltas) menos tudo que sai (saídas e
#   pausas), em % dos ativos do mesmo ano.
#   Natalidade = o que entra sobre os ativos. Mortalidade = o que sai sobre os ativos.
#   Ativo de Y: teve pelo menos um evento em Y. Novato de Y: o primeiro evento da vida caiu em Y.
#   Saída de Y: o último evento da vida caiu em Y e vieram mais de 12 meses sem nada depois.
#   Pausa de Y: um período de atividade terminou em Y e a pessoa voltou depois de 12 meses.
#   Volta de Y: começou em Y um período de atividade depois do primeiro.
# Referência:
#   Equação compensadora da demografia (IBGE, metodologia das projeções 1980-2050).
#   https://ftp.ibge.gov.br/Projecao_da_Populacao/Revisao_2004_Projecoes_1980_2050/metodologia.pdf
#   Novatos e saídas: Foucault et al., ESEC/FSE 2015. https://doi.org/10.1145/2786805.2786870
# Entrada:
#   `pa` (uma linha por pessoa e ano, de `pessoa_ano`) e `fim`.
#   `pa` traz contributor_id, ano, primeiro, idade_anos, idade_dias, faixa, novato, categoria,
#   moved_no_ano, deixou_codigo_no_ano, saida, pausa e volta.
# Resultado esperado:
#   Uma linha por ano: ativos, novatos, saidas, pausas, voltas, moved, deixou_codigo,
#   provisorio, natalidade_pct, mortalidade_pct e crescimento_natural_pct.
#   Crescimento natural positivo: entrou mais gente do que saiu. Negativo: saiu mais do que entrou.
#   A base é o próprio ano. A variação dos ativos sobre o ano anterior é outra conta.
#   Saída, mortalidade e crescimento ficam vazios no ano que a coleta ainda não cobre.
#   `provisorio` verdadeiro marca o último ano completo: quem parou há pouco ainda pode voltar.
#   A função falha alto se ativos(Y+1) não for ativos(Y) menos saídas e pausas, mais novatos e
#   voltas de Y+1.
CATALOGO["tamanho"] = (vitalidade.pessoa_ano, vitalidade.tabela_anual)


# --- composicao ------------------------------------------------------------------------------
# O que é:
#   A pirâmide: ativos por faixa de tempo na linguagem, separados em quem faz código e quem só
#   discute. Responde a RQ1.2.
#   Categorias: non_coding (nunca fez commit nem PR), moved (começou pela discussão e fez commit
#   ou PR neste ano) e coding (começou pelo código). A quarta, moved_to_discussion (já codou e
#   neste ano só discutiu), só existe com `com_moved_to_discussion=True`.
#   Índice de envelhecimento = ativos com 5 anos ou mais na linguagem / ativos com menos de 1.
# Referência:
#   Pirâmide etária e índice de envelhecimento do IBGE.
#   https://seriesestatisticas.ibge.gov.br/series.aspx?vcodigo=CD95
#   Hannemann e Klamma, OSS 2013. https://doi.org/10.1007/978-3-642-38928-3_6
#   Pirâmide em bandas de 3 meses: Onoue et al., ESEM14 e IEICE16.
# Entrada:
#   `pa`, de `pessoa_ano`.
# Resultado esperado:
#   `composicao`: ano, faixa e uma coluna de contagem por categoria.
#   `composicao_trimestral`: ano, band (0 é até 90 dias de idade) e uma coluna por categoria.
#   `indice_envelhecimento`: ano, veteranos, novatos e indice.
#   Quem fez commit ou PR no ano fica do lado do código, mesmo que o último evento seja um
#   comentário.
#   Índice 1: tantos veteranos quanto novatos. Quando sobe, a base encolhe mais rápido que o topo.
#   O índice fica vazio no ano sem novatos.
CATALOGO["composicao"] = (
    vitalidade.composicao,
    vitalidade.composicao_trimestral,
    vitalidade.indice_envelhecimento,
)


# --- retencao --------------------------------------------------------------------------------
# O que é:
#   A tábua de vida: quem entrou no mesmo ano forma uma coorte. A tábua mostra como ela vai
#   diminuindo. Responde a RQ1.3.
#   Para cada ano x de contribuição: l(x) pessoas ainda em observação ao chegar em x, d(x) saídas
#   entre x e x+1, q(x) = d(x) / l(x) é a chance de sair, S(x) é a fração que chega em x e e(x)
#   é quantos anos ainda restam, em média, a quem chegou em x.
#   Quem tem o último evento a 12 meses ou menos do fim da coleta ainda pode voltar. Fica
#   censurado: conta meio intervalo de exposição.
# Referência:
#   IBGE, Tábua Completa de Mortalidade 2023.
#   https://biblioteca.ibge.gov.br/visualizacao/periodicos/3097/tcmb_2023.pdf
#   Hannemann e Klamma, OSS 2013. https://doi.org/10.1007/978-3-642-38928-3_6
# Entrada:
#   `dur`, de `duracoes`: contributor_id, entrada, ultimo, duracao_anos, saiu (falso é
#   censurado) e coorte (ano de entrada).
# Resultado esperado:
#   `tabua_de_vida` (todas as pessoas) e `tabuas_por_coorte` (a mesma tábua com a coluna coorte
#   a mais): x, l, d, censurados, n_efetivo, q, q_inf, q_sup, S, e (anos que restam) e
#   e_truncado.
#   q vai de 0 a 1. Com q = 0,4 em x = 2, 40% de quem chegou a 2 anos sai antes de completar 3.
#   n_efetivo é a exposição de q. Com poucas pessoas q oscila: olhe q_inf e q_sup, o intervalo
#   de 95% pelo método de Wilson.
#   e_truncado verdadeiro: a cauda censurada fica de fora. Nesse caso e(x) é um valor mínimo.
CATALOGO["retencao"] = (vitalidade.duracoes, vitalidade.tabuas_por_coorte, vitalidade.tabua_de_vida)


# --- saida_por_faixa -------------------------------------------------------------------------
# O que é:
#   A taxa de saída de cada faixa de tempo na linguagem, por ano: saídas da faixa / ativos da
#   faixa. É o q(x) da tábua de vida, faixa por faixa. Responde a RQ1.3.
#   Mostra em que fase a comunidade perde mais gente, novatos ou veteranos.
# Referência:
#   Taxa de mortalidade por idade (IBGE, Tábua Completa de Mortalidade 2023).
#   https://biblioteca.ibge.gov.br/visualizacao/periodicos/3097/tcmb_2023.pdf
#   Mínimo de 20 saídas por célula: CDC WONDER, Presentation Standards for Mortality Data, 2024.
# Entrada:
#   `pa` (de `pessoa_ano`) e `fim`.
# Resultado esperado:
#   Uma linha por ano e faixa: ano, faixa, ativos, saidas e taxa_saida.
#   taxa_saida vai de 0 a 1. Com 0,3, a cada 10 ativos da faixa 3 saíram no ano.
#   Ano que a coleta não cobre fica sem saídas e sem taxa. Faixa sem ativos fica sem taxa.
#   Os gráficos marcam como instável a célula com menos de 20 saídas (`saidas_estavel`).
#   A faixa 8+ de Clojure só existe a partir de 2016.
CATALOGO["saida_por_faixa"] = (vitalidade.taxa_saida_por_faixa,)


# --- cenarios --------------------------------------------------------------------------------
# O que é:
#   A projeção da pirâmide do ano seguinte, em faixas de 1 ano (0 a 7 e 8+), por cinco métodos.
#   Responde a RQ3. A projeção avança um ano por vez.
#   ingenuo: a pirâmide do próximo ano é igual à do último ano observado.
#   coorte: cada faixa recebe a faixa anterior vezes a taxa de permanência do último par de
#   anos. Os novatos são a média dos dois últimos anos.
#   pessimista, otimista e conservador: a mesma conta do coorte, com a permanência de cada faixa
#   e os novatos tirados da série histórica. Pessimista usa o menor valor, otimista o maior e
#   conservador a média dos dois (ou a regra da variante: média da janela, ou dos 2 últimos).
#   O backtest prevê cada ano passado só com os anos anteriores e mede o erro.
# Referência:
#   Onoue et al., IEICE16 (ingênuo, coorte, ABRE e Wilcoxon). https://doi.org/10.1587/transinf.2015EDP7363
#   Variantes de projeção da ONU (PRB) e do Ipea (Bonifácio e Guimarães, Texto para Discussão
#   2698, 2021).
#   https://www.prb.org/resource/understanding-population-projections-assumptions-behind-the-numbers/
# Entrada:
#   `pa`, `fim`, o último ano com saída decidida, `teto` (limita a permanência em 1) e `regra`,
#   um `RegraCenario` que `regra_da_variante` monta a partir de `variantes` no yaml.
# Resultado esperado:
#   `backtest`: teto, ano, faixa, real, um previsto por método (ingenuo, coorte, pessimista,
#   conservador, otimista), abre_ingenuo, abre_coorte, abre_conservador e cobre.
#   ABRE é o erro relativo da previsão. 0 é acerto. 0,5 é um erro de metade do menor dos dois
#   valores. Vale igual para quem previu a mais e para quem previu a menos.
#   `cobre` é 1 quando o valor real ficou entre o pessimista e o otimista.
#   `resumo_backtest`: dois quadros. `abre` traz a mediana do erro de cada método e a cobertura.
#   `wilcoxon` traz o p do teste pareado entre métodos: p abaixo de 0,05 diz que um erra menos
#   que o outro além do acaso.
#   `projeta_futuro`: ano, metodo, faixa e previsto. A faixa `total` soma as outras.
#   O otimista junta o melhor ano de cada faixa e funciona como limite superior da projeção.
#   Na replicação (passo de 3 meses, 90 projetos) a projeção é `projection.project` e o erro é
#   `projection.abre`.
CATALOGO["cenarios"] = (
    vitalidade.regra_da_variante,
    vitalidade.cenarios,
    vitalidade.backtest,
    vitalidade.resumo_backtest,
    vitalidade.projeta_futuro,
    projection.project,
    projection.abre,
)


# --- ccr_ncr ---------------------------------------------------------------------------------
# O que é:
#   O equilíbrio da população por trimestre. Responde a RQ1 e RQ2.
#   CCR compara quem faz código com quem só discute: (código - discussão) / o maior dos dois.
#   NCR compara novatos com experientes: (novatos - experientes) / o maior dos dois.
#   Os dois ficam entre -1 e 1. O sinal dos dois dá o tipo do trimestre:
#     A  CCR > 0 e NCR > 0  mais código e mais novatos
#     B  CCR < 0 e NCR > 0  mais discussão e mais novatos
#     C  CCR > 0 e NCR < 0  mais código e mais experientes
#     D  CCR < 0 e NCR < 0  mais discussão e mais experientes
#   Zero exato cai do lado baixo. Lado do código: o primeiro commit ou PR é de antes do fim do
#   trimestre. População do trimestre: quem contribuiu na janela de inatividade até o fim dele.
# Referência:
#   Onoue et al., IEICE16. https://doi.org/10.1587/transinf.2015EDP7363
# Entrada:
#   `compactos` (ou os eventos), `inatividade_dias`, `novato_dias` e `fim`.
#   O estudo usa 12 meses nos dois cortes (`ccr_ncr_inatividade_meses` e `ccr_ncr_novato_meses`).
#   Os padrões da função, 3 e 3 meses, reproduzem o IEICE16.
# Resultado esperado:
#   Uma linha por trimestre: snapshot (o fim do trimestre), coding, non_coding, new,
#   experienced, total, ccr, ncr e type.
#   CCR perto de 0: os dois lados são parecidos. CCR perto de 1: quase só código.
#   Trimestre sem ninguém ativo fica de fora, sem tipo.
#   A replicação faz a mesma conta sobre pirâmides em `metrics.from_pyramids`.
CATALOGO["ccr_ncr"] = (vitalidade.ccr_ncr_trimestral, metrics.from_pyramids)


# --- ccr_ncr_comparado -----------------------------------------------------------------------
# O que é:
#   O `ccr_ncr` das cinco linguagens no mesmo quadro, para os gráficos com todas juntas.
#   Responde a RQ1 e RQ2.
# Referência:
#   Onoue et al., IEICE16. https://doi.org/10.1587/transinf.2015EDP7363
# Entrada:
#   Os `compactos` de cada linguagem de `linguagens_rq2`.
# Resultado esperado:
#   A tabela de `ccr_ncr` de cada linguagem, empilhadas, com a coluna slug na frente.
CATALOGO["ccr_ncr_comparado"] = (vitalidade.ccr_ncr_trimestral,)


# --- stickiness ------------------------------------------------------------------------------
# O que é:
#   A fração de quem contribuiu num ano e volta no ano seguinte. Responde a RQ2.
#   stickiness(P, Y) = devs de P em Y que contribuem em Y+1 / devs de P em Y.
#   Só commits e pull requests contam. Usa o pipeline trimestral do motor.
# Referência:
#   Yamashita et al., MSR 2014. https://doi.org/10.1145/2597073.2597116
#   Ferreira, Silva e Valente, SBES 2020. https://doi.org/10.1145/3422392.3422433
#   ESEM14, seção 3.1.
# Entrada:
#   `pairs`: uma linha única por (scope_id, contributor_id, year), só de commits e pull_requests.
#   `activity` monta `pairs` a partir dos eventos extraídos. `annual` calcula sobre `pairs`.
# Resultado esperado:
#   Uma linha por (scope_id, year): devs, newcomers_here, newcomers_total, retained, magnetism,
#   stickiness (0 a 1), eligible, median_magnetism, median_stickiness, quadrant, left_censored e
#   right_censored. Com stickiness 0,6, 6 de cada 10 pessoas do ano voltaram no seguinte.
#   O último ano fica sem stickiness, porque falta o ano seguinte. Se o último ano da coleta é
#   incompleto, o ano anterior subestima: quem volta depois do fim conta como perdido.
CATALOGO["stickiness"] = (attractiveness.activity, attractiveness.annual)


# --- magnetismo ------------------------------------------------------------------------------
# O que é:
#   A fração dos novatos do ano que escolheram a linguagem. Responde a RQ2.
#   magnetismo(P, Y) = novatos de Y que contribuíram em P / novatos de Y em todas as linguagens.
#   O plano adia o uso: o denominador só representa o GitHub com todas as linguagens coletadas.
#   Por isso fica fora da execução padrão e roda só com `--metricas magnetismo`.
# Referência:
#   Yamashita et al., MSR 2014. https://doi.org/10.1145/2597073.2597116
#   Ferreira, Silva e Valente, SBES 2020. https://doi.org/10.1145/3422392.3422433
# Entrada:
#   A mesma `pairs` da stickiness, com todas as linguagens juntas.
# Resultado esperado:
#   A tabela da stickiness. As colunas deste bloco são magnetism, newcomers_here (novatos na
#   linguagem no ano) e newcomers_total (novatos de todas). Magnetismo 0,3: 3 de cada 10 novatos
#   do ano foram para ela.
#   `quadrant` cruza os dois com a mediana anual das linguagens elegíveis (mais de 10 ativos):
#     attractive  magnetismo e stickiness acima da mediana
#     floating    magnetismo acima, stickiness abaixo
#     stagnant    magnetismo abaixo, stickiness acima
#     terminal    os dois abaixo
CATALOGO["magnetismo"] = (attractiveness.activity, attractiveness.annual)


# --- significancia ---------------------------------------------------------------------------
# O que é:
#   Se a diferença de retenção entre linguagens é real ou ruído. Responde a RQ2.
#   Kaplan-Meier: a probabilidade estimada de uma pessoa ainda estar ativa t anos depois de
#   entrar. Quem segue ativo no fim da coleta entra como ainda sem saída (censura).
#   Log-rank: teste que diz se duas curvas de Kaplan-Meier diferem além do acaso.
# Referência:
#   Constantinou e Mens, Innovations in Systems and Software Engineering, 2017.
#   https://doi.org/10.1007/s11334-017-0303-4
# Entrada:
#   `dur`, de `duracoes`, de cada linguagem.
# Resultado esperado:
#   `kaplan_meier`: anos, S (a fração ainda ativa, que começa em 1 e desce em degraus) e
#   em_risco (quantas pessoas têm duração de `anos` ou mais: quanto menos, menos a curva vale).
#   `logrank` devolve a estatística e o p. P abaixo de 0,05: a diferença passa do acaso.
#   Com milhares de pessoas o p fica minúsculo para qualquer diferença. O que informa é o
#   tamanho dela, por exemplo 0,28 contra 0,36 de fração ativa depois de 5 anos.
#   Uma amostra com mais de 2 milhões de pontos sai com um ponto por dia.
CATALOGO["significancia"] = (vitalidade.kaplan_meier, vitalidade.logrank)


# --- tabua_comparada -------------------------------------------------------------------------
# O que é:
#   A tábua de vida de cada linguagem, lado a lado, até 8 anos na linguagem. Responde a RQ1 e RQ2.
#   e(x) é a vida restante de quem chegou a x. A chance de seguir mais t anos tendo chegado a x
#   sai de l(x+t) / l(x).
# Referência:
#   IBGE, Tábua Completa de Mortalidade 2023.
#   https://biblioteca.ibge.gov.br/visualizacao/periodicos/3097/tcmb_2023.pdf
# Entrada:
#   `dur`, de `duracoes`, de cada linguagem.
# Resultado esperado:
#   A tabela de `retencao` (mesmas colunas) de cada linguagem, empilhadas, com a coluna
#   linguagem na frente, cortada em x até 8.
CATALOGO["tabua_comparada"] = (vitalidade.tabua_de_vida,)


# --- comparacao_corrigida --------------------------------------------------------------------
# O que é:
#   A taxa de saída padronizada e o SMR. Responde a RQ2.
#   Direta: soma, por faixa, de (taxa de saída da faixa na linguagem x peso da faixa na
#   população de referência). Compara as linguagens como se todas tivessem a mesma mistura de
#   novatos e veteranos. O que sobra de diferença vem da retenção.
#   SMR: saídas reais / saídas esperadas, com as taxas da referência aplicadas à composição real
#   da linguagem.
#   A referência é a soma das linguagens da rodada, com os pesos da composição de `ano_pesos`.
# Referência:
#   Ahmad et al., Age Standardization of Rates: A New WHO Standard, OMS, 2001.
#   https://cdn.who.int/media/docs/default-source/gho-documents/global-health-estimates/gpe_discussion_paper_series_paper31_2001_age_standardization_rates.pdf
# Entrada:
#   Um dict {linguagem: tabela de `taxa_saida_por_faixa`} e `ano_pesos` (2025).
# Resultado esperado:
#   Uma linha por linguagem e ano: ativos, saidas, taxa_bruta, taxa_padronizada,
#   taxa_padronizada_ate_5a, saidas_esperadas e smr.
#   SMR 1: saiu o esperado. Acima de 1: saiu mais do que o esperado. Abaixo de 1: saiu menos.
#   taxa_padronizada fica vazia no ano em que alguma faixa não tem ninguém (linguagem jovem).
#   taxa_padronizada_ate_5a usa só as faixas de 0 a 5 anos e começa 5 anos depois do nascimento
#   da comunidade, então compara todas no mesmo intervalo de idades.
#   O resultado depende da referência escolhida.
CATALOGO["comparacao_corrigida"] = (vitalidade.taxa_saida_por_faixa, vitalidade.padronizacao)


# --- trajetoria ------------------------------------------------------------------------------
# O que é:
#   Tamanho, crescimento e composição de cada linguagem, lado a lado, sem o efeito do tamanho.
#   O Python tem mil vezes os ativos do Zig. Só índice, taxas e composição em % se comparam.
#   Responde a RQ2.
#   Índice de ativos: 100 no `ano_base_indice` (2019). Taxas de saída, de volta e de novatos em %
#   dos ativos do ano. Reposição = o que entrou (novatos e voltas) / o que saiu (saídas e pausas).
#   Composição por faixa em % dos ativos do ano.
# Referência:
#   Equação compensadora da demografia e pirâmide etária em % da população (IBGE).
#   https://ftp.ibge.gov.br/Projecao_da_Populacao/Revisao_2004_Projecoes_1980_2050/metodologia.pdf
#   https://seriesestatisticas.ibge.gov.br/series.aspx?vcodigo=CD95
# Entrada:
#   `tabela_anual` e `composicao` de cada linguagem, a partir do `pa` dela.
# Resultado esperado:
#   `trajetoria`: as colunas de `tabela_anual` mais slug, saida_pct, volta_pct, novato_pct,
#   reposicao, provisorio e indice. Reposição acima de 1: o crescimento natural é positivo.
#   `composicao_pct`: a `composicao` com as contagens em % dos ativos do ano.
# shortcut: as colunas em % e o índice saem de `metrica_trajetoria` em scripts/vitalidade.py, fora
# do motor. Este catálogo expõe só as duas funções de base. Mover para o motor quando o catálogo
# virar package.
CATALOGO["trajetoria"] = (vitalidade.tabela_anual, vitalidade.composicao)
