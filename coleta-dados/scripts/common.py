"""
Infraestrutura compartilhada entre etapa_2A (API) e etapa_2B (git clone).

Este módulo contém:
- Configuração da sessão GitHub API (token, retry, rate limit, paginação)
- Utilitários gerais (_login, is_clojure_file, language_from_path, run_git)
- Leitura do CSV de entrada (load_repositories)
- Parse de argumentos (parse_limit)
- Controle de progresso (load_progress, save_progress, update_repo_status)
- Helpers de impressão (warn_if_github_token_missing, print_collection_summary,
  print_collection_finished)

Cada script (2A ou 2B) define seu próprio DATA_DIR, OUTPUT_CSV e
PROGRESS_FILE, e passa esses caminhos para as funções que os utilizam.
"""

import csv
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


load_dotenv()


class TokenPool:
    """Pool de tokens GitHub com rotação automática em rate limit.

    Lê múltiplos tokens da variável GITHUB_TOKEN (um por linha no .env).
    Quando um token atinge rate limit, rotaciona para o próximo.
    Se apenas um token existe, comporta como antes (sleep no rate limit).
    """

    def __init__(self):
        seen = set()
        self.tokens = []
        env_path = Path(__file__).resolve().parent.parent / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if line.startswith("GITHUB_TOKEN="):
                    token = line.split("=", 1)[1].strip().strip("'\"")
                    if token and token not in seen:
                        seen.add(token)
                        self.tokens.append(token)
        self.index = 0

    @property
    def current(self):
        if not self.tokens:
            return None
        return self.tokens[self.index]

    @property
    def count(self):
        return len(self.tokens)

    def rotate(self):
        """Avança para o próximo token. Retorna True se rotacionou, False se
        há apenas um token (rotação ineficaz)."""
        if len(self.tokens) <= 1:
            return False
        self.index = (self.index + 1) % len(self.tokens)
        return True

    def update_session(self, session):
        """Atualiza o header Authorization da sessão com o token atual."""
        if self.current:
            session.headers["Authorization"] = f"Bearer {self.current}"
        elif "Authorization" in session.headers:
            del session.headers["Authorization"]


token_pool = TokenPool()

HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)
token_pool.update_session(SESSION)

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

api_calls = 0


def print_api_usage():
    print(f"Requisições API utilizadas: {api_calls}")

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
    "repo_name",
    "event_type",
    "number",
    "title",
    "author",
    "author_login",
    "author_email",
    "created_at",
    "state",
    "sha",
    "message",
    "url",
    "labels",
    "files",
    "language",
    "collection_status",
    "collection_started_at",
]

EXTENSION_TO_LANGUAGE = {
    ".clj": "Clojure",
    ".cljs": "ClojureScript",
    ".cljc": "Clojure",
    ".edn": "EDN",
    ".bb": "Babashka",
    ".cljx": "Clojure",
}


# utils gerais

def _login(user):
    return (user or {}).get("login", "")


def is_clojure_file(filepath: str) -> bool:
    """Determina se um caminho corresponde a um arquivo Clojure do escopo."""
    if not filepath:
        return False
    return Path(filepath.lower()).suffix in CLOJURE_EXTENSIONS


def language_from_path(filepath: str) -> str:
    """Devolve o nome da linguagem a partir da extensão do arquivo.

    Se o path é None ou vazio, devolve string vazia.
    Se a extensão não mapeia para nenhuma linguagem conhecida, devolve
    string vazia.
    """
    if not filepath:
        return ""
    ext = Path(filepath.lower()).suffix
    return EXTENSION_TO_LANGUAGE.get(ext, "")


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

def _is_rate_limited(response: requests.Response) -> bool:
    """Detecta rate limit primário ou secundário da GitHub API."""
    remaining = response.headers.get("X-RateLimit-Remaining")

    primary = response.status_code == 403 and remaining == "0"
    secondary = response.status_code in {403, 429} and (
        "secondary rate limit" in response.text.lower()
        or "rate limit" in response.text.lower()
        or response.status_code == 429
    )

    return primary or secondary


def _wait_for_rate_limit(response: requests.Response) -> bool:
    """Espera quando a GitHub API informa rate limit primário/secundário.

    Se can_rotate é True e o pool tem mais de um token, não espera
    (rotação é preferível a sleep).
    """
    if not _is_rate_limited(response):
        return False

    reset = response.headers.get("X-RateLimit-Reset")
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
    global api_calls
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            response = SESSION.get(url, params=params, timeout=30)
            api_calls += 1

            if response.status_code == 200:
                return response

            if response.status_code == 404:
                return None

            if response.status_code == 202:
                time.sleep(min(2 * attempt, 10))
                continue

            if _is_rate_limited(response):
                if token_pool.rotate():
                    token_pool.update_session(SESSION)
                    token = token_pool.current
                    masked = token[:4] + "..." + token[-4:] if token and len(token) > 8 else token
                    print(f"Rate limit atingido. Rotacionando para token {masked}...")
                    attempt = 0
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

        current_url = _extract_next_url_from_link(response)

        current_params = None


# linguagem do repositório (cache em memória)

_repo_lang_cache: dict[str, str] = {}


def get_repo_language(owner: str, repo: str) -> str:
    """Devolve a linguagem principal do repositório.

    Usa cache em memória para evitar chamadas duplicadas.
    Se a API não retornar linguagem, devolve string vazia.
    """
    key = f"{owner}/{repo}"
    if key in _repo_lang_cache:
        return _repo_lang_cache[key]

    url = f"https://api.github.com/repos/{owner}/{repo}"
    response = get_response_with_retry(url)
    lang = ""
    if response is not None:
        data = response.json()
        lang = data.get("language") or ""
    _repo_lang_cache[key] = lang
    return lang


# entrada

def load_repositories(input_csv):
    """
    Lê exclusivamente repositorios_clojure_alvo.csv produzido pela Etapa 1.
    """
    if not input_csv.exists():
        raise FileNotFoundError(
            f"Arquivo de entrada não encontrado: {input_csv.resolve()}"
        )

    with input_csv.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter='|')

        required = {"repo_id", "repo_name", "default_branch"}
        missing = required - set(reader.fieldnames or [])

        if missing:
            raise ValueError(
                f"{input_csv} não possui as colunas obrigatórias: "
                f"{', '.join(sorted(missing))}"
            )

        return [
            {
                "repo_id": int(row["repo_id"]),
                "repo_name": row["repo_name"].strip(),
                "branch": (row.get("default_branch") or "main").strip() or "main",
            }
            for row in reader
            if row.get("repo_id")
        ]


def parse_limit(args):
    """
    Extrai --limit N de uma lista de argumentos.

    Retorna int ou None.
    """
    for i, arg in enumerate(args):
        if arg == "--limit" and i + 1 < len(args):
            return int(args[i + 1])
    return None


# controle do progresso

def load_progress(progress_file):
    """Carrega o status de cada repositório."""
    if not progress_file.exists():
        return {}

    try:
        with progress_file.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}

    if isinstance(data.get("repositories"), dict):
        return data["repositories"]

    # Migração da primeira versão baseada em processed_repos.
    return {
        repo_id: {
            "repo_name": "",
            "status": "complete",
            "branch": "",
            "error": "",
            "updated_at": data.get("updated_at", ""),
        }
        for repo_id in data.get("processed_repos", [])
    }


def save_progress(repo_status, progress_file, collection_started_at="", collection_ended_at=""):
    """Salva o status por repositório de forma atômica."""
    global api_calls
    progress_file.parent.mkdir(parents=True, exist_ok=True)

    tmp = progress_file.with_suffix(".tmp")
    payload = {
        "collection_started_at": collection_started_at,
        "collection_ended_at": collection_ended_at,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "api_calls": api_calls,
        "repositories": repo_status,
    }

    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    os.replace(tmp, progress_file)


def save_run_stats(run_dir, stats):
    """Salva ou mergeia estatísticas de execução em reports/estatisticas.json.

    stats é um dict com dados da etapa atual. Se o arquivo já existe,
    os dados são mergeados (cada etapa escreve sua chave).
    """
    stats_file = Path(run_dir) / "reports" / "estatisticas.json"
    stats_file.parent.mkdir(parents=True, exist_ok=True)

    existing = {}
    if stats_file.exists():
        try:
            with stats_file.open("r", encoding="utf-8") as f:
                existing = json.load(f)
        except (OSError, json.JSONDecodeError):
            existing = {}

    existing.update(stats)
    existing["updated_at"] = datetime.now(timezone.utc).isoformat()

    tmp = stats_file.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    os.replace(tmp, stats_file)


def update_repo_status(repo_status, repo_id, repo_name, branch, status, error="", progress_file=None):
    """Atualiza complete/error de um repositório."""
    repo_status[repo_id] = {
        "repo_name": repo_name,
        "status": status,
        "branch": branch,
        "error": error,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if progress_file is not None:
        save_progress(repo_status, progress_file)


# helpers de impressão

def warn_if_github_token_missing():
    if token_pool.count == 0:
        print(
            "AVISO: GITHUB_TOKEN não definido no .env. "
            "Issues e PRs estarão sujeitos ao limite baixo da GitHub API."
        )
    elif token_pool.count == 1:
        print(
            "INFO: Apenas 1 token configurado. "
            "Adicione mais tokens no .env (um por linha) para rotação automática "
            "em caso de rate limit."
        )
    else:
        print(
            f"INFO: {token_pool.count} tokens configurados. "
            "Rotação automática em caso de rate limit."
        )


def print_collection_summary(label, input_csv, output_csv, repositories, repo_status):
    output_exists = output_csv.exists() and output_csv.stat().st_size > 0

    completed_count = 0
    error_count = 0

    for info in repo_status.values():
        status = info.get("status")

        if status == "complete":
            completed_count += 1
        elif status == "error":
            error_count += 1

    print(f"=== Etapa 2{label}: coleta de eventos ===")
    print(f"Entrada: {input_csv}")
    print(f"Saída: {output_csv}")
    print(f"Repos na entrada: {len(repositories)}")
    print(f"Repos já concluídos: {completed_count}")
    print(f"Repos com erro para retentar: {error_count}")

    return output_exists, completed_count, error_count


def print_collection_finished(label, output_csv, progress_file, collection_started_at, collection_ended_at):
    print(f"\n=== Etapa 2{label} concluída ===")
    print(f"Eventos salvos em: {output_csv}")
    print(f"Progresso salvo em: {progress_file}")
    print(f"Coleta iniciada em: {collection_started_at}")
    print(f"Coleta finalizada em: {collection_ended_at}")
    print_api_usage()


# loop de coleta genérico

def _process_single_repo(index, total, repo_info, repo_status, writer, output_file,
                         collection_started_at, process_repo_fn, print_counts_fn,
                         progress_file):
    """
    Processa um repositório. Retorna True se processou (não pulou), False se pulou.
    """
    repo_id = repo_info["repo_id"]
    repo_name = repo_info["repo_name"]
    branch = repo_info["branch"]

    current_status = repo_status.get(repo_id, {}).get("status")

    if current_status == "complete":
        print(
            f"[{index}/{total}] "
            f"Pulando {repo_name} ({repo_id}) (já concluído)"
        )
        return False

    if current_status == "error":
        print(
            f"[{index}/{total}] "
            f"Retentando {repo_name} ({repo_id}) (erro anterior)"
        )
    else:
        print(
            f"[{index}/{total}] "
            f"Processando {repo_name} ({repo_id})"
        )

    try:
        rows = process_repo_fn(repo_id, repo_name, branch, collection_started_at)

    except Exception as exc:
        error_message = str(exc)
        print(f"ERRO em {repo_name} ({repo_id}): {error_message}")

        update_repo_status(
            repo_status,
            repo_id,
            repo_name,
            branch,
            status="error",
            error=error_message,
            progress_file=progress_file,
        )

        print(
            "Status salvo como 'error'. O repositório será "
            "retentado na próxima execução."
        )
        return True

    for row in rows:
        writer.writerow(row)

    # Persiste o lote inteiro do repositório antes de marcá-lo complete.
    output_file.flush()
    os.fsync(output_file.fileno())

    update_repo_status(
        repo_status,
        repo_id,
        repo_name,
        branch,
        status="complete",
        progress_file=progress_file,
    )

    print_counts_fn(rows)
    return True


def collect_repositories(repositories, repo_status, writer, output_file,
                         collection_started_at, process_repo_fn, print_counts_fn,
                         progress_file, limit=None):
    """
    Itera sobre os repositórios e coleta eventos.

    Se limit é informado, para após processar N repositórios novos
    (repos com status "complete" são pulados sem contar).
    """
    processed = 0
    for index, repo_info in enumerate(repositories, start=1):
        was_processed = _process_single_repo(
            index,
            len(repositories),
            repo_info,
            repo_status,
            writer,
            output_file,
            collection_started_at,
            process_repo_fn,
            print_counts_fn,
            progress_file,
        )
        if was_processed:
            processed += 1
            if limit is not None and processed >= limit:
                print(f"\nLimite de {limit} repositórios atingido.")
                break
