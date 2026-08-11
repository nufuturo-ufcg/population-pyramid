# pyramid

Ferramenta que gera pirâmides demográficas de população de software. Recebe
eventos de atividade num formato canônico e devolve as pirâmides, as métricas
derivadas delas (CCR, NCR, tipos A-D, magnetismo, stickiness, projeção
coorte-componente) e as figuras.

A origem dos dados entra por adaptador. O motor não sabe de onde vieram os
eventos. O dump MSR14 (GHTorrent) é o adaptador que existe hoje e serve de caso
de aceite, porque reproduz os números publicados por Onoue et al. (ESEM14 e
IEICE16). Qualquer fonte que implemente o contrato roda o mesmo pipeline.

Antes de qualquer coisa neste repo, ler:

- **`CONTRIBUTING.md`**: como trabalhar aqui. É a fonte da verdade e vence sobre qualquer outra doc em caso de conflito.
- **`docs/README.md`**: mapa dos documentos, com a ordem de leitura.
- **`docs/ferramenta/FONTES.md`**: contrato de entrada, o que um adaptador precisa entregar.
- **`docs/replicacao/discrepancias.md`**: log vivo de ambiguidades investigadas. Toda entrada nova cita o comando ou a query exata usada, além do número obtido.

Escrita: o usuário proíbe a estrutura antitética ("é X, não Y" / "não é X, é Y"
e variantes), o travessão e o símbolo `§` em qualquer texto: doc, commit,
comentário, resposta. Regra completa em `CONTRIBUTING.md`, seção "Escrita", e em
`~/.claude/CLAUDE.md`. Afirme direto o que é; alternativa descartada vira frase
própria.

Fronteira que organiza o repo:

- `adapters/<nome>/` guarda tudo que sabe de um dataset: `source.py` e os scripts de preparação.
- `src/pyramid/sources/` guarda o contrato `ActivityDataSource` e o carregador. Nenhum nome de dataset aparece aqui.
- `src/pyramid/` é o motor. Recebe eventos já no formato canônico e não conhece a origem.
- Adaptador novo se implementa sem tocar em `src/pyramid/`. Precisar tocar significa que o contrato está errado; conserta o contrato.

Regras que já custaram caro e não se renegociam:

- Nunca mover, copiar ou apagar nada dentro de `DATASET_DIR`. É a cópia de trabalho do usuário; o dump entra por bind mount read-only.
- Nunca usar `information_schema.table_rows` para sanity check. Use sempre `COUNT(*)`.
- Nunca escrever SQL fora de `adapters/` e de `src/pyramid/sources/`.
- Escopo é sempre por identificador estável do projeto (`project.id` no MSR14). Nome não serve: `symfony` aparece duas vezes nos 90.
- Reprodutibilidade exata é o critério de aceite do caso MSR14. Número que não bate se resolve como bug ou como ambiguidade declarada. Arredondar para ficar perto está proibido.
- 2013 é right-censored no dump MSR14 (acaba em out/2013): **renderiza pirâmide e fica sem quadrante**. Forma é estoque, olha para trás e escapa da censura; stickiness é fluxo e exige Y+1, que o dump não tem. O ESEM14 faz o mesmo com o mesmo corte. Ver `docs/replicacao/discrepancias.md`, seção 11.1. Não anualizar 9 meses para forçar classificação.
