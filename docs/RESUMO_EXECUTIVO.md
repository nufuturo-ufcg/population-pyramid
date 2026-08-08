# Estado do projeto — 2026-08-06

Replicação independente dos dois artigos de Onoue et al. (ESEM'14 e IEICE'16), que descrevem a
população de um projeto de software como uma pirâmide etária de contribuidores. O pipeline inteiro
roda ponta a ponta sobre o dump MSR'14; o que falta é fechar (ou declarar encerrados) os pontos em
que a réplica não chega no mesmo número que o artigo.

## Pipeline
extract → classify → snapshots → metrics → attractiveness → projection → validate → plots
[✅ ✅ ✅ ✅ ✅ ✅ ✅ ✅]

## Batendo com os artigos
- Os 8 projetos que o IEICE'16 cita pelo nome caem no tipo certo — 8 de 8.
- A figura de 2011 do ESEM'14 reproduz 4 dos 5 projetos; o quinto está aberto abaixo.
- A tabela do MSR'14 bate em 48 das 55 células (87%), e as 7 que falham caem todas em cima da
  linha da mediana, onde um contribuidor a mais ou a menos vira a decisão.
- O achado central do artigo sobre projeção se sustenta: prever por faixa etária erra menos que a
  previsão ingênua, com significância estatística.
- A validação automática compara 167 pontos contra os artigos e não deixa nenhuma divergência
  sem explicação registrada.
- A atividade quase nula do blueprint-css em 2012–2013 era suspeita de bug e é o dado real: seis
  trimestres batem commit a commit com a API do GitHub, que não registra nenhum commit no projeto
  depois de meados de 2011 (§17). Projeto morto, retratado como morto.
- A comparação visual corrigiu o que a conferência numérica não pegava: a pirâmide é um retrato de
  **estoque**, e as figuras estavam filtrando só quem estava ativo. Isso achatava o homebrew (a
  barra de ~750 do artigo saía 73; com estoque sai 734) e esvaziava o blueprint-css. Corrigido, os
  quatro painéis de 2011 batem em forma com o ESEM'14, e as métricas não se moveram (§18).

## Não batendo (aberto, com motivo em 1 linha)
- Distribuição dos tipos A–D: classifico 85 projetos, o artigo classifica 86, e sobra projeto no
  tipo A às custas do C — o resíduo vive nos projetos de 1 a 3 contribuidores, não no método.
- O projeto jekyll em 2011 sai como "flutuante" e o artigo diz "terminal" — é o 5º caso da figura
  de 2011, e as hipóteses testadas até agora foram todas descartadas.
- A projeção parte de 34 projetos elegíveis, o artigo diz 36 — dois projetos ficam em cima do
  corte de 100 contribuidores, e mexer no corte para chegar em 36 seria ajustar método a resultado.
- Dentro da projeção, a categoria "non-coding" anda para o lado oposto ao do artigo — é a única
  das quatro que inverte, e sem significância estatística.
- Ainda na projeção, curto e longo prazo aparecem na ordem trocada — a suspeita é cauda longa rala
  demais (poucas pessoas por faixa acima de ~4 anos), o que deixa o resultado dominado por ruído.
- ver docs/discrepancias.md para o detalhe técnico de qualquer item aqui

## Próximo passo
- A comparação visual das 8 figuras contra as originais está **feita**. Cada figura tem seu
  documento em `docs/figuras/`, dizendo o que saiu igual, o que saiu diferente e por quê. Rendeu
  duas correções reais (§18 e §31) e a trava do painel do blueprint-css, hoje idêntico ao artigo.
- O resíduo do homebrew na Fig.2 do ESEM'14 está **encerrado como divergência declarada**: são 129
  pessoas que classificamos como código e o artigo classifica como discussão, mais 71 pessoas de
  população excedente. Oito hipóteses testadas e refutadas (§33, §34, §36); nenhuma em aberto.
- A grade da Tabela 2 do MSR'14 ganhou a rodada extra de validação (§35): sete hipóteses testadas
  (quatro definições de novato, limiar, desempate, escopo de stickiness). Nenhuma melhora as 48/55
  células; três parâmetros que eram herdados passam a ser **medidos**. Das 7 células que falham,
  3 estão explicadas (2 empates exatos + 1 lacuna de dados no `scala/scala` em 2010) e 4 exigiriam
  correções contraditórias entre si — resíduo aceito e documentado.
- `commit_scope` foi varrido nos três escopos possíveis (§36): `root` vence nos quatro painéis e é
  o único que preserva a trava do blueprint-css. Fica como escolha medida; item encerrado.
- Rodar o caminho de instalação do zero em máquina limpa, que nunca foi testado de fato — **é o
  único item em aberto da lista**.
