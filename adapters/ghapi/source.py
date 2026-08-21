"""Adaptador `ghapi`: JSON cru da API do GitHub, mais o clone parcial.

Traduz uma coleta da API para o formato canônico de eventos. A coleta é feita
fora deste repositório e chega como um diretório apontado por `GHAPI_DIR`.

ESCOPO É O PAR (repositório, linguagem). Um repositório com Clojure e Java vira
dois escopos, e o commit que toca `.clj` e `.java` emite um evento em cada. É
isso que permite a pirâmide por linguagem somar os escopos que compartilham
`scope_meta.language`, sem o motor saber o que é um arquivo.

O layout da coleta não é fixo. Nome de pasta, nome de arquivo e ordem não entram
na conta: cada arquivo é classificado pela forma do primeiro item, e cada item é
atribuído ao repositório pelo campo `url`, que toda busca traz no formato
`https://api.github.com/repos/{owner}/{name}/...`.

As pegadinhas da API que fazem a contagem sair errada em silêncio, todas medidas
em `clj-kondo/clj-kondo` (repo 176829714, 3097 commits):

- `GET /issues` devolve issue E pull request na mesma listagem. O item com a
  chave `pull_request` é um PR, e o `created_at` dele é a abertura do PR. Ler
  `/pulls` além disso conta o mesmo PR duas vezes.
- `GET /commits` não traz a lista de arquivos. Ela sai do clone, e a junção é
  pelo `sha`. Pedir `GET /commits/{sha}` custaria uma requisição por commit.
- A junção por `sha` não é total. No clj-kondo, 284 shas existem só no clone
  (commit fora da branch default, que tem caminho e não tem `author.id`) e 22 só
  na API (commit de merge, que `git log --name-only` não lista arquivo). Os 284
  saem por não ter contribuidor. Os 22 ficam sem caminho e caem no fallback.
- `commit_comments.path` vem `null` em metade dos itens, porque comentário no
  commit inteiro não aponta linha nenhuma. Esses caem no fallback.
- `pull_request_comments.path` vem preenchido sempre.
- O mapa de `GET /languages` exclui prosa e dados. Markdown, YAML e edn nunca
  aparecem nele, e é por isso que ele serve de gabarito do que conta como
  linguagem de programação naquele repositório.
- `author` vem `null` quando o e-mail do commit não casa com conta do GitHub.
  Esses eventos saem, como o `msr14` faz com `commits.author_id` nulo.
"""

from __future__ import annotations

import json
import logging
import os
from collections import Counter
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
from dotenv import load_dotenv

from pyramid.config import ROOT
from pyramid.sources.base import (
    EVENT_COLUMNS,
    ActivityDataSource,
    validate_canonical_schema,
    validate_scope_meta,
)

log = logging.getLogger(__name__)
AQUI = Path(__file__).resolve().parent

# Um escopo é (repo_id, índice da linguagem no universo daquele repositório).
# O universo é ordenado e sai só dos dados, então o id é estável entre execuções.
# 1000 linguagens num repositório só é folga larga: o clj-kondo tem 6.
LINGUAGENS_POR_REPO = 1000

# Rótulo do escopo que recebe evento sem linguagem. Ele é extraído e contado,
# e o `scope_meta.language` dele é None, então o agregador por linguagem o
# separa dos demais em vez de somar com quem tem linguagem de verdade.
SEM_LINGUAGEM = "unknown"


# --- tabela do github-linguist -------------------------------------------------


@cache
def _tabelas_linguist() -> tuple[dict[str, tuple[str, ...]], dict[str, tuple[str, ...]]]:
    """`(extensão -> linguagens, nome de arquivo -> linguagens)`.

    `languages.yml` vem do github-linguist, versionado aqui do jeito que ele
    publica. Traduzir a tabela na mão introduziria erro que ninguém revisa.

    O valor é uma tupla porque extensão tem dono demais: 172 das 1483 são
    ambíguas. `.rs` é Rust e RenderScript, `.h` é C, C++ e Objective-C, `.md` é
    Markdown e GCC Machine Description. O linguist desempata lendo o conteúdo do
    arquivo, que o clone parcial não baixa. Quem desempata aqui é o mapa de bytes
    do repositório, em `_linguagem_no_repo`.

    A extensão sai com o ponto e em minúsculas. Extensão de mais de um ponto
    existe (`.blade.php`, `.cljs.hl`), então quem consulta tenta o sufixo mais
    longo primeiro.
    """
    dados = yaml.safe_load((AQUI / "languages.yml").read_text(encoding="utf-8"))
    por_ext: dict[str, list[str]] = {}
    por_nome: dict[str, list[str]] = {}
    for nome, info in sorted(dados.items()):
        for ext in info.get("extensions", []):
            por_ext.setdefault(ext.lower(), []).append(nome)
        for arquivo in info.get("filenames", []):
            por_nome.setdefault(arquivo, []).append(nome)
    return (
        {k: tuple(v) for k, v in por_ext.items()},
        {k: tuple(v) for k, v in por_nome.items()},
    )


def candidatos_do_caminho(caminho: str) -> tuple[str, ...]:
    """Linguagens que reivindicam este caminho, em ordem estável.

    Tupla vazia sai para arquivo que a tabela não conhece. Tupla de mais de um
    item sai para extensão ambígua, e quem escolhe é o repositório.
    """
    por_ext, por_nome = _tabelas_linguist()
    base = caminho.rsplit("/", 1)[-1]
    if (direto := por_nome.get(base)) is not None:
        return direto
    partes = base.lower().split(".")
    for i in range(1, len(partes)):  # sufixo mais longo primeiro
        if (achou := por_ext.get("." + ".".join(partes[i:]))) is not None:
            return achou
    return ()


def _linguagem_no_repo(caminho: str, bytes_por_lang: Mapping[str, int]) -> str | None:
    """Linguagem do caminho dentro de um repositório, ou `None`.

    O mapa de `GET /languages` é a verdade sobre quais linguagens aquele
    repositório tem, e o GitHub o calculou com o linguist lendo o conteúdo. Usar
    esse mapa para desempatar resolve a ambiguidade de extensão com o dado que
    já veio pronto: `.rs` num repositório Rust dá Rust, e o `.md` de qualquer
    repositório não dá nada, porque o mapa exclui prosa.

    Empate que sobra (`.h` num repositório com C e C++) vai para a linguagem com
    mais bytes.
    """
    candidatos = [c for c in candidatos_do_caminho(caminho) if c in bytes_por_lang]
    if not candidatos:
        return None
    return max(candidatos, key=lambda c: (bytes_por_lang[c], c))


# --- leitura da coleta ---------------------------------------------------------

# Que chaves cada busca traz. A classificação é por presença de chave, e não
# por valor, porque valor nulo é normal: `commit_comments.path` vem `null` em
# metade dos itens e `issue_events.commit_id` vem `null` quase sempre.
#
# A ordem vai do mais específico para o mais geral, e cada linha existe por uma
# colisão medida:
#
# - item de `/pulls` traz `issue_url`, igual a comentário de issue. Sem o
#   `head`/`base` na frente, abertura de PR entraria como comentário, o que
#   inverte o CCR do escopo inteiro.
# - comentário de review traz `commit_id`, igual a comentário de commit, e só o
#   `pull_request_url` separa.
# - comentário de commit traz `position`, que o evento de issue não tem, embora
#   os dois tenham `commit_id`.
_FORMA: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("pull_requests", ("issue_url", "head", "base")),
    ("pull_request_comments", ("pull_request_url",)),
    ("issue_comments", ("issue_url",)),
    ("commit_comments", ("commit_id", "position")),
    ("issue_events", ("event", "actor")),
    ("commits", ("sha", "commit")),
    ("issues", ("repository_url", "number")),
)


def _linhas(arquivo: Path) -> Iterator[dict]:
    """Itens de um arquivo, aceitando JSON Lines ou um array só.

    A coleta grande concatena páginas, e nem sempre no mesmo formato. Ler as duas
    formas evita depender de como quem coletou resolveu gravar.

    Vai linha a linha porque o arquivo é grande: `issue_events` da amostra de
    três repositórios já tem 104 MB, e ler tudo para a memória de uma vez
    multiplica isso pelo JSON expandido.
    """
    with arquivo.open(encoding="utf-8") as f:
        primeiro = f.read(1)
        while primeiro and primeiro.isspace():
            primeiro = f.read(1)
        if primeiro == "[":
            f.seek(0)
            yield from json.load(f)
            return
        f.seek(0)
        for linha in f:
            if linha.strip():
                yield json.loads(linha)


def _classifica(item: Mapping[str, Any]) -> str | None:
    """Qual busca produziu este item, pela forma dele."""
    for busca, chaves in _FORMA:
        if all(c in item for c in chaves):
            return busca
    return None


def _repo_do_item(item: Mapping[str, Any]) -> str | None:
    """`owner/name` a partir do campo `url`, que toda busca traz."""
    url = item.get("url") or item.get("repository_url") or ""
    partes = str(url).split("/repos/", 1)
    if len(partes) != 2:
        return None
    resto = partes[1].split("/")
    return f"{resto[0]}/{resto[1]}" if len(resto) >= 2 else None


def _arquivos_de_evento(raiz: Path) -> list[Path]:
    """Arquivos da coleta que podem conter evento, em ordem estável.

    Fora ficam só os dois de metadado e o que começa com `_`. Nada aqui olha o
    nome do arquivo para adivinhar o que tem dentro.
    """
    return [
        a
        for a in sorted(raiz.rglob("*"))
        if a.is_file()
        and a.suffix in {".json", ".jsonl"}
        and not a.name.startswith("_")
        and a.name not in {"repos.jsonl", "languages.jsonl"}
    ]


# --- a coleta como tabela ------------------------------------------------------

# De qual campo sai o contribuidor em cada busca. `issue_events` usa `actor`,
# `commits` usa `author` (a conta do GitHub, não o `commit.author`, que é só o
# nome e o e-mail gravados no objeto do git).
_QUEM: dict[str, str] = {
    "commits": "author",
    "issues": "user",
    "pull_requests": "user",
    "issue_comments": "user",
    "commit_comments": "user",
    "pull_request_comments": "user",
    "issue_events": "actor",
}


def _quando(busca: str, item: Mapping[str, Any]) -> str | None:
    """Data do evento. `commits` guarda a data dentro do objeto do git."""
    if busca == "commits":
        return (item.get("commit") or {}).get("author", {}).get("date")
    return item.get("created_at")


def _tipo_canonico(busca: str, item: Mapping[str, Any]) -> str:
    """Nome do enum `EVENT_TYPES`.

    `issues` é a única busca que produz dois tipos: item com a chave
    `pull_request` é a abertura de um PR.
    """
    if busca == "issues":
        return "pull_requests" if item.get("pull_request") else "issues"
    return busca


def _e_bot(pessoa: Mapping[str, Any]) -> bool:
    """Conta de bot, por tipo declarado ou por sufixo no login."""
    return pessoa.get("type") == "Bot" or str(pessoa.get("login", "")).endswith("[bot]")


def _caminhos_por_sha(raiz: Path) -> dict[str, list[str]]:
    """`sha -> caminhos tocados`, do TSV que o clone produziu.

    Sem esse arquivo a atribuição por caminho não existe e todo commit cai no
    fallback, o que muda a pirâmide inteira sem erro nenhum. Por isso a ausência
    é erro, e não aviso.
    """
    tsv = next(raiz.rglob("commit_files.tsv"), None)
    if tsv is None:
        raise FileNotFoundError(
            f"sem commit_files.tsv em {raiz}. Ele sai do clone parcial, é o que dá o caminho "
            "dos arquivos de cada commit, e não custa cota nenhuma:\n"
            f"  GHAPI_DIR={raiz} .venv/bin/python adapters/ghapi/coleta.py --completar"
        )
    por_sha: dict[str, list[str]] = {}
    with tsv.open(encoding="utf-8") as f:
        cabecalho = f.readline().rstrip("\n").split("\t")
        try:
            i_sha, i_path = cabecalho.index("sha"), cabecalho.index("path")
        except ValueError as e:
            raise ValueError(f"{tsv}: cabeçalho {cabecalho}, esperado com 'sha' e 'path'") from e
        for linha in f:
            partes = linha.rstrip("\n").split("\t")
            if len(partes) > max(i_sha, i_path):
                por_sha.setdefault(partes[i_sha], []).append(partes[i_path])
    return por_sha


def _metadados(raiz: Path) -> tuple[dict[str, dict], dict[str, dict[str, int]]]:
    """`(owner/name -> GET /repos, owner/name -> mapa de bytes)`."""
    repos_jsonl = next(raiz.rglob("repos.jsonl"), None)
    langs_jsonl = next(raiz.rglob("languages.jsonl"), None)
    if repos_jsonl is None or langs_jsonl is None:
        raise FileNotFoundError(
            f"sem repos.jsonl ou languages.jsonl em {raiz}. A coleta de eventos não produz "
            "os dois, e deles saem o rótulo, a data de criação e o mapa de bytes que decide "
            "a linguagem de cada caminho de arquivo. São duas requisições por repositório:\n"
            f"  GHAPI_DIR={raiz} .venv/bin/python adapters/ghapi/coleta.py --completar"
        )
    repos = {m["full_name"]: m for m in _linhas(repos_jsonl)}
    langs = {m["full_name"]: m["languages"] for m in _linhas(langs_jsonl)}
    faltando = sorted(set(repos) - set(langs))
    if faltando:
        raise ValueError(f"sem mapa de linguagens para {faltando}")
    return repos, langs


# --- política de linguagem -----------------------------------------------------

_PADRAO: dict[str, Any] = {
    "repo_languages": {"policy": "primary", "min_share": 0.0},
    "attribution": "by_path",
    "fallback": "repo_languages",
    "fallback_spread": "top",
    "outside_eligible": "keep",
    "drop_bots": True,
}


def _politica(settings: Mapping[str, Any]) -> dict[str, Any]:
    """Bloco `language:` do settings.yaml, com o default de cada chave."""
    pedido = dict(settings.get("language") or {})
    saida = dict(_PADRAO)
    saida["repo_languages"] = {**_PADRAO["repo_languages"], **(pedido.pop("repo_languages", {}))}
    saida.update(pedido)
    if desconhecidas := sorted(set(saida) - set(_PADRAO)):
        raise ValueError(f"language: chave desconhecida {desconhecidas}")
    return saida


def _elegiveis(bytes_por_lang: Mapping[str, int], politica: Mapping[str, Any]) -> list[str]:
    """Linguagens do repositório que viram escopo, em ordem de bytes.

    `primary` devolve só a de mais bytes e reproduz o recorte de hoje.
    `min_share` devolve todas acima do corte, e é o gancho para "só entram
    linguagens com mais de X% do repositório".
    """
    if not bytes_por_lang:
        return []
    ordenado = sorted(bytes_por_lang.items(), key=lambda kv: (-kv[1], kv[0]))
    modo = politica["policy"]
    if modo == "primary":
        return [ordenado[0][0]]
    if modo == "min_share":
        total = sum(bytes_por_lang.values())
        corte = float(politica["min_share"])
        return [k for k, v in ordenado if 100.0 * v / total >= corte]
    raise ValueError(f"language.repo_languages.policy={modo!r}. Use primary ou min_share.")


def _do_fallback(elegiveis: list[str], politica: Mapping[str, Any]) -> list[str]:
    """Para onde vai o evento que não tem caminho de arquivo."""
    modo = politica["fallback"]
    if modo == "drop":
        return []
    if modo == "unknown":
        return [SEM_LINGUAGEM]
    if modo != "repo_languages":
        raise ValueError(f"language.fallback={modo!r}. Use repo_languages, unknown ou drop.")
    if not elegiveis:
        return [SEM_LINGUAGEM]
    espalha = politica["fallback_spread"]
    if espalha == "top":
        return elegiveis[:1]
    if espalha == "all":
        return elegiveis
    raise ValueError(f"language.fallback_spread={espalha!r}. Use top ou all.")


def _destino(achadas: set[str], elegiveis: list[str], politica: Mapping[str, Any]) -> list[str]:
    """Escopos de um evento cujo caminho deu as linguagens `achadas`.

    Linguagem fora do conjunto elegível é governada por `outside_eligible`, e é
    o caso do `.java` dentro de um repositório Clojure.
    """
    if not achadas:
        return _do_fallback(elegiveis, politica)
    dentro = sorted(achadas & set(elegiveis))
    fora = sorted(achadas - set(elegiveis))
    if not fora:
        return dentro
    modo = politica["outside_eligible"]
    if modo == "keep":
        return dentro + fora
    if modo == "drop":
        return dentro
    if modo == "fallback":
        return dentro or _do_fallback(elegiveis, politica)
    raise ValueError(f"language.outside_eligible={modo!r}. Use keep, fallback ou drop.")


# --- o adaptador ---------------------------------------------------------------


@dataclass(frozen=True)
class _Contexto:
    """O que a montagem precisa saber sobre os repositórios, calculado uma vez."""

    repos: dict[str, dict]
    langs: dict[str, dict[str, int]]
    universo: dict[str, list[str]]
    elegiveis: dict[str, list[str]]
    por_sha: dict[str, list[str]]


def _dir_coleta(settings: Mapping[str, Any]) -> Path:
    """Onde está a coleta. `GHAPI_DIR` no ambiente vence o settings.yaml."""
    load_dotenv(ROOT / ".env")
    bruto = os.getenv("GHAPI_DIR") or (settings.get("ghapi") or {}).get("dir") or "data/ghapi"
    caminho = Path(bruto)
    return caminho if caminho.is_absolute() else ROOT / caminho


class GHAPISource(ActivityDataSource):
    """Escopo = par (repositório, linguagem)."""

    def __init__(self, settings: Mapping[str, Any], raiz: Path | None = None) -> None:
        """Configura a fonte. `raiz` existe para o teste apontar outra coleta."""
        super().__init__(settings)
        self.raiz = raiz or _dir_coleta(settings)
        self.politica = _politica(settings)
        self._tabela: pd.DataFrame | None = None
        self._meta: dict[int, dict[str, Any]] = {}

    # -- montagem -------------------------------------------------------------

    def _monta(self) -> pd.DataFrame:
        """Lê a coleta inteira uma vez e devolve os eventos já com `scope_id`.

        Uma varredura só, com o resultado guardado, porque `extract` chama
        `get_events` uma vez por escopo e a coleta tem centenas de MB.

        ponytail: a tabela inteira mora na memória. Cabe para a ordem de grandeza
        de dezenas de repositórios. Passar disso pede gravar parquet por
        repositório aqui dentro e ler por escopo.
        """
        if not self.raiz.is_dir():
            raise FileNotFoundError(
                f"GHAPI_DIR '{self.raiz}' nao existe. Aponte no .env para a pasta da coleta."
            )
        repos, langs = _metadados(self.raiz)
        por_sha = _caminhos_por_sha(self.raiz)
        arquivos = _arquivos_de_evento(self.raiz)
        if not arquivos:
            raise ValueError(f"{self.raiz}: nenhum arquivo .json ou .jsonl de evento.")

        # Universo de linguagens de cada repositório, ordenado, de onde sai o
        # índice que compõe o `scope_id`. Sai só dos dados, então é estável.
        universo = {nome: sorted({*langs[nome], SEM_LINGUAGEM}) for nome in repos}
        elegiveis = {
            nome: _elegiveis(langs[nome], self.politica["repo_languages"]) for nome in repos
        }
        if self.politica["attribution"] not in {"by_path", "repo_languages"}:
            raise ValueError(
                f"language.attribution={self.politica['attribution']!r}. "
                "Use by_path ou repo_languages."
            )
        ctx = _Contexto(repos, langs, universo, elegiveis, por_sha)

        linhas: list[tuple[int, int, str, str]] = []
        descartes: Counter[str] = Counter()
        # A classificação é POR ITEM, e não por arquivo. A coleta pode separar
        # por busca, por repositório, ou jogar tudo num arquivo só, e nenhuma
        # dessas formas muda o resultado. Classificar pelo primeiro item e
        # aplicar o veredito ao arquivo inteiro leria um arquivo misto errado,
        # trocando o tipo de evento de tudo que viesse depois da primeira linha.
        for arquivo in arquivos:
            for item in _linhas(arquivo):
                busca = _classifica(item) if isinstance(item, dict) else None
                if busca is None:
                    descartes["forma nao reconhecida"] += 1
                    continue
                saiu, motivo = self._linhas_do_item(busca, item, ctx)
                linhas.extend(saiu)
                if motivo:
                    descartes[motivo] += 1

        for motivo, n in sorted(descartes.items()):
            log.info("descartados %d eventos: %s", n, motivo, extra={"stage": "extract"})

        df = pd.DataFrame(linhas, columns=["scope_id", "contributor_id", "event_type", "timestamp"])
        # Naive em UTC: `snapshots` compara com datas do settings.yaml, que são
        # naive, e comparar tz-aware com naive levanta exceção no pandas.
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
        df = df[df["timestamp"].notna()].copy()
        df["timestamp"] = df["timestamp"].dt.tz_localize(None)
        df["scope_id"] = df["scope_id"].astype("int64")
        df["contributor_id"] = df["contributor_id"].astype("int64")
        df["event_type"] = df["event_type"].astype("string")

        self._meta = self._monta_meta(repos, langs, universo, set(df["scope_id"]))
        # Duplicata exata sai, como o contrato cobra de toda fonte. Isso colapsa
        # evento que a API conta separado e que nas quatro colunas canônicas fica
        # idêntico: rotular uma issue com três etiquetas de uma vez gera três
        # `issue_events` do mesmo ator, no mesmo segundo, no mesmo escopo. Medido
        # na amostra de três repositórios: `issue_events` cai 29,5% (19110 para
        # 13469) e nenhum outro tipo passa de 0,2%. A pirâmide conta pessoa e
        # data, então o colapso não muda banda nem lado.
        return df.drop_duplicates().reset_index(drop=True)

    def _linhas_do_item(
        self, busca: str, item: Mapping[str, Any], ctx: _Contexto
    ) -> tuple[list[tuple[int, int, str, str]], str | None]:
        """Linhas canônicas de um item, ou o motivo de ele ter saído.

        Um item vira mais de uma linha quando toca mais de uma linguagem, e vira
        nenhuma quando a política manda descartar.
        """
        nome = _repo_do_item(item)
        if nome is None or nome not in ctx.repos:
            return [], "repo desconhecido"
        pessoa = item.get(_QUEM[busca]) or {}
        if not pessoa.get("id"):
            return [], "sem contribuidor"
        if self.politica["drop_bots"] and _e_bot(pessoa):
            return [], "bot"
        quando = _quando(busca, item)
        if not quando:
            return [], "sem data"

        achadas: set[str] = set()
        if self.politica["attribution"] == "by_path":
            for caminho in self._caminhos(busca, item, ctx.por_sha):
                if (lang := _linguagem_no_repo(caminho, ctx.langs[nome])) is not None:
                    achadas.add(lang)
        destinos = _destino(achadas, ctx.elegiveis[nome], self.politica)
        if not destinos:
            return [], "sem destino"

        rid = int(ctx.repos[nome]["id"])
        tipo = _tipo_canonico(busca, item)
        universo = ctx.universo[nome]
        return (
            [
                (rid * LINGUAGENS_POR_REPO + universo.index(lang), int(pessoa["id"]), tipo, quando)
                for lang in destinos
                if lang in universo
            ],
            None,
        )

    def _caminhos(
        self, busca: str, item: Mapping[str, Any], por_sha: dict[str, list[str]]
    ) -> list[str]:
        """Caminhos de arquivo que este evento tocou. Vazio quando não tocou nenhum."""
        if busca == "commits":
            return por_sha.get(str(item.get("sha")), [])
        if busca in {"commit_comments", "pull_request_comments"}:
            caminho = item.get("path")
            return [str(caminho)] if caminho else []
        return []

    def _monta_meta(
        self,
        repos: dict[str, dict],
        langs: dict[str, dict[str, int]],
        universo: dict[str, list[str]],
        vivos: set[int],
    ) -> dict[int, dict[str, Any]]:
        """`scope_meta` de cada escopo que ficou com pelo menos um evento."""
        saida: dict[int, dict[str, Any]] = {}
        for nome, meta in repos.items():
            rid = int(meta["id"])
            for idx, lang in enumerate(universo[nome]):
                sid = rid * LINGUAGENS_POR_REPO + idx
                if sid not in vivos:
                    continue
                criado = meta.get("created_at")
                saida[sid] = {
                    "label": f"{nome} [{lang}]",
                    "language": None if lang == SEM_LINGUAGEM else lang,
                    "created_at": pd.Timestamp(criado).tz_localize(None) if criado else None,
                    "repo_id": rid,
                    "repo": nome,
                    "language_bytes": langs[nome].get(lang),
                }
        return saida

    def _cache(self) -> pd.DataFrame:
        """A tabela montada, uma vez por instância."""
        if self._tabela is None:
            self._tabela = self._monta()
        return self._tabela

    # -- contrato -------------------------------------------------------------

    def list_scopes(self) -> list[int]:
        """Pares (repositório, linguagem) com pelo menos um evento, em ordem."""
        self._cache()
        return sorted(self._meta)

    def get_events(self, scope_id: int) -> pd.DataFrame:
        """Eventos de um escopo, nas colunas de EVENT_COLUMNS."""
        df = self._cache()
        recorte = df[df["scope_id"] == int(scope_id)][EVENT_COLUMNS].reset_index(drop=True)
        return validate_canonical_schema(recorte, scope_id=scope_id)

    def scope_meta(self, scope_id: int) -> dict[str, Any]:
        """label, language e created_at do par (repositório, linguagem)."""
        self._cache()
        meta = self._meta.get(
            int(scope_id), {"label": str(scope_id), "language": None, "created_at": None}
        )
        return validate_scope_meta(dict(meta), scope_id=scope_id)

    def scope_label(self, scope_id: int) -> str:
        """`owner/name [Linguagem]`, ou o id quando o escopo não existe."""
        self._cache()
        meta = self._meta.get(int(scope_id))
        return str(meta["label"]) if meta else str(scope_id)

    def provenance(self) -> dict[str, Any]:
        """As escolhas desta fonte que mudam o parquet de saída."""
        return {
            "colecao": str(self.raiz),
            "language_policy": self.politica,
            "linguist": "github-linguist/linguist@b45dbe9",
        }


SOURCE = GHAPISource
