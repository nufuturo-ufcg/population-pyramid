# MSR14 Tabela 2: a grade de quadrantes da replicação

Gerado por `pyramid plot --figure quadrant-table`.

Mesmo formato da Tabela 2 do artigo, com os mesmos 12 projetos e os mesmos
anos, para comparar célula a célula. `-` é ano sem atividade no projeto e
`*` é ano ativo com 10 desenvolvedores ou menos, que o artigo deixa fora do
filtro. Onde a replicação discorda do artigo, a célula traz o valor do
artigo entre parênteses.

| quadrante em 2011 | projeto | 2004 | 2005 | 2006 | 2007 | 2008 | 2009 | 2010 |
|---|---|---|---|---|---|---|---|---|
| Attractive | `rails/rails` | * | Terminal | Stagnant | Stagnant | Fluctuating | Fluctuating | Attractive |
| Attractive | `xbmc/xbmc` | - | Stagnant | Attractive | **Fluctuating** (Attractive) | Stagnant | **Stagnant** (Attractive) | Terminal |
| Attractive | `django/django` | - | * | * | Stagnant | Stagnant | Stagnant | Stagnant |
| Fluctuating | `jquery/jquery` | - | - | Fluctuating | Terminal | * | Attractive | **Attractive** (Fluctuating) |
| Fluctuating | `thoughtbot/paperclip` | - | - | - | * | Fluctuating | Terminal | Fluctuating |
| Fluctuating | `chriseppstein/compass` | - | - | - | - | * | Fluctuating | **Terminal** (Fluctuating) |
| Stagnant | `scala/scala` | Terminal | Terminal | * | * | Attractive | Terminal | **-** (Fluctuating) |
| Stagnant | `memcached/memcached` | * | * | Terminal | Fluctuating | Stagnant | Terminal | * |
| Stagnant | `clojure/clojure` | - | - | * | * | * | Attractive | Attractive |
| Terminal | `django-debug-toolbar/django-debug-toolbar` | - | - | - | - | Terminal | Terminal | Terminal |
| Terminal | `mojombo/jekyll` | - | - | - | - | Fluctuating | Fluctuating | Terminal |
| Terminal | `joshuaclayton/blueprint-css` | - | - | - | * | * | Terminal | * |

Células com quadrante iguais às do artigo: **38/43**. Células de
estrutura (`-` e `*`): **41/41**. As divergentes estão em
negrito, com o valor do artigo ao lado, e cada uma tem causa no
`docs/replicacao/RESUMO_EXECUTIVO.md`, seção 3.

O total aqui é menor que os 55 da seção 3 porque a coluna de 2011 virou a
primeira coluna, como no artigo, e não se repete.

O veredito formal continua sendo o do `pyramid validate`: esta tabela é a
vista lado a lado, não um segundo juiz.
