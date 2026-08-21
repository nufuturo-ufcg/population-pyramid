"""Etapa 1: Mineração e Filtragem de Repositórios Clojure Alvo.

Critérios metodológicos de filtragem baseados nas diretrizes canônicas de:
- Kalliamvakou, E. et al. (2014, 2016). An in-depth study of the promises and perils of mining GitHub.
- Kitchenham, B. A. et al. (2002). Preliminary guidelines for empirical research in software engineering.
"""

import os
import time
import requests
import csv
import json
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv
from urllib.parse import quote

# Carrega variáveis de ambiente do arquivo .env
load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
} if GITHUB_TOKEN else {
    "Accept": "application/vnd.github.v3+json"
}

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Sessão HTTP global reutilizável para pool de conexões e retries
SESSION = requests.Session()
SESSION.headers.update(HEADERS)
_adapter = HTTPAdapter(
    pool_connections=20,
    pool_maxsize=20,
    max_retries=Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504]),
)
SESSION.mount("https://", _adapter)
SESSION.mount("http://", _adapter)

DEFAULT_CRITERIA = {
    'min_stars': 0,
    'min_watchers': 0,
    'min_clojure_ratio': 0.0,
    'min_commits': 0,
    'min_contributors': 1,
    'max_top_contributor_ratio': 1.0,
    'min_lifespan_days': 0
}

STRUCTURAL_FIELDS = [
    'tree_scan_status', 'file_count', 'code_file_count',
    'documentation_file_count', 'media_file_count', 'documentation_ratio',
    'media_ratio', 'code_ratio', 'educational_signal_count',
    'structure_flags', 'structure_classification',
]
BUILD_DESCRIPTORS = {'project.clj', 'deps.edn', 'build.boot', 'shadow-cljs.edn', 'bb.edn'}
CODE_EXTENSIONS = {'.clj', '.cljs', '.cljc', '.edn', '.bb', '.cljx'}
DOCUMENTATION_EXTENSIONS = {'.md', '.markdown', '.mdown', '.rst', '.adoc', '.asciidoc', '.org', '.txt', '.tex'}
MEDIA_EXTENSIONS = {'.pdf', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.bmp', '.ico'}
def _ratio(part, total):
    return round(part / total, 4) if total else 0.0


def get_repository_tree(owner, repo_name, branch):
    """Return the Git tree used for a lightweight structural classification."""
    url = f"https://api.github.com/repos/{owner}/{repo_name}/git/trees/{quote(branch, safe='')}"
    return get_with_retry(url, params={'recursive': '1'})


def analyze_tree_structure(tree_items: list[dict], repo_name: str = "", description: str = "") -> tuple[dict, str | None]:
    """
    Avalia a proporção quantitativa de código vs documentação vs mídia e
    a presença de manifestos de build para classificar o repositório como software real
    ou descartar repositórios exclusivamente documentais/mídia/sem código.
    """
    files = [item for item in tree_items if item.get('type') == 'blob']
    total_bytes = sum(int(item.get('size') or 0) for item in files)
    counts = {'code': 0, 'documentation': 0, 'media': 0}
    bytes_by_kind = {'code': 0, 'documentation': 0, 'media': 0}
    flags = set()
    has_build_descriptor = False

    for item in files:
        path = item.get('path', '').replace('\\', '/').lower()
        name = path.rsplit('/', 1)[-1]
        ext = os.path.splitext(name)[1]
        size = int(item.get('size') or 0)
        parts = set(path.split('/'))
        
        # Detecta manifesto de build na raiz ou primeiro nível
        if name in BUILD_DESCRIPTORS and len(parts) <= 2:
            has_build_descriptor = True
            flags.add('has_clojure_build_descriptor')

        if ext in CODE_EXTENSIONS or name in BUILD_DESCRIPTORS:
            kind = 'code'
        elif ext in DOCUMENTATION_EXTENSIONS:
            kind = 'documentation'
        elif ext in MEDIA_EXTENSIONS:
            kind = 'media'
        else:
            continue
            
        counts[kind] += 1
        bytes_by_kind[kind] += size

    documentation_ratio = _ratio(bytes_by_kind['documentation'], total_bytes)
    media_ratio = _ratio(bytes_by_kind['media'], total_bytes)
    code_ratio = _ratio(bytes_by_kind['code'], total_bytes)

    if counts['code'] == 0:
        flags.add('no_code_files')
        classification = 'no_code'
        rejection_reason = "Repositório sem arquivos de código Clojure (.clj, .cljs, .cljc, .edn)"
    else:
        classification = 'software'
        rejection_reason = None

    result = {
        'tree_scan_status': 'complete',
        'file_count': len(files),
        'code_file_count': counts['code'],
        'documentation_file_count': counts['documentation'],
        'media_file_count': counts['media'],
        'documentation_ratio': documentation_ratio,
        'media_ratio': media_ratio,
        'code_ratio': code_ratio,
        'educational_signal_count': 0,
        'structure_flags': ';'.join(sorted(flags)),
        'structure_classification': classification,
    }
    return result, rejection_reason


def inspect_repository_structure(owner, repo_name, branch, description=''):
    """Calculate documentation, media, code and educational signals from the tree."""
    empty = {
        field: ("unavailable" if field == 'tree_scan_status' else 0 if field.endswith('_count') or field.endswith('_ratio') else '')
        for field in STRUCTURAL_FIELDS
    }
    empty['structure_classification'] = 'unknown'
    tree_data = get_repository_tree(owner, repo_name, branch)
    if not tree_data or not isinstance(tree_data.get('tree'), list):
        empty['tree_scan_status'] = 'unavailable'
        return empty, None

    result, rejection_reason = analyze_tree_structure(tree_data['tree'], repo_name, description)
    if tree_data.get('truncated'):
        result['tree_scan_status'] = 'partial'
    return result, rejection_reason

def interactive_config():
    criteria = DEFAULT_CRITERIA.copy()
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print("\n=== Configuração de Critérios da Coleta ===")
        print(f"1. Estrelas mínimas: {criteria['min_stars']}")
        print(f"2. Watchers mínimos: {criteria['min_watchers']}")
        print(f"3. Proporção mínima de Clojure (0.0 a 1.0): {criteria['min_clojure_ratio']}")
        print(f"4. Commits mínimos: {criteria['min_commits']}")
        print(f"5. Contribuidores mínimos: {criteria['min_contributors']}")
        print(f"6. Proporção máxima do top contributor (0.0 a 1.0): {criteria['max_top_contributor_ratio']}")
        print(f"7. Tempo de vida mínimo (dias): {criteria['min_lifespan_days']}")
        print("0. INICIAR coleta com esses critérios")
        
        choice = input("\nEscolha um número para editar (ou 0 para iniciar): ").strip()
        
        if choice == '0':
            return criteria
        elif choice == '1':
            val = input("Novo valor para estrelas mínimas: ")
            if val.isdigit(): criteria['min_stars'] = int(val)
        elif choice == '2':
            val = input("Novo valor para watchers mínimos: ")
            if val.isdigit(): criteria['min_watchers'] = int(val)
        elif choice == '3':
            val = input("Novo valor para proporção mínima de Clojure (ex: 0.5): ")
            try: criteria['min_clojure_ratio'] = float(val)
            except ValueError: pass
        elif choice == '4':
            val = input("Novo valor para commits mínimos: ")
            if val.isdigit(): criteria['min_commits'] = int(val)
        elif choice == '5':
            val = input("Novo valor para contribuidores mínimos: ")
            if val.isdigit(): criteria['min_contributors'] = int(val)
        elif choice == '6':
            val = input("Novo valor para proporção máxima do top contributor (ex: 0.8): ")
            try: criteria['max_top_contributor_ratio'] = float(val)
            except ValueError: pass
        elif choice == '7':
            val = input("Novo valor para tempo de vida mínimo (dias): ")
            if val.isdigit(): criteria['min_lifespan_days'] = int(val)

def get_with_retry(url, params=None, max_retries=3):
    """
    Realiza requisições GET para a API do GitHub com tratamento de erros,
    paginação, conexão persistente (keep-alive) e limite de taxa.
    """
    for attempt in range(max_retries):
        try:
            response = SESSION.get(url, params=params, timeout=20)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 202:
                time.sleep(2)
            elif response.status_code == 403 and "rate limit" in response.text.lower():
                reset_time = int(response.headers.get("X-RateLimit-Reset", time.time() + 60))
                sleep_time = max(reset_time - time.time(), 0) + 1
                print(f"Limite de taxa excedido. Aguardando {sleep_time} segundos...")
                time.sleep(sleep_time)
            elif response.status_code == 404:
                return None
            else:
                print(f"Erro {response.status_code} na URL {url}")
                break
        except requests.RequestException as e:
            if attempt == max_retries - 1:
                print(f"Falha de conexão em {url}: {e}")
            time.sleep(1)
    return None

README_MAX_CHARS = 4000

def get_readme_preview(owner, repo_name, max_chars=README_MAX_CHARS):
    """
    Obtém um extrato significativo e estruturado do README do repositório (até max_chars)
    preservando quebras de linha e formatação Markdown para a validação manual.
    """
    url = f"https://api.github.com/repos/{owner}/{repo_name}/readme"
    headers = {"Accept": "application/vnd.github.v3.raw"}
    
    for attempt in range(2):
        try:
            response = SESSION.get(url, headers=headers, timeout=15)
            if response.status_code == 200:
                import re
                text = response.text.strip()
                # Normaliza quebras de linha excessivas mantendo parágrafos
                text = re.sub(r'\r\n', '\n', text)
                text = re.sub(r'\n{3,}', '\n\n', text)
                if len(text) > max_chars:
                    return text[:max_chars] + "\n\n... [README truncado para validação]"
                return text
            elif response.status_code == 404:
                return "(Sem README disponível)"
            elif response.status_code == 403 and "rate limit" in response.text.lower():
                time.sleep(2)
        except requests.RequestException:
            pass
    return "(Erro ao obter README)"

def process_repo(item, criteria):
    """
    Verifica se um repositório atende a todos os critérios.
    Retorna (dicionário_com_dados, string_com_motivo, desc_do_projeto)
    Se válido, string_com_motivo é None.
    """
    owner = item['owner']['login']
    repo_name = item['name']
    repo_id = item['full_name']
    desc = item['description'] or ""
    
    # Preenche um dict base com o que já sabemos
    repo_dict = {
        'repo_id': repo_id,
        'repo_url': item['html_url'],
        'clone_url': item['clone_url'],
        'default_branch': item['default_branch'],
        'size_kb': item.get('size', 0),
        'stars': item['stargazers_count'],
        'watchers': item.get('watchers_count', 0), # Fallback temporário
        'clojure_ratio': 0.0,
        'total_commits': 0,
        'lifespan_days': 0,
        'num_contributors': 0,
        'top_contributor_ratio': 0.0,
        'collected_at': datetime.now(timezone.utc).isoformat()
    }

    # 1. Watchers (subscribers_count) e Verificação de Arquivado
    details_url = f"https://api.github.com/repos/{owner}/{repo_name}"
    details = get_with_retry(details_url)
    if not details: 
        return repo_dict, "Erro ao obter detalhes (possível exclusão ou erro de API)", desc
        
    if item.get('archived') or details.get('archived'):
        return repo_dict, "Repositório arquivado no GitHub (read-only)", desc

    watchers = details.get('subscribers_count', 0)
    repo_dict['watchers'] = watchers
    if watchers < criteria['min_watchers']:
        return repo_dict, f"Watchers insuficientes ({watchers} < {criteria['min_watchers']})", desc

    # 2. Clojure Ratio
    langs_url = f"https://api.github.com/repos/{owner}/{repo_name}/languages"
    langs = get_with_retry(langs_url)
    if not langs:
        return repo_dict, "Não foi possível obter linguagens", desc
        
    total_bytes = sum(langs.values())
    if total_bytes == 0:
        return repo_dict, "Repositório vazio (0 bytes)", desc
    clojure_bytes = langs.get('Clojure', 0)
    clojure_ratio = clojure_bytes / total_bytes
    repo_dict['clojure_ratio'] = round(clojure_ratio, 4)
    if clojure_ratio < criteria['min_clojure_ratio']:
        return repo_dict, f"Clojure ratio menor que o exigido ({clojure_ratio:.2f} < {criteria['min_clojure_ratio']})", desc

    # 3. Atividade e Contributors
    stats_url = f"https://api.github.com/repos/{owner}/{repo_name}/stats/contributors"
    stats = get_with_retry(stats_url)
    if not stats or not isinstance(stats, list):
        return repo_dict, "Não foi possível obter estatísticas de contributors (API 202 ou erro)", desc
        
    num_contributors = len(stats)
    repo_dict['num_contributors'] = num_contributors
    if num_contributors < criteria['min_contributors']:
        return repo_dict, f"Contribuidores insuficientes ({num_contributors} < {criteria['min_contributors']})", desc
        
    total_commits = 0
    max_commits_by_single_user = 0
    first_commit_time = float('inf')
    last_commit_time = 0
    
    for contributor in stats:
        commits = contributor['total']
        total_commits += commits
        if commits > max_commits_by_single_user:
            max_commits_by_single_user = commits
            
        for week in contributor['weeks']:
            if week['c'] > 0:
                if week['w'] < first_commit_time:
                    first_commit_time = week['w']
                if week['w'] > last_commit_time:
                    last_commit_time = week['w']
                    
    repo_dict['total_commits'] = total_commits
    if total_commits < criteria['min_commits']:
        return repo_dict, f"Commits insuficientes ({total_commits} < {criteria['min_commits']})", desc
        
    top_contributor_ratio = max_commits_by_single_user / total_commits if total_commits > 0 else 0
    repo_dict['top_contributor_ratio'] = round(top_contributor_ratio, 4)
    if top_contributor_ratio > criteria['max_top_contributor_ratio']:
        return repo_dict, f"Concentração alta do top contributor ({top_contributor_ratio:.2f} > {criteria['max_top_contributor_ratio']})", desc
        
    lifespan_days = (last_commit_time - first_commit_time) / (60 * 60 * 24)
    repo_dict['lifespan_days'] = int(lifespan_days)
    if lifespan_days < criteria['min_lifespan_days']:
        return repo_dict, f"Tempo de vida insuficiente ({int(lifespan_days)} dias < {criteria['min_lifespan_days']})", desc

    # 4. Triagem estrutural baseada em proporção real de conteúdo e build descriptors
    structure, structure_reason = inspect_repository_structure(
        owner, repo_name, item['default_branch'], desc,
    )
    repo_dict.update(structure)

    if structure_reason:
        return repo_dict, f"Descartado por análise estrutural ({structure_reason})", desc

    # Passou em tudo!
    return repo_dict, None, desc

def main():
    if not GITHUB_TOKEN:
        print("AVISO: GITHUB_TOKEN não definido no .env. A taxa de requisições será muito limitada (60/hora).")
    
    criteria = interactive_config()
    
    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    criteria_file = reports_dir / "criterios_coleta.json"
    temp_file = reports_dir / "criterios_coleta.tmp.json"
    
    criteria_to_save = {"saved_at": datetime.now(timezone.utc).isoformat()}
    criteria_to_save.update(criteria)
    
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(criteria_to_save, f, indent=4)
    temp_file.replace(criteria_file)
    print(f"Critérios salvos em {criteria_file}")
    
    csv_file = "repositorios_clojure_alvo.csv"
    pending_csv = "repositorios_pendentes_avaliacao.csv"
    invalid_csv = "repositorios_invalidos.csv"
    
    file_exists = os.path.isfile(csv_file)
    pending_exists = os.path.isfile(pending_csv)
    invalid_exists = os.path.isfile(invalid_csv)
    
    fieldnames = [
        'repo_id', 'repo_url', 'clone_url', 'default_branch', 'size_kb', 'stars', 
        'watchers', 'clojure_ratio', 'total_commits', 'lifespan_days', 
        'num_contributors', 'top_contributor_ratio', 'collected_at',
        'about', 'readme_preview'
    ] + STRUCTURAL_FIELDS
    pending_fieldnames = fieldnames + ['motivo']
    invalid_fieldnames = fieldnames + ['motivo']
    
    processed_repos = set()
    total_size_kb = 0
    
    if file_exists:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                processed_repos.add(row['repo_id'])
                if 'size_kb' in row and row['size_kb']:
                    total_size_kb += int(row['size_kb'])
                    
    if pending_exists:
        with open(pending_csv, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                processed_repos.add(row['repo_id'])

    if invalid_exists:
        with open(invalid_csv, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                processed_repos.add(row['repo_id'])
                
    # Mantém CSVs antigos legíveis e migra colunas se necessário
    for path, expected_fields in ((csv_file, fieldnames), (pending_csv, pending_fieldnames), (invalid_csv, invalid_fieldnames)):
        if not os.path.isfile(path):
            continue
        with open(path, 'r', newline='', encoding='utf-8') as existing:
            reader = csv.DictReader(existing)
            old_fields = reader.fieldnames or []
            if set(expected_fields).issubset(old_fields):
                continue
            rows = list(reader)
        with tempfile.NamedTemporaryFile('w', newline='', encoding='utf-8', delete=False, dir='.') as migrated:
            writer = csv.DictWriter(migrated, fieldnames=expected_fields)
            writer.writeheader()
            for row in rows:
                writer.writerow({field: row.get(field, '') for field in expected_fields})
            temporary = migrated.name
        os.replace(temporary, path)

    file_exists = os.path.isfile(csv_file)
    pending_exists = os.path.isfile(pending_csv)
    invalid_exists = os.path.isfile(invalid_csv)

    with open(csv_file, 'a', newline='', encoding='utf-8') as f, \
         open(pending_csv, 'a', newline='', encoding='utf-8') as pend_f, \
         open(invalid_csv, 'a', newline='', encoding='utf-8') as inv_f:
         
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        pend_writer = csv.DictWriter(pend_f, fieldnames=pending_fieldnames)
        inv_writer = csv.DictWriter(inv_f, fieldnames=invalid_fieldnames)
        
        if not file_exists:
            writer.writeheader()
        if not pending_exists:
            pend_writer.writeheader()
        if not invalid_exists:
            inv_writer.writeheader()
            
        page = 1
        max_pages = 34
        
        print("\nIniciando coleta de repositórios Clojure...")
        
        while page <= max_pages:
            print(f"Consultando página {page} da pesquisa...")
            search_url = "https://api.github.com/search/repositories"
            params = {
                "q": f"language:clojure stars:>={criteria['min_stars']} fork:false archived:false",
                "sort": "stars",
                "order": "desc",
                "per_page": 30,
                "page": page
            }
            
            response = get_with_retry(search_url, params=params)
            if not response or 'items' not in response or not response['items']:
                break
                
            for item in response['items']:
                repo_id = item['full_name']
                
                if repo_id in processed_repos:
                    continue

                print(f"Analisando: {repo_id}...")
                repo_dict, reason, desc = process_repo(item, criteria)
                
                size_kb = repo_dict.get('size_kb', 0)
                size_mb = size_kb / 1024
                total_size_kb += size_kb
                
                readme_preview = get_readme_preview(item['owner']['login'], item['name'])
                repo_dict['about'] = desc
                repo_dict['readme_preview'] = readme_preview

                if reason is not None:
                    print(f"INVÁLIDO AUTOMÁTICO: {repo_id} - Motivo: {reason}")
                    invalid_dict = repo_dict.copy()
                    invalid_dict['motivo'] = reason
                    inv_writer.writerow(invalid_dict)
                    inv_f.flush()
                else:
                    print(f"VÁLIDO AUTOMÁTICO: {repo_id} (Tamanho aprox: {size_mb:.2f} MB) - Adicionado ao alvo.csv.")
                    writer.writerow(repo_dict)
                    f.flush()
                    
                processed_repos.add(repo_id)
                time.sleep(1)
                
            page += 1
            
        print("\n=== Resumo da Coleta ===")
        total_size_mb = total_size_kb / 1024
        total_size_gb = total_size_mb / 1024
        print(f"Total de repositórios (válidos ou inválidos) varridos/analisados: {len(processed_repos)}")
        print(f"Tamanho total aproximado dos VÁLIDOS (incluindo histórico do Git): {total_size_mb:.2f} MB ({total_size_gb:.2f} GB)")

if __name__ == "__main__":
    main()
