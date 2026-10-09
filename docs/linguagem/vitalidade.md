# Métricas de vitalidade: definições

Régua do Plano de Experimento, aplicada por `src/pyramid/vitalidade.py`.
Reproduz com:

```bash
uv run python scripts/vitalidade.py --linguagem clojure   # etapas 1 a 4 e 7, uma linguagem
uv run python scripts/vitalidade.py --comparativo         # etapas 5 e 6, Clojure, Elixir e Zig
```

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
- Cenários: menor, maior e média dos dois, por banda, só com anos em que a banda teve 20 saídas ou mais. Os novatos seguem a mesma regra sem o filtro.
- Banda sem nenhum ano válido usa a permanência do último ano nos três cenários. Sem isso, Zig não teria cenário nenhum.
- Banda com gente em T e vazia em T-1 não tem permanência: a célula fica sem previsão e sai do erro, como em `projection.py`.
- O ano em que a coleta termina está pela metade e fica fora da projeção. Clojure projeta a partir de 2025.
- Backtest: cada ano previsto usa só os anos anteriores. Erro em ABRE por faixa de apresentação, Wilcoxon pareado entre métodos.
- Cobertura: fração de anos em que o real ficou entre o pessimista e o otimista.
- Teto em 1 na permanência: roda das duas formas e adota a de menor mediana do ABRE do coorte. Em Clojure as duas dão o mesmo número, porque nenhuma permanência passou de 1.
