"""Coleta e completa o dado de entrada do adaptador `ghapi`.

Dois modos. O primeiro baixa uma amostra do zero, para o adaptador ter dado real
contra o qual rodar. O segundo completa uma coleta feita por outra pessoa.

    # amostra de desenvolvimento, tudo do zero
    GHAPI_DIR=data/ghapi .venv/bin/python adapters/ghapi/coleta.py \
        clj-kondo/clj-kondo borkdude/edamame weavejester/medley

    # coleta que chegou pronta: só o que falta nela
    GHAPI_DIR=/caminho/da/coleta .venv/bin/python adapters/ghapi/coleta.py --completar

O formato é o JSON cru da API, um arquivo por busca, com os itens de todos os
repositórios concatenados na mesma lista. Cada item carrega o campo `url`, no
formato `https://api.github.com/repos/{owner}/{repo}/...`, e é dele que sai a
qual repositório o evento pertence. Nome de arquivo e ordem não entram na conta,
e é isso que o modo `--completar` usa para descobrir quais repositórios a coleta
contém sem precisar de lista.

Três coisas a coleta de eventos não produz, e as três são baratas:

- `GET /repos` dá o rótulo e a data de criação.
- `GET /repos/{owner}/{repo}/languages` dá o mapa de bytes por linguagem, que é
  o que decide a linguagem de cada caminho de arquivo.
- O clone parcial dá os caminhos de arquivo de cada commit. A API só entrega
  isso a uma requisição por commit, o que estoura qualquer cota.

As duas requisições custam duas por repositório, e o clone não custa cota
nenhuma.

Autenticação e paginação saem do `gh`.

ponytail: sem retomada e sem ETag. Script que morre no meio recomeça do zero.
Para amostra pequena isso custa minutos, e o modo `--completar` pula o que já
está no disco, que é retomada suficiente para dezenas de repositórios. Coleta
grande de evento é outro programa, feito por outra pessoa.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

# As seis requisições paginadas que produzem evento.
#
# `issues` traz issue e pull request na mesma listagem, separados pela chave
# `pull_request` de cada item. Por isso `/pulls` não aparece aqui.
#
# `sort=created&direction=asc` em vez de `since`: o `since` filtra por
# `updated_at`, que muda quando alguém comenta em coisa velha, e o backfill
# perderia item. A ordem por criação é estável para varredura histórica.
BUSCAS: dict[str, str] = {
    "commits": "repos/{repo}/commits?per_page=100",
    "issues": "repos/{repo}/issues?state=all&sort=created&direction=asc&per_page=100",
    "issue_comments": "repos/{repo}/issues/comments?sort=created&direction=asc&per_page=100",
    "commit_comments": "repos/{repo}/comments?per_page=100",
    "pull_request_comments": "repos/{repo}/pulls/comments?sort=created&direction=asc&per_page=100",
    "issue_events": "repos/{repo}/issues/events?per_page=100",
}

CABECALHO_TSV = "repo\tsha\tauthor_date\tauthor_email\tpath"


def _gh(endpoint: str, *, paginado: bool) -> str:
    """Chama `gh api` e devolve a saída crua.

    `--paginate` percorre o cabeçalho `Link` até a última página. `--slurp`
    junta as páginas num array só, o que evita costurar JSON à mão.
    """
    cmd = ["gh", "api", endpoint]
    if paginado:
        cmd += ["--paginate", "--slurp"]
    r = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if r.returncode != 0:
        raise RuntimeError(f"gh api {endpoint} falhou: {r.stderr.strip()}")
    return r.stdout


def _acrescenta(destino: Path, itens: list[dict]) -> int:
    """Acrescenta um objeto JSON por linha e devolve quantos foram."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("a", encoding="utf-8") as f:
        for item in itens:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    return len(itens)


def _achata(paginas: list) -> list[dict]:
    """`--slurp` devolve lista de páginas. A saída é a lista de itens."""
    itens: list[dict] = []
    for pagina in paginas:
        if isinstance(pagina, list):
            itens.extend(pagina)
        else:  # endpoint de item único devolvido dentro do slurp
            itens.append(pagina)
    return itens


def _clone_e_arquivos(repo: str, raiz: Path, scratch: Path) -> int:
    """Clone parcial e as linhas (repo, sha, data, e-mail, caminho).

    `--filter=blob:none` baixa commits e árvores e pula o conteúdo dos arquivos.
    `git log --name-only` lê só as árvores, então nenhum blob é buscado depois.

    Commit de merge não lista arquivo neste formato. Ele aparece em
    `commits.jsonl` e some daqui, e o adaptador trata como commit sem caminho.
    """
    espelho = scratch / (repo.replace("/", "__") + ".git")
    if espelho.exists():
        shutil.rmtree(espelho)
    subprocess.run(
        [
            "git",
            "clone",
            "--bare",
            "--filter=blob:none",
            f"https://github.com/{repo}.git",
            str(espelho),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    log = subprocess.run(
        [
            "git",
            "-C",
            str(espelho),
            "log",
            "--all",
            "--pretty=format:C\t%H\t%aI\t%ae",
            "--name-only",
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout

    destino = raiz / "commit_files.tsv"
    if not destino.exists():
        destino.write_text(CABECALHO_TSV + "\n", encoding="utf-8")
    linhas = 0
    cabeca: tuple[str, str, str] | None = None
    with destino.open("a", encoding="utf-8") as f:
        for linha in log.split("\n"):
            if linha.startswith("C\t"):
                _, sha, data, email = linha.split("\t")
                cabeca = (sha, data, email)
            elif linha.strip() and cabeca is not None:
                sha, data, email = cabeca
                f.write(f"{repo}\t{sha}\t{data}\t{email}\t{linha.strip()}\n")
                linhas += 1
    shutil.rmtree(espelho)
    return linhas


def coleta_repo(repo: str, raiz: Path, scratch: Path) -> tuple[dict, dict[str, int]]:
    """Baixa um repositório. Devolve o `GET /repos` e as contagens."""
    meta = json.loads(_gh(f"repos/{repo}", paginado=False))
    print(f"  {repo:28} id={meta['id']} language={meta['language']}", flush=True)

    # O `GET /languages` devolve um objeto pelado, sem dizer de qual repositório
    # veio. Concatenar sem embrulhar perderia essa ligação.
    _acrescenta(
        raiz / "languages.jsonl",
        [
            {
                "repo_id": int(meta["id"]),
                "full_name": meta["full_name"],
                "languages": json.loads(_gh(f"repos/{repo}/languages", paginado=False)),
            }
        ],
    )

    contagens: dict[str, int] = {}
    for busca, molde in BUSCAS.items():
        itens = _achata(json.loads(_gh(molde.format(repo=repo), paginado=True)))
        contagens[busca] = _acrescenta(raiz / f"{busca}.jsonl", itens)
        print(f"    {busca:22} {contagens[busca]:6}", flush=True)

    contagens["commit_files"] = _clone_e_arquivos(repo, raiz, scratch)
    print(f"    {'commit_files':22} {contagens['commit_files']:6}", flush=True)
    return meta, contagens


def repos_da_coleta(raiz: Path) -> list[str]:
    """Quais repositórios aparecem nos eventos, lidos do campo `url` de cada item.

    Descobre pelo conteúdo, sem lista e sem depender de nome de arquivo. É o que
    permite receber a coleta de outra pessoa apontando só o caminho.
    """
    achados: set[str] = set()
    for arquivo in sorted(raiz.rglob("*")):
        if not arquivo.is_file() or arquivo.suffix not in {".json", ".jsonl"}:
            continue
        if arquivo.name in {"repos.jsonl", "languages.jsonl"} or arquivo.name.startswith("_"):
            continue
        for item in _linhas_de(arquivo):
            url = str(item.get("url") or item.get("repository_url") or "")
            partes = url.split("/repos/", 1)
            if len(partes) == 2:
                pedaco = partes[1].split("/")
                if len(pedaco) >= 2:
                    achados.add(f"{pedaco[0]}/{pedaco[1]}")
    return sorted(achados)


def _linhas_de(arquivo: Path) -> Iterator[dict]:
    """Itens de um arquivo, em JSON Lines ou num array só."""
    with arquivo.open(encoding="utf-8") as f:
        primeiro = f.read(1)
        while primeiro and primeiro.isspace():
            primeiro = f.read(1)
        f.seek(0)
        if primeiro == "[":
            yield from json.load(f)
            return
        for linha in f:
            if linha.strip():
                yield json.loads(linha)


def completar(raiz: Path) -> int:
    """Produz o que a coleta de eventos não traz: metadados e caminhos de arquivo.

    Pula o que já está no disco, então rodar de novo depois de uma queda continua
    de onde parou.
    """
    if not raiz.is_dir():
        print(f"GHAPI_DIR '{raiz}' nao existe.", file=sys.stderr)
        return 2
    repos = repos_da_coleta(raiz)
    if not repos:
        print(f"nenhum repositorio encontrado em {raiz}.", file=sys.stderr)
        return 1
    print(f"{len(repos)} repositorios na coleta de {raiz}", flush=True)

    metadados = raiz / "repos.jsonl"
    ja_meta = {m["full_name"] for m in _linhas_de(metadados)} if metadados.exists() else set()
    ja_clone = set()
    tsv = raiz / "commit_files.tsv"
    if tsv.exists():
        with tsv.open(encoding="utf-8") as f:
            f.readline()
            ja_clone = {linha.split("\t", 1)[0] for linha in f if linha.strip()}

    scratch = raiz / "_scratch"
    scratch.mkdir(parents=True, exist_ok=True)
    for repo in repos:
        if repo not in ja_meta:
            meta = json.loads(_gh(f"repos/{repo}", paginado=False))
            _acrescenta(raiz / "repos.jsonl", [meta])
            _acrescenta(
                raiz / "languages.jsonl",
                [
                    {
                        "repo_id": int(meta["id"]),
                        "full_name": meta["full_name"],
                        "languages": json.loads(_gh(f"repos/{repo}/languages", paginado=False)),
                    }
                ],
            )
            print(f"  {repo:34} metadados", flush=True)
        if repo not in ja_clone:
            n = _clone_e_arquivos(repo, raiz, scratch)
            print(f"  {repo:34} {n} caminhos de arquivo", flush=True)
    shutil.rmtree(scratch, ignore_errors=True)
    print("pronto.", flush=True)
    return 0


def main(repos: list[str]) -> int:
    """Coleta a lista pedida em `GHAPI_DIR` e grava `_coleta.json`."""
    raiz = Path(os.getenv("GHAPI_DIR", "data/ghapi"))
    if repos == ["--completar"]:
        return completar(raiz)
    if not repos:
        print(
            "uso: coleta.py owner/repo [owner/repo ...]\n"
            "     coleta.py --completar     (metadados e clones do que ja esta em GHAPI_DIR)",
            file=sys.stderr,
        )
        return 2

    scratch = raiz / "_scratch"
    if raiz.exists():
        shutil.rmtree(raiz)  # os arquivos são acrescentados; recomeçar evita duplicar
    scratch.mkdir(parents=True, exist_ok=True)
    print(f"coletando {len(repos)} repositórios em {raiz}", flush=True)

    metas: list[dict] = []
    contagens: dict[str, dict[str, int]] = {}
    for repo in repos:
        meta, cont = coleta_repo(repo, raiz, scratch)
        metas.append(meta)
        contagens[str(meta["id"])] = cont

    _acrescenta(raiz / "repos.jsonl", metas)
    shutil.rmtree(scratch, ignore_errors=True)

    agora = datetime.now(UTC)
    (raiz / "_coleta.json").write_text(
        json.dumps(
            {
                "coletado_em": agora.isoformat(timespec="seconds"),
                "corte": agora.isoformat(timespec="seconds"),
                "criterio": "amostra de desenvolvimento, escolhida à mão",
                "coletor": "adapters/ghapi/coleta.py",
                "repos": [int(m["id"]) for m in metas],
                "contagens": contagens,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"pronto. {raiz / '_coleta.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
