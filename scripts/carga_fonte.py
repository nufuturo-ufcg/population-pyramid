"""De onde vêm os eventos de uma linguagem: arquivos de eventos, arquivos-alvo e papel de cada um.

Os CSV brutos ficam onde foram coletados (na batuta, dezenas ou centenas de GB). A
ferramenta recebe os caminhos e lê de lá, sem mover, copiar nem apagar nada.

Um arquivo de eventos tem um papel:

  api    issue, pr e comentários (autor em `author_login`, linguagem em `language`)
  git    commits do clone (autor em `author`, arquivos tocados em `files`)
  misto  os dois juntos, como `eventos_repositorios.csv` e `eventos_python.csv`;
         a linha com `event_type == "commit"` segue a regra do git, as outras a da API

O arquivo-alvo (`repositorios_<linguagem>_alvo.csv`) traz o mapa de linguagens e a
data de criação de cada repositório. Uma coleta repartida entre máquinas tem um
alvo por parte, e todos entram.

Onde procurar, em ordem:

  1. a linha de comando: `--dados PASTA`, ou `--eventos ARQ` e `--alvo ARQ`
  2. `scripts/vitalidade_fontes.yaml`, com os caminhos da batuta
  3. a pasta `data/<linguagem>-*` do repositório, a de sempre
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import yaml

import figuras_linguagem_bruta as fb

# Linguagens que a vitalidade conhece e `figuras_linguagem_bruta.LINGUAGENS` não: as figuras
# de 4 linguagens daquele script seguem como estão.
LINGUAGENS_EXTRAS = {
    "ocaml": fb.Linguagem(
        "OCaml", "ocaml", (".ml", ".mli", ".mll", ".mly", ".eliom", ".eliomi", ".ml4"), False
    ),
}
CORES_EXTRAS = {"ocaml": "#e8590c"}
LINGUAGENS = {**fb.LINGUAGENS, **LINGUAGENS_EXTRAS}

YAML_FONTES = Path(__file__).parent / "vitalidade_fontes.yaml"
PAPEIS = ("api", "git", "misto")
COLUNAS_DO_ALVO = ["repo_id", "mainLanguage", "createdAt", "languages"]


@dataclass
class Arquivo:
    caminho: Path
    papel: str


@dataclass
class Fonte:
    slug: str
    eventos: list[Arquivo]
    alvos: list[Path]
    origem: str = ""  # de onde a fonte veio (linha de comando, yaml, pasta do repositório)
    pasta_dados: Path | None = field(default=None)  # só se o layout é o de `carrega_eventos`

    def bytes_de_eventos(self) -> int:
        return sum(a.caminho.stat().st_size for a in self.eventos)

    def cabe_no_carregador_original(self, limite_gb: float) -> bool:
        """O pipeline do motor (ccr_ncr, stickiness) lê tudo para a RAM, com `carrega_eventos`."""
        return self.pasta_dados is not None and self.bytes_de_eventos() < limite_gb * 1e9


def papel_pelo_nome(caminho: Path) -> str:
    nome = caminho.name.lower()
    if "_api" in nome:
        return "api"
    if "_git" in nome:
        return "git"
    return "misto"


def _arquivo(item: str | dict) -> Arquivo:
    if isinstance(item, dict):
        caminho = Path(item["arquivo"]).expanduser()
        papel = item.get("papel") or papel_pelo_nome(caminho)
    else:
        caminho = Path(item).expanduser()
        papel = papel_pelo_nome(caminho)
    if papel not in PAPEIS:
        raise SystemExit(f"papel {papel!r} de {caminho}: use {PAPEIS}.")
    return Arquivo(caminho, papel)


def descobre_na_pasta(slug: str, pasta: Path) -> Fonte:
    """Eventos e alvo numa pasta: api+git se existirem, senão o arquivo único."""
    pasta = pasta.expanduser()
    api, git = pasta / "eventos_api.csv", pasta / "eventos_git.csv"
    if api.exists() and git.exists():
        eventos = [Arquivo(api, "api"), Arquivo(git, "git")]
    else:
        unico = [pasta / f"eventos_{slug}.csv", pasta / "eventos_repositorios.csv"]
        achados = [Arquivo(c, "misto") for c in unico if c.exists()]
        if not achados:
            raise SystemExit(f"{pasta}: sem eventos_api.csv + eventos_git.csv nem arquivo único.")
        eventos = achados[:1]
    alvos = sorted(pasta.glob(f"repositorios_{slug}_alvo.csv"))
    if not alvos:
        raise SystemExit(f"{pasta}: sem repositorios_{slug}_alvo.csv. Passe --alvo.")
    return Fonte(slug, eventos, alvos, f"pasta {pasta}", pasta_dados=pasta)


def _do_yaml(slug: str) -> Fonte | None:
    todas = yaml.safe_load(YAML_FONTES.read_text()) or {}
    entrada = (todas.get("linguagens") or {}).get(slug)
    if not entrada:
        return None
    if "pasta" in entrada:
        return descobre_na_pasta(slug, Path(entrada["pasta"]))
    eventos = [_arquivo(item) for item in entrada["eventos"]]
    alvos = [Path(a).expanduser() for a in entrada["alvos"]]
    return Fonte(slug, eventos, alvos, f"{YAML_FONTES.name}")


def _confere_que_existe(fonte: Fonte) -> None:
    faltam = [a.caminho for a in fonte.eventos if not a.caminho.exists()]
    faltam += [a for a in fonte.alvos if not a.exists()]
    if faltam:
        lista = "\n  ".join(str(f) for f in faltam)
        raise SystemExit(
            f"fonte de {fonte.slug!r} (de {fonte.origem}): arquivo não existe:\n  {lista}\n"
            "Passe --dados PASTA, ou --eventos e --alvo."
        )


def resolve_fonte(
    slug: str,
    dados: str | None = None,
    eventos: list[str] | None = None,
    alvos: list[str] | None = None,
) -> Fonte:
    """Escolhe a fonte pela ordem do módulo: linha de comando, yaml, pasta do repositório."""
    if eventos:
        arquivos = [_arquivo(e) for e in eventos]
        achados = [Path(a).expanduser() for a in alvos or []]
        if not achados and dados:
            achados = descobre_na_pasta(slug, Path(dados)).alvos
        fonte = Fonte(slug, arquivos, achados, "linha de comando")
        if not fonte.alvos:
            raise SystemExit("--eventos pede também --alvo (ou --dados com o alvo dentro).")
    elif dados:
        fonte = descobre_na_pasta(slug, Path(dados))
        if alvos:
            fonte.alvos = [Path(a).expanduser() for a in alvos]
    else:
        fonte = _do_yaml(slug)
        yaml_serve = fonte is not None and all(a.caminho.exists() for a in fonte.eventos)
        if not yaml_serve:
            padrao, _ = fb._caminhos_padrao(fb.RODADA)
            fonte = descobre_na_pasta(slug, padrao) if padrao.exists() else fonte
        if fonte is None:
            raise SystemExit(f"sem fonte para {slug!r}: passe --dados ou configure o yaml.")
    _confere_que_existe(fonte)
    return fonte


def le_alvos(fonte: Fonte) -> pd.DataFrame:
    """Os alvos juntos, um por repositório, com a data de criação já em UTC sem fuso."""
    partes = []
    for caminho in fonte.alvos:
        partes.append(pd.read_csv(caminho, usecols=COLUNAS_DO_ALVO, dtype={"repo_id": str}))
    alvo = pd.concat(partes, ignore_index=True).drop_duplicates("repo_id")
    alvo["createdAt"] = pd.to_datetime(
        alvo["createdAt"], utc=True, format="ISO8601", errors="coerce"
    ).dt.tz_localize(None)
    return alvo.reset_index(drop=True)


def _participacao(linguagens_json: str, linguagem: str) -> float:
    try:
        mapa = json.loads(linguagens_json)
    except (TypeError, ValueError):
        return 0.0
    total = sum(mapa.values())
    return mapa.get(linguagem, 0) / total if total else 0.0


def marca_elegiveis(alvo: pd.DataFrame) -> pd.DataFrame:
    """Coluna `elegivel`: mais de `LIMIAR_SHARE_LINGUAGEM` do código na linguagem (regra de fb)."""
    nome = fb.LING.atual.nome
    participacao = alvo["languages"].map(lambda texto: _participacao(texto, nome))
    alvo = alvo.assign(elegivel=participacao > fb.LIMIAR_SHARE_LINGUAGEM)
    excluidos = int((~alvo["elegivel"]).sum())
    fb._stats()["repos_total"] = len(alvo)
    fb._stats()["repos_excluidos_share"] = excluidos
    fb._stats()["repos_elegiveis"] = len(alvo) - excluidos
    if excluidos:
        print(
            f"aviso: {excluidos} repositórios excluídos por terem <= "
            f"{fb.LIMIAR_SHARE_LINGUAGEM:.0%} de {nome} no código",
            file=sys.stderr,
        )
    return alvo.drop(columns="languages")


def aplica_linguagem(slug: str) -> None:
    """Escolhe a linguagem atual, também as que só a vitalidade conhece."""
    if slug in fb.LINGUAGENS:
        fb.LING.aplica(slug)
    elif slug in LINGUAGENS_EXTRAS:
        fb.LING.atual = LINGUAGENS_EXTRAS[slug]
    else:
        raise SystemExit(f"linguagem desconhecida: {slug!r}. Use: {', '.join(LINGUAGENS)}")


def cor_da_linguagem(slug: str) -> str:
    return fb.CORES_LINGUAGEM.get(slug) or CORES_EXTRAS[slug]
