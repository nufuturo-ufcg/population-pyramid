"""Item 0 de `projecao-rq3/correcao-elegibilidade/hipoteses.md`: tokens válidos do `.env` da coleta e a cota restante de cada um.

Lê `GITHUB_TOKEN=` do `.env`, chama `GET /rate_limit` (que não gasta cota) e imprime uma linha por token com um rótulo (`<host>-<n>`), o status, a cota restante e a expiração.
Os valores dos tokens não são impressos nem gravados.

Uso: python3 checa_tokens.py <host> <.env>
"""

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

HOST, ENV = sys.argv[1], Path(sys.argv[2])
tokens = []
for linha in ENV.read_text(encoding="utf-8").splitlines():
    if linha.startswith("GITHUB_TOKEN="):
        tokens.append(linha.split("=", 1)[1].strip())
print("rotulo,status,restante,limite,reinicio_em_minutos,expira")
for numero, token in enumerate(tokens, start=1):
    pedido = urllib.request.Request(
        "https://api.github.com/rate_limit",
        headers={"Authorization": f"Bearer {token}", "User-Agent": "coleta-pesquisa"},
    )
    try:
        with urllib.request.urlopen(pedido, timeout=30) as resposta:
            nucleo = json.loads(resposta.read())["resources"]["core"]
            expira = resposta.headers.get("github-authentication-token-expiration", "sem data")
            import time

            minutos = max(0, round((nucleo["reset"] - time.time()) / 60))
            print(f"{HOST}-{numero},200,{nucleo['remaining']},{nucleo['limit']},{minutos},{expira}")
    except urllib.error.HTTPError as erro:
        print(f"{HOST}-{numero},{erro.code},,,,")
