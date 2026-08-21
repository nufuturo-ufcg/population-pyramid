"""Coleta a amostra de desenvolvimento do adaptador `ghapi`.

Baixa poucos repositórios no layout que `docs/ferramenta/COLETA_GITHUB.md`
descreve, para o adaptador ter dado real contra o qual rodar enquanto a coleta
grande não chega. O contrato de saída é o mesmo dos dois casos, então o
`source.py` não sabe qual das duas produziu o diretório.

    GHAPI_DIR=data/ghapi .venv/bin/python adapters/ghapi/coleta_amostra.py \
        clj-kondo/clj-kondo borkdude/edamame weavejester/medley

Autenticação sai do `gh`, que já resolve token e paginação. A coleta grande usa
outro coletor, com rotação de token, retomada por checkpoint e `ETag`. Aqui a
amostra tem três repositórios e cabe numa cota de uma hora.

ponytail: sem retomada e sem ETag. Script que morre no meio recomeça do zero.
Para amostra de três repositórios isso custa minutos. A coleta grande precisa
das duas coisas, e é por isso que ela é outro programa.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

# As sete requisições da seção "As oito buscas por repositório" do
# `docs/ferramenta/COLETA_GITHUB.md`. A oitava é o clone, tratada à parte.
#
# `issues` traz issue e pull request na mesma listagem, separados pela chave
# `pull_request` de cada item. Por isso `/pulls` não aparece aqui.
#
# `sort=created&direction=asc` em vez de `since`: o `since` filtra por
# `updated_at`, que muda quando alguém comenta em coisa velha, e o backfill
# perderia item. A ordem por criação é estável para varredura histórica.
BUSCAS_PAGINADAS: dict[str, str] = {
    "commits": "repos/{repo}/commits?per_page=100",
    "issues": "repos/{repo}/issues?state=all&sort=created&direction=asc&per_page=100",
    "issue_comments": "repos/{repo}/issues/comments?sort=created&direction=asc&per_page=100",
    "commit_comments": "repos/{repo}/comments?per_page=100",
    "pull_request_comments": "repos/{repo}/pulls/comments?sort=created&direction=asc&per_page=100",
    "issue_events": "repos/{repo}/issues/events?per_page=100",
}

CABECALHO_TSV = "sha\tauthor_date\tauthor_email\tpath"


def _gh(endpoint: str, *, paginado: bool) -> str:
    """Chama `gh api` e devolve a saída crua.

    `--paginate` percorre o cabeçalho `Link` até a última página. `--slurp`
    junta as páginas num array só, o que evita ter de costurar JSON à mão.
    """
    cmd = ["gh", "api", endpoint]
    if paginado:
        cmd += ["--paginate", "--slurp"]
    r = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if r.returncode != 0:
        raise RuntimeError(f"gh api {endpoint} falhou: {r.stderr.strip()}")
    return r.stdout


def _grava_jsonl(destino: Path, itens: list[dict]) -> int:
    """Grava um objeto JSON por linha e devolve quantos foram."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("w", encoding="utf-8") as f:
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


def _clone_e_arquivos(repo: str, repo_id: int, raiz: Path, scratch: Path) -> int:
    """Clone parcial e a tabela (sha, data, e-mail, caminho).

    `--filter=blob:none` baixa commits e árvores e pula o conteúdo dos arquivos.
    `git log --name-only` lê só as árvores, então nenhum blob é buscado depois.

    Commit de merge não lista arquivo neste formato. Ele existe no
    `commits/<repo_id>.jsonl` e some daqui, o que é esperado e está declarado no
    contrato de coleta.
    """
    espelho = scratch / f"{repo_id}.git"
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

    destino = raiz / "commit_files" / f"{repo_id}.tsv"
    destino.parent.mkdir(parents=True, exist_ok=True)
    linhas = 0
    cabeca: tuple[str, str, str] | None = None
    with destino.open("w", encoding="utf-8") as f:
        f.write(CABECALHO_TSV + "\n")
        for linha in log.split("\n"):
            if linha.startswith("C\t"):
                _, sha, data, email = linha.split("\t")
                cabeca = (sha, data, email)
            elif linha.strip() and cabeca is not None:
                sha, data, email = cabeca
                f.write(f"{sha}\t{data}\t{email}\t{linha.strip()}\n")
                linhas += 1
    shutil.rmtree(espelho)
    return linhas


def coleta_repo(repo: str, raiz: Path, scratch: Path) -> tuple[dict, dict[str, int]]:
    """Baixa as oito buscas de um repositório. Devolve o `GET /repos` e as contagens."""
    meta = json.loads(_gh(f"repos/{repo}", paginado=False))
    repo_id = int(meta["id"])
    print(f"  {repo:28} id={repo_id} language={meta['language']}", flush=True)

    (raiz / "languages").mkdir(parents=True, exist_ok=True)
    (raiz / "languages" / f"{repo_id}.json").write_text(
        _gh(f"repos/{repo}/languages", paginado=False), encoding="utf-8"
    )

    contagens: dict[str, int] = {}
    for busca, molde in BUSCAS_PAGINADAS.items():
        itens = _achata(json.loads(_gh(molde.format(repo=repo), paginado=True)))
        contagens[busca] = _grava_jsonl(raiz / busca / f"{repo_id}.jsonl", itens)
        print(f"    {busca:22} {contagens[busca]:6}", flush=True)

    contagens["commit_files"] = _clone_e_arquivos(repo, repo_id, raiz, scratch)
    print(f"    {'commit_files':22} {contagens['commit_files']:6}", flush=True)
    return meta, contagens


def main(repos: list[str]) -> int:
    """Coleta a lista pedida em `GHAPI_DIR` e grava `_coleta.json`."""
    if not repos:
        print("uso: coleta_amostra.py owner/repo [owner/repo ...]", file=sys.stderr)
        return 2

    raiz = Path(os.getenv("GHAPI_DIR", "data/ghapi"))
    scratch = raiz / "_scratch"
    raiz.mkdir(parents=True, exist_ok=True)
    scratch.mkdir(parents=True, exist_ok=True)
    print(f"coletando {len(repos)} repositórios em {raiz}", flush=True)

    metas: list[dict] = []
    contagens: dict[str, dict[str, int]] = {}
    for repo in repos:
        meta, cont = coleta_repo(repo, raiz, scratch)
        metas.append(meta)
        contagens[str(meta["id"])] = cont

    _grava_jsonl(raiz / "repos.jsonl", metas)
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
