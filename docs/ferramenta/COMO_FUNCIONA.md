# Como a ferramenta funciona

Visão de alto nível. Sem fórmula e sem nome de biblioteca. Descreve o que o
programa pensa. Como ele calcula está em [`../replicacao/METODO.md`](../replicacao/METODO.md).

## O problema

Um projeto de software tem gente entrando e gente saindo o tempo todo. Olhar só
o total ("o projeto tem 500 contribuidores") esconde o que importa: são 500
veteranos que nunca renovaram, ou 500 novatos que chegaram mês passado? Os dois
projetos têm o mesmo número e futuros opostos.

Os artigos que estamos replicando resolvem isso com uma ideia emprestada da
demografia: desenhar a **pirâmide populacional** do projeto.

## A analogia

Você já viu a pirâmide populacional de um país. Um eixo vertical de faixas
etárias, homens de um lado, mulheres do outro, cada faixa é uma barra
horizontal. Base larga = país jovem. Topo pesado = país envelhecendo.

A pirâmide de um projeto de software é a mesma figura, com duas trocas:

| No país | No projeto |
|---|---|
| homens / mulheres | quem **escreve código** / quem **só conversa** |
| idade da pessoa | há quanto tempo ela está **no projeto** |

Uma pessoa que chegou ao projeto ontem tem "0 anos de idade", mesmo que tenha
40 de vida. Uma pessoa que está lá desde o primeiro dia é a mais "velha" do
projeto.

E a leitura é a mesma da demografia. Base larga: chega gente nova, projeto
atrativo. Base vazia e topo cheio: ninguém novo entra, projeto envelhecendo.
Pirâmide inteira minguando: projeto morrendo.

## O que o programa pergunta sobre cada pessoa

Três perguntas. Elas definem, respectivamente, o **lado**, a **altura** e a
**cor** de cada pessoa na figura.

Vou usar uma pessoa de verdade: o contribuidor `2617` do projeto paperclip.

### 1. De que lado ela fica?

Olhamos tudo que a pessoa fez no projeto e separamos em dois montes:

- **código**: mandou commit, abriu pull request;
- **conversa**: comentou num commit, num pull request, numa issue.

Quem só tem o segundo monte fica à esquerda. Quem tem o primeiro fica à
direita.

Existe um terceiro caso, e é o interessante: gente que **começou conversando e
depois virou programador**. É exatamente o caso do `2617`. Ele apareceu no
paperclip em novembro de 2009 comentando; o primeiro código dele só veio em
outubro de 2011, quase dois anos depois. Essa pessoa aparece do lado do código,
mas marcada à parte: é a evidência de que o projeto converte conversador em
programador, que é uma das coisas que os artigos querem medir.

### 2. Em que altura ela fica?

Conta-se o tempo desde a primeira vez que a pessoa fez aquilo que a colocou no
lado dela. Para o `2617`, o relógio do lado do código começa em outubro de 2011.
Não em 2009. Ele é um programador *novo* no projeto, mesmo sendo uma cara
conhecida há dois anos.

Esse tempo cai numa faixa. As faixas são trimestres, então cada ano de idade
vira quatro barras empilhadas. Por isso as pirâmides têm tantas linhas finas.

### 3. Ela ainda está aqui?

Uma pessoa que não dá sinal de vida há muito tempo saiu, na prática. O programa
marca cada pessoa como ativa ou inativa conforme ela tenha aparecido ou não
dentro de uma janela recente.

O `2617` também serve aqui: ele aparece no paperclip em três blocos separados
(alguns dias em 2009, um dia em 2011, um dia em 2012) com anos de silêncio no
meio. Dependendo da data em que você fotografa o projeto, ele está vivo ou não.

**Um detalhe que confunde e vale fixar:** a pirâmide desenha *todo mundo que já
passou pelo projeto*. Não desenha só quem está ativo. Ela é uma foto do acervo.
Não é do movimento. Quem está ativo importa para as *contas* (crescimento,
projeção). Não importa para o desenho. Errar isso foi um bug real aqui: as
figuras saíam achatadas a um décimo do tamanho.

## Do banco de dados à figura

Cinco etapas. Cada uma lê o resultado da anterior e grava o seu, então dá para
parar no meio, conferir e recomeçar dali.

1. **Extrair**: varre o dump do GitHub e reduz cada projeto a uma lista de
   eventos: quem, o quê, quando.
2. **Perfilar**: junta os eventos por pessoa e responde as três perguntas
   acima: o lado dela, quando o relógio dela começou, seus períodos de
   atividade.
3. **Fotografar**: escolhe uma data (por exemplo 31/dez/2011) e produz o
   retrato do projeto naquele dia: cada pessoa com seu lado, sua faixa e seu
   estado. Isso é a pirâmide.
4. **Interpretar**: compara fotos de datas diferentes e responde perguntas
   sobre o projeto: ele atrai gente nova? segura quem chega? para onde ele vai?
   Daí saem os rótulos que os artigos usam (atrativo, flutuante, estagnado,
   terminal) e a projeção de futuro.
5. **Desenhar e conferir**: gera as 8 figuras dos artigos e roda a checagem
   descrita abaixo.

Um comando por etapa, na ordem:

```
uv run pyramid extract
uv run pyramid classify
uv run pyramid snapshots
uv run pyramid metrics
uv run pyramid attractiveness
uv run pyramid projection
uv run pyramid plot --figure all
uv run pyramid validate --report output/validation_report.md
```

Ou `uv run pyramid run-all`, que roda tudo na ordem e para no primeiro estágio
que falhar.

## Como o programa não deixa a gente se enganar

Esta é a parte que mais importa e a que menos aparece.

O objetivo aqui é chegar **no mesmo número que os artigos**. Figura bonita não
conta. Então cada valor que os artigos publicam foi transcrito num arquivo
de gabarito, e o programa se compara a ele toda vez que roda. Hoje são 167
pontos de comparação.

Cada ponto tem um de três destinos:

- **bate**: nada a fazer;
- **não bate, e sabemos por quê**: a divergência fica registrada com o motivo,
  e o programa passa a exigir que ela continue exatamente daquele tamanho;
- **não bate e não sabemos por quê**: o programa falha. Não existe a opção de
  arredondar para ficar perto.

O segundo caso é o mais útil e o menos óbvio. Quando não conseguimos chegar no
número do artigo, não escondemos o desvio. **Travamos** ele. Se um dia alguém
mexer no código e o desvio mudar de tamanho, o programa avisa na hora, mesmo
que mude "para melhor". Isso transforma cada discordância com o artigo em um
alarme, em vez de deixá-la virar ruído de fundo.

Exemplo concreto: no projeto homebrew sobram 129 pessoas que classificamos como
programadoras e o artigo classifica como conversadoras. Não descobrimos por quê
(seis hipóteses testadas e derrubadas). Então o número 129 está travado, com
nome e endereço, e qualquer alteração nele quebra a checagem.

## Onde ler mais

| Quero saber... | Vou em |
|---|---|
| como está o projeto hoje, em uma página | `docs/replicacao/RESUMO_EXECUTIVO.md` |
| o que cada figura mostra e onde ela diverge do artigo | `docs/replicacao/figuras/` |
| o detalhe técnico de qualquer divergência, com os comandos usados | `docs/replicacao/discrepancias.md` |
| de onde vêm os dados e como plugar outra fonte | `docs/ferramenta/FONTES.md` |
| a especificação que manda em tudo | `INSTRUCOES_CLAUDE_CODE.MD` |
