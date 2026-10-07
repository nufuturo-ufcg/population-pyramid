"""Teste sem framework: o token para de gastar quando chega a 1% da cota.

Rodar: cd scripts && ../venv/bin/python test_reserva_de_cota.py
"""

import time

from requests.structures import CaseInsensitiveDict

import common


class FakeResponse:
    """Resposta 200 do GitHub com os cabeçalhos de cota."""

    def __init__(self, remaining: int) -> None:
        self.status_code = 200
        self.text = "{}"
        self.url = "https://api.github.com/x"
        self.headers = CaseInsensitiveDict(
            {
                "X-RateLimit-Remaining": str(remaining),
                "X-RateLimit-Limit": "5000",
                "X-RateLimit-Reset": str(int(time.time()) + 30),
            }
        )


class FakeSession:
    """Sessão que devolve sempre a mesma resposta."""

    def __init__(self, remaining: int) -> None:
        self.headers: dict[str, str] = {}
        self.remaining = remaining

    def get(self, url: str, params: dict | None = None, timeout: int | None = None) -> FakeResponse:
        """Devolve a resposta falsa, ignorando os argumentos."""
        return FakeResponse(self.remaining)


def esperas_com(remaining: int) -> list[float]:
    """Roda uma chamada com `remaining` requisições restantes e devolve os sleeps."""
    esperas: list[float] = []
    sleep_original = common.time.sleep
    common.time.sleep = esperas.append
    common._thread_local.assigned_token = "token-de-teste"
    common.get_thread_session = lambda: FakeSession(remaining)
    try:
        resposta = common.get_response_with_retry("https://api.github.com/x")
    finally:
        common.time.sleep = sleep_original
    assert resposta.status_code == 200  # o dado da chamada que bateu na reserva é aproveitado
    return esperas


def main() -> None:
    """Acima da reserva segue direto; na reserva (50 de 5000) espera o reset."""
    assert esperas_com(4000) == []
    assert esperas_com(51) == []  # 51 > 50: ainda pode gastar
    esperas = esperas_com(50)  # chegou na reserva
    assert len(esperas) == 1 and 25 < esperas[0] <= 32
    assert len(esperas_com(0)) == 1
    print("ok")


if __name__ == "__main__":
    main()
