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
- Novatos por trimestre, `transicao_trimestral.csv` de cada linguagem (coluna `nascimentos`): Clojure fica entre 284 e 342 de 2019T1 a 2020T4 e sobe para 353 a 422 de 2021T1 a 2022T4. Elixir e OCaml ficam estáveis ou caem no mesmo período.
- Novatos por ano, índice com 2019 = 100 (`trajetoria.csv`): Clojure 119 em 2021 e 126 em 2022. Elixir 95 e 89. OCaml 90 e 83. Python 122 e 120.
- A subida existe e é só de Clojure entre as de nicho. Causa não testada: pode ser contratação do próprio Nubank, assunto na comunidade ou outra coisa. Teste proposto: a parcela de novatos com primeiro evento em repositórios `nubank/*`.

### 6.2 Programadores experientes adotam Clojure mais que iniciantes?

- Os dados medem o tempo na linguagem. A experiência anterior em programação não está nos dados.
- Proxies possíveis: idade da conta do GitHub no primeiro evento em Clojure (exige coletar `created_at` de cada login pela API) e atividade anterior nas outras quatro linguagens coletadas (login presente nos dados de Elixir, OCaml, Zig ou Python com evento antes do primeiro em Clojure).
- Comparar com os novatos de Elixir e Python, que servem de controle.

### 6.3 ClojureScript entra?

- Sim. Ver seção 3.
