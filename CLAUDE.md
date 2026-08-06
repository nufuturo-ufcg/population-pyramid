# pyramid-replication

Antes de qualquer coisa neste repo, ler:

- **`INSTRUCOES_CLAUDE_CODE.MD`** — spec de implementação (fonte da verdade; vence sobre qualquer outra doc em caso de conflito).
- **`docs/discrepancias.md`** — log vivo de ambiguidades investigadas. Toda entrada nova cita o comando/query exato usado, não só o número.

Regras que já custaram caro e não se renegociam:

- Nunca mover, copiar ou apagar nada dentro de `DATASET_DIR` — é a cópia de trabalho do usuário; o dump entra por bind mount read-only.
- Nunca usar `information_schema.table_rows` para sanity check — só `COUNT(*)`.
- Nunca escrever SQL fora de `src/pyramid/sources/`.
- Escopo é sempre por `project.id`, nunca por `name` (`symfony` aparece duas vezes nos 90).
- Reprodutibilidade exata é o critério de aceite: número que não bate é bug ou ambiguidade, nunca "arredondar pra ficar perto".
- 2013 é right-censored (dump acaba em out/2013): **renderiza pirâmide, não recebe quadrante**. Forma é estoque (olha pra trás, não sofre censura); stickiness é fluxo (precisa de Y+1, não existe). O ESEM14 faz o mesmo com o mesmo corte — ver `discrepancias.md` §11.1. Não anualizar 9 meses para forçar classificação.
