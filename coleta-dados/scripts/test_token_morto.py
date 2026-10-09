"""Teste sem framework: token 401 "Bad credentials" é aposentado e a thread
segue com outro token, sem levantar erro (o repositório não vira "error").

Rodar: cd scripts && ../venv/bin/python test_token_morto.py
"""

import itertools
import tempfile
from pathlib import Path

import common


class FakeResponse:
    def __init__(self, status_code, text):
        self.status_code = status_code
        self.text = text
        self.url = "https://api.github.com/x"
        self.headers = {}


# tokens que o "GitHub" falso recusa com 401
revogados = {"dead-OiN0"}


class FakeSession:
    def __init__(self):
        self.headers = {}

    def get(self, url, params=None, timeout=None):
        token = common._thread_local.assigned_token
        self.headers["Authorization"] = f"Bearer {token}"
        if token in revogados:
            return FakeResponse(401, '{"message": "Bad credentials"}')
        return FakeResponse(200, "{}")


def main():
    common.token_pool.tokens = ["dead-OiN0", "live-AAAA"]
    common._token_cycle = itertools.cycle(common.token_pool.tokens)
    common._thread_local.assigned_token = "dead-OiN0"
    fake = FakeSession()
    common.get_thread_session = lambda: fake
    common.dead_tokens_file = Path(tempfile.mkdtemp()) / "tokens_mortos.txt"

    response = common.get_response_with_retry("https://api.github.com/x")

    assert response.status_code == 200
    assert common._thread_local.assigned_token == "live-AAAA"
    assert common.dead_tokens_file.read_text() == "...OiN0\n"

    # o outro token também é revogado: sem token vivo, cai no erro de sempre
    revogados.add("live-AAAA")
    try:
        common.get_response_with_retry("https://api.github.com/x")
        raise AssertionError("devia levantar")
    except RuntimeError as exc:
        assert "Falha ao acessar" in str(exc)
    print("ok")


def test_fila_poe_erro_401_na_frente():
    repo_status = {
        "1": {"status": "error", "error": "Token ...x retornou 422 para u"},
        "2": {"status": "error", "error": "Token ...OiN0 retornou 401 para u"},
        "3": {},
        "4": {"status": "error", "error": "Token ...OiN0 retornou 401 para u"},
    }
    pending = [(i, {"repo_id": i}) for i in (1, 2, 3, 4)]
    ordered = common._prioritize_dead_token_errors(pending, repo_status)
    # 401 na frente (2, 4), nunca tentado no meio (3), erro permanente 422 por último (1)
    assert [item[0] for item in ordered] == [2, 4, 3, 1]

    repo_status = {
        "1": {"status": "error", "error": "Token ...x retornou 403 para u"},
        "2": {"status": "error", "error": "Token ...x retornou 451 para u"},
        "3": {"status": "error", "error": "git clone: timeout"},  # transitório: não vai para o fim
        "4": {},
        "5": {"status": "error", "error": "Token ...x retornou 401 para u"},
    }
    pending = [(i, {"repo_id": i}) for i in (1, 2, 3, 4, 5)]
    ordered = common._prioritize_dead_token_errors(pending, repo_status)
    assert [item[0] for item in ordered] == [5, 3, 4, 1, 2]


if __name__ == "__main__":
    main()
    test_fila_poe_erro_401_na_frente()
    print("ok fila")
