# Estado do projeto — 2026-08-08

Replicação independente dos dois artigos de Onoue et al. (ESEM'14 e IEICE'16), que descrevem a
população de um projeto de software como uma pirâmide etária de contribuidores. Pipeline completo
(extract → classify → snapshots → metrics → attractiveness → projection → validate → plots), rodando
do zero em máquina limpa, com `validation_report.md` idêntico ao de referência.

## O que confirmamos
- **O achado central do IEICE'16 se sustenta**: prever crescimento por faixa etária erra menos que a
  previsão ingênua, com significância estatística.
- Os 8 projetos que o IEICE'16 cita pelo nome caem no tipo certo (8 de 8).
- A figura de 2011 do ESEM'14 reproduz 4 dos 5 projetos em forma; a tabela do MSR'14 bate em 48 das
  55 células (87%), e as 7 que falham caem em cima da linha da mediana.
- Comparação visual das 8 figuras contra as originais: feita, uma a uma (`docs/figuras/`).

## O que concluímos diferente do artigo
1. **A vantagem da previsão por faixa é do agregado, não de cada categoria.** O artigo reporta
   significância em quase todos os recortes (faixa × tipo de contribuição); na réplica isso aparece
   em 2 de 14. O sinal existe, mas é mais fraco do que o artigo faz parecer.
2. **A categoria "non-coding" inverte de direção** — é a única das quatro que anda para o lado
   oposto, e sem significância.
3. **Curto e longo prazo saem na ordem trocada**, e sem significância (artigo: sim). Suspeita: a
   cauda longa é rala demais e o resultado fica dominado por ruído.

Nenhuma das três derruba o achado principal; as três enfraquecem generalizações secundárias.

## Divergências numéricas declaradas (com hipóteses testadas e refutadas)
- Distribuição dos tipos A–D: 85 projetos vs. 86 do artigo (resíduo em projetos de 1–3 pessoas).
- `jekyll` 2011 sai "flutuante", o artigo diz "terminal".
- Projeção parte de 34 projetos elegíveis, o artigo diz 36 (dois em cima do corte de 100).
- Resíduo do homebrew na Fig. 2 do ESEM'14: 129 pessoas que classificamos como código e o artigo
  como discussão, mais 71 de população excedente.

Nada em aberto na lista de execução. Detalhe técnico de qualquer item: `docs/discrepancias.md`.
