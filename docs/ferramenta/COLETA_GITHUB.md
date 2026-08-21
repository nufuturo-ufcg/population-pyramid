# Coleta da API do GitHub: o que entregar

Este documento é o contrato de quem coleta. Ele diz quais requisições fazer, o
que gravar e em que layout. Quem escreve adaptador lê `FONTES.md`.

A ferramenta monta pirâmide demográfica por linguagem de programação. A amostra
é o conjunto de repositórios de uma linguagem, e o adaptador `ghapi` transforma
o que está aqui em evento canônico.

Todos os números deste documento foram medidos em `clj-kondo/clj-kondo`
(repo id 176829714, `language: Clojure`, 3097 commits).

## A regra que vale mais que todas

**Entregue o dado cru, do jeito que a API devolveu.**

Não aplique regra de linguagem. Não filtre bot. Não junte, não deduplique, não
explode uma linha em várias. Toda decisão de método mora na ferramenta, em
`config/settings.yaml`, e precisa ser reversível sem coletar de novo.

Coleta que já veio decidida obriga a recoletar quando a decisão muda.

## As oito buscas por repositório

Sete são requisições à API. A oitava é um clone.

| busca | requisição | campos que a ferramenta usa |
|---|---|---|
| `repo` | `GET /repos/{owner}/{repo}` | `id`, `full_name`, `language`, `created_at`, `fork` |
| `languages` | `GET /repos/{owner}/{repo}/languages` | o mapa de linguagem para bytes |
| `commits` | `GET /repos/{owner}/{repo}/commits?per_page=100` | `sha`, `author.id`, `author.login`, `author.type`, `commit.author.date` |
| `issues` | `GET /repos/{owner}/{repo}/issues?state=all&sort=created&direction=asc&per_page=100` | `id`, `number`, `user.id`, `user.login`, `user.type`, `created_at`, a chave `pull_request` |
| `issue_comments` | `GET /repos/{owner}/{repo}/issues/comments?per_page=100` | `id`, `user.id`, `user.login`, `user.type`, `created_at`, `issue_url` |
| `commit_comments` | `GET /repos/{owner}/{repo}/comments?per_page=100` | `id`, `user.id`, `user.login`, `user.type`, `created_at`, `commit_id`, `path` |
| `pull_request_comments` | `GET /repos/{owner}/{repo}/pulls/comments?per_page=100` | `id`, `user.id`, `user.login`, `user.type`, `created_at`, `path`, `commit_id` |
| `commit_files` | clone parcial, ver abaixo | `sha`, data, e-mail do autor, caminhos tocados |

Grave a resposta inteira de cada item, sem podar campo. A lista acima diz o que
a ferramenta lê hoje. Campo que sobra não atrapalha, e campo que falta obriga a
recoletar.

### Três decisões que a medição já resolveu

**`/issues?state=all` entrega issue e pull request na mesma listagem.** O item
que tem a chave `pull_request` é um PR, e o `created_at` dele é a data de
abertura do PR. Isso dispensa a listagem `/pulls` inteira. Não colete `/pulls`.

**`GET /commits` traz `author.id` e não traz a lista de arquivos.** São 100
commits por página, então o clj-kondo custa 31 requisições. É de lá que sai a
identidade estável de quem commitou. O clone entrega os caminhos, e as duas
partes se juntam pelo `sha`.

**Não use `GET /commits/{sha}` para pegar arquivos.** Ele custa uma requisição
por commit. O clj-kondo passaria de 31 para 3097 requisições, e a amostra
inteira estouraria a cota.

### Nenhuma busca percorre issue por issue

`issue_comments`, `commit_comments`, `pull_request_comments` e `issue_events`
têm listagem no nível do repositório. Percorrer issue por issue multiplica o
custo por milhares sem trazer nada a mais.

### Os arquivos de cada commit, pelo clone

```bash
git clone --bare --filter=blob:none https://github.com/{owner}/{repo}.git
git -C {repo}.git log --all --pretty=format:'%H%x09%aI%x09%ae' --name-only
```

`--filter=blob:none` baixa os commits e as árvores e pula o conteúdo dos
arquivos. O `git log --name-only` lê só as árvores, então nenhum conteúdo desce.
O clj-kondo inteiro fica em 3,0 MB e leva segundos.

Isso custa zero de cota. A alternativa pela API custaria 3097 requisições.

## O que gravar, e onde

Um diretório por coleta. O adaptador lê este layout.

```
<GHAPI_DIR>/
  _coleta.json
  repos.jsonl
  languages/<repo_id>.json
  commits/<repo_id>.jsonl
  issues/<repo_id>.jsonl
  issue_comments/<repo_id>.jsonl
  commit_comments/<repo_id>.jsonl
  pull_request_comments/<repo_id>.jsonl
  issue_events/<repo_id>.jsonl
  commit_files/<repo_id>.tsv
```

**JSON Lines**: um objeto JSON por linha, sem vírgula no fim, sem array
envolvendo. As páginas da API são concatenadas, item a item, na ordem em que
vieram.

**`repos.jsonl`**: uma linha por repositório, com a resposta de `GET /repos`.

**`languages/<repo_id>.json`**: a resposta de `GET /languages`, um objeto só.

**`commit_files/<repo_id>.tsv`**: uma linha por par (commit, arquivo), com
cabeçalho, separado por tabulação.

```
sha	author_date	author_email	path
a1b2c3	2019-04-02T10:11:00-03:00	ana@x.com	src/main/clj/parser.clj
a1b2c3	2019-04-02T10:11:00-03:00	ana@x.com	README.md
```

Commit de merge não lista arquivo no `git log --name-only`. Ele aparece no
`commits/<repo_id>.jsonl` e não aparece aqui. Isso é esperado.

**`_coleta.json`**: o que descreve a coleta.

```json
{
  "coletado_em": "2026-08-21T14:03:00Z",
  "corte": "2026-08-20T00:00:00Z",
  "criterio": "linguagem primária Clojure, mais de 50 estrelas, sem fork",
  "repos": [176829714, 203157123],
  "contagens": {
    "176829714": {"commits": 3097, "issues": 2951, "issue_comments": 8412}
  }
}
```

`corte` é a data limite da coleta. Sem ela, duas execuções em semanas
diferentes não são comparáveis, e a ferramenta não tem como declarar isso.

## Regras de coleta

**Cota.** 5000 requisições por hora por token autenticado, 60 sem token. No
máximo 100 requisições concorrentes, e cerca de 900 pontos por minuto no mesmo
endpoint. Respeite `Retry-After` e o cabeçalho `x-ratelimit-remaining`, com
espera crescente.

**Aceite mais de um token.** A rotação entre tokens multiplica a cota por hora.
Mantenha a lógica fora do laço de paginação, para dar para paralelizar depois.

**Retomada.** Grave um ponto de parada por par (repositório, busca), com a
última página ou o último cursor. Script que morre no meio recomeça de onde
parou. Recomeçar do zero em amostra grande custa horas.

**`ETag` torna a recoleta quase grátis.** Guarde o `ETag` de cada página e mande
`If-None-Match` na próxima vez. Resposta `304` não consome cota.

**Backfill histórico pagina por criação, não por atualização.** O parâmetro
`since` das issues e dos comentários filtra por `updated_at`, que muda quando
alguém comenta em coisa velha. Para varrer o histórico inteiro use
`sort=created&direction=asc` e caminhe pelas páginas. Para commits, use janelas
de `since` e `until`.

**Log por busca.** Número de requisições, sucessos, erros por código HTTP,
itens obtidos, e quanto de cota sobrou. É isso que diz se a coleta ficou
completa ou se parou no meio.

## O que a medição encontrou, e você vai ver também

**Metade dos comentários de commit não aponta arquivo.** No clj-kondo,
`commit_comments.path` veio `null` em 15 de 30 itens, porque comentário no
commit inteiro não aponta linha nenhuma. Grave o `null`. A ferramenta decide o
destino.

**Comentário de review sempre aponta arquivo.** `pull_request_comments.path`
veio preenchido em 100 de 100: 91 `.clj`, 4 `.md`, 2 `.edn`, 2 `.gitignore`,
1 `.yaml`.

**Metade dos commits não toca código.** No clj-kondo, 2032 dos 3097 commits
tocam arquivo de código e 1065 tocam só prosa, configuração ou nada. Isso é
normal e a ferramenta trata.

**Bot existe e não é filtrado aqui.** `dependabot[bot]` e companhia aparecem com
`user.type == "Bot"` e sufixo `[bot]` no login. Grave como veio, com o `type`. A
ferramenta filtra e declara que filtrou.

**Commit sem conta do GitHub.** `author` vem `null` quando o e-mail do commit
não casa com nenhuma conta. Grave o `null`.

**O mapa de `/languages` exclui prosa e dados.** Markdown, YAML, edn e SVG não
aparecem nele. O mapa do clj-kondo é Clojure 2107009 bytes, Shell 19405, Java
1327, Batchfile 1193, Dockerfile 807, Emacs Lisp 62. Esse mapa é o que a
ferramenta usa para decidir o que conta como linguagem de programação naquele
repositório.

## Amostras verificadas

Respostas reais de `clj-kondo/clj-kondo`, com os campos que importam.

```
repo         id=176829714 full_name="clj-kondo/clj-kondo" language="Clojure" fork=false
             created_at="2019-03-20T22:58:13Z"
languages    {"Clojure":2107009,"Shell":19405,"Java":1327,"Batchfile":1193,
              "Dockerfile":807,"Emacs Lisp":62}
commits      sha="d92d1550..." commit.author.date="2026-08-20T18:19:33Z"
             author={"id":5185341,"login":"willcohen","type":"User"}
issues (PR)  id=5205777150 number=2951 user.id=284934 user.type="User"
             created_at="2026-08-20T16:42:41Z" pull_request.url=".../pulls/2951"
issue_cmt    id=476159301 user.id=284934 created_at="2019-03-25T11:37:15Z"
             issue_url=".../issues/11"
commit_cmt   id=35413719 user.id=284934 created_at="2019-10-08T18:54:00Z"
             commit_id="803876c6..." path=null
pr_review    id=283154803 user.id=1738897 created_at="2019-05-12T21:10:02Z"
             path="deps.edn" commit_id="4f227b97..."
issue_event  id=29761313637 actor.id=284934 actor.type="User" event="closed"
             created_at="2026-08-20T18:19:34Z"
```

## Antes de entregar

Confira, por repositório:

1. Os oito arquivos existem e nenhum está vazio sem motivo.
2. `repos.jsonl` tem uma linha por repositório da lista, e o `id` bate com o
   nome do arquivo das outras buscas.
3. A contagem de linhas de cada `.jsonl` bate com o que está em
   `_coleta.json`.
4. A última página de cada busca foi mesmo alcançada. Coleta que parou no meio
   por cota estourada some com os eventos mais antigos e envelhece a pirâmide
   inteira sem avisar.
5. `_coleta.json` tem `corte` preenchido.

O `adapters/ghapi/prepare_dataset.sh` roda essas conferências e falha com
mensagem. Rode `make check ADAPTER=ghapi` antes de considerar a coleta pronta.
