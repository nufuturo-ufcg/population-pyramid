# Parâmetros das métricas de vitalidade

Duas fontes de configuração:

- `scripts/vitalidade.yaml`: o que se calcula. Sobrepõe-se por execução com `--set chave=valor`.
- `scripts/vitalidade_figuras.yaml`: como se desenha. Sobrepõe-se com `--estilo figura:opção=valor`. Redesenha em segundos com `--so-figuras`.

Coluna "muda": **tabela** pede recálculo (rodar sem `--so-figuras`). **desenho** vale com `--so-figuras`.
Se um parâmetro de tabela mudar, `--so-figuras` avisa que as tabelas gravadas são antigas.

## 1. Parâmetro para configuração

### Quem entra e onde o estudo termina

| parâmetro | padrão | configura | muda |
|---|---|---|---|
| `populacao` | `passou_30_dias` | quem conta como pessoa. `todos`, `codigo`, `mais_de_um_dia`, `passou_N_dias`. Cada uma grava em pasta própria (`python-passou_30_dias`). O cache dos eventos é um só. | tabela |
| `data_de_corte` | `2025-12-31` | fim do estudo. Eventos depois dela saem de tudo. Tem de ser o último dia de um trimestre. `null` usa o último evento. | tabela |
| `carencia_anos` | 1 | anos de coleta depois de um ano para a saída dele valer como firme. Ano mais recente que isso sai tracejado. | desenho (e a coluna `provisorio` da trajetória) |

### Cenários e projeção (RQ3)

| parâmetro | padrão | configura | muda |
|---|---|---|---|
| `min_saidas` | 0 | saídas mínimas de uma banda no ano anterior para a permanência dela entrar no cenário. 0 desliga. | tabela |
| `variantes` | 4 regras | regras de cenário comparadas no backtest: rótulo, janela em anos (`null` = história toda), novatos por taxa. A primeira é a do plano. | tabela |
| `horizonte` | 5 | anos projetados à frente. | tabela |
| `teto` | false | permanência com ou sem teto em 1 nas figuras. Os CSVs trazem as duas. | desenho |

### Comparação entre linguagens (RQ2)

| parâmetro | padrão | configura | muda |
|---|---|---|---|
| `linguagens_rq2` | clojure, elixir, zig, ocaml, python | linguagens do comparativo. A primeira é a referência do log-rank. | tabela |
| `rodadas_padronizacao` | `nicho`, `python` | quais linguagens formam cada rodada do SMR e da taxa padronizada. | tabela |
| `ano_pesos` | 2025 | ano cuja composição por faixa pesa a referência de cada rodada. | tabela |
| `ano_base_indice` | 2019 | ano em que o índice de ativos vale 100. | tabela |
| `ano_comparacao` | 2024 | ano das pirâmides lado a lado entre linguagens. | desenho |

### CCR e NCR

| parâmetro | padrão | configura | muda |
|---|---|---|---|
| `ccr_ncr_inatividade_meses` | 12 | quem não contribuiu nesse tempo já saiu e não entra na população ativa do trimestre. 12 é o limite de Avelino et al. (ESEM 2019). | tabela |
| `ccr_ncr_novato_meses` | 12 | idade máxima de um novato. 12 casa com a janela de saída. O IEICE16 usa 3. | tabela |

Com 3 e 3 o resultado é o do motor, exatamente (validado em Clojure, Elixir, Zig e OCaml).

### Tábua de vida e retenção

| parâmetro | padrão | configura | muda |
|---|---|---|---|
| `tabua_ate_anos` | 8 | anos de casa mostrados na tábua comparada. 8 é a última faixa das pirâmides. | tabela |
| `coortes_tabua` | 2010, 2013, 2016, 2019, 2022 | coortes de entrada desenhadas na tábua por coorte. | desenho |

### Pirâmides e taxas por faixa

| parâmetro | padrão | configura | muda |
|---|---|---|---|
| `anos_piramide` | 2010, 2014, 2018, 2022, 2025 | anos das pirâmides por linguagem. | desenho |
| `piramide_em_pct` | true | pirâmides em % dos ativos do ano. `false` desenha contagens. | desenho |
| `saidas_estavel` | 20 | taxa de saída da célula (faixa, ano) fica vazada com menos saídas que isso. Mesmo critério do CDC. | desenho |

### Carga dos eventos

| parâmetro | padrão | configura |
|---|---|---|
| `motor` | `auto` | `pandas`, `duckdb` ou `auto` (duckdb acima de `limite_pandas_gb`). |
| `limite_pandas_gb` | 20 | tamanho de eventos acima do qual `auto` escolhe duckdb. |
| `limite_bruto_gb` | 20 | acima disso o pipeline do motor (`ccr_ncr` pelo motor, `stickiness`, `magnetismo`) recusa o pedido. |
| `memoria` | 30GB | memória do duckdb. |
| `threads` | 16 | núcleos do duckdb. `null` usa todos. |
| `contar_linhas_brutas` | false | releitura do arquivo só para contar linhas brutas (estatística do filtro, sem efeito nas métricas). |

Origem dos dados: `scripts/vitalidade_fontes.yaml`, `--dados`, `--eventos`, `--alvo`.

## 2. Métrica para parâmetros

| métrica | escopo | lê (tabela) | lê (só desenho) |
|---|---|---|---|
| `tamanho` | linguagem | `populacao`, `data_de_corte` | `carencia_anos` |
| `composicao` | linguagem | `populacao`, `data_de_corte` | `anos_piramide`, `piramide_em_pct` |
| `retencao` | linguagem | `populacao`, `data_de_corte` | `coortes_tabua` |
| `saida_por_faixa` | linguagem | `populacao`, `data_de_corte` | `saidas_estavel`, `carencia_anos` |
| `cenarios` | linguagem | `min_saidas`, `variantes`, `horizonte` | `teto` |
| `ccr_ncr` | linguagem | `ccr_ncr_inatividade_meses`, `ccr_ncr_novato_meses` | |
| `significancia` | comparativo | `linguagens_rq2` | |
| `comparacao_corrigida` | comparativo | `linguagens_rq2`, `rodadas_padronizacao`, `ano_pesos` | `carencia_anos` |
| `trajetoria` | comparativo | `linguagens_rq2`, `ano_base_indice`, `carencia_anos` | `ano_comparacao` |
| `ccr_ncr_comparado` | comparativo | `linguagens_rq2`, `ccr_ncr_inatividade_meses`, `ccr_ncr_novato_meses` | |
| `tabua_comparada` | comparativo | `linguagens_rq2`, `tabua_ate_anos` | |
| `stickiness`, `magnetismo` | linguagem | nenhum (fora do padrão) | |

Todas as métricas leem `populacao` e `data_de_corte` pelo contexto, mesmo as que não aparecem na linha.

## 3. Constantes que ficam no código

Estas não têm chave no yaml. Mudar exige editar `src/pyramid/vitalidade.py`.

| constante | valor | o que fixa |
|---|---|---|
| `GAP_DIAS` | 12 meses | silêncio que separa dois períodos. Saída definitiva e pausa partem dele. |
| `FAIXAS` | 0-1, 1-2, 2-3, 3-5, 5-8, 8+ | faixas de tempo de casa. |
| `BAND_DIAS` | 90 | banda das pirâmides trimestrais. |
| `NOVATO_DIAS` | 91 | novato do motor, usado só como padrão da função. |
| `MAX_PONTOS_KM` | 2 000 000 | acima disso o Kaplan-Meier afina os pontos. |
| `VERSAO_CACHE` | 3 | sobe quando o filtro ou a compactação mudam. Invalida todo cache. |

## 4. Estilo dos gráficos

`scripts/vitalidade_figuras.yaml`, seção `global`, vale para todo gráfico. A seção `figuras` dá opções a um gráfico só, com a chave `metrica.figura` (por exemplo `tamanho.fluxo`). O gráfico usa `global` com as opções dele por cima.

| opção | configura |
|---|---|
| `figsize`, `dpi`, `formato` | tamanho, resolução e arquivo (png, svg, pdf). |
| `titulo`, `titulo_geral`, `rotulo_x`, `rotulo_y` | textos. `{linguagem}` vira o nome. |
| `xlim`, `ylim`, `escala_y` | eixos. `escala_y: log` no índice de ativos. |
| `grade`, `fontes`, `legenda`, `linha` | grade, fontes, legenda e largura das linhas. |
| `paleta`, `cores_linguagem` | cores categóricas, rampa e cor de cada linguagem. |
| `linhas_horizontais`, `linhas_verticais`, `textos` | anotações nos dados. |
| `eixos` | opções do segundo painel em diante. |

Exemplos:

```
uv run python scripts/vitalidade.py --so-figuras --figuras tamanho
--estilo tamanho.fluxo:titulo="{linguagem}: entradas e saídas"
--estilo global:dpi=300
```
