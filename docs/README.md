# Mapa dos documentos

Este arquivo diz qual doc responde qual pergunta. Comece por aqui quando não
souber onde procurar.

O repo tem dois assuntos, e todo doc pertence a um deles.

- **A ferramenta**: o programa que transforma eventos de atividade em pirâmides
  demográficas. Muda quando o código muda.
- **A replicação**: o caso de aceite construído sobre o dump MSR14, que
  reproduz Onoue et al. Muda quando um número muda.

## Por onde entrar

| Quero... | Vou em |
|---|---|
| rodar o pipeline do zero | [`README.md`](../README.md) na raiz |
| entender o que o programa faz, sem fórmula | [`ferramenta/COMO_FUNCIONA.md`](ferramenta/COMO_FUNCIONA.md) |
| plugar outra fonte de dados | [`ferramenta/FONTES.md`](ferramenta/FONTES.md) |
| olhar a pirâmide de uma linguagem | [`linguagem/clojure.md`](linguagem/clojure.md) |
| mexer no código | [`CONTRIBUTING.md`](../CONTRIBUTING.md) |
| saber como está o projeto hoje | [`replicacao/RESUMO_EXECUTIVO.md`](replicacao/RESUMO_EXECUTIVO.md) |
| entender o método replicado | [`replicacao/METODO.md`](replicacao/METODO.md) |
| saber por que um número não bate | [`replicacao/discrepancias.md`](replicacao/discrepancias.md) |

## Raiz do repo

| arquivo | o que é |
|---|---|
| [`README.md`](../README.md) | o que o projeto é, instalação, comandos, definição de pronto. |
| [`CONTRIBUTING.md`](../CONTRIBUTING.md) | ambiente, hooks, testes, CI, contrato de estágio, adaptador novo, regras de escrita e de commit. É a fonte da verdade e vence sobre qualquer outra doc em caso de conflito. |
| [`CLAUDE.md`](../CLAUDE.md) | resumo do repo para agente de IA. Duplica de propósito as regras que já custaram caro. |

## `ferramenta/`: como o programa funciona

Muda quando o código muda.

| arquivo | o que é |
|---|---|
| [`COMO_FUNCIONA.md`](ferramenta/COMO_FUNCIONA.md) | visão de alto nível, sem fórmula e sem nome de biblioteca. Comece por aqui. |
| [`FONTES.md`](ferramenta/FONTES.md) | contrato de entrada: formato canônico de evento e como escrever uma fonte nova. |

Como preparar o dump MSR14 está no [`README.md`](../README.md) da raiz, em
"Dados do adaptador msr14". O que cada query do adaptador faz está comentado dentro
de `adapters/msr14/source.py`.

## `linguagem/`: a pirâmide por linguagem de programação

Muda quando a coleta muda.

| arquivo | o que é |
|---|---|
| [`clojure.md`](linguagem/clojure.md) | os números e as figuras da amostra de desenvolvimento, com a leitura de cada um. |
| `numeros.json` | a mesma coisa em JSON, gerado por `scripts/figuras_linguagem.py`. Nenhum número do doc é digitado à mão. |
| `figuras/` | uma pirâmide por linguagem, no snapshot da classificação. |

## `replicacao/`: o que os artigos dizem e o que saiu aqui

Muda quando um número muda.

| arquivo | o que é |
|---|---|
| [`RESUMO_EXECUTIVO.md`](replicacao/RESUMO_EXECUTIVO.md) | estado do projeto numa página: o placar da replicação, o que existe da pirâmide por linguagem, e o que está pendente. Reescrito por completo a cada sessão. |
| [`METODO.md`](replicacao/METODO.md) | do dump ao número, estágio por estágio, com o parâmetro de cada decisão. |
| [`discrepancias.md`](replicacao/discrepancias.md) | log vivo de ambiguidade investigada. Cada entrada cita o comando exato e o número obtido. Cresce por acréscimo e nunca é podado. |
| [`figuras/`](replicacao/figuras/README.md) | uma leitura por figura replicada: o que mostra, o que bate, o que diverge. |
| `papers/` | PDFs de referência (ESEM14, MSR14, IEICE16 e o erratum). |

## Documento gerado, fora de `docs/`

`output/` sai do pipeline e não é escrito à mão. `output/validation_report.md`
compara cada número contra `config/checkpoints.yaml`. `output/plots/` guarda as
figuras e as tabelas em CSV e Markdown, com `_manifest.json` declarando o que
foi gerado.
