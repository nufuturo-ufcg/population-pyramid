# Métricas de vitalidade: definições

Régua do Plano de Experimento, aplicada por `src/pyramid/vitalidade.py`.
Reproduz com:

```bash
uv run python scripts/vitalidade.py                              # métricas padrão de uma linguagem
uv run python scripts/vitalidade.py --metricas tamanho,cenarios  # só algumas
uv run python scripts/vitalidade.py --comparativo                # significancia e comparacao_corrigida
uv run python scripts/vitalidade.py --metricas magnetismo        # fora do padrão, pede o nome
uv run python scripts/vitalidade.py --figuras todas              # todos os gráficos de cada métrica
uv run python scripts/vitalidade.py --figuras tamanho.fluxo      # um gráfico só
uv run python scripts/vitalidade.py --figuras nenhuma            # só as tabelas
uv run python scripts/vitalidade.py --so-figuras                 # redesenha do disco, sem recalcular
uv run python scripts/vitalidade.py --so-figuras --estilo global:dpi=300
uv run python scripts/vitalidade.py --set min_saidas=20          # troca um parâmetro
uv run python scripts/vitalidade.py --linguagem python --motor duckdb   # 344 GB na batuta
uv run python scripts/vitalidade.py --dados PASTA                # eventos e alvo de outra pasta
uv run python scripts/vitalidade.py --empacota                   # tudo num .tar.gz
uv run python scripts/vitalidade.py --importa PACOTE.tar.gz      # abre o pacote em --saida
uv run python scripts/vitalidade.py --lista                      # métricas, figuras, referências
```

## Estrutura

- `scripts/vitalidade.py`: as métricas e o runner. Cada linha da tabela de variáveis dependentes do plano é uma função `metrica_*`, com o que ela faz e a referência do cálculo na docstring. A função devolve tabelas.
- `scripts/vitalidade_figuras.py`: os gráficos e a camada de estilo. Cada gráfico é uma função `(contexto, tabelas)` registrada com `@figura(metrica, nome)`.
- Nomes das métricas: `tamanho`, `composicao`, `retencao`, `saida_por_faixa`, `cenarios`, `ccr_ncr`, `stickiness`, `significancia`, `comparacao_corrigida` e `magnetismo`.
- O magnetismo está implementado e fica fora da execução padrão, porque o plano o adia. Só roda com `--metricas magnetismo`.
- Cada métrica tem mais de um gráfico. Sem `--figuras` saem os marcados como padrão.
- `main` roda as métricas pedidas em sequência. Cada uma grava as tabelas (parquet em `resultados/` e CSV) e depois desenha as figuras escolhidas.
- Parâmetros do cálculo em `scripts/vitalidade.yaml`: `min_saidas`, `saidas_estavel`, `teto`, `horizonte`, `ano_pesos`, `linguagens_rq2`, `anos_piramide`, `coortes_tabua`, `variantes`. `--set chave=valor` sobrepõe uma execução.
- A régua (12 meses, faixas, passo anual) fica em `src/pyramid/vitalidade.py` como constante. Mudá-la exige editar o motor.
- `ccr_ncr`, `stickiness` e `magnetismo` rodam o pipeline trimestral do motor (banda de 3 meses). Os gráficos deles desenham das tabelas, como os outros.

## Populações e comparação entre linguagens

- `populacao: todos` conta quem teve qualquer evento. `populacao: codigo` conta só quem fez ao menos um commit ou PR na vida, com todos os eventos dela. Em cada linguagem, entre 52% e 64% das pessoas só abriram issue ou comentaram. Cada população grava em pasta própria (`python`, `python-codigo`, `geral-codigo`), e o cache dos eventos é um só.
- Rodar a segunda população não relê os CSV: `--set populacao=codigo` usa o cache. A população `codigo` olha o que a pessoa fez em algum momento da vida, não se ela voltou, então não carrega o viés de condicionar no futuro que um corte de "pelo menos 2 dias de atividade" teria.
- Quase metade das pessoas de toda linguagem tem vida de um dia só (Clojure 44%, Elixir 43%, Python 42%) e cerca de dois terços saem a cada ano. O público de evento único existe em todas igualmente, e é por isso que as curvas de retenção ficam próximas.
- A métrica `trajetoria` (comparativa) tira o tamanho da comparação: índice de ativos (100 em `ano_base_indice`), crescimento natural, taxas de saída e de volta em % dos ativos, e as pirâmides de cada linguagem em % no mesmo ano (`anos_comparacao`).
- A pirâmide por faixa sai em % dos ativos do ano (`piramide_em_pct`). A de contagem fica em `composicao.piramides_contagem`.
- `composicao.piramides_trimestrais` desenha como o artigo: idade em bandas de 90 dias no fim do ano, só para olhar. As métricas usam as faixas de 1 ano.
- `populacao: mais_de_um_dia` tira quem teve atividade num dia só. O corte olha o futuro da pessoa (só fica quem voltou em outro dia), então derruba a saída dos novatos e infla a retenção: serve de sensibilidade, não de população principal.
- `populacao: passou_N_dias` (passou_30_dias, passou_60_dias, passou_90_dias) mantém quem tem uma contribuição N ou mais dias depois da primeira: a pessoa só conta como viva depois de provar presença, como a saída só vale depois de 12 meses de silêncio. Serve à composição (pirâmide). Olha o futuro da pessoa, então derruba a saída dos novatos e não serve às taxas de saída da faixa 0-1.
- `data_de_corte` (2025-12-31) fecha o estudo: ativos, novatos, pirâmides e CCR/NCR vão até esse dia. Com `usa_acompanhamento`, os eventos depois dela (2026) só decidem quem saiu, quem pausou e quem pertence à população, e a saída de 2025 aparece e pode estar um pouco alta. Sem o acompanhamento, a saída de 2025 não existe. Tem de ser o último dia de um trimestre, para a compactação ser exata.
- Limite de saída: 12 meses em tudo, de Avelino et al. (ESEM 2019, seção II-B e Tabela II). O CCR e o NCR usavam 3 meses de inatividade (IEICE16) e agora usam `ccr_ncr_inatividade_meses` (12). O corte de novato do CCR e NCR é `ccr_ncr_novato_meses` (12, a mesma janela da saída). Com 3 e 3 o resultado é o do motor, exatamente. Refeita com os nossos dados, a Tabela II do Avelino tem a maior média harmônica em 12 meses nas cinco linguagens.
- Natalidade e mortalidade saem da tabela anual: natalidade = (novatos + voltas) / ativos e mortalidade = (saídas + pausas) / ativos.

## Gráficos

Aparência em `scripts/vitalidade_figuras.yaml`, por gráfico (`tamanho.anual`) ou para todos (`global`):

- Opções: `figsize`, `dpi`, `formato` (png, svg, pdf), `titulo` e `titulo_geral` (`{linguagem}` vira o nome), `rotulo_x`, `rotulo_y`, `xlim`, `ylim`, `grade`, `fontes`, `legenda` (mostrar, posição, colunas), `linha`, `paleta`, `cores_linguagem`, `linhas_horizontais`, `linhas_verticais`, `textos` e `eixos` (opções dos painéis além do primeiro).
- Opção ausente ou null mantém o que a função do gráfico desenha. Sem alteração, a figura sai idêntica byte a byte.
- Uma execução sobrepõe qualquer opção: `--estilo tamanho.anual:legenda.posicao=abaixo`, `--estilo global:dpi=300`.
- Opção desconhecida ou gráfico inexistente no yaml ou no `--estilo` falha com erro, para erro de digitação não passar em silêncio.
- Painel novo ou série nova se muda na função do gráfico, que é curta e isolada. Gráfico novo é uma função com `@figura`.
- `--figuras` escolhe: `padrao`, `todas`, `nenhuma`, `metrica` (todos os gráficos dela) ou `metrica.figura`. Sozinho, `--figuras tamanho.anual` roda só a métrica dona.

## Redesenhar sem recalcular

- Cada execução grava as tabelas de cada métrica em `<saída>/resultados/vitalidade/<métrica>/*.parquet` (comparações em `geral/resultados/`), com o `meta.json` do fim da coleta e dos parâmetros. O parquet guarda os tipos (período, categoria, data) que o CSV perderia.
- `--so-figuras` desenha dessas tabelas, sem ler os eventos nem recalcular. Redesenhar uma figura leva menos de 1 segundo, e todas as figuras de Clojure e do comparativo saem iguais byte a byte às desenhadas na hora do cálculo.
- Se um parâmetro do cálculo (`min_saidas`, `horizonte`, `ano_pesos`, `linguagens_rq2`, `variantes`) mudou desde a gravação, avisa que os gráficos usam as tabelas antigas.
- Fluxo de trabalho: `uv run python scripts/vitalidade.py` uma vez; depois, a cada "muda isso", editar o yaml ou passar `--estilo` e rodar com `--so-figuras`.

## Escala e dados na batuta

Os eventos brutos ficam na batuta (`wendell@batuta.splab.ufcg.edu.br`, em `/home/wendell/dados-brutos/`), por falta de espaço no Mac. O Python tem um arquivo de 344 GB. A ferramenta recebe os caminhos e lê de lá: nada é movido, copiado nem apagado.

- Onde ler, em ordem: linha de comando (`--dados PASTA`, ou `--eventos ARQ` e `--alvo ARQ`, repetíveis), `scripts/vitalidade_fontes.yaml` (os caminhos da batuta) e a pasta `data/<linguagem>-*` do repositório.
- Um arquivo de eventos tem papel `api`, `git` ou `misto` (api e git juntos, como `eventos_repositorios.csv` e `eventos_python.csv`). O papel vem do nome ou do yaml. No `misto`, a linha `commit` segue a regra do git e as outras a da API.
- Uma coleta repartida entre máquinas tem um alvo por parte (Python: 4 alvos, 422.720 repositórios juntos). Todos entram.
- OCaml é linguagem da ferramenta (`--linguagem ocaml`) sem entrar na lista de 4 do `figuras_linguagem_bruta.py`.

Motores de carga (`scripts/carga_compacta.py`, `motor` no yaml ou `--motor`; `auto` usa duckdb acima de 20 GB de eventos):

- `pandas` (`carga_pandas.py`): lê em pedaços de 500 mil linhas, um núcleo, tudo na memória. Pico de 1,6 a 2,8 GB em Zig, Clojure e Elixir, contra 4 a 4,7 GB do carregador original.
- `duckdb` (`adapters/coleta_csv/carga_duckdb.py`, o SQL só mora em `adapters/`): lê com vários núcleos, derrama em disco (`<saída>/<linguagem>/trabalho/`) e devolve só o resultado compactado. É o motor para centenas de GB.
- Outro motor entra registrando uma função em `MOTORES`, que recebe a `Fonte` e devolve [contributor_id, event_type, timestamp].
- Os dois aplicam as mesmas regras de `carrega_eventos` (elegibilidade, commit duplicado entre repositórios, piso do repositório, conta apagada, bot, datas impossíveis). Conferidos contra `carrega_eventos` em Zig, Clojure e Elixir: o pandas devolve os mesmos eventos, o duckdb as mesmas métricas e as mesmas contagens de cada filtro. `tests/test_carga.py` repete a conferência num caso pequeno com cada regra, nos dois layouts, com alvo repartido.
- O duckdb lê o autor como o pandas: valores como `NA`, `null` e `None` viram vazio nos dois motores, e o `contributor_id` é `hash(autor)`, não o sha1 do `figuras_linguagem_bruta`.
- `vitalidade.compacta` guarda de cada pessoa o primeiro e o último evento de cada trimestre, mais o primeiro de código e o primeiro de discussão. Nenhuma métrica muda (`test_compacta_nao_muda_nenhuma_metrica`). Em Zig, 1,26 milhão de eventos viram 71 mil linhas.
- `vitalidade.periodos` troca o laço por pessoa de `classify.profile` por uma passada vetorizada, com saída igual.
- O resultado compactado vai para `<saída>/<linguagem>/cache/`. Execuções seguintes leem dali enquanto os arquivos de entrada não mudarem de tamanho nem de data (`--sem-cache` relê). Quem só quer redesenhar usa `--so-figuras`.
- A curva de Kaplan-Meier de uma amostra com mais de 2 milhões de pontos sai com um ponto por dia, exato nesse instante.
- Limites: `FUNDIR_IDENTIDADES` fica fora da carga compacta. `ccr_ncr`, `stickiness` e `magnetismo` usam o pipeline do motor, que lê tudo para a memória: acima de `limite_bruto_gb` (20 GB) saem da execução padrão e recusam o pedido explícito. Em Python eles não rodam.

## Resultados num arquivo só

- `--empacota [ARQUIVO]` junta num `.tar.gz` as tabelas (parquet e CSV) de todas as linguagens e do comparativo, com um manifesto do commit e da data. O cache, a pasta de trabalho e as figuras ficam de fora. Cinco linguagens cabem em poucos MB.
- `--importa PACOTE` abre o `.tar.gz` em `--saida`, e `--so-figuras` desenha dali.
- `--saida PASTA` (padrão `~/Documents/pyramid-vitalidade`, env `PYRAMID_SAIDA`) escolhe onde ficam resultados e figuras.
- Fluxo: na batuta, calcular e `--empacota`; copiar o `.tar.gz` para o Mac com `scp`; no Mac, `--importa` e `--so-figuras` com o estilo que quiser.

## Rodar na batuta

O código só se edita no Mac e sobe para o GitHub. Na batuta só há clone, pull e execução.

```bash
# uma vez
ssh wendell@batuta.splab.ufcg.edu.br
git clone --branch feat/piramide-por-linguagem https://github.com/nufuturo-ufcg/population-pyramid.git ~/pyramid-vitalidade
curl -LsSf https://astral.sh/uv/install.sh | sh        # sem uv
cd ~/pyramid-vitalidade && uv sync

# a cada rodada: todas as linguagens e populações em paralelo, um processo por tarefa
cd ~/pyramid-vitalidade && git pull && export MPLBACKEND=Agg
nohup setsid uv run python scripts/vitalidade_grade.py --saida ~/pyramid-vitalidade-saida \
    --populacoes passou_30_dias,todos > ~/pyramid-vitalidade-saida/grade.log 2>&1 < /dev/null &
uv run python scripts/vitalidade.py --saida ~/pyramid-vitalidade-saida --empacota

# no Mac
scp wendell@batuta.splab.ufcg.edu.br:pyramid-vitalidade-saida/vitalidade-resultados-*.tar.gz .
uv run python scripts/vitalidade.py --importa vitalidade-resultados-AAAA-MM-DD-HHMM.tar.gz
uv run python scripts/vitalidade.py --linguagem python --so-figuras --figuras todas
```

- `/tmp` da batuta tem 2,7 GB. Resultados e a pasta de trabalho do duckdb ficam na pasta de `--saida`, em `/home`.
- `vitalidade_grade.py` espalha as tarefas em `processos` processos (yaml): a leitura dos eventos de cada linguagem vem primeiro, depois as outras populações dela, e o comparativo espera o cache de todas. Uma linguagem de cada vez continua valendo com `vitalidade.py --linguagem`. O Python leva cerca de 1 hora com o motor duckdb (10 GB leem em 2 minutos) e usa até 24 GB de memória (`memoria` no yaml). A batuta divide memória com as coletas: deixe folga.
- A pasta `~/population-pyramid` da batuta é a da coleta. Não use.
- Sem display, `MPLBACKEND=Agg`. Com `--figuras nenhuma` a batuta só calcula, e o Mac desenha.

## Régua

- Saída: 12 meses sem contribuir (Avelino et al., ESEM 2019). A replicação do IEICE16 usa 3.
- Idade no ano Y: Y menos o ano da primeira contribuição. Quem entrou em Y tem idade 0.
- Faixas de tempo na linguagem: 0-1, 1-2, 2-3, 3-5, 5-8, 8+ anos. Idade 1 cai em 1-2.
- A idade medida em 1/jan caiu porque punha duas coortes de entrada na faixa 0-1, e a projeção por coorte precisa de uma coorte por faixa de 1 ano.
- Com a idade por ano de calendário, a faixa 8+ de Clojure aparece em 2016, como diz o plano.
- Passo anual.
- Dois eventos do mesmo ano de calendário nunca viram dois períodos, mesmo com mais de 365,25 dias entre eles (só acontece em ano bissexto, de 1/jan a 31/dez). A janela de 12 meses lê-se como "quem contribuiu durante o ano" (`discrepancias.md`, seção 19). Sem isso a pessoa teria duas saídas no mesmo ano e a tabela anual não fecha. Em 4,2 milhões de pessoas do Python, uma caiu aí, e as tabelas de Clojure saem idênticas.

## Contagens por ano

- Ativo de Y: teve pelo menos um evento em Y.
- Novato de Y: primeiro evento da vida caiu em Y. Entra na faixa 0-1.
- Saída de Y: o último evento da vida da pessoa caiu em Y, e depois dele vieram mais de 12 meses sem nada até o fim da coleta. Quem para e volta tem uma pausa. A saída é como a morte na demografia, e é o que o plano diz ("pessoas cuja última contribuição foi naquele ano").
- Pausa de Y: um período de atividade terminou em Y e a pessoa voltou depois de mais de 12 meses. Quem volta não saiu: a pausa não entra na mortalidade e a pessoa segue viva.
- Volta de Y: um período de atividade que não é o primeiro começou em Y.
- Moved de Y: o primeiro commit ou PR caiu em Y, depois de a pessoa já ter discutido.
- A conta fecha: ativos(Y+1) = ativos(Y) - saídas(Y) - pausas(Y) + novatos(Y+1) + voltas(Y+1). `tabela_anual` falha se não fechar.
- `crescimento_natural_pct` = tudo que entra menos tudo que sai = (novatos + voltas - saídas - pausas) / ativos, em %. É a natalidade menos a mortalidade. É a única medida de crescimento do estudo.
- A base são os ativos do próprio ano Y, e os fluxos são os de Y: quem entrou em Y e quem tem a última contribuição de um período de atividade em Y. A variação sobre o ano anterior, ativos(Y) / ativos(Y-1) - 1, é outra conta: usa os ativos de Y-1 como base e as saídas e pausas de Y-1. Clojure 2024: crescimento natural -8,4%, variação dos ativos -18,8%. O relatório mostra as duas lado a lado.
- Hindsight: saber que a pessoa volta no futuro tira a saída dela. O custo é que a saída dos anos finais é provisória, porque quem parou há pouco ainda pode voltar. Das pausas que terminam, 54% a 67% duram até 2 anos, 75% a 86% até 3 e 90% a 98% até 5, nas cinco linguagens. Os gráficos vão até o último ano completo da coleta. O último ano completo conta como saída quem não contribuiu desde então, com menos de 12 meses de coleta confirmados (`provisorio` na tabela anual). Os `carencia_anos` (1) últimos anos completos saem tracejados nos gráficos de saída, mortalidade e crescimento. O ano da coleta, incompleto, fica fora.

## Escolhas feitas com o usuário (2026-10-09)

- Denominador da taxa de saída por faixa: ativos do ano. O plano fala em "ativos no início do ano". Essa leitura caiu porque deixaria no denominador de Y quem já saiu em Y-1, já que a saída é datada pelo último evento.
- Índice de envelhecimento: ativos com 5 anos ou mais na linguagem divididos pelos ativos com menos de 1.

## Censura à direita

- A saída de Y só se decide 12 meses depois de 31/12/Y.
- Com a coleta de Clojure terminando em 2026-09-03, saídas fecham até 2024. 2025 e 2026 têm ativos, novatos, voltas e pirâmide, e ficam sem saída, sem taxa e sem crescimento natural.
- Anualizar o ano aberto está proibido.

## Tábua de vida

- Duração de uma pessoa: último evento menos primeiro, em anos. Os intervalos sem contribuir entram na conta.
- Censurado: quem tem o último evento a 12 meses ou menos do fim da coleta.
- Método atuarial: q(x) = d(x) / (l(x) - censurados(x)/2).
- Quando a tábua termina com gente censurada, e(x) é um piso. A coluna `e_truncado` marca esse caso.

## Kaplan-Meier e log-rank

- Mesma duração e mesma censura da tábua de vida.
- `scipy.stats.ecdf` com `CensoredData` faz a curva. `scipy.stats.logrank` compara Clojure com cada linguagem.
- Sem censura, o S(1) do Kaplan-Meier é igual ao S(1) da tábua (teste em `tests/test_vitalidade.py`).

## Categorias da pirâmide

Por padrão (`usa_moved_to_discussion: false`) as pirâmides têm três categorias, as do artigo: `non_coding`, `moved` e `coding`, com quem já codou e neste ano só discutiu no lugar que a história dele o põe. Com `usa_moved_to_discussion: true` entra a quarta, abaixo.

No fim de cada ano, cada pessoa ativa cai em uma de quatro categorias, pelo que fez até esse ano.

| categoria | lado | quem é |
|---|---|---|
| `non_coding` | discussão | nunca fez commit nem PR |
| `moved_to_discussion` | discussão | já codou em anos anteriores e neste ano só discutiu |
| `moved` | código | começou pela discussão e fez commit ou PR neste ano |
| `coding` | código | começou pelo código e fez commit ou PR neste ano |

- Quem fez algum commit ou PR no ano fica do lado do código, mesmo que o último evento do ano seja um comentário. A regra anterior, que olhava o último evento do ano, jogava em `moved_to_discussion` quem comentou depois do último commit. Em Clojure 2024 isso dava 1.531 pessoas, e 752 delas tinham feito commit no próprio 2024.
- Quem volta a codar muda de categoria no ano seguinte.
- O parâmetro `piramide_lado` limita o desenho a uma parte: `moved_para_discussao`, `moved_para_codigo`, `codigo` (moved + coding), `discussao` (non_coding + moved_to_discussion) ou `todos`. A base da % continua sendo os ativos do ano todo.
- `moved_to_discussion` é uma situação (estoque). A coluna `deixou_codigo` da tabela anual e a figura de troca de papel contam um fluxo, olhando o futuro.

## Troca de papel

- `moved` (ida): primeiro commit ou PR depois de já ter discutido. Ano = o do primeiro commit ou PR.
- `deixou_codigo` (volta): a última atividade de discussão vem depois do último commit ou PR. Ano = o do último commit ou PR.
- A volta olha o futuro: quem voltar a codar deixa de contar. No último ano da coleta o último commit é só o último visto, e quem ainda vai codar entra como quem deixou o código (2025 em Clojure dá 19%, contra 10% nos anos anteriores). A figura para em `fim.year - 1`, e o último ano dela ainda sobe um pouco.
- A compactação guarda o último evento de código e de discussão de cada trimestre. Muda `VERSAO_CACHE`: caches antigos são refeitos.
- Figura: `tamanho.troca_de_papel`, em % dos ativos do ano.

## Tábua comparada

- Métrica `tabua_comparada` (comparativa): a tábua de vida de todas as pessoas de cada linguagem, até `tabua_ate_anos` (8, a última faixa das pirâmides).
- e(x) é a vida restante de quem chegou a x. A chance de seguir mais t anos tendo chegado a x sai de l(x+t) / l(x).
- A figura `chegar_e_ficar` separa chegar à senioridade, S(x), de permanecer nela, 1 - q(x).
- e(x) é piso: a cauda censurada fica de fora (`e_truncado`).

## Taxa padronizada e SMR

- Referência: a soma das linguagens comparadas.
- Pesos: composição por faixa dos ativos de todas juntas em 2025.
- Direta: soma de taxa da faixa vezes peso. Fica vazia em ano com faixa sem ninguém (Clojure antes de 2016, Elixir antes de 2019, Zig antes de 2023).
- SMR: saídas reais / soma de taxa da referência vezes ativos da faixa.
- Python e OCaml entram quando as coletas fecharem, e a referência muda junto.
- Nos anos em que só Clojure existe (2008 a 2010), ela é a própria referência e o SMR dá 1.

## Projeção

- Bandas de 1 ano de 0 a 7 e a 8+ aberta. Cada banda de 0 a 7 é uma coorte de entrada.
- P(8+, T+1) = SR(7) P(7, T) + SR(8+) P(8+, T). SR(7) usa quem tem exatamente 8 anos em T; SR(8+) usa quem tem 9 ou mais.
- Ingênuo: a pirâmide de T+1 repete a de T.
- Coorte: permanência do último par de anos e novatos = média dos dois últimos anos.
- Cenários: menor, maior e média dos dois, por banda. Os novatos seguem a mesma regra.
- Filtro dos cenários: `--set min_saidas=N` só aceita o ano em que a banda teve N saídas ou mais. Padrão 0, a pedido do usuário (2026-10-09), para ver primeiro sem filtro. `projecao_anos_validos.csv` conta os anos que sobram com 10 e com 20.
- Banda sem nenhum ano válido usa a permanência do último ano nos três cenários. Sem isso, Zig não teria cenário nenhum.
- Banda com gente em T e vazia em T-1 não tem permanência: a célula fica sem previsão e sai do erro, como em `projection.py`.
- O ano em que a coleta termina está pela metade e fica fora da projeção. Clojure projeta a partir de 2025.
- Backtest: cada ano previsto usa só os anos anteriores. Erro em ABRE por faixa de apresentação, Wilcoxon pareado entre métodos.
- Cobertura: fração de anos em que o real ficou entre o pessimista e o otimista.
- Teto em 1 na permanência: roda das duas formas. A adotada é sem teto, como no IEICE16 (escolha do usuário, 2026-10-09). Com teto fica como sensibilidade, nos mesmos CSVs, com a coluna `teto`.

## Natalidade e mortalidade

- Natalidade: (novatos + voltas) / ativos do ano. Mortalidade: (saídas + pausas) / ativos do ano. A diferença é o crescimento natural.
- Saem da tabela anual, sem cálculo à parte. Dois gráficos com o mesmo tamanho e o mesmo eixo dos anos: `tamanho.natalidade_mortalidade` e `tamanho.natalidade_mortalidade_com_populacao`, o segundo com a população de cada ano em barras ao fundo. A população do ano é o mesmo grupo dos ativos.

## Identidade das pessoas

- Na carga (`adapters/coleta_csv/carga_duckdb.py`), a pessoa é o nome do autor no commit (`author`) e o login do GitHub nos eventos da API (`author_login`).
- A mesma pessoa vira duas quando o nome de commit difere do login, ou quando ela usa nomes diferentes no git. Duas pessoas com o mesmo nome de commit viram uma.
- A fusão fica desligada por padrão. `fundir_identidades: true` (motor duckdb) junta o nome de commit ao login pelo e-mail noreply do GitHub e pela heurística dos repositórios em comum de `scripts/figuras_linguagem_bruta.py` (`FUNDIR_IDENTIDADES`).
- Com `autores:` em `scripts/vitalidade_fontes.yaml`, o commit conta para o login que o GitHub liga ao e-mail do autor (`autores_commits.csv`, coletado por GraphQL) ou ao e-mail noreply. E-mail sem conta (cerca de 32%) segue com o nome do autor. Esse caminho não usa a heurística e força o motor duckdb. As cinco linguagens da batuta têm `autores:` desde 2026-10-26.
- Medida em Clojure (2026-10-19), nos commits que tocam a linguagem:

```
uv run python adapters/coleta_csv/identidades.py \
    --git '/home/wendell/dados-brutos/clojure/*/eventos_git.csv' \
    --api '/home/wendell/dados-brutos/clojure/*/eventos_api.csv' \
    --extensoes .clj .cljs .cljc .cljx .edn .bb
```

| contagem | Clojure |
|---|---|
| nomes de commit | 12663 |
| e-mails de commit | 14542 |
| e-mails com mais de um nome | 1515 |
| nomes com mais de um e-mail | 2502 |
| logins da API | 43666 |
| nomes de commit iguais a algum login | 2060 |

- Só 2060 dos 12663 nomes de commit (16%) coincidem com um login. Quem commita e também abre issue, PR ou comenta com nome de commit diferente do login conta como duas pessoas: uma no lado do código pelo commit e outra pelo login.
- 1515 e-mails aparecem com mais de um nome: a mesma pessoa partida em vários nomes.
- 2502 nomes aparecem com mais de um e-mail. Parte é a mesma pessoa com vários e-mails (sem efeito, o nome é o mesmo) e parte são pessoas diferentes com o mesmo nome, fundidas.
- O efeito nas métricas não foi medido. Partir uma pessoa em duas aumenta pessoas, novatos e saídas. A correção exige o login do autor de cada commit, que a API de commits do GitHub devolve e o clone não tem.
