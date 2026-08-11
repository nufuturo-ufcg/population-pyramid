# Documentação

Duas pastas, dois assuntos.

## `replicacao/`: o que os artigos dizem e o que saiu aqui

Muda quando um número muda.

| arquivo | o que é |
|---|---|
| [`RESUMO_EXECUTIVO.md`](replicacao/RESUMO_EXECUTIVO.md) | estado do projeto em uma página: o que bate, o que diverge, o placar. |
| [`METODO.md`](replicacao/METODO.md) | do dump ao número, estágio por estágio, com o parâmetro de cada decisão. |
| [`discrepancias.md`](replicacao/discrepancias.md) | log vivo de ambiguidade investigada. Cada entrada cita o comando exato e o número obtido. |
| [`figuras/`](replicacao/figuras/README.md) | uma leitura por figura replicada: o que mostra, o que bate, o que diverge. |
| `papers/` | PDFs de referência (ESEM14, MSR14, IEICE16 e o erratum). |

## `ferramenta/`: como o programa funciona

Muda quando o código muda.

| arquivo | o que é |
|---|---|
| [`COMO_FUNCIONA.md`](ferramenta/COMO_FUNCIONA.md) | visão de alto nível, sem fórmula e sem nome de biblioteca. Comece por aqui. |
| [`FONTES.md`](ferramenta/FONTES.md) | contrato de entrada: formato canônico de evento e como escrever uma fonte nova. |

Fora de `docs/`: `INSTRUCOES_CLAUDE_CODE.MD` é a spec de implementação e vence
sobre qualquer doc em caso de conflito. `CONTRIBUTING.md` cobre ambiente,
hooks, CI e formato de commit.
