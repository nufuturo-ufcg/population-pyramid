"""Item 1 de `projecao-rq3/correcao-elegibilidade/hipoteses.md`: `GET /repos/{owner}/{repo}/languages` para os candidatos com `languages` vazio na SEART.

Um fio de execução por token válido do `.env`, cada um com a cota lida dos cabeçalhos de cada resposta. Reserva de 1% da cota para o dono do token.
Só usa a biblioteca padrão e não grava nem imprime o valor dos tokens (eles aparecem como `<host>-<n>`).
Retomável: o CSV de saída é gravado a cada resposta. Ao reiniciar, os repositórios com resposta final são pulados e os com erro transitório são refeitos.

Resposta final: 200, 404, 451, 410 e 403 de bloqueio do repositório. Resto (rede, 5xx, 403 de limite, 429) é transitório.

Uso: python3 consulta_languages.py <host> <.env> <entrada.csv> <saida.csv>
  entrada.csv: repo_id, repo_name, linguagem
"""

import csv
import json
import queue
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

HOST, ENV, ENTRADA, SAIDA = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
RESERVA = 50  # 1% de 5.000
ALVO = {
    "python": "Python",
    "clojure": "Clojure",
    "elixir": "Elixir",
    "ocaml": "OCaml",
    "zig": "Zig",
}
FINAIS = {200, 404, 410, 451}
COLUNAS = [
    "repo_id",
    "repo_name",
    "linguagem",
    "http_status",
    "bytes_por_linguagem",
    "linguagem_alvo",
    "fracao_linguagem_alvo",
    "data_consulta",
    "url_final",
    "mensagem",
]
trava_saida = threading.Lock()
trava_log = threading.Lock()
contagem = {"feitos": 0, "tokens_vivos": 0}


def agora() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(texto: str) -> None:
    with trava_log:
        print(f"{agora()} {texto}", flush=True)


def pede(url: str, token: str) -> tuple[int, dict, str, str]:
    """Status, cabeçalhos (minúsculos), corpo e URL final. Status 0 é erro de rede."""
    pedido = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "coleta-pesquisa",
        },
    )
    try:
        with urllib.request.urlopen(pedido, timeout=40) as resposta:
            cab = {k.lower(): v for k, v in resposta.headers.items()}
            return (
                resposta.status,
                cab,
                resposta.read().decode("utf-8", errors="replace"),
                resposta.geturl(),
            )
    except urllib.error.HTTPError as erro:
        cab = {k.lower(): v for k, v in erro.headers.items()}
        return erro.code, cab, erro.read().decode("utf-8", errors="replace"), url
    except (urllib.error.URLError, TimeoutError, OSError) as erro:
        return 0, {}, str(erro)[:200], url


def eh_final(status: int, corpo: str) -> bool:
    if status in FINAIS:
        return True
    return status == 403 and "blocked" in corpo.lower()


def dorme_ate(reinicio: int) -> None:
    espera = max(5, reinicio - int(time.time()) + 5)
    time.sleep(espera)


tokens = []
for linha in ENV.read_text(encoding="utf-8").splitlines():
    if linha.startswith("GITHUB_TOKEN="):
        tokens.append(linha.split("=", 1)[1].strip())

fila: queue.Queue = queue.Queue()
ja_feitos = set()
if SAIDA.exists():
    with SAIDA.open(encoding="utf-8", newline="") as arquivo:
        for linha in csv.DictReader(arquivo):
            if eh_final(int(linha["http_status"]), linha["mensagem"]):
                ja_feitos.add((linha["linguagem"], linha["repo_id"]))
novo_arquivo = not SAIDA.exists()
saida = SAIDA.open("a", encoding="utf-8", newline="")
escritor = csv.DictWriter(saida, fieldnames=COLUNAS)
if novo_arquivo:
    escritor.writeheader()
    saida.flush()
pendentes = 0
with ENTRADA.open(encoding="utf-8", newline="") as arquivo:
    for linha in csv.DictReader(arquivo):
        if (linha["linguagem"], linha["repo_id"]) not in ja_feitos:
            fila.put(linha)
            pendentes += 1
log(f"{HOST}: {pendentes} repositórios a consultar, {len(ja_feitos)} já feitos")


def grava(linha: dict) -> None:
    with trava_saida:
        escritor.writerow(linha)
        saida.flush()
        contagem["feitos"] += 1
        if contagem["feitos"] % 1000 == 0:
            log(
                f"{HOST}: {contagem['feitos']} consultas gravadas, {fila.qsize()} na fila, {contagem['tokens_vivos']} tokens vivos"
            )


def trabalha(rotulo: str, token: str) -> None:
    """Consome a fila com um token até a fila esvaziar ou o token morrer."""
    status, cab, corpo, _ = pede("https://api.github.com/rate_limit", token)
    if status != 200:
        log(f"{rotulo}: token fora (status {status})")
        return
    nucleo = json.loads(corpo)["resources"]["core"]
    restante, reinicio = nucleo["remaining"], nucleo["reset"]
    contagem["tokens_vivos"] += 1
    while True:
        if restante <= RESERVA:
            log(f"{rotulo}: cota no fim da janela, espera até o reinício")
            dorme_ate(reinicio)
            status, cab, corpo, _ = pede("https://api.github.com/rate_limit", token)
            if status != 200:
                break
            nucleo = json.loads(corpo)["resources"]["core"]
            restante, reinicio = nucleo["remaining"], nucleo["reset"]
            continue
        try:
            item = fila.get_nowait()
        except queue.Empty:
            break
        url = f"https://api.github.com/repos/{urllib.parse.quote(item['repo_name'], safe='/')}/languages"
        for tentativa in range(4):
            status, cab, corpo, url_final = pede(url, token)
            if "x-ratelimit-remaining" in cab:
                restante = int(cab["x-ratelimit-remaining"])
                reinicio = int(cab.get("x-ratelimit-reset", reinicio))
            if status == 401:
                break
            if status in (403, 429) and not eh_final(status, corpo):
                espera = int(cab.get("retry-after", 60))
                if restante == 0:
                    dorme_ate(reinicio)
                else:
                    time.sleep(espera)
                continue
            if status == 0 or status >= 500:
                time.sleep(2**tentativa * 3)
                continue
            break
        if status == 401:
            fila.put(item)
            log(f"{rotulo}: token morreu no meio da consulta")
            break
        bytes_json, fracao = "", ""
        if status == 200:
            mapa = json.loads(corpo)
            total = sum(mapa.values())
            bytes_json = json.dumps(mapa, separators=(",", ":"))
            alvo = ALVO[item["linguagem"]]
            fracao = f"{mapa.get(alvo, 0) / total:.6f}" if total else ""
        mensagem = "" if status == 200 else corpo.replace("\n", " ")[:160]
        grava(
            {
                "repo_id": item["repo_id"],
                "repo_name": item["repo_name"],
                "linguagem": item["linguagem"],
                "http_status": status,
                "bytes_por_linguagem": bytes_json,
                "linguagem_alvo": ALVO[item["linguagem"]],
                "fracao_linguagem_alvo": fracao,
                "data_consulta": agora(),
                "url_final": url_final if status == 200 else "",
                "mensagem": mensagem,
            }
        )
    contagem["tokens_vivos"] -= 1
    log(f"{rotulo}: fio terminado")


fios = []
for numero, token in enumerate(tokens, start=1):
    fio = threading.Thread(target=trabalha, args=(f"{HOST}-{numero}", token), daemon=True)
    fio.start()
    fios.append(fio)
for fio in fios:
    fio.join()
log(f"{HOST}: fim. Gravadas nesta execução: {contagem['feitos']}. Restam na fila: {fila.qsize()}")
saida.close()
