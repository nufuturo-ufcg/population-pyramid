"""Coleta a amostra de desenvolvimento do adaptador `ghapi`.

Baixa poucos repositórios no mesmo formato em que a coleta grande vai chegar,
para o adaptador ter dado real contra o qual rodar enquanto ela não vem.

    GHAPI_DIR=data/ghapi .venv/bin/python adapters/ghapi/coleta_amostra.py \
        clj-kondo/clj-kondo borkdude/edamame weavejester/medley

O formato é o JSON cru da API, um arquivo por busca, com os itens de todos os
repositórios concatenados na mesma lista. Cada item carrega o campo `url`, no
formato `https://api.github.com/repos/{owner}/{repo}/...`, e é dele que o
adaptador tira a qual repositório o evento pertence. Nome de arquivo e ordem
não entram na conta.

Duas buscas ficam de fora do que a coleta grande produz, e o adaptador resolve
sozinho porque são baratas:

- `GET /repos` e `GET /repos/{owner}/{repo}/languages` custam duas requisições
  por repositório e dão o rótulo, a data de criação e o mapa de bytes por
  linguagem.
- O clone parcial dá o caminho dos arquivos de cada commit. A API só entrega
  isso a uma requisição por commit, o que estoura qualquer cota.

Autenticação e paginação saem do `gh`.

ponytail: sem retomada e sem ETag. Script que morre no meio recomeça do zero.
Para amostra de três repositórios isso custa minutos. A coleta grande é outro
programa, feito por outra pessoa, e precisa das duas coisas.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
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


def main(repos: list[str]) -> int:
    """Coleta a lista pedida em `GHAPI_DIR` e grava `_coleta.json`."""
    if not repos:
        print("uso: coleta_amostra.py owner/repo [owner/repo ...]", file=sys.stderr)
        return 2

    raiz = Path(os.getenv("GHAPI_DIR", "data/ghapi"))
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
                "coletor": "adapters/ghapi/coleta_amostra.py",
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
