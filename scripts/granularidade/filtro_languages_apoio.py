"""Classificação da coluna `languages` da SEART, compartilhada por `filtro_languages.py` e `lista_vazios.py`."""

import json


def le_bytes(texto: object) -> dict | None:
    """Objeto JSON com bytes por linguagem, ou None se o texto não tem esse formato (vazio fica de fora, ver `classifica`)."""
    try:
        mapa = json.loads(str(texto))
    except ValueError:
        return None
    if not isinstance(mapa, dict):
        return None
    for v in mapa.values():
        if not isinstance(v, (int, float)):
            return None
    return mapa


def classifica(texto: object, linguagem: str) -> tuple[str, float, str]:
    """Categoria, participação da linguagem e a linguagem com mais bytes (vazio se não houver objeto)."""
    categoria, participacao, maior = "outro formato", 0.0, ""
    vazio = not isinstance(texto, str) or texto.strip() == ""
    mapa = None if vazio else le_bytes(texto)
    if vazio:
        categoria = "vazia"
    elif mapa is not None:
        total = sum(mapa.values())
        if total <= 0:
            categoria = "vazia"
        else:
            maior = max(mapa, key=lambda nome: mapa[nome])
            participacao = mapa.get(linguagem, 0) / total
            if mapa.get(linguagem, 0) <= 0:
                categoria = "sem a linguagem"
            elif participacao > 0.5:
                categoria = "com a linguagem acima de 50%"
            else:
                categoria = "com a linguagem abaixo de 50%"
    return categoria, participacao, maior
