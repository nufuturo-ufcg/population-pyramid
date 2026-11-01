"""Motor `pandas` da carga: lê os CSV em pedaços, tudo na memória, até algumas dezenas de GB.

`figuras_linguagem_bruta.carrega_eventos` lê os CSV inteiros e o pico de memória fica
perto de 2x o tamanho dos CSV. Este motor aplica as mesmas regras, na mesma ordem, lendo
`PEDACO` linhas por vez e só as colunas de que precisa. O que fica na memória são 30
bytes por evento da linguagem, sem texto.

Regras repetidas de `figuras_linguagem_bruta.py` (`_carrega_api`, `_carrega_git`,
`_carrega_r2`, `_finaliza_eventos`), conferidas pelo `tests/test_carga.py`:

  1. API: sem autor sai; `language` vazia usa a linguagem principal do repositório.
  2. Git: sem autor sai; só entra commit que toca arquivo da linguagem; commit
     idêntico (autor, data, arquivos) em mais de um repositório fica no mais antigo.
  3. Evento da API antes do primeiro commit da linguagem no repositório sai.
  4. Só repositório elegível (mais da metade do código na linguagem).
  5. Conta apagada (`ghost`) e bot (`[bot]`) saem. Datas ilegíveis, futuras ou
     anteriores a 2008 saem.

Fica de fora `FUNDIR_IDENTIDADES`, que precisa dos textos dos autores.

Limite: o commit duplicado guarda um hash por commit da linguagem, também dos
repositórios inelegíveis, até o fim da leitura. Cabe em RAM até algumas centenas de
milhões de commits, e a leitura usa um núcleo só. Para mais que isso, o motor `duckdb`.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Iterator

import numpy as np
import pandas as pd

import figuras_linguagem_bruta as fb
from carga_fonte import Arquivo, Fonte, le_alvos, marca_elegiveis

PEDACO = 500_000
COLUNAS_API = ["repo_id", "event_type", "author_login", "created_at", "language"]
COLUNAS_GIT = ["repo_id", "event_type", "author", "created_at", "files"]
COLUNAS_DO_PAPEL = {
    "api": COLUNAS_API,
    "git": COLUNAS_GIT,
    "misto": sorted({*COLUNAS_API, *COLUNAS_GIT}),
}
MARCA_NORMAL, MARCA_FANTASMA, MARCA_BOT = 0, 1, 2


class _Identidades:
    """Nome -> (id estável, marca), calculado uma vez por nome distinto."""

    def __init__(self) -> None:
        self.por_nome: dict[str, tuple[int, int]] = {}

    def resolve(self, nomes: pd.Series) -> tuple[np.ndarray, np.ndarray]:
        codigos, unicos = pd.factorize(nomes)
        ids = np.empty(len(unicos), dtype="int64")
        marcas = np.empty(len(unicos), dtype="int8")
        for i, nome in enumerate(unicos):
            if nome not in self.por_nome:
                marca = MARCA_NORMAL
                if nome == "ghost":
                    marca = MARCA_FANTASMA
                elif nome.endswith("[bot]"):
                    marca = MARCA_BOT
                self.por_nome[nome] = (fb._id_estavel(nome), marca)
            ids[i], marcas[i] = self.por_nome[nome]
        return ids[codigos], marcas[codigos]


def _timestamp(texto: pd.Series) -> pd.Series:
    """Mesma conversão de `_finaliza_eventos`: UTC, sem fuso, ilegível vira NaT."""
    return pd.to_datetime(texto, utc=True, format="ISO8601", errors="coerce").dt.tz_localize(None)


def _pedacos(arquivo: Arquivo) -> Iterator[pd.DataFrame]:
    """Pedaços do CSV, tudo como texto: um login numérico não vira número em um pedaço só."""
    return pd.read_csv(
        arquivo.caminho,
        sep="|",
        usecols=COLUNAS_DO_PAPEL[arquivo.papel],
        dtype=str,
        chunksize=PEDACO,
    )


class _Referencias:
    """O que as linhas leves precisam saber de cada repositório."""

    def __init__(self, fonte: Fonte) -> None:
        alvo = marca_elegiveis(le_alvos(fonte))
        self.codigo = {repo: i for i, repo in enumerate(alvo["repo_id"])}
        self.principal = dict(zip(alvo["repo_id"], alvo["mainLanguage"], strict=True))
        # `criado[-1]` é NaT: repositório fora do alvo não prova que um commit é cópia.
        criado = alvo["createdAt"].to_numpy()
        self.criado = np.append(criado, np.array(["NaT"], dtype=criado.dtype))
        self.codigos_elegiveis = np.flatnonzero(alvo["elegivel"].to_numpy())
        self.nomes_tipo = sorted(set(fb.MAPA_TIPO_R2.values()))
        self.tipo = {bruto: self.nomes_tipo.index(n) for bruto, n in fb.MAPA_TIPO_R2.items()}
        self.pessoas = _Identidades()


def _leve(df: pd.DataFrame, autor: str, ref: _Referencias) -> pd.DataFrame:
    """Uma linha leve por evento: repositório, tipo, pessoa, marca e instante."""
    pessoa, marca = ref.pessoas.resolve(df[autor])
    return pd.DataFrame(
        {
            "codigo": df["repo_id"].map(ref.codigo).fillna(-1).astype("int32").to_numpy(),
            "tipo": df["event_type"].map(ref.tipo).fillna(-1).astype("int8").to_numpy(),
            "pessoa": pessoa,
            "marca": marca,
            "ts": _timestamp(df["created_at"]).to_numpy(),
        }
    )


def _parte_api(df: pd.DataFrame, ref: _Referencias) -> pd.DataFrame:
    df = df[df["author_login"].notna()].copy()
    df["language"] = df["language"].fillna(df["repo_id"].map(ref.principal))
    df = df[df["language"] == fb.LING.atual.nome]
    return _leve(df, "author_login", ref)


def _parte_git(df: pd.DataFrame, ref: _Referencias, toca_a_linguagem: re.Pattern) -> pd.DataFrame:
    df = df[df["author"].notna()]
    df = df[df["files"].str.lower().str.contains(toca_a_linguagem, na=False)]
    leve = _leve(df, "author", ref)
    leve["h"] = pd.util.hash_pandas_object(
        df[["author", "created_at", "files"]], index=False
    ).to_numpy()
    return leve


def _le_tudo(fonte: Fonte, ref: _Referencias) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Linhas leves de API e de git de todos os arquivos, já filtradas linha a linha."""
    # Qualquer caminho que termine numa extensão da linguagem, no fim da lista ou antes de ";".
    extensoes = "|".join(re.escape(e) for e in fb.LING.atual.extensoes)
    toca_a_linguagem = re.compile(f"(?:{extensoes})(?:;|$)")
    api, git = [], []
    bruto = {"api": 0, "git": 0}
    lidas = 0
    for arquivo in fonte.eventos:
        for pedaco in _pedacos(arquivo):
            if arquivo.papel == "misto":
                commit = (pedaco["event_type"] == "commit").to_numpy()
                para_a_api, para_o_git = pedaco[~commit], pedaco[commit]
            elif arquivo.papel == "api":
                para_a_api, para_o_git = pedaco, pedaco.iloc[:0]
            else:
                para_a_api, para_o_git = pedaco.iloc[:0], pedaco
            bruto["api"] += len(para_a_api)
            bruto["git"] += len(para_o_git)
            if len(para_a_api):
                api.append(_parte_api(para_a_api, ref))
            if len(para_o_git):
                git.append(_parte_git(para_o_git, ref, toca_a_linguagem))
            lidas += len(pedaco)
            if (lidas // PEDACO) % 20 == 0:
                print(f"carga: {lidas} linhas lidas", file=sys.stderr)
    fb._stats()["eventos_api_bruto"] = bruto["api"]
    fb._stats()["eventos_git_bruto"] = bruto["git"]
    vazio = pd.DataFrame({"codigo": [], "tipo": [], "pessoa": [], "marca": [], "ts": []})
    return (pd.concat(api, ignore_index=True) if api else vazio), (
        pd.concat(git, ignore_index=True) if git else vazio.assign(h=[])
    )


def _sem_copias(git: pd.DataFrame, ref: _Referencias) -> pd.DataFrame:
    """Tira o commit idêntico de repositório mais novo (fork completo, clone empurrado)."""
    fb._stats()["eventos_git_desta_linguagem"] = len(git)
    data_do_repo = pd.Series(ref.criado[git["codigo"].to_numpy()])
    mais_antigo = data_do_repo.groupby(git["h"].to_numpy()).transform("min")
    duplicado = (data_do_repo > mais_antigo).to_numpy()
    fb._stats()["commits_duplicados_descartados"] = int(duplicado.sum())
    if duplicado.any():
        print(
            f"aviso: {int(duplicado.sum())} commits descartados por serem cópia de "
            "histórico já contado num repositório criado antes (fork completo ou "
            "clone empurrado pra um repositório novo)",
            file=sys.stderr,
        )
    return git[~duplicado].drop(columns="h")


def carrega(fonte: Fonte) -> pd.DataFrame:
    """Eventos [contributor_id, event_type, timestamp] da linguagem atual, filtrados."""
    fb.ESTATISTICAS_CARGA.pop(fb.LING.atual.slug, None)
    fb._stats_erros_coleta()
    ref = _Referencias(fonte)
    api, git = _le_tudo(fonte, ref)
    fb._stats()["eventos_api_desta_linguagem"] = len(api)
    git = _sem_copias(git, ref)

    # Piso: nenhum evento conta antes do primeiro commit da linguagem no repositório.
    piso_por_repo = git.groupby("codigo")["ts"].min()
    todos = pd.concat([api, git], ignore_index=True)
    del api, git
    piso = todos["codigo"].map(piso_por_repo)
    antes_do_piso = (piso.notna() & (todos["ts"] < piso)).to_numpy()
    fb._stats()["eventos_antes_do_piso_descartados"] = int(antes_do_piso.sum())
    if antes_do_piso.any():
        print(
            f"aviso: {int(antes_do_piso.sum())} eventos descartados por serem anteriores "
            f"ao primeiro commit que de fato toca {fb.LING.atual.nome} no mesmo repositório "
            "(issue/pr/comentário datado antes do repositório virar essa linguagem)",
            file=sys.stderr,
        )
    todos = todos[~antes_do_piso]

    df = todos[todos["codigo"].isin(ref.codigos_elegiveis)]
    del todos
    fb._stats()["eventos_apos_elegibilidade"] = len(df)
    return _finaliza(df, ref.nomes_tipo)


def _finaliza(df: pd.DataFrame, nomes_tipo: list[str]) -> pd.DataFrame:
    """Conta apagada, bot, tipo fora do mapa e datas impossíveis saem; devolve as 3 colunas."""
    fantasma = (df["marca"] == MARCA_FANTASMA).to_numpy()
    if fantasma.sum():
        fb._salva_fantasmas_por_ano(pd.DataFrame({"created_at": df.loc[fantasma, "ts"]}))
    df = df[~fantasma]
    bot = (df["marca"] == MARCA_BOT).to_numpy()
    df = df[~bot]
    fb._stats()["eventos_fantasma_descartados"] = int(fantasma.sum())
    fb._stats()["eventos_bot_descartados"] = int(bot.sum())
    print(
        f"aviso: {fantasma.sum()} eventos de conta apagada descartados da pirâmide "
        f"(registrados à parte); {bot.sum()} eventos de bot descartados",
        file=sys.stderr,
    )

    df = df[df["tipo"] >= 0]
    descartados = int(df["ts"].isna().sum())
    fb._stats()["eventos_data_ilegivel_descartados"] = descartados
    if descartados:
        print(f"aviso: {descartados} eventos com data ilegível descartados", file=sys.stderr)
    agora = pd.Timestamp.now()
    futuros = int((df["ts"] > agora).sum())
    fb._stats()["eventos_futuro_descartados"] = futuros
    if futuros:
        print(f"aviso: {futuros} eventos com data no futuro descartados", file=sys.stderr)
    antes_2008 = int((df["ts"] < pd.Timestamp("2008-01-01")).sum())
    fb._stats()["eventos_antes_2008_descartados"] = antes_2008
    df = df[(df["ts"] >= "2008-01-01") & (df["ts"] <= agora)]

    fb._stats()["eventos_finais"] = len(df)
    fb._stats()["repos_finais"] = int(df["codigo"].nunique())
    fb._stats()["contribuidores_finais"] = int(df["pessoa"].nunique())
    return pd.DataFrame(
        {
            "contributor_id": df["pessoa"].to_numpy(),
            "event_type": pd.Categorical.from_codes(df["tipo"].to_numpy(), categories=nomes_tipo),
            "timestamp": df["ts"].to_numpy(),
        }
    )
