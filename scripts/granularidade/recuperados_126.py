"""Os 126 não elegíveis de Python sem evento, depois da nova tentativa de coleta (item 1 de `correcao-elegibilidade/hipoteses.md`).

Lê em `<pasta>/dados/`: `ids_126.csv`, `candidatos_compacto.csv`, `consulta_languages.csv` e
`coleta-126/` (`eventos_repositorios.csv` e os progressos 2A e 2B da nova tentativa).
Grava `<pasta>/recuperados_126.csv` (um repositório por linha) e `<pasta>/secao_126.md`.

Uso (na raiz do repo): .venv/bin/python scripts/granularidade/recuperados_126.py <correcao-elegibilidade>
"""

import csv
import json
import re
import sys
from pathlib import Path

PASTA = Path(sys.argv[1])
DADOS = PASTA / "dados"
COLETA = DADOS / "coleta-126"
ELEGIVEL_SEART = "com a linguagem acima de 50%"
csv.field_size_limit(sys.maxsize)

ids = []
with (DADOS / "ids_126.csv").open(encoding="utf-8", newline="") as arquivo:
    for linha in csv.DictReader(arquivo):
        ids.append(linha["repo_id"])
alvo = set(ids)

candidatos = {}
with (DADOS / "candidatos_compacto.csv").open(encoding="utf-8", newline="") as arquivo:
    for linha in csv.DictReader(arquivo):
        if linha["linguagem"] == "python" and linha["repo_id"] in alvo:
            candidatos[linha["repo_id"]] = linha

consulta = {}
with (DADOS / "consulta_languages.csv").open(encoding="utf-8", newline="") as arquivo:
    for linha in csv.DictReader(arquivo):
        if linha["linguagem"] == "python" and linha["repo_id"] in alvo:
            consulta[linha["repo_id"]] = linha

eventos = {}
ultimo = {}
with (COLETA / "eventos_repositorios.csv").open(encoding="utf-8", newline="") as arquivo:
    for linha in csv.DictReader(arquivo, delimiter="|"):
        repo = linha["repo_id"]
        eventos.setdefault(repo, {})
        tipo = linha["event_type"]
        eventos[repo][tipo] = eventos[repo].get(tipo, 0) + 1
        ano = linha["created_at"][:4]
        if repo not in ultimo or ano > ultimo[repo]:
            ultimo[repo] = ano


def causa(registro: dict) -> str:
    """Código de erro de uma etapa: `complete`, `403`, `451` ou o motivo do git."""
    if registro["status"] == "complete":
        return "completa"
    texto = str(registro.get("error", ""))
    achou = re.search(r"retornou (\d+)", texto)
    if achou:
        return achou.group(1)
    if "could not read Username" in texto:
        return "clone sem acesso"
    return "outro erro do git"


progresso = {}
for etapa in ("2A", "2B"):
    caminho = COLETA / "reports" / f"etapa_{etapa}_progresso.json"
    progresso[etapa] = json.loads(caminho.read_text(encoding="utf-8"))["repositories"]

linhas = []
for repo in ids:
    cand = candidatos[repo]
    api = consulta.get(repo)
    categoria = cand["categoria"]
    fonte, fracao, elegivel = "", "", "não"
    if categoria == ELEGIVEL_SEART:
        fonte, fracao, elegivel = "seart", cand["fracao_seart"], "sim"
    elif categoria == "vazia" and api is not None and api["http_status"] == "200":
        fonte, fracao = "api", api["fracao_linguagem_alvo"]
        if fracao and float(fracao) > 0.5:
            elegivel = "sim"
    resposta_api = api["http_status"] if api is not None else ""
    por_tipo = eventos.get(repo, {})
    linhas.append(
        {
            "repo_id": repo,
            "repo_name": cand["repo_name"],
            "categoria_seart": categoria,
            "resposta_api_languages": resposta_api,
            "fonte_fracao": fonte,
            "fracao_linguagem": fracao,
            "elegivel_regra_nova": elegivel,
            "etapa_2A": causa(progresso["2A"][repo]),
            "etapa_2B": causa(progresso["2B"][repo]) if repo in progresso["2B"] else "sem registro",
            "eventos": sum(por_tipo.values()),
            "ultimo_evento_ano": ultimo.get(repo, ""),
        }
    )

with (PASTA / "recuperados_126.csv").open("w", encoding="utf-8", newline="") as arquivo:
    escritor = csv.DictWriter(arquivo, fieldnames=list(linhas[0].keys()))
    escritor.writeheader()
    escritor.writerows(linhas)

com_dados = []
sem_dados = []
for linha in linhas:
    if linha["eventos"] > 0:
        com_dados.append(linha)
    else:
        sem_dados.append(linha)

grupos: dict[tuple[str, str], int] = {}
for linha in sem_dados:
    chave = (linha["etapa_2A"], linha["etapa_2B"])
    grupos[chave] = grupos.get(chave, 0) + 1

elegiveis_novos = 0
for linha in linhas:
    if linha["elegivel_regra_nova"] == "sim":
        elegiveis_novos += 1
elegiveis_sem_dados = 0
for linha in sem_dados:
    if linha["elegivel_regra_nova"] == "sim":
        elegiveis_sem_dados += 1

texto = [
    "## 5. Os 126 não elegíveis sem evento, depois da nova tentativa de coleta",
    "",
    f"- Dos 126, {elegiveis_novos} são elegíveis pela regra nova (todos pela API, com a SEART vazia).",
    f"- {len(com_dados)} repositórios passaram a ter evento e {len(sem_dados)} continuam sem nenhum.",
    f"- Dos {len(sem_dados)} sem dados, {elegiveis_sem_dados} são elegíveis pela regra nova e entram na carga sem evento.",
    "",
    "### Os 4 com dados, pela regra do item 2",
    "",
    "| Repositório | Categoria na SEART | Resposta da API | Fonte da fração | Fração | Elegível | Eventos | Ano do último evento |",
    "|---|---|---|---|---|---|---|---|",
]
for linha in com_dados:
    fracao = linha["fracao_linguagem"]
    fracao_txt = f"{100 * float(fracao):.1f}%".replace(".", ",") if fracao else "n/d"
    texto.append(
        f"| {linha['repo_name']} | {linha['categoria_seart']} | {linha['resposta_api_languages'] or 'n/d'}"
        f" | {linha['fonte_fracao'] or 'nenhuma'} | {fracao_txt} | {linha['elegivel_regra_nova']}"
        f" | {linha['eventos']} | {linha['ultimo_evento_ano']} |"
    )
texto += [
    "",
    f"### Os {len(sem_dados)} sem dados, por código de erro",
    "",
    "| Etapa 2A (API) | Etapa 2B (git) | Repositórios |",
    "|---|---|---|",
]
for (a, b), n in sorted(grupos.items(), key=lambda x: -x[1]):
    texto.append(f"| {a} | {b} | {n} |")
texto.append(f"| Total | | {len(sem_dados)} |")

(PASTA / "secao_126.md").write_text("\n".join(texto) + "\n", encoding="utf-8")
print("\n".join(texto))
