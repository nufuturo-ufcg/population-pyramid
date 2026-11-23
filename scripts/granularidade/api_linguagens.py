"""Item 3 de `projecao-rq3/filtro-python/hipoteses.md`: consulta `GET /repos/{owner}/{repo}/languages` da API do GitHub para a amostra de 50 repositórios.

Lê `<saida>/amostra_api.csv` e o `.env` da coleta (o token não é impresso nem gravado). Grava `<saida>/api_linguagens.csv`.

Uso (na VM): .venv/bin/python scripts/granularidade/api_linguagens.py <env da coleta> <saida>
"""

import csv
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ENV, SAIDA = Path(sys.argv[1]), Path(sys.argv[2])

tokens = []
for linha in ENV.read_text(encoding="utf-8").splitlines():
    if linha.startswith("GITHUB_TOKEN="):
        tokens.append(linha.split("=", 1)[1].strip())
if not tokens:
    sys.exit("nenhum token no .env")


def consulta(url: str, token: str) -> tuple[int, str, str]:
    """Status HTTP, URL final (depois de redirecionamentos) e o corpo."""
    pedido = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "coleta-pesquisa",
        },
    )
    try:
        with urllib.request.urlopen(pedido, timeout=30) as resposta:
            return resposta.status, resposta.geturl(), resposta.read().decode("utf-8")
    except urllib.error.HTTPError as erro:
        return erro.code, url, erro.read().decode("utf-8", errors="replace")


# escolhe o primeiro token que a API aceita (401 é token morto)
indice = 0
while indice < len(tokens):
    status, _, _ = consulta("https://api.github.com/rate_limit", tokens[indice])
    if status == 200:
        break
    indice += 1
if indice == len(tokens):
    sys.exit("nenhum token aceito pela API")
token = tokens[indice]

linhas = []
with (SAIDA / "amostra_api.csv").open(encoding="utf-8") as arquivo:
    for repo in csv.DictReader(arquivo):
        status, url_final, corpo = consulta(
            f"https://api.github.com/repos/{repo['repo_name']}/languages", token
        )
        bytes_python, bytes_total, maior, participacao = 0, 0, "", ""
        if status == 200:
            mapa = json.loads(corpo)
            bytes_total = sum(mapa.values())
            bytes_python = mapa.get("Python", 0)
            if bytes_total:
                maior = max(mapa, key=lambda nome: mapa[nome])
                participacao = bytes_python / bytes_total
        linhas.append(
            {
                "repo_id": repo["repo_id"],
                "repo_name": repo["repo_name"],
                "http_status": status,
                "url_final": url_final,
                "bytes_python": bytes_python,
                "bytes_total": bytes_total,
                "participacao_python_hoje": participacao,
                "maior_linguagem_hoje": maior,
                "participacao_python_seart": repo["participacao"],
            }
        )
        time.sleep(0.5)

with (SAIDA / "api_linguagens.csv").open("w", newline="", encoding="utf-8") as arquivo:
    escritor = csv.DictWriter(arquivo, fieldnames=list(linhas[0]))
    escritor.writeheader()
    escritor.writerows(linhas)
print(f"{len(linhas)} consultas feitas")
