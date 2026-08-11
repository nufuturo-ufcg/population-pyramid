"""Registro de adaptadores de entrada.

O motor de cálculo não conhece origem de dados. Quem sabe de banco, de API ou
de CSV é um adaptador, e cada adaptador mora em `adapters/<nome>/source.py`
com uma classe que implementa `ActivityDataSource` (o contrato em `base.py`).
O adaptador em uso vem de `config/settings.yaml`, chave `input.adapter`.

Adaptador é pasta, não módulo do pacote: junto do `source.py` moram os scripts
de preparação daquele dataset (subir banco, baixar dump, conferir contagem),
que são específicos dele e não do motor. `adapters/msr14/` é o primeiro.

O módulo carregado é registrado em `sys.modules` como `pyramid.sources.<nome>`,
então `patch("pyramid.sources.msr14.pd.read_sql")` continua valendo em teste.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from pyramid.config import ROOT, settings

from .base import EVENT_COLUMNS, EVENT_TYPES, ActivityDataSource, validate_canonical_schema

__all__ = [
    "EVENT_COLUMNS",
    "EVENT_TYPES",
    "ActivityDataSource",
    "adapters_dir",
    "disponiveis",
    "load",
    "validate_canonical_schema",
]


def adapters_dir() -> Path:
    """Pasta que guarda um diretório por adaptador."""
    return ROOT / "adapters"


def disponiveis() -> list[str]:
    """Nomes dos adaptadores presentes no repositório, em ordem."""
    raiz = adapters_dir()
    if not raiz.is_dir():
        return []
    return sorted(p.name for p in raiz.iterdir() if (p / "source.py").is_file())


def load(nome: str | None = None) -> type[ActivityDataSource]:
    """Devolve a classe de fonte do adaptador `nome`.

    Sem argumento, usa `input.adapter` do settings.yaml. O adaptador precisa
    expor `SOURCE`, apontando para a classe. Falha alto e com a lista do que
    existe: nome errado aqui só apareceria três estágios adiante, como
    "tabela não existe".
    """
    nome = nome or str(settings()["input"]["adapter"])
    modname = f"{__name__}.{nome}"
    if (mod := sys.modules.get(modname)) is None:
        arquivo = adapters_dir() / nome / "source.py"
        if not arquivo.is_file():
            raise SystemExit(
                f"adaptador '{nome}' nao encontrado em {arquivo}.\n"
                f"  disponiveis: {', '.join(disponiveis()) or '(nenhum)'}\n"
                f"  a escolha vem de config/settings.yaml, chave input.adapter"
            )
        spec = importlib.util.spec_from_file_location(modname, arquivo)
        if spec is None or spec.loader is None:
            raise SystemExit(f"nao consegui carregar {arquivo}")
        mod = importlib.util.module_from_spec(spec)
        # Registrar ANTES de executar: o módulo pode se importar de volta, e
        # `mock.patch` precisa achar o nome pontuado depois.
        sys.modules[modname] = mod
        setattr(sys.modules[__name__], nome, mod)
        try:
            spec.loader.exec_module(mod)
        except BaseException:
            del sys.modules[modname]
            raise

    classe = getattr(mod, "SOURCE", None)
    if not (isinstance(classe, type) and issubclass(classe, ActivityDataSource)):
        raise SystemExit(
            f"adapters/{nome}/source.py precisa expor SOURCE = <classe>, "
            f"subclasse de ActivityDataSource (achei {classe!r})"
        )
    return classe
