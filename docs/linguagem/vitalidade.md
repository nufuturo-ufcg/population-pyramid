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

# a cada rodada
cd ~/pyramid-vitalidade && git pull && export MPLBACKEND=Agg
nohup setsid uv run python scripts/vitalidade.py --linguagem python --saida ~/pyramid-vitalidade-saida \
    --figuras nenhuma > ~/pyramid-vitalidade-saida/python-run.log 2>&1 < /dev/null &
uv run python scripts/vitalidade.py --comparativo --saida ~/pyramid-vitalidade-saida --figuras nenhuma
uv run python scripts/vitalidade.py --saida ~/pyramid-vitalidade-saida --empacota

# no Mac
scp wendell@batuta.splab.ufcg.edu.br:pyramid-vitalidade-saida/vitalidade-resultados-*.tar.gz .
uv run python scripts/vitalidade.py --importa vitalidade-resultados-AAAA-MM-DD-HHMM.tar.gz
uv run python scripts/vitalidade.py --linguagem python --so-figuras --figuras todas
```

- `/tmp` da batuta tem 2,7 GB. Resultados e a pasta de trabalho do duckdb ficam na pasta de `--saida`, em `/home`.
- Uma linguagem de cada vez. O Python leva cerca de 1 hora com o motor duckdb (10 GB leem em 2 minutos) e usa até 24 GB de memória (`memoria` no yaml). A batuta divide memória com as coletas: deixe folga.
- A pasta `~/population-pyramid` da batuta é a da coleta. Não use.
- Sem display, `MPLBACKEND=Agg`. Com `--figuras nenhuma` a batuta só calcula, e o Mac desenha.

## Régua

- Saída: 12 meses sem contribuir (Avelino et al., ESEM 2019). A replicação do IEICE16 usa 3.
- Idade no ano Y: Y menos o ano da primeira contribuição. Quem entrou em Y tem idade 0.
- Faixas de tempo de casa: 0-1, 1-2, 2-3, 3-5, 5-8, 8+ anos. Idade 1 cai em 1-2.
- A idade medida em 1/jan caiu porque punha duas coortes de entrada na faixa 0-1, e a projeção por coorte precisa de uma coorte por faixa de 1 ano.
- Com a idade por ano de calendário, a faixa 8+ de Clojure aparece em 2016, como diz o plano.
- Passo anual.

## Contagens por ano

- Ativo de Y: teve pelo menos um evento em Y.
- Novato de Y: primeiro evento da vida caiu em Y. Entra na faixa 0-1.
- Saída de Y: o último evento de um período de atividade caiu em Y, e depois dele vieram mais de 12 meses sem nada.
- Volta de Y: um período de atividade que não é o primeiro começou em Y.
- Moved de Y: o primeiro commit ou PR caiu em Y, depois de a pessoa já ter discutido.
- A conta fecha: ativos(Y+1) = ativos(Y) - saídas(Y) + novatos(Y+1) + voltas(Y+1). `tabela_anual` falha se não fechar.

## Escolhas feitas com o usuário (2026-10-09)

- Denominador da taxa de saída por faixa: ativos do ano. O plano fala em "ativos no início do ano". Essa leitura caiu porque deixaria no denominador de Y quem já saiu em Y-1, já que a saída é datada pelo último evento.
- Índice de envelhecimento: ativos com 5 anos ou mais de casa divididos pelos ativos com menos de 1.

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

## Transição demográfica

- Natalidade: nascimentos / população do período. Mortalidade: óbitos / população do período.
- Passo anual e trimestral (`fluxos(eventos, fim, "Y")` e `"Q"`).
- População de um período: quem tem um período de atividade que o cobre, contando os meses sem evento no meio.
- No passo anual a população é igual aos ativos de `tabela_anual`. Conferido em Clojure, Elixir e Zig (2026-10-09). O teste `test_fluxos_anual_bate_com_tabela_anual` cobre o caso pequeno.
- No trimestral a mesma conta de fluxo fecha: pop(P+1) = pop(P) - óbitos(P) + nascimentos(P+1) + voltas(P+1).
- O período em que a coleta termina fica de fora. Óbito sem 12 meses de coleta depois fica vazio.
