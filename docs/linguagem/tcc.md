# Notas para o TCC

Material para a escrita do trabalho de conclusão. Os números saem dos documentos gerados em
`~/Documents/pyramid-vitalidade/` (`AMOSTRA.md`, `METRICAS_POR_RQ.md`, `RELATORIO.md`), que o
script refaz a partir dos CSV. Este arquivo diz o que escrever e onde está cada número.

## 1. Referências, em ordem de prioridade

1. Onoue et al., ESEM 2014 e IEICE 2016 (https://doi.org/10.1587/transinf.2015EDP7363). Pirâmides de software, CCR e NCR, tipos A a D, projeção por cenários (ingênuo, coorte, erro ABRE, Wilcoxon). Base do método.
2. IBGE, Tábua Completa de Mortalidade 2023. Tábua de vida: chance de seguir mais 1 ano, fração que chega a x, anos que ainda restam.
3. IBGE, pirâmide etária e índice de envelhecimento (série CD95). Composição por tempo na linguagem.
4. IBGE, metodologia das projeções 1980-2050, e PRB Population Handbook 2011. Equação compensadora: natalidade, mortalidade e crescimento natural.
5. Hannemann e Klamma, OSS 2013 (https://doi.org/10.1007/978-3-642-38928-3_6). Demografia em comunidades de código aberto.
6. Foucault et al., ESEC/FSE 2015 (https://doi.org/10.1145/2786805.2786870). Quem entra e quem sai de um projeto.
7. Ahmad et al., OMS 2001. Padronização por idade: taxa padronizada e SMR.
8. Constantinou e Mens, 2017 (https://doi.org/10.1007/s11334-017-0303-4). Kaplan-Meier e log-rank entre ecossistemas.
9. PRB, variantes de projeção da ONU, e Ipea (Bonifácio e Guimarães, Texto para Discussão 2698, 2021). Cenários pessimista, conservador e otimista.
10. Yamashita et al., MSR 2014 (https://doi.org/10.1145/2597073.2597116), e Ferreira, Silva e Valente, SBES 2020 (https://doi.org/10.1145/3422392.3422433). Magnetismo e stickiness, fora da execução padrão.
11. Avelino et al., ESEM 2019. Limite de 12 meses sem contribuir para a saída.
12. Falta citar: Wilson, 1927, Journal of the American Statistical Association. Margem de erro da tábua de vida.

## 2. Critérios de inclusão e exclusão

Números e tabela por filtro: `AMOSTRA.md`, seção Critérios de inclusão e exclusão.

- Repositório entra com 10 estrelas ou mais, listado pela SEART.
- Repositório sai com 50% ou menos do código na linguagem (coluna `languages` da SEART).
- Os outros filtros da busca na SEART (forks, data de criação) não estão registrados. Recuperar antes de escrever.
- Commit entra com autor e tocando pelo menos um arquivo com extensão da linguagem.
- Issue, PR e comentário entram com login e no repositório da linguagem.
- Saem: commit copiado de repositório mais antigo, evento anterior ao primeiro commit da linguagem no repositório, conta apagada (`ghost`), bot (`[bot]`), data ilegível, futura ou anterior a 2008.
- População `passou_30_dias`: o último evento cai pelo menos 30 dias depois do primeiro.

## 3. Extensões

Definidas à mão em `scripts/figuras_linguagem_bruta.py` (`LINGUAGENS`) e `scripts/carga_fonte.py` (OCaml). A tabela está em `AMOSTRA.md`.

- Nenhuma fonte externa sustenta a lista. Comparar com a do github-linguist antes de escrever.
- `.edn` conta como Clojure. É arquivo de dados, e o linguist o trata como linguagem própria.
- `.ipynb` fica fora de Python.
- ClojureScript entra: `.cljs` e `.cljc` estão na lista, e o GitHub classifica repositório de ClojureScript como Clojure. O estudo não separa os dois.

## 4. Recorte de tempo

Detalhe em `AMOSTRA.md`, seção Recorte de tempo.

- Estudo de 01/01/2008 a 31/12/2025.
- Eventos de 2026, até o fim da coleta de cada linguagem, só decidem quem saiu, quem pausou e quem pertence à população.
- Saída: última contribuição seguida de 12 meses sem nada. A saída de 2025 só se confirma em 2026, e a coleta termina entre setembro e outubro de 2026.
- Tudo que depende de saída vai até 2024. O que conta só quem estava ativo pode ir até 2025.

## 5. Limites da amostra

Lista em `AMOSTRA.md`, seção O que a amostra pode estar perdendo.

- Identidade: no commit a pessoa é o nome do autor, na API é o login. Medida e comando em `vitalidade.md`, seção Identidade das pessoas. Efeito nas métricas ainda não medido.
- Repositórios com menos de 10 estrelas, poliglotas (50% ou menos na linguagem), apagados ou privados ficam de fora.
- Atividade fora do GitHub não entra.
- Bots sem `[bot]` continuam contando.

## 6. Perguntas do gestor do Nubank (2026-10-20)

### 6.1 A compra da Cognitect atraiu gente para Clojure?

- O Nubank comprou a Cognitect, empresa que cuidava de Clojure, em julho de 2020.
- Novatos por trimestre, `transicao_trimestral.csv` (coluna `nascimentos`): Clojure fica entre 284 e 342 de 2019T1 a 2020T4 e sobe para 339 a 422 de 2021T1 a 2022T4. Elixir e OCaml ficam estáveis ou caem.
- Comparando 8 trimestres antes e 8 depois de cada trimestre possível, a maior diferença entre Clojure e a média de Elixir e OCaml cai em 2020T3, o trimestre da compra (+33 pontos).
- Comparação sem excluir repositório, com as regras oficiais da carga (`scripts/origem_dos_novatos.py`, que grava o repositório e o tipo do primeiro evento de cada pessoa). A contagem de novatos bate com a coluna `nascimentos` (Clojure 2021: 396, 356, 362, 353).
- Mudança da média dos 8 trimestres depois de 2020T3 sobre a dos 8 antes (`compra_mudanca_por_corte.csv`):

| Medida | Clojure | Elixir | OCaml | Zig |
|---|---|---|---|---|
| Novatos | +15,8% | -13,1% | -21,0% | +118,5% |
| Novatos que chegaram com commit ou PR | -21,2% | -18,4% | -14,4% | +177,9% |
| Novatos que fizeram commit ou PR alguma vez | -18,0% | -20,3% | -16,9% | +134,6% |
| Repositórios que receberam algum novato | -19,2% | -15,4% | -12,6% | +262,6% |

- Só a contagem total separa Clojure das outras. Com as outras três medidas, Clojure acompanha Elixir e OCaml.
- Zig fica fora da leitura: a linguagem nasceu em 2016 e cresce em qualquer corte.
- Parte dos novatos do ano que chegou pelo repositório que mais recebeu: Elixir e OCaml ficam entre 3% e 8% em todos os anos. Clojure fica entre 4% e 7% até 2020 e vai a 25% em 2021, 40% em 2022 e 36% em 2023, sempre em `logseq/logseq`.
- Medida de popularidade, nos próprios dados: pessoas distintas por trimestre no repositório (`repos_por_trimestre.parquet`). Logseq foi criado em maio de 2020, tinha 1 pessoa em 2020T2, 110 em 2020T3 e 774 em 2022T2. Em 2021 e 2022 Logseq somou 4.311 pessoas-trimestre, Penpot 805 e Athens 530, os três primeiros de Clojure. O quarto (`mtgred/netrunner`) teve 504.
- Dos 1.818 novatos que chegaram por Logseq, 1.634 chegaram por issue ou comentário e 235 fizeram commit ou PR alguma vez.
- Conclusão para escrever: os dados não mostram mais programadores chegando a Clojure depois da compra. A subida da contagem vem de um repositório só, criado dois meses antes da compra, com usuários abrindo issues. Os novatos que codaram caem no mesmo ritmo de Elixir e OCaml.
- Repositórios `nubank/*` explicam 0 a 7 novatos por trimestre. O trabalho do Nubank em Clojure fica quase todo em repositórios privados, fora dos dados.
- Efeito no resto do estudo: "novato" inclui quem só abriu issue. Isso pesa na natalidade e no crescimento natural de Clojure de 2021 a 2023.
- Python entra na comparação quando a carga com origem terminar na batuta.
- Como reproduzir (na batuta):

```
uv run python scripts/origem_dos_novatos.py --saida ~/pyramid-vitalidade-saida \
    --linguagens clojure elixir ocaml zig python
```

- Figuras em `~/Documents/pyramid-vitalidade/geral-passou_30_dias/vitalidade/`:

![Novatos por ano](../../../pyramid-vitalidade/geral-passou_30_dias/vitalidade/compra_novatos.png)
![Novatos que chegaram codando](../../../pyramid-vitalidade/geral-passou_30_dias/vitalidade/compra_novatos_codando.png)
![Parte dos novatos que chegou por um repositório](../../../pyramid-vitalidade/geral-passou_30_dias/vitalidade/compra_maior_repositorio.png)

### 6.2 Programadores experientes adotam Clojure mais que iniciantes?

- Os dados medem o tempo na linguagem. A experiência anterior em programação não está nos dados.
- Proxies possíveis: idade da conta do GitHub no primeiro evento em Clojure (exige coletar `created_at` de cada login pela API) e atividade anterior nas outras quatro linguagens coletadas (login presente nos dados de Elixir, OCaml, Zig ou Python com evento antes do primeiro em Clojure).
- Comparar com os novatos de Elixir e Python, que servem de controle.

### 6.3 ClojureScript entra?

- Sim. Ver seção 3.
