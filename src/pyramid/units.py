"""Unidade de análise: uma pirâmide por quê.

O adaptador entrega escopo. `analysis.unit` decide se cada escopo do adaptador
vira uma pirâmide, ou se vários deles são somados numa só.

`project` devolve o que o adaptador expõe, um para um. `language` agrupa os
escopos que compartilham `scope_meta.language`, e é a unidade que responde
"quem escreve Clojure", somando os N repositórios da linguagem.

A soma acontece em `extract`, antes de `classify.profile()`. Isso importa: o
`profile` calcula o primeiro evento e os períodos de atividade com um
`groupby("contributor_id")` dentro do escopo. Somando antes, quem mexe em cinco
repositórios Clojure é uma pessoa só, com a idade contada do evento mais antigo
entre os cinco, e um silêncio no repositório A que a atividade no B preenche não
quebra o período. Somando pirâmides prontas, a mesma pessoa vira cinco pessoas,
cada uma nascendo na estreia do repositório dela.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .config import analysis_unit

if TYPE_CHECKING:
    from .sources.base import ActivityDataSource

# Rótulo do grupo que junta escopo sem linguagem declarada. Ele é extraído e
# contado, e some das figuras, porque "unknown" não é uma linguagem.
SEM_LINGUAGEM = "unknown"


@dataclass(frozen=True)
class Escopo:
    """Uma pirâmide: o id que a nomeia e os escopos do adaptador que ela soma."""

    id: int
    label: str
    membros: tuple[int, ...]
    meta: dict[str, Any]

    @property
    def plotavel(self) -> bool:
        """Escopo sem linguagem é contado e não vira figura."""
        return self.meta.get("language") is not None


def id_da_linguagem(nome: str) -> int:
    """Id estável de uma linguagem, derivado só do nome.

    Índice numa lista ordenada seria mais legível e não serve: incluir um
    repositório de uma linguagem nova reordenaria a lista e mudaria o id de
    todas as outras, e os parquets gravados antes continuariam no disco com o
    nome de outra linguagem.

    O rótulo legível sai de `scope_label`, e o manifesto guarda os dois, que é o
    que `CONTRIBUTING.md` exige de artefato que mostra id.
    """
    return int(hashlib.sha1(nome.encode()).hexdigest()[:8], 16)


def _por_linguagem(src: ActivityDataSource) -> list[Escopo]:
    """Um escopo por linguagem, somando os escopos do adaptador que a têm."""
    grupos: dict[str, list[int]] = {}
    nascimento: dict[str, Any] = {}
    for sid in src.list_scopes():
        meta = src.scope_meta(sid)
        nome = meta.get("language") or SEM_LINGUAGEM
        grupos.setdefault(nome, []).append(sid)
        criado = meta.get("created_at")
        if criado is not None and (nascimento.get(nome) is None or criado < nascimento[nome]):
            nascimento[nome] = criado

    saida = [
        Escopo(
            id=id_da_linguagem(nome),
            label=nome,
            membros=tuple(membros),
            meta={
                "label": nome,
                "language": None if nome == SEM_LINGUAGEM else nome,
                "created_at": nascimento.get(nome),
                "membros": len(membros),
            },
        )
        for nome, membros in sorted(grupos.items())
    ]
    if len({e.id for e in saida}) != len(saida):
        colisao = sorted(e.label for e in saida)
        raise ValueError(f"duas linguagens com o mesmo id: {colisao}")
    return saida


def scopes_of_unit(src: ActivityDataSource) -> list[Escopo]:
    """Os escopos lógicos da unidade configurada, em ordem estável."""
    unit = analysis_unit()
    if unit == "language":
        return _por_linguagem(src)
    # O rótulo sai do `scope_meta`, e não do `scope_label`. O contrato exige que
    # os dois digam a mesma coisa (`test_scope_meta_label_bate_com_scope_label`),
    # e assim é uma pergunta só por escopo.
    escopos = []
    for sid in src.list_scopes():
        meta = src.scope_meta(sid)
        escopos.append(Escopo(id=sid, label=str(meta["label"]), membros=(sid,), meta=meta))
    return escopos
