# Organização dos arquivos na batuta

Como a home da batuta (`/home/wendell`) é organizada, onde cada coisa nova entra e o que nunca se move. Revisado em 2026-11-13.

## 1. Mapa da home

```
~/
  pyramid/          tudo da pirâmide por linguagem
    repo/             clone do repositório (código)
    rodadas/<nome>/   saída de cada rodada (oficial é a principal)
    exploracao/       scripts, logs e CSV soltos, não oficiais
  chaoss/           grimoirelab, pyramid-transpose-grimoire, community-vitality
  dados-brutos/     coletas por linguagem e a coleta de autores (autores/)
  coleta/           apoio da coleta: divisao3, merge_parte2.sh, recuperar_2b.sh, ho
  backups/          notebook, notebook-w11 (backups pessoais)
  outros/           o que não cabe nos grupos acima (public_html)
  population-pyramid/   pipeline da coleta (fica na home)
  coleta-status-bot/    bot do Slack da coleta (fica na home)
  tmp-etapa2/           temporário da etapa 2 da coleta (fica na home)
  pretrain_azure_doc/   pertence ao root, sem permissão para mover
```

## 2. Onde entra cada coisa nova

- Código da pirâmide: `pyramid/repo/`, sincronizado do Mac.
- Resultado de uma execução: `pyramid/rodadas/<nome>/`, com o nome de uma rodada de `scripts/vitalidade_rodadas.json`.
- Script ou log de investigação, sem fazer parte do repositório: `pyramid/exploracao/`.
- Dado coletado do GitHub: `dados-brutos/<linguagem>/` ou `dados-brutos/autores/<linguagem>/`.
- Ferramenta ou projeto do CHAOSS: `chaoss/`.
- Script de apoio à coleta: `coleta/`.

## 3. Rodadas

- A rodada `oficial` é a que os resultados e o TCC usam.
- As variantes (`sem-mentioned`, `sem-marcacao`, `com-fusao`) não ficam guardadas. Regeram-se por flag: `--set rodada=NOME`.
- As flags de cada rodada estão em `scripts/vitalidade_rodadas.json`. Rodada nova entra nesse arquivo antes de ser executada.
- Cada rodada tem uma pasta: `pyramid/rodadas/<nome>/`. A pasta carrega o cache dos eventos (`<linguagem>/cache`), a origem (`<linguagem>/origem`) e os resultados por população.
- Rodar uma rodada: `uv run python scripts/vitalidade_grade.py --saida ~/pyramid/rodadas/<nome> --populacoes mais_de_uma_ocasiao --set rodada=<nome>`.

## 4. Sincronizar o código do Mac para a batuta

- Mande só os arquivos que o git conhece: `git ls-files -co --exclude-standard` como lista de `rsync --files-from`.
- Nunca mande a pasta inteira. O Mac tem `data/` com 16 GB e um `.env` que não deve subir.
- Não mande `exploracao/`, `graphify-out/`, `.claude/` nem `logs/`.
- O clone na batuta não guarda alteração própria. Código novo nasce no Mac e desce por `rsync`.

## 5. O que nunca se move

- `population-pyramid/`, `coleta-status-bot/` e `tmp-etapa2/`. O bot acha os runs da coleta pelo caminho `coleta-dados/runs/`, e `dados-brutos` tem links para dentro do `population-pyramid`. O `run.sh` da coleta usa `tmp-etapa2`.
- Nada dentro de `dados-brutos/` muda de nome. O `vitalidade_fontes.yaml` aponta para esses caminhos.
- Mover os autores muda o caminho gravado no selo do cache e invalida todos os caches. Mover `dados-brutos/autores/` exige refazê-los.
- Pasta que tem processo rodando (terminal, `opencode`, tmux) com o diretório atual nela. O processo continua, mas o caminho antigo fica errado.

## 6. O que se apaga

- Pacotes `.tar.gz` de resultado antigos. Fica o mais recente.
- Logs de rodada (`grade*.log`, `rodada*.log`).
- Pastas de variante de rodada, que se regeram pela flag.
- Cache com `versao` diferente da atual (`VERSAO_CACHE` em `scripts/vitalidade.py`). O pipeline refaz sozinho.

## 7. Acesso

- O SSH da batuta dá timeout de vez em quando. Comandos idempotentes e repetição resolvem.
- O ping não responde porque o ICMP é bloqueado. A máquina está de pé se o SSH conecta.
- Execuções longas rodam em sessão tmux. O log da rodada fica dentro da pasta dela.
