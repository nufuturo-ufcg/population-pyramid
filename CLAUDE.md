# pyramid-replication

Antes de qualquer coisa neste repo, ler:

- **`INSTRUCOES_CLAUDE_CODE.MD`**: spec de implementação (fonte da verdade; vence sobre qualquer outra doc em caso de conflito).
- **`docs/replicacao/discrepancias.md`**: log vivo de ambiguidades investigadas. Toda entrada nova cita o comando/query exato usado, além do número obtido.

Escrita: o usuário proíbe a estrutura antitética ("é X, não Y" / "não é X, é Y" e variantes)
em qualquer texto: doc, commit, comentário, resposta. Regra completa e exemplos em
`~/.claude/CLAUDE.md`. Afirme direto o que é; alternativa descartada vira frase própria.

Regras que já custaram caro e não se renegociam:

- Nunca mover, copiar ou apagar nada dentro de `DATASET_DIR`. É a cópia de trabalho do usuário; o dump entra por bind mount read-only.
- Nunca usar `information_schema.table_rows` para sanity check. Use sempre `COUNT(*)`.
- Nunca escrever SQL fora de `src/pyramid/sources/`.
- Escopo é sempre por `project.id`. Não use `name`: `symfony` aparece duas vezes nos 90.
- Reprodutibilidade exata é o critério de aceite. Número que não bate se resolve como bug ou como ambiguidade declarada. Arredondar para ficar perto está proibido.
- 2013 é right-censored (dump acaba em out/2013): **renderiza pirâmide e fica sem quadrante**. Forma é estoque, olha para trás e escapa da censura; stickiness é fluxo e exige Y+1, que o dump não tem. O ESEM14 faz o mesmo com o mesmo corte. Ver docs/replicacao/discrepancias.md, seção 11.1. Não anualizar 9 meses para forçar classificação.
