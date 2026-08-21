"""
Etapa 2: Mineração de Eventos de Repositórios Clojure Alvo.

Entrada:
    repositorios_clojure_alvo.csv

Saída:
    eventos_repositorios.csv

Escopo:
- Issues: todas as issues reais, sem filtro por arquivo.
- Pull Requests: apenas PRs que alteram ao menos um arquivo Clojure.
- Commits: apenas commits que alteram ao menos um arquivo Clojure.

Estratégia:
- Issues: GitHub REST API.
- PRs: GitHub REST API + arquivos modificados pelo PR.
- Commits: git clone --bare --filter=blob:none + git log --all --name-only.

A Etapa 2 NÃO procura nem revalida repositórios Clojure. Ela trabalha
exclusivamente sobre os repositórios aprovados pela Etapa 1 e presentes em
repositorios_clojure_alvo.csv.

A coleta é resumível por repositório:
- complete: não é processado novamente.
- error: é tentado novamente na próxima execução.
"""

import csv
import json
import os
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
} if GITHUB_TOKEN else {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)

_adapter = HTTPAdapter(
    pool_connections=20,
    pool_maxsize=20,
    max_retries=Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET"],
    ),
)
SESSION.mount("https://", _adapter)
SESSION.mount("http://", _adapter)


INPUT_CSV = Path("repositorios_clojure_alvo.csv")
OUTPUT_CSV = Path("eventos_repositorios.csv")
PROGRESS_FILE = Path("reports/etapa_2_eventos_progresso.json")

CLOJURE_EXTENSIONS = {
    ".clj",
    ".cljs",
    ".cljc",
    ".edn",
    ".bb",
    ".cljx",
}

OUTPUT_FIELDS = [
    "repo_id",
    "event_type",
    "number",
    "title",
    "author",
    "created_at",
    "state",
    "sha",
    "message",
    "url",
    "labels",
    "clojure_files",
    "collection_status",
]


# utils gerais

def is_clojure_file(filepath: str) -> bool:
    """Determina se um caminho corresponde a um arquivo Clojure do escopo."""
    if not filepath:
        return False
    return Path(filepath.lower()).suffix in CLOJURE_EXTENSIONS


def _login(user):
    return (user or {}).get("login", "")


def run_git(args, cwd=None):
    """Executa Git e devolve stdout; falhas viram RuntimeError."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "Git não está instalado ou não está disponível no PATH."
        ) from exc

    if result.returncode != 0:
        command = "git " + " ".join(args)
        raise RuntimeError(
            f"Falha ao executar `{command}`:\n{result.stderr.strip()}"
        )

    return result.stdout


# github API: retry, rate limit e paginação

def _wait_for_rate_limit(response: requests.Response) -> bool:
    """Espera quando a GitHub API informa rate limit primário/secundário."""
    remaining = response.headers.get("X-RateLimit-Remaining")
    reset = response.headers.get("X-RateLimit-Reset")

    primary = response.status_code == 403 and remaining == "0"
    secondary = response.status_code in {403, 429} and (
        "secondary rate limit" in response.text.lower()
        or "rate limit" in response.text.lower()
        or response.status_code == 429
    )

    if not (primary or secondary):
        return False

    retry_after = response.headers.get("Retry-After")

    if retry_after:
        sleep_time = max(float(retry_after), 1.0)
    elif reset:
        sleep_time = max(float(reset) - time.time(), 0.0) + 1.0
    else:
        sleep_time = 60.0

    print(f"Rate limit atingido. Aguardando {sleep_time:.1f}s...")
    time.sleep(sleep_time)
    return True


def get_response_with_retry(url, params=None, max_retries=5):
    """Executa GET com retry para falhas transitórias e rate limit."""
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            response = SESSION.get(url, params=params, timeout=30)

            if response.status_code == 200:
                return response

            if response.status_code == 404:
                return None

            if response.status_code == 202:
                time.sleep(min(2 * attempt, 10))
                continue

            if _wait_for_rate_limit(response):
                continue

            if response.status_code in {500, 502, 503, 504}:
                time.sleep(min(2 ** attempt, 30))
                continue

            last_error = RuntimeError(
                f"GitHub API retornou {response.status_code} para "
                f"{response.url}: {response.text[:500]}"
            )
            break

        except requests.RequestException as exc:
            last_error = exc
            if attempt < max_retries:
                time.sleep(min(2 ** attempt, 30))

    raise RuntimeError(f"Falha ao acessar {url}: {last_error}")

def _extract_next_url_from_link(response):
    """
    Extrai a URL marcada como rel="next" do header Link da GitHub API.
    Retorna None quando não existe próxima página.
    """
    link_header = response.headers.get("Link")

    if not link_header:
        return None

    for link in link_header.split(","):
        parts = link.strip().split(";")

        if len(parts) < 2:
            continue

        url_part = parts[0].strip()
        rel_part = ";".join(parts[1:]).strip()

        if 'rel="next"' in rel_part:
            if url_part.startswith("<") and url_part.endswith(">"):
                return url_part[1:-1]

    return None


def get_paginated(url, params=None):
    """
    Percorre todas as páginas seguindo rel="next" do header Link.

    A primeira requisição usa os params fornecidos.
    As seguintes usam exatamente a URL fornecida pelo GitHub.
    """
    current_url = url

    initial_params = dict(params or {})
    initial_params.setdefault("per_page", 100)

    current_params = initial_params

    while current_url:
        response = get_response_with_retry(
            current_url,
            params=current_params,
        )

        if response is None:
            return

        data = response.json()

        if not isinstance(data, list):
            raise RuntimeError(
                f"Resposta paginada inesperada em {response.url}: "
                f"{type(data).__name__}"
            )

        yield from data

        # O GitHub determina como acessar a próxima página.
        current_url = _extract_next_url_from_link(response)

        # A URL de rel="next" já contém os parâmetros necessários,
        # como page=N, after=cursor etc.
        current_params = None


# normalização

def normalize_issue(repo_id, issue):
    labels = [
        label.get("name", "")
        for label in issue.get("labels", [])
        if isinstance(label, dict)
    ]

    return {
        "repo_id": repo_id,
        "event_type": "issue",
        "number": issue.get("number", ""),
        "title": issue.get("title", ""),
        "author": _login(issue.get("user")),
        "created_at": issue.get("created_at", ""),
        "state": issue.get("state", ""),
        "sha": "",
        "message": "",
        "url": issue.get("html_url", ""),
        "labels": ";".join(labels),
        "clojure_files": "",
        "collection_status": "complete",
    }


def normalize_pr(repo_id, pr, clojure_files):
    labels = [
        label.get("name", "")
        for label in pr.get("labels", [])
        if isinstance(label, dict)
    ]

    state = "merged" if pr.get("merged_at") else pr.get("state", "")

    return {
        "repo_id": repo_id,
        "event_type": "pr",
        "number": pr.get("number", ""),
        "title": pr.get("title", ""),
        "author": _login(pr.get("user")),
        "created_at": pr.get("created_at", ""),
        "state": state,
        "sha": (pr.get("head") or {}).get("sha", ""),
        "message": "",
        "url": pr.get("html_url", ""),
        "labels": ";".join(labels),
        "clojure_files": ";".join(sorted(clojure_files)),
        "collection_status": "complete",
    }


def normalize_commit(repo_id, commit):
    return {
        "repo_id": repo_id,
        "event_type": "commit",
        "number": "",
        "title": "",
        "author": commit["author"],
        "created_at": commit["created_at"],
        "state": "",
        "sha": commit["sha"],
        "message": commit["message"],
        "url": f"https://github.com/{repo_id}/commit/{commit['sha']}",
        "labels": "",
        "clojure_files": ";".join(sorted(commit["clojure_files"])),
        "collection_status": "complete",
    }


# evento 1: issues

def collect_issues(repo_id, owner, repo):
    """
    Coleta todas as issues reais.

    O endpoint /issues também retorna PRs. Objetos com a chave `pull_request`
    são descartados aqui porque PR é outro tipo de evento.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/issues"
    rows = []

    for item in get_paginated(
        url,
        params={
            "state": "all",
            "sort": "created",
            "direction": "asc",
        },
    ):
        if "pull_request" not in item:
            rows.append(normalize_issue(repo_id, item))

    return rows


#evento 2: pull requests

def collect_prs(repo_id, owner, repo):
    """
    Coleta somente PRs que tocaram pelo menos um arquivo Clojure.

    Para cada PR, consulta /pulls/{number}/files e aplica o filtro de extensão.
    """
    prs_url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
    rows = []

    for pr in get_paginated(
        prs_url,
        params={
            "state": "all",
            "sort": "created",
            "direction": "asc",
        },
    ):
        number = pr.get("number")
        if number is None:
            continue

        files_url = (
            f"https://api.github.com/repos/{owner}/{repo}/pulls/{number}/files"
        )

        clojure_files = set()

        for file_data in get_paginated(files_url):
            filename = file_data.get("filename", "")
            if is_clojure_file(filename):
                clojure_files.add(filename)

        if clojure_files:
            rows.append(
                normalize_pr(
                    repo_id=repo_id,
                    pr=pr,
                    clojure_files=clojure_files,
                )
            )

    return rows


# evento 3: commits

def clone_bare_repository(repo_id, destination):
    """
    Faz clone bare sem blobs.

    O histórico e os nomes de caminhos ficam disponíveis, mas o conteúdo
    completo dos arquivos não é baixado.
    """
    clone_url = f"https://github.com/{repo_id}.git"

    run_git(
        [
            "clone",
            "--bare",
            "--filter=blob:none",
            "--no-tags",
            clone_url,
            str(destination),
        ]
    )


def get_commit_files_from_git(repo_dir):
    """
    Usa `git log --all --name-only` para mapear SHA -> arquivos Clojure tocados.

    Isso considera todo o histórico disponível em todas as refs do clone,
    inclusive commits relativos a arquivos que já foram removidos da árvore
    atual do repositório.
    """
    marker = "__ETAPA2_COMMIT__"

    output = run_git(
        [
            "log",
            "--all",
            f"--format={marker}%H",
            "--name-only",
            "--no-renames",
        ],
        cwd=repo_dir,
    )

    commits = {}
    current_sha = None

    for raw_line in output.splitlines():
        line = raw_line.strip()

        if not line:
            continue

        if line.startswith(marker):
            current_sha = line[len(marker):].strip()
            commits.setdefault(current_sha, set())
            continue

        if current_sha is not None and is_clojure_file(line):
            commits[current_sha].add(line)

    # Só permanecem commits que tocaram ao menos um arquivo Clojure.
    return {
        sha: files
        for sha, files in commits.items()
        if files
    }


def get_commit_metadata(repo_dir, sha):
    """Obtém metadados de um commit diretamente do clone local."""
    # Separadores de controle reduzem o risco de colisão com texto do commit.
    field_sep = "\x1f"
    format_string = "%H%x1f%an%x1f%aI%x1f%B"

    output = run_git(
        [
            "show",
            "-s",
            f"--format={format_string}",
            sha,
        ],
        cwd=repo_dir,
    )

    parts = output.split(field_sep, 3)
    if len(parts) != 4:
        raise RuntimeError(f"Não foi possível interpretar metadados do commit {sha}")

    parsed_sha, author, created_at, message = parts

    return {
        "sha": parsed_sha.strip(),
        "author": author.strip(),
        "created_at": created_at.strip(),
        "message": message.rstrip(),
    }


def collect_commits(repo_id, owner, repo):
    """
    Coleta commits Clojure usando Git local.

    Fluxo:
        git clone --bare --filter=blob:none
        -> git log --all --name-only
        -> filtra caminhos pelas extensões Clojure
        -> obtém metadados dos SHAs selecionados

    `owner` e `repo` permanecem na assinatura para manter a mesma interface das
    funções de eventos; o repo_id é a fonte usada para montar a URL do clone.
    """
    del owner, repo

    temp_root = Path(tempfile.mkdtemp(prefix="etapa2_git_"))
    repo_dir = temp_root / "repository.git"

    try:
        print("    Clonando histórico Git sem blobs...")
        clone_bare_repository(repo_id, repo_dir)

        print("    Analisando arquivos tocados por cada commit...")
        commit_files = get_commit_files_from_git(repo_dir)

        rows = []
        total = len(commit_files)

        for index, (sha, clojure_files) in enumerate(commit_files.items(), start=1):
            if index == 1 or index % 500 == 0 or index == total:
                print(f"    Metadados de commits: {index}/{total}")

            metadata = get_commit_metadata(repo_dir, sha)
            metadata["clojure_files"] = clojure_files
            rows.append(normalize_commit(repo_id, metadata))

        return rows

    finally:
        shutil.rmtree(temp_root, ignore_errors=True)

# controle do status

def load_progress():
    """Carrega o status de cada repositório."""
    if not PROGRESS_FILE.exists():
        return {}

    try:
        with PROGRESS_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}

    if isinstance(data.get("repositories"), dict):
        return data["repositories"]

    # Migração da primeira versão baseada em processed_repos.
    return {
        repo_id: {
            "status": "complete",
            "branch": "",
            "error": "",
            "updated_at": data.get("updated_at", ""),
        }
        for repo_id in data.get("processed_repos", [])
    }


def save_progress(repo_status):
    """Salva o status por repositório de forma atômica."""
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)

    tmp = PROGRESS_FILE.with_suffix(".tmp")
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "repositories": repo_status,
    }

    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    os.replace(tmp, PROGRESS_FILE)


def update_repo_status(repo_status, repo_id, branch, status, error=""):
    """Atualiza complete/error de um repositório."""
    repo_status[repo_id] = {
        "status": status,
        "branch": branch,
        "error": error,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    save_progress(repo_status)


# carrega entrada da etapa 1

def load_repositories():
    """
    Lê exclusivamente repositorios_clojure_alvo.csv produzido pela Etapa 1.
    """
    if not INPUT_CSV.exists():
        raise FileNotFoundError(
            f"Arquivo de entrada não encontrado: {INPUT_CSV.resolve()}"
        )

    with INPUT_CSV.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        required = {"repo_id", "default_branch"}
        missing = required - set(reader.fieldnames or [])

        if missing:
            raise ValueError(
                f"{INPUT_CSV} não possui as colunas obrigatórias: "
                f"{', '.join(sorted(missing))}"
            )

        return [
            {
                "repo_id": row["repo_id"].strip(),
                "branch": (row.get("default_branch") or "main").strip() or "main",
            }
            for row in reader
            if row.get("repo_id")
        ]


def process_repo(repo_id, branch):
    """
    Orquestra os três módulos de eventos.

    Cada tipo de evento possui sua própria função:
        collect_issues()
        collect_prs()
        collect_commits()
    """
    if "/" not in repo_id:
        raise ValueError(f"repo_id inválido: {repo_id!r}")

    owner, repo = repo_id.split("/", 1)

    print("  Coletando issues...")
    issue_rows = collect_issues(repo_id, owner, repo)

    print("  Coletando PRs que tocam Clojure...")
    pr_rows = collect_prs(repo_id, owner, repo)

    print("  Coletando commits que tocam Clojure...")
    commit_rows = collect_commits(repo_id, owner, repo)

    return issue_rows + pr_rows + commit_rows


def main():
    if not GITHUB_TOKEN:
        print(
            "AVISO: GITHUB_TOKEN não definido no .env. "
            "Issues e PRs estarão sujeitos ao limite baixo da GitHub API."
        )

    repositories = load_repositories()
    repo_status = load_progress()

    output_exists = OUTPUT_CSV.exists() and OUTPUT_CSV.stat().st_size > 0

    completed_count = sum(
        1
        for info in repo_status.values()
        if info.get("status") == "complete"
    )
    error_count = sum(
        1
        for info in repo_status.values()
        if info.get("status") == "error"
    )

    print("=== Etapa 2: coleta de eventos ===")
    print(f"Entrada: {INPUT_CSV}")
    print(f"Saída: {OUTPUT_CSV}")
    print(f"Repos na entrada: {len(repositories)}")
    print(f"Repos já concluídos: {completed_count}")
    print(f"Repos com erro para retentar: {error_count}")

    with OUTPUT_CSV.open("a", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=OUTPUT_FIELDS)

        if not output_exists:
            writer.writeheader()
            output_file.flush()
            os.fsync(output_file.fileno())

        for index, repo_info in enumerate(repositories, start=1):
            repo_id = repo_info["repo_id"]
            branch = repo_info["branch"]

            current_status = repo_status.get(repo_id, {}).get("status")

            if current_status == "complete":
                print(
                    f"[{index}/{len(repositories)}] "
                    f"Pulando {repo_id} (já concluído)"
                )
                continue

            if current_status == "error":
                print(
                    f"[{index}/{len(repositories)}] "
                    f"Retentando {repo_id} (erro anterior)"
                )
            else:
                print(
                    f"[{index}/{len(repositories)}] "
                    f"Processando {repo_id}"
                )

            try:
                rows = process_repo(repo_id, branch)

            except Exception as exc:
                error_message = str(exc)
                print(f"ERRO em {repo_id}: {error_message}")

                update_repo_status(
                    repo_status,
                    repo_id,
                    branch,
                    status="error",
                    error=error_message,
                )

                print(
                    "Status salvo como 'error'. O repositório será "
                    "retentado na próxima execução."
                )
                continue

            for row in rows:
                writer.writerow(row)

            # Persiste o lote inteiro do repositório antes de marcá-lo complete.
            output_file.flush()
            os.fsync(output_file.fileno())

            update_repo_status(
                repo_status,
                repo_id,
                branch,
                status="complete",
            )

            issue_count = sum(
                row["event_type"] == "issue"
                for row in rows
            )
            pr_count = sum(
                row["event_type"] == "pr"
                for row in rows
            )
            commit_count = sum(
                row["event_type"] == "commit"
                for row in rows
            )

            print(
                f"  Concluído: {issue_count} issues, "
                f"{pr_count} PRs Clojure, "
                f"{commit_count} commits Clojure."
            )

    print("\n=== Etapa 2 concluída ===")
    print(f"Eventos salvos em: {OUTPUT_CSV}")
    print(f"Progresso salvo em: {PROGRESS_FILE}")


if __name__ == "__main__":
    main()