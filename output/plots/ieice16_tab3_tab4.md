# IEICE16 Tabelas 3 e 4: replicação vs. artigo

Gerado por `pyramid plot --figure abre-table`. Tolerância relativa: 2%.
Cada célula traz `replicação (artigo)`; `≠` marca quem está fora da tolerância.

## Tabela 3: mediana do ABRE (menor é melhor)

| tipo | projetos | pares | non_coding coorte | non_coding baseline | moved coorte | moved baseline | coding coorte | coding baseline | all coorte | all baseline |
|---|---|---|---|---|---|---|---|---|---|---|
| A | 8 | 71 | 1.0000 (0.4993) ≠ | 0.5714 (0.5000) ≠ | 0.2645 (0.3027) ≠ | 0.3077 (0.5000) ≠ | 0.2500 (0.1865) ≠ | 0.9667 (0.3731) ≠ | 0.3333 (0.2534) ≠ | 0.5000 (0.5000) |
| B | 19 | 170 | 0.5804 (0.5000) ≠ | 0.5000 (0.6332) ≠ | 0.5000 (0.3523) ≠ | 0.5000 (0.5000) | 0.5794 (0.5000) ≠ | 0.5000 (0.5750) ≠ | 0.5000 (0.5000) | 0.5046 (0.5917) ≠ |
| C | 5 | 56 | 0.5492 (0.6711) ≠ | 1.0000 (1.0000) | 0.5000 (0.2500) ≠ | 0.7500 (0.7179) ≠ | 0.5188 (0.3684) ≠ | 0.5500 (0.6250) ≠ | 0.2857 (0.2875) | 0.5000 (0.6667) ≠ |
| D | 2 | 38 | 0.4280 (0.3137) ≠ | 0.2857 (0.0000) ≠ | 0.3333 (0.2578) ≠ | 0.5000 (0.2500) ≠ | 0.6154 (0.4988) ≠ | 0.8750 (0.6154) ≠ | 0.2980 (0.3333) ≠ | 0.3571 (0.7500) ≠ |
| All types | 34 | 335 | 0.5804 (0.5000) ≠ | 0.5000 (0.6667) ≠ | 0.4411 (0.3299) ≠ | 0.5000 (0.5000) | 0.5000 (0.4074) ≠ | 0.6154 (0.5417) ≠ | 0.3894 (0.4000) ≠ | 0.5000 (0.6000) ≠ |

## Tabela 4: Wilcoxon pareado, coorte vs. baseline (95%)

| tipo | non_coding | moved | coding | all |
|---|---|---|---|---|
| A | 0.00138* (0.02748*) | 0.75086 (0.01158*) ≠ | 0.00031* (0.26867) ≠ | 0.17219 (0.00014*) ≠ |
| B | 0.12530 (0.00037*) ≠ | 0.61058 (0.01845*) ≠ | 0.23309 (0.06200) | 0.26300 (0.00001*) ≠ |
| C | 0.02165* (0.05935) ≠ | 0.01053* (0.00035*) | 0.75134 (0.16800) | 0.08349 (0.00013*) ≠ |
| D | 0.79384 (0.00001*) ≠ | 0.09180 (0.02700*) ≠ | 0.10989 (0.02901*) ≠ | 0.22171 (0.00000*) ≠ |
| All types | 0.11451 (0.00000*) ≠ | 0.03333* (0.00000*) | 0.03450* (0.00116*) | 0.01243* (0.00000*) |

`*` = significativo a 95%. Em Tab.4 compara-se a decisão; o p exato fica de fora.

## Curto vs. longo prazo (corte em 1 ano de atividade)

| medida | replicação | artigo |
|---|---|---|
| ABRE mediano, curto prazo | 0.3363 (n=135) | 0.4055 |
| ABRE mediano, longo prazo | 0.4816 (n=200) | 0.3333 |
| p-valor | 0.1768 | 0.046 |

A inversão de curto/longo prazo está analisada em `docs/discrepancias.md`, seção 12.3.

## Resumo

- Tabela 3: **6/40** células dentro de 2%.
- Tabela 4: **7/20** decisões de significância iguais às do artigo.

O veredito formal é do `pyramid validate`. Esta tabela é a vista lado a
lado, e usa o mesmo critério de igualdade (`validate._perto`) para não
poder discordar dele.
