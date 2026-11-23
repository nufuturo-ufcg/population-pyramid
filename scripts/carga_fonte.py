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
    autores: Path | None = None  # autores_commits.csv: e-mail de commit -> login (só duckdb)
    duplicados: Path | None = None  # CSV com repo_id dos repositórios a excluir (só duckdb)
    fracoes_api: Path | None = None  # CSV da API de linguagens, para quem tem `languages` vazio

    def repos_excluidos(self) -> tuple[str, ...]:
        """Os `repo_id` do arquivo `duplicados`, ou nenhum."""
        if self.duplicados is None:
            return ()
        tabela = pd.read_csv(self.duplicados, usecols=["repo_id"], dtype={"repo_id": str})
        return tuple(tabela["repo_id"])

    def grupos_de_duplicados(self) -> dict[str, str]:
        """`repo_id` do duplicado -> `repo_id` do repositório que fica, ou nenhum."""
        if self.duplicados is None:
            return {}
        tabela = pd.read_csv(self.duplicados, usecols=["repo_id", "mantido_repo_id"], dtype=str)
        grupos = {}
        for duplicado, mantido in zip(tabela["repo_id"], tabela["mantido_repo_id"], strict=True):
            grupos[duplicado] = mantido
        return grupos

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
        fonte = descobre_na_pasta(slug, Path(entrada["pasta"]))
    else:
        eventos = [_arquivo(item) for item in entrada["eventos"]]
        alvos = [Path(a).expanduser() for a in entrada["alvos"]]
        fonte = Fonte(slug, eventos, alvos, f"{YAML_FONTES.name}")
    if entrada.get("autores"):
        fonte.autores = Path(entrada["autores"]).expanduser()
    if entrada.get("duplicados"):
        fonte.duplicados = Path(entrada["duplicados"]).expanduser()
    if entrada.get("fracoes_api"):
        fonte.fracoes_api = Path(entrada["fracoes_api"]).expanduser()
    return fonte


def _confere_que_existe(fonte: Fonte) -> None:
    faltam = [a.caminho for a in fonte.eventos if not a.caminho.exists()]
    faltam += [a for a in fonte.alvos if not a.exists()]
    if fonte.autores and not fonte.autores.exists():
        faltam.append(fonte.autores)
    if fonte.duplicados and not fonte.duplicados.exists():
        faltam.append(fonte.duplicados)
    if fonte.fracoes_api and not fonte.fracoes_api.exists():
        faltam.append(fonte.fracoes_api)
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
    if fonte.fracoes_api is not None:
        alvo["fracao_api"] = alvo["repo_id"].map(le_fracoes_api(fonte))
    return alvo.reset_index(drop=True)


def le_fracoes_api(fonte: Fonte) -> dict[str, float]:
    """`repo_id` -> fração da linguagem-alvo na API de linguagens do GitHub (200 com bytes).

    O CSV é o de `scripts/granularidade/consulta_languages.py`. Quem respondeu 404, 403, 451
    ou sem bytes não aparece, e a elegibilidade o trata como sem dado.
    """
    if fonte.fracoes_api is None:
        return {}
    tabela = pd.read_csv(
        fonte.fracoes_api,
        usecols=["repo_id", "linguagem", "http_status", "fracao_linguagem_alvo"],
        dtype={"repo_id": str, "linguagem": str},
    )
    tabela = tabela[(tabela["linguagem"] == fonte.slug) & (tabela["http_status"] == 200)]
    tabela = tabela.dropna(subset=["fracao_linguagem_alvo"])
    return dict(zip(tabela["repo_id"], tabela["fracao_linguagem_alvo"].astype(float), strict=True))


def _participacao(linguagens_json: str, linguagem: str) -> float:
    try:
        mapa = json.loads(linguagens_json)
    except (TypeError, ValueError):
        return 0.0
    total = sum(mapa.values())
    return mapa.get(linguagem, 0) / total if total else 0.0


def le_contas(caminho: Path | None) -> tuple[str, ...]:
    """As contas da coluna `conta` de um CSV, como `contas_com_bot_sem_marcador.csv`."""
    if caminho is None:
        return ()
    tabela = pd.read_csv(Path(caminho).expanduser(), usecols=["conta"], dtype=str)
    return tuple(tabela["conta"].dropna())


def repos_sem_mapa(fonte: Fonte) -> tuple[str, ...]:
    """Alvos com o mapa de linguagens vazio que não estão num grupo com membro elegível.

    Mapa vazio é texto que não é JSON ou JSON sem nenhum byte. A participação deles conta como 0
    e eles saem pela elegibilidade sem que se saiba a linguagem do código.
    """
    nome = fb.LING.atual.nome
    partes = []
    for caminho in fonte.alvos:
        partes.append(pd.read_csv(caminho, usecols=["repo_id", "languages"], dtype=str))
    alvo = pd.concat(partes, ignore_index=True).drop_duplicates("repo_id")
    vazio = {}
    elegivel = {}
    for repo, texto in zip(alvo["repo_id"], alvo["languages"], strict=True):
        try:
            mapa = json.loads(texto)
        except (TypeError, ValueError):
            mapa = {}
        total = sum(mapa.values())
        vazio[repo] = total == 0
        elegivel[repo] = total > 0 and mapa.get(nome, 0) / total > fb.LIMIAR_SHARE_LINGUAGEM
    grupo_com_elegivel = set()
    grupos = fonte.grupos_de_duplicados()
    membros: dict[str, list[str]] = {}
    for duplicado, mantido in grupos.items():
        membros.setdefault(mantido, [mantido]).append(duplicado)
    for lista in membros.values():
        tem_elegivel = False
        for repo in lista:
            if elegivel.get(repo, False):
                tem_elegivel = True
        if tem_elegivel:
            grupo_com_elegivel.update(lista)
    resultado = []
    for repo, sem_mapa in vazio.items():
        if sem_mapa and repo not in grupo_com_elegivel:
            resultado.append(repo)
    return tuple(resultado)


def _tem_bytes(linguagens_json: str) -> bool:
    """A coluna `languages` da SEART traz um objeto JSON com bytes somando mais de 0."""
    try:
        mapa = json.loads(linguagens_json)
    except (TypeError, ValueError):
        return False
    return isinstance(mapa, dict) and sum(mapa.values()) > 0


def fracao_e_fonte(alvo: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """Fração da linguagem no código e de onde ela veio: `seart`, `api` ou vazio (sem dado).

    A SEART vale quando a coluna `languages` tem bytes. Quando está vazia e o alvo traz
    `fracao_api` (de `le_alvos`, com o CSV da API de linguagens), vale a API.
    """
    nome = fb.LING.atual.nome
    fracao = alvo["languages"].map(lambda texto: _participacao(texto, nome))
    fonte = pd.Series(
        ["seart" if _tem_bytes(texto) else "" for texto in alvo["languages"]], index=alvo.index
    )
    if "fracao_api" in alvo.columns:
        usa_api = (fonte == "") & alvo["fracao_api"].notna()
        fracao = fracao.where(~usa_api, alvo["fracao_api"])
        fonte = fonte.where(~usa_api, "api")
    return fracao, fonte


def marca_elegiveis(alvo: pd.DataFrame) -> pd.DataFrame:
    """Colunas `elegivel`, `fracao_linguagem` e `fonte_fracao`.

    Elegível: mais de `LIMIAR_SHARE_LINGUAGEM` do código na linguagem. A fração vem da SEART
    quando ela tem o dado e da API quando a SEART está vazia (ver `fracao_e_fonte`).
    """
    nome = fb.LING.atual.nome
    fracao, fonte = fracao_e_fonte(alvo)
    alvo = alvo.assign(
        elegivel=fracao > fb.LIMIAR_SHARE_LINGUAGEM, fracao_linguagem=fracao, fonte_fracao=fonte
    )
    excluidos = int((~alvo["elegivel"]).sum())
    fb._stats()["repos_total"] = len(alvo)
    fb._stats()["repos_excluidos_share"] = excluidos
    fb._stats()["repos_elegiveis"] = len(alvo) - excluidos
    if "fracao_api" in alvo.columns:
        fb._stats()["repos_elegiveis_pela_api"] = int((alvo["elegivel"] & (fonte == "api")).sum())
        fb._stats()["repos_sem_fracao"] = int((fonte == "").sum())
    if excluidos:
        print(
            f"aviso: {excluidos} repositórios excluídos por terem <= "
            f"{fb.LIMIAR_SHARE_LINGUAGEM:.0%} de {nome} no código",
            file=sys.stderr,
        )
    return alvo.drop(columns=["languages", "fracao_api"], errors="ignore")


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
