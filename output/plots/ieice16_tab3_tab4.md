# IEICE16 Tabelas 3 e 4 — réplica vs. artigo

Gerado por `pyramid plot --figure abre-table`. Tolerância relativa: 2%.
Cada célula traz `réplica (artigo)`; `≠` marca quem está fora da tolerância.

## Tabela 3 — mediana do ABRE (menor é melhor)

| tipo | projetos | pares | non_coding coorte | non_coding baseline | moved coorte | moved baseline | coding coorte | coding baseline | all coorte | all baseline |
|---|---|---|---|---|---|---|---|---|---|---|
| A | 8 | 72 | 0.5938 (0.4993) ≠ | 0.6667 (0.5000) ≠ | 0.1869 (0.3027) ≠ | 0.2917 (0.5000) ≠ | 0.3333 (0.1865) ≠ | 0.6000 (0.3731) ≠ | 0.4791 (0.2534) ≠ | 0.5000 (0.5000) |
| B | 19 | 168 | 0.6000 (0.5000) ≠ | 0.5000 (0.6332) ≠ | 0.5000 (0.3523) ≠ | 0.5000 (0.5000) | 0.5556 (0.5000) ≠ | 0.6154 (0.5750) ≠ | 0.5000 (0.5000) | 0.5000 (0.5917) ≠ |
| C | 5 | 57 | 0.6723 (0.6711) | 1.0000 (1.0000) | 0.5000 (0.2500) ≠ | 0.5000 (0.7179) ≠ | 0.5000 (0.3684) ≠ | 0.9444 (0.6250) ≠ | 0.3475 (0.2875) ≠ | 0.6607 (0.6667) |
| D | 2 | 36 | 0.4000 (0.3137) ≠ | 0.2980 (0.0000) ≠ | 0.2859 (0.2578) ≠ | 0.6833 (0.2500) ≠ | 0.4813 (0.4988) ≠ | 0.8167 (0.6154) ≠ | 0.3185 (0.3333) ≠ | 0.3299 (0.7500) ≠ |
| All types | 34 | 333 | 0.5664 (0.5000) ≠ | 0.5000 (0.6667) ≠ | 0.4666 (0.3299) ≠ | 0.5000 (0.5000) | 0.5000 (0.4074) ≠ | 0.6771 (0.5417) ≠ | 0.4208 (0.4000) ≠ | 0.5000 (0.6000) ≠ |

## Tabela 4 — Wilcoxon pareado, coorte vs. baseline (95%)

| tipo | non_coding | moved | coding | all |
|---|---|---|---|---|
| A | 0.02065* (0.02748*) | 0.92344 (0.01158*) ≠ | 0.01344* (0.26867) ≠ | 0.82533 (0.00014*) ≠ |
| B | 0.31570 (0.00037*) ≠ | 0.81360 (0.01845*) ≠ | 0.52548 (0.06200) | 0.18935 (0.00001*) ≠ |
| C | 0.12086 (0.05935) | 0.02197* (0.00035*) | 0.14178 (0.16800) | 0.00567* (0.00013*) |
| D | 0.82276 (0.00001*) ≠ | 0.01012* (0.02700*) | 0.03778* (0.02901*) | 0.04277* (0.00000*) |
| All types | 0.32468 (0.00000*) ≠ | 0.05871 (0.00000*) ≠ | 0.01677* (0.00116*) | 0.00729* (0.00000*) |

`*` = significativo a 95%. Em Tab.4 o que se compara é a decisão, não o p exato.

## Curto vs. longo prazo (corte em 1 ano de atividade)

| medida | réplica | artigo |
|---|---|---|
| ABRE mediano, curto prazo | 0.3412 (n=136) | 0.4055 |
| ABRE mediano, longo prazo | 0.5000 (n=197) | 0.3333 |
| p-valor | 0.1192 | 0.046 |

A inversão de curto/longo prazo está analisada em `docs/discrepancias.md` §12.3.

## Resumo

- Tabela 3: **7/40** células dentro de 2%.
- Tabela 4: **11/20** decisões de significância iguais às do artigo.

O veredito formal é do `pyramid validate` — esta tabela é a vista lado a
lado, e usa o mesmo critério de igualdade (`validate._perto`) para não
poder discordar dele.
