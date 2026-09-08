#!/usr/bin/env python
"""Gera as figuras da pirâmide de uma linguagem a partir de uma coleta bruta em CSV.

    .venv/bin/python scripts/figuras_linguagem_bruta.py
    .venv/bin/python scripts/figuras_linguagem_bruta.py --linguagem elixir
    .venv/bin/python scripts/figuras_linguagem_bruta.py --linguagem clojure --rodada 1
    .venv/bin/python scripts/figuras_linguagem_bruta.py --figuras piramide,abandono

A coleta ainda não fala o contrato `ActivityDataSource` (é CSV cru de um
coletor externo, não o adaptador `ghapi`): este script traduz na hora, com uma
fonte descartável (`FonteCSV`, dentro de `monta_fonte`) que nunca é gravada em
disco. `--linguagem` escolhe qual coleta ler (ver `LINGUAGENS` abaixo pra
extensão de arquivo e nome exato usado no dado). Só Clojure já teve duas
coletas com formato diferente, escolhidas por `--rodada`:

  --rodada 1  `eventos_repositorios.csv`, um arquivo só, 3 tipos de evento
              (commit, issue, pr). Coleta antiga, ~1000 repositórios. Só existe
              para Clojure.
  --rodada 2  `eventos_api.csv` + `eventos_git.csv`, pipe-delimitado, 7 tipos
              de evento. Formato corrente, o único que Elixir e Zig têm.
              Default.

Figuras disponíveis (`--figuras`, separadas por vírgula; default "all"):
  piramide       pirâmide avulsa (table1, janela 3 meses), uma por valor de
                 BANDAS_MESES_PIRAMIDE (default: 3 meses "com quarter" e 12
                 meses "sem quarter")
  linha-tempo    linha do tempo automática (ULTIMOS_ANOS, PASSO_ANOS, banda 3 meses)
  linha-tempo-4  linha do tempo com ANOS_ESCOLHIDOS e banda de BANDA_ANOS anos,
                 gerada duas vezes: janela de população de 3 meses e de 12 meses
  projecao       projeção coorte-componente (tabela impressa + figura)
  magnetismo     magnetismo x stickiness por ano (scatter, sem cor)
  stickiness-ano stickiness por ano (barra)
  ccr-ncr        CCR x NCR por trimestre (scatter)
  fantasmas      contas apagadas ('ghost') por ano: não entram na pirâmide,
                 só o registro de quantas existiram ao longo do tempo
  abandono       pessoas com conta de verdade sem contribuição nos últimos 3
                 meses (referência fixa: o evento mais recente da coleta),
                 por ano da última contribuição, mais as versões acumuladas
  voltas         quantas voltas (retorno após 3+ meses sumido) por ano
  contribuintes  contribuinte distinto por ano

Variáveis de ambiente (sobrepõem o default de cada uma; caminho sobrepõe o que
`--linguagem`/`--rodada` escolheriam):
  LINGUAGEM            clojure | elixir | zig (default: clojure; equivalente a `--linguagem`)
  RODADA               1 ou 2 (default: 2; equivalente a `--rodada`)
  DADOS_DIR            pasta da coleta (default: depende de LINGUAGEM/RODADA)
  SAIDA_DIR            pasta de saída (default: depende de LINGUAGEM)
  FIGURAS              quais gerar (default: all; equivalente a `--figuras`)
  ULTIMOS_ANOS         janela da linha-tempo automática (default: 20)
  PASSO_ANOS           espaçamento da linha-tempo automática (default: 2)
  ANOS_ESCOLHIDOS      anos da linha-tempo-4, separados por vírgula (default: 2010,2016,2020,2026)
  BANDA_ANOS_TIMELINE  largura de banda (anos) do eixo Y da linha-tempo-4 (default: 2)
  BANDAS_MESES_PIRAMIDE  larguras de banda (meses) da figura "piramide", uma
                          por valor, separadas por vírgula (default: 3,12)
  FUNDIR_IDENTIDADES   liga a heurística de fusão nome-de-commit <-> login
                       (default: false; ver `candidatos_mesma_pessoa`)
  FUSAO_JACCARD_MIN    limiar de sobreposição de repositório pra fundir (default: 0.5)
  FUSAO_REPOS_MIN      repositórios mínimos em comum pra considerar candidato (default: 5)

Não mexe em `config/` nem `output/` do repo: cada figura roda numa cópia de
rascunho (`tempfile.mkdtemp`), apagada no fim. A saída vai para fora do
repositório, em `~/Documents/pyramid-tmp/<linguagem>/` por default: a coleta
não passou pelo contrato de adaptador nem pela auditoria de `docs/linguagem/`,
então não é material para `docs/`. `~/Documents/pyramid-tmp/` é a pasta
temporária de TODAS as linguagens: cada uma tem a própria subpasta, e um plot
que compare linguagens (nenhum existe ainda) vai solto ali, fora de subpasta.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import matplotlib
import pandas as pd
import yaml

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

DAYS_PER_MONTH = 30.4375

# Cada rodada de coleta tem o próprio enum de tipo bruto -> canônico. A rodada
# 1 só tinha 3 tipos; a 2 trouxe os 7 do contrato (ver docs/ferramenta/FONTES.md).
# Isso é do FORMATO da coleta, não da linguagem: as duas tabelas valem pra
# qualquer `--linguagem`.
MAPA_TIPO_R1 = {"commit": "commits", "issue": "issues", "pr": "pull_requests"}
MAPA_TIPO_R2 = {
    "commit": "commits",
    "commit_comment": "commit_comments",
    "issue": "issues",
    "issue_comment": "issue_comments",
    "issue_event": "issue_events",
    "pr": "pull_requests",
    "pr_comment": "pull_request_comments",
}


@dataclass(frozen=True)
class Linguagem:
    """O que muda de uma linguagem pra outra: nada de método, só esses 4 fatos."""

    nome: str  # valor exato em `language`/`mainLanguage` no CSV (github-linguist)
    slug: str  # nome de pasta e de arquivo (minúsculo, sem espaço)
    extensoes: tuple[str, ...]  # extensão de arquivo-fonte, pro fallback do commit sem `language`
    tem_rodada_1: bool  # só Clojure teve uma coleta no formato antigo (3 tipos, 1 arquivo só)


_EXT_CLOJURE = (".clj", ".cljs", ".cljc", ".cljx", ".edn", ".bb")
LINGUAGENS = {
    "clojure": Linguagem("Clojure", "clojure", _EXT_CLOJURE, True),
    "elixir": Linguagem("Elixir", "elixir", (".ex", ".exs"), False),
    "zig": Linguagem("Zig", "zig", (".zig",), False),
    "python": Linguagem("Python", "python", (".py", ".pyw", ".pyi"), False),
}


class _EstadoLinguagem:
    """Linguagem escolhida, mutável por `--linguagem` (atributo, não `global`:
    mesmo padrão de `_Config` logo abaixo)."""

    def aplica(self, slug: str) -> None:
        if slug not in LINGUAGENS:
            raise SystemExit(f"--linguagem desconhecida: {slug!r}. Use: {', '.join(LINGUAGENS)}")
        self.atual = LINGUAGENS[slug]


LING = _EstadoLinguagem()
LING.aplica(os.environ.get("LINGUAGEM", "clojure"))

# Pasta temporária única do projeto, não do dataset: cada linguagem tem a
# própria subpasta (`clojure/`, `elixir/`, `zig/`, ...), pra achar a figura sem
# lembrar de qual rodada ela veio. Um plot que compare linguagens entre si
# (nenhum existe ainda) vai direto em `TMP_BASE`, fora de qualquer subpasta.
TMP_BASE = Path.home() / "Documents" / "pyramid-tmp"


def _caminhos_padrao(rodada: int) -> tuple[Path, Path]:
    # "rodada" é o formato do dado (1 = arquivo único antigo, 2 = api+git
    # split). Só Clojure já foi coletada duas vezes com formato diferente, e
    # por coincidência o nome da pasta de cada coleta bate com o número da
    # rodada. Elixir e Zig só têm uma coleta cada (sempre no formato 2), e ela
    # se chama "first-round" mesmo sendo formato 2: "first" conta coleta, não
    # formato.
    if LING.atual.tem_rodada_1:
        sufixo = "first-round" if rodada == 1 else "second-round"
    else:
        sufixo = "first-round"
    dados = ROOT / "data" / f"{LING.atual.slug}-{sufixo}"
    saida = TMP_BASE / LING.atual.slug
    return dados, saida


class _Config:
    """Caminhos de entrada/saída, escolhidos por rodada e sobrepostos por env
    var. Atributo de objeto, não `global`: mesmo padrão que `roda_pipeline` já
    usa para trocar `config.OUTPUT_DIR` de fora do módulo `config`."""

    def aplica(self, rodada: int) -> None:
        dados_padrao, saida_padrao = _caminhos_padrao(rodada)
        self.dados = Path(os.environ.get("DADOS_DIR", dados_padrao))
        self.saida = Path(os.environ.get("SAIDA_DIR", saida_padrao))


def _rodada_do_ambiente() -> int:
    rodada = int(os.environ.get("RODADA", "2"))
    if rodada not in (1, 2):
        raise SystemExit(f"RODADA={rodada}: use 1 ou 2.")
    return rodada


RODADA = _rodada_do_ambiente()
CFG = _Config()
CFG.aplica(RODADA)
FIGURAS = os.environ.get("FIGURAS", "all")
ULTIMOS_ANOS = int(os.environ.get("ULTIMOS_ANOS", "20"))
PASSO_ANOS = int(os.environ.get("PASSO_ANOS", "2"))
ANOS_ESCOLHIDOS = [
    int(a) for a in os.environ.get("ANOS_ESCOLHIDOS", "2010,2016,2020,2026").split(",")
]
BANDA_ANOS_TIMELINE = int(os.environ.get("BANDA_ANOS_TIMELINE", "2"))
BANDAS_MESES_PIRAMIDE = [int(b) for b in os.environ.get("BANDAS_MESES_PIRAMIDE", "3,12").split(",")]

# Heurística OPT-IN de fusão de identidade (nome de commit <-> login de
# issue/pr que compartilham quase todo repositório). Desligada por default:
# é heurística, não certeza (duas pessoas diferentes podem coincidir de
# repositório), e a promessa é a coleta trazer `author.id` de verdade, que
# resolve isso sem heurística nenhuma. Liga com FUNDIR_IDENTIDADES=true.
FUNDIR_IDENTIDADES = os.environ.get("FUNDIR_IDENTIDADES", "false").lower() == "true"
FUSAO_JACCARD_MIN = float(os.environ.get("FUSAO_JACCARD_MIN", "0.5"))
FUSAO_REPOS_MIN = int(os.environ.get("FUSAO_REPOS_MIN", "5"))


def _id_estavel(texto: str) -> int:
    return int(hashlib.sha1(str(texto).encode()).hexdigest()[:15], 16)


def candidatos_mesma_pessoa(df: pd.DataFrame) -> dict[str, str]:
    """Nome de commit (git log) <-> login (issue/pr) que compartilham quase
    todo repositório: candidato forte a ser a mesma pessoa sob dois nomes.
    Heurística, não certeza. Ver `FUNDIR_IDENTIDADES` no topo do arquivo."""
    tipo_por_autor = df.groupby("author")["event_type"].apply(set)
    so_commit = [a for a, t in tipo_por_autor.items() if t == {"commit"}]
    so_api = [a for a, t in tipo_por_autor.items() if t and t <= {"issue", "pr"}]
    repos_de = df.groupby("author")["repo_id"].apply(set)
    contagem = df["author"].value_counts()
    so_commit = [a for a in so_commit if contagem[a] >= FUSAO_REPOS_MIN]
    so_api = [a for a in so_api if contagem[a] >= FUSAO_REPOS_MIN]

    mapa: dict[str, str] = {}
    for c in so_commit:
        rc = repos_de[c]
        melhor: tuple[str, float] | None = None
        for a in so_api:
            ra = repos_de[a]
            inter = len(rc & ra)
            if inter < FUSAO_REPOS_MIN:
                continue
            jac = inter / len(rc | ra)
            if melhor is None or jac > melhor[1]:
                melhor = (a, jac)
        if melhor and melhor[1] >= FUSAO_JACCARD_MIN:
            mapa[c] = melhor[0]
    return mapa


def _salva_fantasmas_por_ano(fantasmas: pd.DataFrame) -> None:
    """Não entram na pirâmide (não são uma pessoa rastreável), mas ficam
    registrados: quantos eventos de conta apagada por ano, à parte."""
    ts = pd.to_datetime(
        fantasmas["created_at"], utc=True, format="ISO8601", errors="coerce"
    ).dt.tz_localize(None)
    por_ano = ts.dt.year.value_counts().sort_index()
    CFG.saida.mkdir(parents=True, exist_ok=True)
    caminho = CFG.saida / "fantasmas_por_ano.csv"
    por_ano.rename("eventos_de_conta_apagada").to_csv(caminho, header=True, index_label="ano")
    print(
        f"salvo: {caminho} ({len(fantasmas)} eventos de conta apagada, "
        f"{por_ano.index.min()}-{por_ano.index.max()})",
        file=sys.stderr,
    )


def _carrega_r1() -> pd.DataFrame:
    """`eventos_repositorios.csv`: um arquivo só, 3 tipos, sem `language`."""
    df = pd.read_csv(CFG.dados / "eventos_repositorios.csv")
    df = df[df["author"].notna()].copy()
    df = df.rename(columns={"author": "identidade"})
    return df[["repo_id", "event_type", "identidade", "created_at"]]


def _linguagem_principal() -> dict[str, str]:
    """`repo_id -> mainLanguage`, do arquivo-alvo da coleta (rodada 2)."""
    alvo = pd.read_csv(
        CFG.dados / f"repositorios_{LING.atual.slug}_alvo.csv", dtype={"repo_id": str}
    )
    return dict(zip(alvo["repo_id"], alvo["mainLanguage"], strict=True))


# Um repositório "wrapper" (ex.: allyourcodebase/nasm, que empacota o NASM com
# um build.zig por cima) tem `mainLanguage: Zig` pro GitHub, mas 0,21% do
# código é Zig de verdade: o resto é o histórico inteiro do projeto que ele
# empacota, importado junto. Sem esse corte, esse histórico alheio (de antes
# da linguagem escolhida sequer existir, no caso do NASM) entra na amostra
# inteiro. Limiar de maioria simples: mais da metade do código do repositório
# tem que ser da linguagem escolhida.
LIMIAR_SHARE_LINGUAGEM = 0.5


def _repos_elegiveis(rodada: int) -> set[str]:
    """`repo_id` cujo repositório tem mais de `LIMIAR_SHARE_LINGUAGEM` do
    código na linguagem escolhida. Rodada 1 já traz a fração pronta
    (`clojure_ratio`); rodada 2 traz o mapa completo de bytes por linguagem
    (`languages`, JSON) e a fração é calculada aqui."""
    alvo = pd.read_csv(
        CFG.dados / f"repositorios_{LING.atual.slug}_alvo.csv", dtype={"repo_id": str}
    )
    if rodada == 1:
        participacao = alvo["clojure_ratio"]
    else:

        def _participacao(linguagens_json: str) -> float:
            try:
                mapa = json.loads(linguagens_json)
            except (TypeError, ValueError):
                return 0.0
            total = sum(mapa.values())
            return mapa.get(LING.atual.nome, 0) / total if total else 0.0

        participacao = alvo["languages"].map(_participacao)

    mascara = participacao > LIMIAR_SHARE_LINGUAGEM
    excluidos = int((~mascara).sum())
    if excluidos:
        print(
            f"aviso: {excluidos} repositórios excluídos por terem <= "
            f"{LIMIAR_SHARE_LINGUAGEM:.0%} de {LING.atual.nome} no código",
            file=sys.stderr,
        )
    return set(alvo.loc[mascara, "repo_id"])


def _repo_created_at() -> dict[str, pd.Timestamp]:
    """`repo_id -> createdAt`, do arquivo-alvo (só existe na rodada 2). Usado
    por `_carrega_git` pra decidir, entre `repo_id` diferentes que carregam o
    MESMO commit (autor, data e arquivos idênticos: histórico herdado de fork
    ou clone completo), qual fica com o evento: o repositório criado há mais
    tempo, mais perto do original. `isFork` não serve pra achar esses casos:
    achado em Zig, 3 dos 7 `repo_id` que compartilhavam o histórico inicial
    do compilador `ziglang/zig` vinham marcados `isFork=False` (fork
    "destacado" da rede do GitHub, ou push manual de um clone completo pra um
    repositório novo, os dois preservam o histórico sem preservar a marca)."""
    alvo = pd.read_csv(
        CFG.dados / f"repositorios_{LING.atual.slug}_alvo.csv", dtype={"repo_id": str}
    )
    criado = pd.to_datetime(
        alvo["createdAt"], utc=True, format="ISO8601", errors="coerce"
    ).dt.tz_localize(None)
    return dict(zip(alvo["repo_id"], criado, strict=True))


def _e_arquivo_da_linguagem(caminhos: str) -> bool:
    """Ao menos um arquivo tocado tem extensão da linguagem escolhida."""
    if not isinstance(caminhos, str) or not caminhos:
        return False
    return any(p.lower().endswith(LING.atual.extensoes) for p in caminhos.split(";"))


def _carrega_api(main_lang: dict[str, str]) -> pd.DataFrame:
    """`eventos_api.csv`: issue/pr/comentário/evento. Vem pipe-delimitado.

    `language` já vem preenchido pelo coletor pra issue_comment/issue_event/
    pull_request_comment (fallback = linguagem principal do repositório,
    conferido: 100% de bate nos casos checados). `issue` e `pr` não vêm
    preenchidos (lacuna do lado da coleta); aplicamos o mesmo fallback aqui.
    """
    df = pd.read_csv(CFG.dados / "eventos_api.csv", sep="|", dtype={"repo_id": str})
    df = df[df["author_login"].notna()].copy()
    df["language"] = df["language"].fillna(df["repo_id"].map(main_lang))
    df = df[df["language"] == LING.atual.nome]
    df = df.rename(columns={"author_login": "identidade"})
    return df[["repo_id", "event_type", "identidade", "created_at"]]


def _carrega_git() -> pd.DataFrame:
    """`eventos_git.csv`: só commit, do clone. Sem `language`; decide pela
    extensão dos arquivos tocados.

    Não tem fallback pra linguagem principal do repositório quando o commit
    não toca arquivo nenhum (merge vazio, ou lacuna da coleta). Existia um
    fallback assim; caiu depois de achar o caso `Lukáš Lalinský`/Chromaprint
    (repo_id 3899291): repositório de 2011, reescrito aos poucos até virar
    majoritariamente Zig hoje, com um punhado de commit de 2011 sem `files`
    registrado. O fallback lia "sem arquivo, repositório é Zig hoje" e
    contava aquele commit de 2011 como atividade Zig, 4 anos antes da
    linguagem existir. Sem forma de saber que linguagem um commit sem
    `files` tocou de verdade, a escolha correta é não contar, não chutar
    pela linguagem atual do repositório.

    Também deduplica commit idêntico (mesmo autor, mesma data, mesmos
    arquivos) que aparece em `repo_id` diferentes: fork completo ou clone
    empurrado pra um repositório novo, preservando o histórico do original.
    Sem isso, o mesmo commit conta uma vez por cópia, e um contribuidor de
    2015 aparece "ativo" em repositórios criados anos depois. Ver
    `_repo_created_at`."""
    df = pd.read_csv(CFG.dados / "eventos_git.csv", sep="|", dtype={"repo_id": str})
    df = df[df["author"].notna()].copy()
    df = df[df["files"].map(_e_arquivo_da_linguagem)]

    df["_criado"] = df["repo_id"].map(_repo_created_at())
    chave = ["author", "created_at", "files"]
    mais_antigo = df.groupby(chave)["_criado"].transform("min")
    duplicado = df["_criado"] > mais_antigo
    if duplicado.any():
        print(
            f"aviso: {int(duplicado.sum())} commits descartados por serem cópia de "
            "histórico já contado num repositório criado antes (fork completo ou "
            "clone empurrado pra um repositório novo)",
            file=sys.stderr,
        )
    df = df[~duplicado].drop(columns="_criado")

    df = df.rename(columns={"author": "identidade"})
    return df[["repo_id", "event_type", "identidade", "created_at"]]


def _carrega_r2() -> pd.DataFrame:
    """`issue`/`pr` sem `language` (e `issue_comment`/`issue_event`/`pr_comment`,
    já preenchidos assim pelo próprio coletor) usam a linguagem principal do
    repositório como fallback: a API não diz em que linguagem uma issue foi
    aberta, só o repositório sabe. Isso data qualquer issue antiga como sendo
    da linguagem atual do repositório, mesmo se o repositório só virou
    majoritariamente Zig/Elixir/... anos depois (achado em Zig: issue de 2014
    num repositório que só teve o primeiro commit `.zig` de verdade em 2018).
    Piso: nenhum evento conta pra essa linguagem antes do primeiro commit que
    de fato toca um arquivo dela, no mesmo repositório. Repositório sem
    nenhum commit assim (raro, dado o filtro de >50% de participação) fica
    sem piso, evento nenhum descartado por essa regra."""
    main_lang = _linguagem_principal()
    git = _carrega_git()
    piso_por_repo = (
        pd.to_datetime(git["created_at"], utc=True, format="ISO8601", errors="coerce")
        .groupby(git["repo_id"])
        .min()
        .dt.tz_localize(None)
    )

    todos = pd.concat([_carrega_api(main_lang), git], ignore_index=True)
    timestamp = pd.to_datetime(
        todos["created_at"], utc=True, format="ISO8601", errors="coerce"
    ).dt.tz_localize(None)
    piso = todos["repo_id"].map(piso_por_repo)
    antes_do_piso = piso.notna() & (timestamp < piso)
    if antes_do_piso.any():
        print(
            f"aviso: {int(antes_do_piso.sum())} eventos descartados por serem anteriores "
            f"ao primeiro commit que de fato toca {LING.atual.nome} no mesmo repositório "
            "(issue/pr/comentário datado antes do repositório virar essa linguagem)",
            file=sys.stderr,
        )
    return todos[~antes_do_piso]


def _finaliza_eventos(bruto: pd.DataFrame, mapa_tipo: dict[str, str]) -> pd.DataFrame:
    """Filtro e tradução comuns às duas rodadas, uma vez que cada uma já
    devolveu `[repo_id, event_type(bruto), identidade, created_at]`."""
    df = bruto

    # "ghost": sentinela fixa que a API do GitHub devolve no lugar do autor
    # quando a conta foi apagada. Não é uma pessoa (são N contas diferentes,
    # já deletadas, colapsadas no mesmo literal), então não entra na
    # pirâmide. Fica só o registro de quantos existiram por ano.
    fantasma = df["identidade"] == "ghost"
    if fantasma.sum():
        _salva_fantasmas_por_ano(df[fantasma])
    df = df[~fantasma]

    # `[bot]` é o sufixo que o próprio GitHub gruda no login de toda conta de
    # app/bot instalada (Dependabot, Renovate, GitHub Actions, ...). É convenção
    # da plataforma, não heurística nossa. Cobre login (API) e nome de commit (git).
    bot = df["identidade"].astype(str).str.contains(r"\[bot\]$", regex=True)
    df = df[~bot]

    print(
        f"aviso: {fantasma.sum()} eventos de conta apagada descartados da pirâmide "
        f"(registrados à parte); {bot.sum()} eventos de bot descartados",
        file=sys.stderr,
    )

    if FUNDIR_IDENTIDADES:
        mapa = candidatos_mesma_pessoa(df.rename(columns={"identidade": "author"}))
        if mapa:
            afetados = df["identidade"].isin(mapa).sum()
            print(
                f"aviso: FUNDIR_IDENTIDADES ligado: fundindo {len(mapa)} identidades "
                f"({afetados} eventos), jaccard>={FUSAO_JACCARD_MIN}, repos_min={FUSAO_REPOS_MIN}",
                file=sys.stderr,
            )
            df["identidade"] = df["identidade"].replace(mapa)

    df["event_type"] = df["event_type"].map(mapa_tipo)
    df = df[df["event_type"].notna()]
    # `errors="coerce"`: uma coleta em andamento pode deixar linha cortada no
    # meio da escrita, com o literal do formato do `git log` (`%aI`) vazando
    # pra dentro da data em vez de uma data de verdade. Isso vira `NaT` em vez
    # de derrubar a carga inteira, e o filtro de 2008 abaixo já descarta `NaT`
    # (comparação com `NaT` é sempre falsa).
    timestamp = pd.to_datetime(df["created_at"], utc=True, format="ISO8601", errors="coerce")
    descartados = timestamp.isna().sum()
    if descartados:
        print(f"aviso: {descartados} eventos com data ilegível descartados", file=sys.stderr)
    df["timestamp"] = timestamp.dt.tz_localize(None)
    # Piso: 1 evento corrompido (2001), achado na rodada 1. Teto: relógio do
    # computador de quem commitou estava errado (achado na coleta de Python,
    # 6 eventos com data em 2030/2037). Sem o teto, esse punhado de outlier
    # estica a série de trimestre pra anos que ainda não existem, e a última
    # data da série (usada como "agora" pra classificar a pirâmide inteira)
    # passa a ser um ano no futuro em vez do último dado de verdade.
    agora = pd.Timestamp.now()
    futuros = int((df["timestamp"] > agora).sum())
    if futuros:
        print(f"aviso: {futuros} eventos com data no futuro descartados", file=sys.stderr)
    df = df[(df["timestamp"] >= "2008-01-01") & (df["timestamp"] <= agora)]
    df["contributor_id"] = df["identidade"].map(_id_estavel)
    df["scope_id"] = df["repo_id"].map(_id_estavel)
    return df[["scope_id", "contributor_id", "event_type", "timestamp", "repo_id"]].reset_index(
        drop=True
    )


def carrega_eventos(rodada: int = RODADA) -> pd.DataFrame:
    elegiveis = _repos_elegiveis(rodada)
    if rodada == 1:
        bruto, mapa_tipo = _carrega_r1(), MAPA_TIPO_R1
    else:
        bruto, mapa_tipo = _carrega_r2(), MAPA_TIPO_R2
    bruto = bruto[bruto["repo_id"].isin(elegiveis)]
    return _finaliza_eventos(bruto, mapa_tipo)


def monta_fonte(eventos: pd.DataFrame) -> type:
    """`eventos["idioma"]`, quando presente, dá a linguagem por LINHA (não a
    global `LING.atual.nome`): é o que permite `gera_comparacao_linguagens`
    juntar as 4 coletas numa fonte só e deixar `unit: language` (`_por_linguagem`
    em `units.py`) somar os escopos de cada linguagem de verdade, no lugar de
    marcar tudo com uma linguagem só. Ausente (todo uso de uma linguagem por
    vez), cai no comportamento de sempre."""
    from pyramid.sources.base import ActivityDataSource

    por_repo = {sid: g for sid, g in eventos.groupby("scope_id")}
    rotulo = eventos.drop_duplicates("scope_id").set_index("scope_id")["repo_id"].to_dict()
    idioma = (
        eventos.drop_duplicates("scope_id").set_index("scope_id")["idioma"].to_dict()
        if "idioma" in eventos.columns
        else None
    )

    class FonteCSV(ActivityDataSource):
        def list_scopes(self) -> list[int]:
            return sorted(por_repo)

        def get_events(self, scope_id: int) -> pd.DataFrame:
            cols = ["scope_id", "contributor_id", "event_type", "timestamp"]
            return por_repo[scope_id][cols].reset_index(drop=True)

        def scope_meta(self, scope_id: int) -> dict:
            g = por_repo[scope_id]
            return {
                "label": rotulo[scope_id],
                "language": idioma[scope_id] if idioma else LING.atual.nome,
                "created_at": g["timestamp"].min(),
            }

    return FonteCSV


def _serie_trimestral(
    eventos: pd.DataFrame, fim_forcado: pd.Timestamp | None = None
) -> pd.DatetimeIndex:
    inicio = (eventos["timestamp"].min() + pd.offsets.QuarterEnd(0)).normalize()
    fim = (
        fim_forcado
        if fim_forcado is not None
        else (eventos["timestamp"].max() - pd.offsets.QuarterEnd(1)).normalize()
    )
    return pd.date_range(inicio, fim, freq="QE")


def escreve_config(
    scratch: Path,
    eventos: pd.DataFrame,
    band_months: int,
    fim_forcado: pd.Timestamp | None = None,
) -> None:
    alvo = scratch / "config" / "settings.yaml"
    cfg = yaml.safe_load(alvo.read_text(encoding="utf-8"))
    cfg["analysis"]["unit"] = "language"
    cfg["taxonomy"]["variant"] = "table1"
    cfg["plots"]["pyramid_window_months"] = 3
    cfg["periods"]["band_months"] = band_months
    cfg["periods"]["band_days"] = round(band_months * DAYS_PER_MONTH)

    serie = _serie_trimestral(eventos, fim_forcado)
    cfg["snapshots"]["start"] = str(serie[0].date())
    cfg["snapshots"]["end"] = str(serie[-1].date())
    cfg["snapshots"]["classification_snapshot"] = str(serie[-1].date())
    cfg["snapshots"]["projection_base"] = [str(serie[-3].date()), str(serie[-2].date())]
    cfg["snapshots"]["projection_target"] = str(serie[-1].date())
    # Projeção exige > 100 contribuidores no snapshot base para o escopo entrar.
    # Nossa amostra é grande o bastante; mantém o limiar do artigo.
    alvo.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")


def roda_pipeline(
    eventos: pd.DataFrame, band_months: int, fim_forcado: pd.Timestamp | None = None
) -> SimpleNamespace:
    """Extract/classify/snapshots/metrics numa config de rascunho.

    `fim_forcado` sobrepõe o último trimestre da série (ver `gera_piramide_comparativa`,
    que precisa das 4 linguagens no mesmo corte em vez do próprio máximo de cada uma).
    Devolve os módulos e o scope id.
    """
    scratch = Path(tempfile.mkdtemp(prefix="pyr_lang_fig_"))
    shutil.copytree(ROOT / "config", scratch / "config")
    escreve_config(scratch, eventos, band_months, fim_forcado)

    from pyramid import config

    config.CONFIG_DIR = scratch / "config"
    config.OUTPUT_DIR = scratch / "output"
    config.LOG_DIR = scratch / "logs"
    config.settings.cache_clear()
    config.checkpoints.cache_clear()

    from pyramid import logging_config

    logging_config.LOG_DIR = config.LOG_DIR

    from pyramid import attractiveness as attr
    from pyramid import classify, extract, metrics, plots, projection, snapshots, units

    fonte_cls = monta_fonte(eventos)
    fabrica = lambda: fonte_cls(config.settings())  # noqa: E731
    # `classify`/`snapshots`/`metrics`/`projection`/`attractiveness` importaram
    # `source` com `from .extract import source`: cada um tem seu próprio nome
    # ligado à função original. Sobrescreve todos, não só `extract.source`.
    extract.source = fabrica
    classify.source = fabrica
    snapshots.source = fabrica
    metrics.source = fabrica
    attr.source = fabrica

    for estagio in (extract, classify, snapshots, metrics):
        res = estagio.run(None, force=True, fail_fast=True)
        if res.get("failed"):
            raise SystemExit(f"{estagio.STAGE} falhou: {res['failed']}")

    sid = units.id_da_linguagem(LING.atual.nome)
    return SimpleNamespace(
        config=config,
        plots=plots,
        snapshots=snapshots,
        metrics=metrics,
        projection=projection,
        attractiveness=attr,
        scratch=scratch,
        sid=sid,
    )


def _salva(caminho: Path, nome: str) -> None:
    CFG.saida.mkdir(parents=True, exist_ok=True)
    destino = CFG.saida / nome
    shutil.copy(caminho, destino)
    print(f"salvo: {destino}")


def _salva_fig(fig: object, nome: str) -> None:
    CFG.saida.mkdir(parents=True, exist_ok=True)
    caminho = CFG.saida / nome
    fig.savefig(caminho, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"salvo: {caminho}")


def gera_piramide_multi(eventos: pd.DataFrame) -> None:
    """Uma pirâmide por valor de `BANDAS_MESES_PIRAMIDE` (default: 3 e 12 meses
    de banda). 3 meses é a divisão em quarter da metodologia; qualquer outro
    valor não é. O nome do arquivo carrega os dois: se é quarter ou não, e a
    largura de banda exata, pra nenhuma versão pisar na outra."""
    for banda_meses in BANDAS_MESES_PIRAMIDE:
        pl = roda_pipeline(eventos, band_months=banda_meses)
        try:
            caminho = pl.plots.figure_pyramid(pl.sid)
            rotulo = "comquarter" if banda_meses == 3 else "semquarter"
            nome = f"piramide_{LING.atual.slug}_metodologia_{rotulo}_banda{banda_meses}m.png"
            _salva(caminho, nome)
        finally:
            shutil.rmtree(pl.scratch, ignore_errors=True)


def gera_linha_tempo(pl: SimpleNamespace) -> None:
    caminho = pl.plots.figure_pyramid_timeline(
        pl.sid, ultimos_anos=ULTIMOS_ANOS, passo_anos=PASSO_ANOS
    )
    nome = f"linha_do_tempo_{LING.atual.slug}_metodologia_{ULTIMOS_ANOS}anos_passo{PASSO_ANOS}.png"
    _salva(caminho, nome)


def gera_linha_tempo_4(eventos: pd.DataFrame) -> None:
    """Banda de eixo Y customizada: precisa rodar snapshots de novo com outro band_months."""
    pl = roda_pipeline(eventos, band_months=BANDA_ANOS_TIMELINE * 12)
    for janela in (3, 12):
        alvo = pl.scratch / "config" / "settings.yaml"
        cfg = yaml.safe_load(alvo.read_text(encoding="utf-8"))
        cfg["plots"]["pyramid_window_months"] = janela
        alvo.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
        pl.config.settings.cache_clear()
        caminho = pl.plots.figure_pyramid_timeline(pl.sid, anos=ANOS_ESCOLHIDOS)
        anos_txt = "-".join(str(a) for a in ANOS_ESCOLHIDOS)
        nome = (
            f"linha_do_tempo_{LING.atual.slug}_4anos_{anos_txt}"
            f"_banda{BANDA_ANOS_TIMELINE}a_janela{janela}m.png"
        )
        _salva(caminho, nome)
    shutil.rmtree(pl.scratch, ignore_errors=True)


def gera_projecao(pl: SimpleNamespace) -> None:
    """`projection.run()` trava em `unit: project` (UNIDADES=("project",)),
    mas `compute()` não tem essa checagem: é chamada direta, contornando só
    o portão do CLI, não a lógica. Ver o comentário de `UNIDADES` em
    `projection.py`, que já prevê essa amostra maior destravando o portão."""
    df = pl.projection.compute()
    linha = df[df["scope_id"] == pl.sid]
    if linha.empty:
        limiar = pl.config.settings()["projection"]["min_contributors"]
        print(
            f"{LING.atual.nome} (scope_id={pl.sid}) não tem >{limiar} contribuidores ativos "
            "no snapshot base: fora do critério de elegibilidade do método.",
            file=sys.stderr,
        )
        return
    ancoras = pl.snapshots.anchors()
    print(f"\n=== Projeção coorte-componente, {LING.atual.nome} ===")
    print(
        f"base T-1: {ancoras['projection_base'][0]}  base T: {ancoras['projection_base'][1]}"
        f"  alvo: {ancoras['projection_target']}"
    )
    todos = linha[linha["category"] == "all"].sort_values("band")
    print(todos.to_string(index=False))
    print("\nmediana do ABRE por categoria (menor = melhor; cohort vs baseline):")
    resumo = linha.groupby("category")[["abre_cohort", "abre_baseline"]].median()
    print(resumo.to_string())
    saida = CFG.saida / f"projecao_{LING.atual.slug}_metodologia_numeros.csv"
    CFG.saida.mkdir(parents=True, exist_ok=True)
    linha.to_csv(saida, index=False)
    print(f"salvo: {saida}")


def gera_projecao_backtest(eventos: pd.DataFrame, ano_base: int) -> None:
    """Mesma projeção coorte-componente de `gera_projecao`, mas ancorada em Q4
    de `ano_base` (T-1 = Q3, T = Q4, alvo = Q1 do ano seguinte) em vez do
    último trimestre da coleta: `roda_pipeline`/`escreve_config` já sabem
    forçar esse corte (`fim_forcado`, criado pra `gera_piramide_comparativa`).
    Mostra se a taxa de sobrevivência calculada num ponto passado da história
    ainda acerta o real, não só no trimestre mais recente."""
    alvo_forcado = pd.Timestamp(f"{ano_base + 1}-03-31")
    pl = roda_pipeline(eventos, band_months=3, fim_forcado=alvo_forcado)
    try:
        df = pl.projection.compute()
        linha = df[df["scope_id"] == pl.sid]
        if linha.empty:
            limiar = pl.config.settings()["projection"]["min_contributors"]
            print(
                f"{LING.atual.nome} em {ano_base} (scope_id={pl.sid}) não tem >{limiar} "
                "contribuidores ativos no snapshot base: fora do critério de elegibilidade.",
                file=sys.stderr,
            )
            return
        ancoras = pl.snapshots.anchors()
        alvo_real = pd.Timestamp(ancoras["projection_target"]).date()
        print(f"\n=== Backtest {ano_base}, {LING.atual.nome} ===")
        print(
            f"base T-1: {ancoras['projection_base'][0]}  base T: {ancoras['projection_base'][1]}"
            f"  alvo: {ancoras['projection_target']}"
        )
        resumo = linha.groupby("category")[["abre_cohort", "abre_baseline"]].median()
        print("mediana do ABRE por categoria (menor = melhor; cohort vs baseline):")
        print(resumo.to_string())

        CFG.saida.mkdir(parents=True, exist_ok=True)
        saida_csv = CFG.saida / f"projecao_{LING.atual.slug}_backtest_{ano_base}.csv"
        linha.to_csv(saida_csv, index=False)
        print(f"salvo: {saida_csv}")

        todos = linha[linha["category"] == "all"].sort_values("band")
        n = len(todos)
        largura = 0.25
        x = list(range(n))
        fig, ax = plt.subplots(figsize=(max(7.0, 0.5 * n), 4.5))
        ax.bar([i - largura for i in x], todos["actual"], largura, color="black", label="real")
        ax.bar(x, todos["cohort_pred"], largura, color="#3b6fa0", label="previsto (coorte)")
        ax.bar(
            [i + largura for i in x],
            todos["baseline_pred"],
            largura,
            color="#aaaaaa",
            label="previsto (baseline)",
        )
        ax.set_xticks(x)
        ax.set_xticklabels(todos["band"].astype(int))
        ax.set_xlabel("banda (idade em trimestres)")
        ax.set_ylabel("contribuidores")
        ax.set_title(f"{LING.atual.nome}: backtest {ano_base} -> {alvo_real}")
        ax.legend()
        _salva_fig(fig, f"projecao_{LING.atual.slug}_backtest_{ano_base}.png")
    finally:
        shutil.rmtree(pl.scratch, ignore_errors=True)


def _rotulo(pl: SimpleNamespace) -> str:
    return pl.plots.labels().get(pl.sid, str(pl.sid))


def gera_magnetismo(pl: SimpleNamespace) -> None:
    """Sem cor (pedido explícito): magnetismo é sempre 1,0 aqui (1 linguagem
    só), então todo ponto cai na mesma coluna X. Os rótulos de ano vão numa
    coluna igualmente espaçada à direita, cada um com uma linha fina até o
    ponto real: zero sobreposição garantida, independente de quantos anos
    colidirem em Y."""
    pairs, coverage = pl.attractiveness.activity(scopes=[pl.sid])
    df = pl.attractiveness.annual(pairs, coverage_end=coverage)
    df = (
        df[df["scope_id"] == pl.sid]
        .dropna(subset=["magnetism", "stickiness"])
        .sort_values("stickiness")
        .reset_index(drop=True)
    )
    n = len(df)
    fig, ax = plt.subplots(figsize=(6.5, max(4.0, 0.3 * n)))
    ax.scatter(df["magnetism"], df["stickiness"], color="black", s=30, zorder=3)

    x_rotulo = df["magnetism"].max() + 0.03
    y_min, y_max = df["stickiness"].min(), df["stickiness"].max()
    ys_rotulo = [y_min] if n == 1 else list(pd.Series(range(n)) / (n - 1) * (y_max - y_min) + y_min)
    for y_lab, (_, row) in zip(ys_rotulo, df.iterrows(), strict=True):
        ax.plot(
            [row["magnetism"], x_rotulo],
            [row["stickiness"], y_lab],
            color="#aaaaaa",
            lw=0.5,
            zorder=1,
        )
        ax.annotate(str(int(row["year"])), (x_rotulo, y_lab), fontsize=8, va="center", ha="left")

    ax.set_xlim(df["magnetism"].min() - 0.02, x_rotulo + 0.06)
    ax.set_xlabel("magnetismo (degenerado em 1,0: unit=language com 1 linguagem só)")
    ax.set_ylabel("stickiness")
    ax.set_title(f"{_rotulo(pl)}: magnetismo x stickiness por ano")
    _salva_fig(fig, f"magnetismo_stickiness_{LING.atual.slug}_metodologia.png")


def gera_stickiness_ano(pl: SimpleNamespace) -> None:
    pairs, coverage = pl.attractiveness.activity(scopes=[pl.sid])
    df = pl.attractiveness.annual(pairs, coverage_end=coverage)
    df = df[df["scope_id"] == pl.sid].dropna(subset=["stickiness"]).sort_values("year")
    fig, ax = plt.subplots(figsize=(max(7.0, 0.45 * len(df)), 4))
    ax.bar(df["year"].astype(int).astype(str), df["stickiness"], color="black")
    ax.tick_params(axis="x", rotation=90)  # senão o rótulo de ano cola um no outro
    ax.set_ylabel("stickiness")
    ax.set_title(f"{_rotulo(pl)}: stickiness por ano (magnetismo omitido, degenerado em 1,0)")
    _salva_fig(fig, f"stickiness_por_ano_{LING.atual.slug}_metodologia.png")


def gera_ccr_ncr(pl: SimpleNamespace) -> None:
    todos = pl.metrics.load_all()
    df = todos[todos["scope_id"] == pl.sid].dropna(subset=["ccr", "ncr"]).sort_values("snapshot")
    fig, ax = plt.subplots(figsize=(7.5, 6.5))
    ax.axhline(0, color="#888888", lw=0.7)
    ax.axvline(0, color="#888888", lw=0.7)
    # Sem linha ligando os trimestres em ordem cronológica: o caminho não é
    # espacialmente monótono, e a linha virava um rabisco cruzando a figura
    # inteira sem comunicar nada. Só os pontos.
    ax.scatter(df["ccr"], df["ncr"], color="black", s=22, zorder=3)
    for _, row in df.iloc[::8].iterrows():  # 1 rótulo a cada 8 trimestres (2 em 2 anos)
        ax.annotate(
            str(pd.Timestamp(row["snapshot"]).year),
            (row["ccr"], row["ncr"]),
            fontsize=7,
            textcoords="offset points",
            xytext=(5, 5),
        )
    ax.set_xlabel("CCR")
    ax.set_ylabel("NCR")
    ax.set_title(f"{_rotulo(pl)}: CCR x NCR por trimestre")
    _salva_fig(fig, f"tipos_ccr_ncr_{LING.atual.slug}_metodologia.png")

    # CSV ao lado do PNG: sem isso, comparar CCR/NCR entre linguagens
    # (`gera_geral_ccr_ncr`) precisaria rodar o pipeline de novo pra cada
    # linguagem só pra reler o que essa figura já calculou.
    caminho_csv = CFG.saida / f"tipos_ccr_ncr_{LING.atual.slug}_metodologia.csv"
    df[["snapshot", "ccr", "ncr", "type"]].to_csv(caminho_csv, index=False)
    print(f"salvo: {caminho_csv}")


def gera_fantasmas(ev: pd.DataFrame) -> None:  # noqa: ARG001
    """Lê o CSV que `carrega_eventos` já gravou e desenha a barra. Não recalcula."""
    caminho_csv = CFG.saida / "fantasmas_por_ano.csv"
    if not caminho_csv.exists():
        print(
            "aviso: fantasmas_por_ano.csv não existe (rode com --figuras incluindo "
            "'piramide' ou qualquer outra, carrega_eventos sempre grava o CSV)",
            file=sys.stderr,
        )
        return
    df = pd.read_csv(caminho_csv)
    fig, ax = plt.subplots(figsize=(max(7.0, 0.45 * len(df)), 4))
    ax.bar(df["ano"].astype(str), df["eventos_de_conta_apagada"], color="black")
    ax.tick_params(axis="x", rotation=90)  # senão o rótulo de ano cola um no outro
    ax.set_ylabel("eventos de conta apagada ('ghost')")
    ax.set_title(f"{LING.atual.nome}: contas apagadas por ano (fora da pirâmide, só registro)")
    _salva_fig(fig, "fantasmas_por_ano.png")


def gera_abandono_por_ano(ev: pd.DataFrame) -> None:
    """Abandono: gente com conta de verdade (não fantasma, já filtrado em
    `carrega_eventos`), sem nenhuma contribuição na linguagem nos últimos 3 meses,
    olhando a partir de um ponto fixo (o evento mais recente da coleta, não um
    corte por ano corrido). Agrupado pelo ano da ÚLTIMA contribuição de cada um:
    "quando essa pessoa foi vista pela última vez, antes de abandonar até hoje".
    Não é "quem abandonou naquele ano" no sentido de span (ver
    `gera_voltas_por_ano` pra isso, que conta retorno depois de abandono
    temporário); é só a distância entre a última contribuição e hoje, sem volta
    até agora. Gera três figuras: eixo duplo, mesma escala, e só o acumulado."""
    ultimo_por_pessoa = ev.groupby("contributor_id")["timestamp"].max()
    agora = ev["timestamp"].max()
    limite = agora - pd.Timedelta(days=3 * DAYS_PER_MONTH)
    abandonou = ultimo_por_pessoa[ultimo_por_pessoa < limite]
    por_ano = abandonou.dt.year.value_counts().sort_index()

    CFG.saida.mkdir(parents=True, exist_ok=True)
    caminho_csv = CFG.saida / "abandono_por_ano.csv"
    por_ano.rename("pessoas_que_abandonaram").to_csv(
        caminho_csv, header=True, index_label="ano_da_ultima_contribuicao"
    )
    print(
        f"salvo: {caminho_csv} ({len(abandonou)} pessoas sem contribuição nos últimos 3 meses, "
        f"referência fixa: {agora.date()})",
        file=sys.stderr,
    )

    # Bolinha (stem+dot) em vez de barra sólida preta: menos tinta na página,
    # mais fácil de ler ano a ano.
    anos = por_ano.index.astype(str)
    acumulado = por_ano.cumsum()
    fig, ax = plt.subplots(figsize=(max(7.0, 0.45 * len(por_ano)), 4))
    ax.vlines(anos, 0, por_ano.to_numpy(), color="#cccccc", linewidth=1, zorder=1)
    ax.plot(anos, por_ano.to_numpy(), color="#555555", linewidth=1.3, zorder=2)
    ax.scatter(anos, por_ano.to_numpy(), color="black", s=45, zorder=3, label="por ano")
    ax.tick_params(axis="x", rotation=90)
    ax.set_xlabel("ano")
    ax.set_ylabel("pessoas naquele ano")
    ax.set_title(
        f"{LING.atual.nome}: quantas pessoas abandonaram, "
        "por ano em que contribuíram pela última vez"
    )

    # Acumulado em eixo secundário: escala bem maior que o valor por ano,
    # então divide o eixo Y em vez de esmagar as bolinhas lá embaixo.
    eixo2 = ax.twinx()
    eixo2.plot(
        anos,
        acumulado.to_numpy(),
        color="#a6431f",
        linewidth=1.6,
        linestyle="--",
        zorder=2,
        label="acumulado",
    )
    eixo2.set_ylabel("acumulado", color="#a6431f")
    eixo2.tick_params(axis="y", colors="#a6431f")

    linhas1, rotulos1 = ax.get_legend_handles_labels()
    linhas2, rotulos2 = eixo2.get_legend_handles_labels()
    ax.legend(linhas1 + linhas2, rotulos1 + rotulos2, loc="upper left")
    fig.tight_layout()
    _salva_fig(fig, "abandono_por_ano.png")

    # As duas linhas juntas, numa régua só (sem eixo duplo). O valor por ano
    # fica achatado perto do eixo porque a escala é a do acumulado; assim
    # mesmo, de propósito.
    fig3, ax4 = plt.subplots(figsize=(max(7.0, 0.45 * len(por_ano)), 4))
    ax4.plot(
        anos,
        por_ano.to_numpy(),
        color="black",
        linewidth=1.3,
        marker="o",
        markersize=5,
        label="por ano",
    )
    ax4.plot(
        anos,
        acumulado.to_numpy(),
        color="#a6431f",
        linewidth=1.6,
        marker="o",
        markersize=5,
        label="acumulado",
    )
    ax4.tick_params(axis="x", rotation=90)
    ax4.set_xlabel("ano")
    ax4.set_ylabel("pessoas")
    ax4.set_title(f"{LING.atual.nome}: abandono por ano e acumulado, mesma escala")
    ax4.legend(loc="upper left")
    _salva_fig(fig3, "abandono_por_ano_mesma_escala.png")

    # Figura separada só do acumulado, sem o eixo duplo: pra quem quer olhar
    # só a soma corrida, sem o valor por ano competindo por atenção.
    fig2, ax3 = plt.subplots(figsize=(max(7.0, 0.45 * len(por_ano)), 4))
    ax3.plot(
        anos,
        acumulado.to_numpy(),
        color="#a6431f",
        linewidth=1.6,
        marker="o",
        markersize=5,
        markerfacecolor="black",
        markeredgecolor="black",
    )
    ax3.tick_params(axis="x", rotation=90)
    ax3.set_xlabel("ano")
    ax3.set_ylabel("pessoas (acumulado)")
    ax3.set_title(
        f"{LING.atual.nome}: abandono acumulado por ano "
        f"(total até {anos[-1]}: {int(acumulado.iloc[-1])})"
    )
    _salva_fig(fig2, "abandono_acumulado_por_ano.png")


def gera_voltas_por_ano(ev: pd.DataFrame) -> None:
    """Quantas VOLTAS aconteceram em cada ano: pessoa que ficou mais de 3 meses
    sem contribuir e depois contribuiu de novo. Cada retorno é um evento próprio
    (uma pessoa pode voltar várias vezes ao longo da história), contado no ano em
    que o retorno aconteceu, não confundir com `gera_abandono_por_ano`, que é
    uma foto fixa de hoje. Usa `classify.profile`, o mesmo cálculo de span que o
    motor usa pra decidir quem está vivo."""
    from pyramid import classify

    coding = {"commits", "pull_requests"}
    gap_days = 3 * DAYS_PER_MONTH
    perfil = classify.profile(ev, coding, gap_days)
    voltas = perfil[perfil["span_idx"] > 0]  # span 0 é a primeira aparição, não é volta
    por_ano = pd.Series(voltas["span_start"]).dt.year.value_counts().sort_index()

    CFG.saida.mkdir(parents=True, exist_ok=True)
    caminho_csv = CFG.saida / "voltas_por_ano.csv"
    por_ano.rename("voltas").to_csv(caminho_csv, header=True, index_label="ano_da_volta")
    print(f"salvo: {caminho_csv} ({len(voltas)} voltas no total)", file=sys.stderr)

    anos = por_ano.index.astype(str)
    fig, ax = plt.subplots(figsize=(max(7.0, 0.45 * len(por_ano)), 4))
    ax.vlines(anos, 0, por_ano.to_numpy(), color="#cccccc", linewidth=1, zorder=1)
    ax.plot(anos, por_ano.to_numpy(), color="#555555", linewidth=1.3, zorder=2)
    ax.scatter(anos, por_ano.to_numpy(), color="black", s=45, zorder=3)
    ax.tick_params(axis="x", rotation=90)
    ax.set_xlabel("ano da volta")
    ax.set_ylabel("quantidade de voltas (pessoa que ficou 3+ meses sumida e contribuiu de novo)")
    ax.set_title(f"{LING.atual.nome}: voltas por ano")
    _salva_fig(fig, "voltas_por_ano.png")


def gera_contribuintes_por_ano(ev: pd.DataFrame) -> None:
    """Contribuinte distinto por ano: quem teve pelo menos 1 evento (código ou
    discussão) naquele ano, contando só uma vez mesmo com vários eventos. A
    mesma pessoa aparece em vários anos se contribuiu em vários anos; isso não
    é sobre banda de idade nem sobre abandono, é presença simples ano a ano."""
    anos_evento = ev["timestamp"].dt.year
    por_ano = ev.assign(ano=anos_evento).groupby("ano")["contributor_id"].nunique()
    total = ev["contributor_id"].nunique()

    CFG.saida.mkdir(parents=True, exist_ok=True)
    caminho_csv = CFG.saida / "contribuintes_por_ano.csv"
    por_ano.rename("contribuintes_distintos").to_csv(caminho_csv, header=True, index_label="ano")
    print(
        f"salvo: {caminho_csv} (total geral, todos os anos: {total} contribuintes distintos)",
        file=sys.stderr,
    )

    anos = por_ano.index.astype(str)
    fig, ax = plt.subplots(figsize=(max(7.0, 0.45 * len(por_ano)), 4))
    ax.vlines(anos, 0, por_ano.to_numpy(), color="#cccccc", linewidth=1, zorder=1)
    ax.plot(anos, por_ano.to_numpy(), color="#555555", linewidth=1.3, zorder=2)
    ax.scatter(anos, por_ano.to_numpy(), color="black", s=45, zorder=3)
    ax.tick_params(axis="x", rotation=90)
    ax.set_xlabel("ano")
    ax.set_ylabel("contribuintes distintos naquele ano")
    ax.set_title(f"{LING.atual.nome}: contribuintes por ano (total geral, todos os anos: {total})")
    _salva_fig(fig, "contribuintes_por_ano.png")

    _registra_total_geral(total)


REGISTRO_GERAL = TMP_BASE / "contribuintes_por_linguagem.json"


def _registra_total_geral(total: int) -> None:
    """Guarda o total de contribuintes desta linguagem num arquivo compartilhado,
    lido depois por `gera_geral_contribuintes`. Lê e regrava (não é concorrente:
    cada linguagem roda a própria vez), então uma linguagem não apaga o registro
    das outras."""
    registro = {}
    if REGISTRO_GERAL.exists():
        registro = json.loads(REGISTRO_GERAL.read_text(encoding="utf-8"))
    registro[LING.atual.slug] = total
    TMP_BASE.mkdir(parents=True, exist_ok=True)
    REGISTRO_GERAL.write_text(json.dumps(registro, indent=2, ensure_ascii=False), encoding="utf-8")


def gera_geral_contribuintes() -> None:
    """Plot que compara linguagem com linguagem: vai na raiz de `TMP_BASE`, não
    na subpasta de nenhuma linguagem específica. Lê `REGISTRO_GERAL`, que cada
    `--figuras contribuintes` (ou `all`) já vai deixando atualizado; não recarrega
    CSV nenhum."""
    if not REGISTRO_GERAL.exists():
        raise SystemExit(
            f"{REGISTRO_GERAL} não existe ainda. Rode `--figuras contribuintes` "
            "(ou `all`) em cada linguagem antes de `--geral`."
        )
    registro = json.loads(REGISTRO_GERAL.read_text(encoding="utf-8"))
    faltando = set(LINGUAGENS) - set(registro)
    if faltando:
        print(f"aviso: sem registro ainda para {', '.join(sorted(faltando))}", file=sys.stderr)

    itens = sorted(registro.items(), key=lambda kv: -kv[1])
    slugs = [k for k, _ in itens]
    valores = [v for _, v in itens]
    rotulos = [LINGUAGENS[s].nome if s in LINGUAGENS else s for s in slugs]

    fig, ax = plt.subplots(figsize=(max(6.0, 1.2 * len(itens)), 5))
    ax.bar(rotulos, valores, color="black")
    for i, v in enumerate(valores):
        ax.annotate(
            str(v),
            (i, v),
            ha="center",
            va="bottom",
            fontsize=9,
            xytext=(0, 3),
            textcoords="offset points",
        )
    ax.set_ylabel("contribuintes distintos (todos os anos)")
    ax.set_title("Contribuintes distintos por linguagem")
    TMP_BASE.mkdir(parents=True, exist_ok=True)
    caminho = TMP_BASE / "geral_contribuintes_por_linguagem.png"
    fig.savefig(caminho, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"salvo: {caminho}")


CORES_LINGUAGEM = {
    "clojure": "#5881d8",
    "elixir": "#8250df",
    "zig": "#f7a41d",
    "python": "#2f9e44",
}

# CCR e NCR vivem em [-1, 1] por construção (razão com o maior dos dois lados
# no denominador, ver `metrics.py`). Magnetismo e stickiness vivem em [0, 1]
# (fração de um subconjunto sobre o todo, nunca negativa). Pedido explícito do
# usuário: as 4 métricas nos MESMOS eixos, mesmo magnetismo/stickiness nunca
# ocupando a metade negativa, pra comparar os 3 plots (CCR-NCR isolado, CCR-NCR
# geral, magnetismo-stickiness) de relance, sem reler o número em cada eixo.
ESCALA_METRICA = (-1.05, 1.05)


def gera_geral_ccr_ncr() -> None:
    """CCR x NCR das 4 linguagens no mesmo plano, uma cor por linguagem. Lê o
    CSV que `--figuras ccr-ncr` (ou `all`) já deixou em cada subpasta; não
    recalcula nada."""
    partes = []
    faltando = []
    for slug, linguagem in LINGUAGENS.items():
        caminho_csv = TMP_BASE / slug / f"tipos_ccr_ncr_{slug}_metodologia.csv"
        if not caminho_csv.exists():
            faltando.append(slug)
            continue
        df = pd.read_csv(caminho_csv)
        df["linguagem"] = linguagem.nome
        partes.append(df)
    if faltando:
        print(
            f"aviso: sem CSV de CCR/NCR ainda para {', '.join(sorted(faltando))}", file=sys.stderr
        )
    if not partes:
        raise SystemExit(
            "nenhum tipos_ccr_ncr_*_metodologia.csv encontrado. Rode `--figuras "
            "ccr-ncr` (ou `all`) em cada linguagem antes."
        )
    todos = pd.concat(partes, ignore_index=True)

    fig, ax = plt.subplots(figsize=(8.0, 7.0))
    ax.axhline(0, color="#888888", lw=0.7)
    ax.axvline(0, color="#888888", lw=0.7)
    for slug, grupo in todos.groupby("linguagem"):
        ax.scatter(
            grupo["ccr"],
            grupo["ncr"],
            color=CORES_LINGUAGEM.get(next(k for k, v in LINGUAGENS.items() if v.nome == slug)),
            s=18,
            alpha=0.65,
            label=slug,
        )
    ax.set_xlim(*ESCALA_METRICA)
    ax.set_ylim(*ESCALA_METRICA)
    ax.set_xlabel("CCR")
    ax.set_ylabel("NCR")
    ax.set_title("CCR x NCR por trimestre, 4 linguagens")
    ax.legend(loc="best", fontsize=9)
    TMP_BASE.mkdir(parents=True, exist_ok=True)
    caminho = TMP_BASE / "geral_ccr_ncr_por_linguagem.png"
    fig.savefig(caminho, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"salvo: {caminho}")


def gera_geral_contribuintes_evolucao() -> None:
    """Contribuintes distintos por ano, as 4 linguagens no mesmo plano, uma
    linha por linguagem. Lê `contribuintes_por_ano.csv`, que `--figuras
    contribuintes` (ou `all`) já deixa em cada subpasta; não recalcula nada."""
    fig, ax = plt.subplots(figsize=(10, 6))
    faltando = []
    for slug, linguagem in LINGUAGENS.items():
        caminho_csv = TMP_BASE / slug / "contribuintes_por_ano.csv"
        if not caminho_csv.exists():
            faltando.append(slug)
            continue
        df = pd.read_csv(caminho_csv)
        ax.plot(
            df["ano"],
            df["contribuintes_distintos"],
            marker="o",
            markersize=4,
            color=CORES_LINGUAGEM[slug],
            label=linguagem.nome,
        )
    if faltando:
        print(
            f"aviso: sem contribuintes_por_ano.csv ainda para {', '.join(sorted(faltando))}",
            file=sys.stderr,
        )
    ax.set_xlabel("ano")
    ax.set_ylabel("contribuintes distintos naquele ano")
    ax.set_title("Contribuintes distintos por ano, 4 linguagens")
    ax.legend(loc="best")
    TMP_BASE.mkdir(parents=True, exist_ok=True)
    caminho = TMP_BASE / "geral_contribuintes_evolucao_por_ano.png"
    fig.savefig(caminho, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"salvo: {caminho}")


def _carrega_todas_linguagens(rodada: int = 2) -> dict[str, pd.DataFrame]:
    """As 4 coletas carregadas e filtradas (`carrega_eventos`), cada uma com a
    própria coluna `idioma` (ver `monta_fonte`). Ponto único de carga pras
    figuras que comparam linguagem com linguagem (`--comparativa` e
    `--comparativa-metricas`): reaproveita o mesmo dict em vez de recarregar
    os CSVs brutos de novo pra cada figura."""
    eventos_por_lingua: dict[str, pd.DataFrame] = {}
    for slug, linguagem in LINGUAGENS.items():
        LING.aplica(slug)
        CFG.aplica(rodada)
        ev = carrega_eventos(rodada).copy()
        ev["idioma"] = linguagem.nome
        eventos_por_lingua[slug] = ev
    return eventos_por_lingua


def gera_piramide_comparativa() -> None:
    """As 4 pirâmides lado a lado, todas cortadas no mesmo trimestre: o último
    trimestre completo da linguagem mais atrasada (senão a comparação mistura
    uma pirâmide "hoje" com outra de meses atrás, e a diferença de forma pode
    ser só isso). Mesma metodologia da pirâmide avulsa; o corte final é comum
    às 4, e roda uma vez por valor de `BANDAS_MESES_PIRAMIDE` (default: 3 meses
    "com quarter" e 12 meses "sem quarter", mesma convenção de
    `gera_piramide_multi`). Vai na raiz de `TMP_BASE`, como qualquer geral."""
    eventos_por_lingua = _carrega_todas_linguagens()
    fim_natural = {slug: _serie_trimestral(ev)[-1] for slug, ev in eventos_por_lingua.items()}

    fim_comum = min(fim_natural.values())
    atrasada = min(fim_natural, key=fim_natural.get)
    print(
        f"corte comum: {fim_comum.date()} (definido por {LINGUAGENS[atrasada].nome}, "
        "a linguagem com o trimestre mais atrasado)",
        file=sys.stderr,
    )

    for banda_meses in BANDAS_MESES_PIRAMIDE:
        fig, eixos = plt.subplots(2, 2, figsize=(14, 14))
        for eixo, slug in zip(eixos.flat, LINGUAGENS, strict=True):
            LING.aplica(slug)
            CFG.aplica(2)
            pl = roda_pipeline(
                eventos_por_lingua[slug], band_months=banda_meses, fim_forcado=fim_comum
            )
            try:
                caminho = pl.plots.figure_pyramid(pl.sid)
                eixo.imshow(plt.imread(caminho))
                eixo.axis("off")
                eixo.set_title(LING.atual.nome)
            finally:
                shutil.rmtree(pl.scratch, ignore_errors=True)

        rotulo = "comquarter" if banda_meses == 3 else "semquarter"
        fig.suptitle(
            f"Pirâmide por linguagem, mesmo corte de data ({fim_comum.date()}), "
            f"banda {banda_meses}m",
            fontsize=14,
        )
        fig.tight_layout()
        TMP_BASE.mkdir(parents=True, exist_ok=True)
        caminho = TMP_BASE / f"piramides_por_linguagem_mesmo_corte_{rotulo}_banda{banda_meses}m.png"
        fig.savefig(caminho, dpi=200, bbox_inches="tight")
        plt.close(fig)
        print(f"salvo: {caminho}")

    gera_comparacao_metricas_linguagens(eventos_por_lingua)
    gera_comparacao_metricas_linguagens(eventos_por_lingua, janela_anos=5)


def _desenha_pontos_por_linguagem(
    ax: plt.Axes,
    ids_por_nome: dict[str, int],
    cores: dict[str, str],
    x_por_sid: pd.Series,
    y_por_sid: pd.Series,
    rotulo_x: str,
    rotulo_y: str,
    titulo: str,
    *,
    linhas_zero: bool = False,
) -> None:
    """Um ponto rotulado por linguagem, eixos na `ESCALA_METRICA` comum.
    Compartilhado pelos dois painéis de `gera_comparacao_metricas_linguagens`."""
    if linhas_zero:
        ax.axhline(0, color="#888888", lw=0.7)
        ax.axvline(0, color="#888888", lw=0.7)
    for nome, sid in ids_por_nome.items():
        if sid not in x_por_sid.index:
            continue
        x, y = x_por_sid[sid], y_por_sid[sid]
        ax.scatter(x, y, color=cores[nome], s=70, zorder=3)
        ax.annotate(nome, (x, y), fontsize=9, xytext=(6, 6), textcoords="offset points")
    ax.set_xlim(*ESCALA_METRICA)
    ax.set_ylim(*ESCALA_METRICA)
    ax.set_xlabel(rotulo_x)
    ax.set_ylabel(rotulo_y)
    ax.set_title(titulo)


def gera_comparacao_metricas_linguagens(
    eventos_por_lingua: dict[str, pd.DataFrame], janela_anos: int | None = None
) -> None:
    """CCR/NCR e magnetismo/stickiness com a LINGUAGEM como unidade, um ponto
    por linguagem, dentro do MESMO pipeline (as 4 juntas numa fonte só, com
    `eventos["idioma"]` dizendo a linguagem de origem por linha; ver
    `monta_fonte`). Rodar cada linguagem sozinha (como `gera_magnetismo` faz)
    deixa magnetismo travado em 1,0: `unit: language` com 1 linguagem só não
    tem contra quem competir por atenção. Junto, magnetismo compara as 4 de
    verdade.

    `janela_anos=None` (default): NCR x CCR no último trimestre, stickiness x
    magnetismo no último ano completo, um ponto por linguagem (o valor mais
    recente). `janela_anos=N`: mediana dos últimos N anos em cada painel
    (últimos 4*N trimestres pro CCR/NCR), pra suavizar oscilação de curto
    prazo e mostrar a posição típica da linguagem, não só o instante atual."""
    from pyramid import units

    eventos = pd.concat(eventos_por_lingua.values(), ignore_index=True)
    pl = roda_pipeline(eventos, band_months=3)
    try:
        ids_por_nome = {v.nome: units.id_da_linguagem(v.nome) for v in LINGUAGENS.values()}
        cores = {v.nome: CORES_LINGUAGEM[k] for k, v in LINGUAGENS.items()}

        ccr_ncr = pl.metrics.load_all()
        ccr_ncr = ccr_ncr[ccr_ncr["scope_id"].isin(ids_por_nome.values())].dropna(
            subset=["ccr", "ncr"]
        )
        pares, cobertura = pl.attractiveness.activity(scopes=list(ids_por_nome.values()))
        anual = pl.attractiveness.annual(pares, coverage_end=cobertura).dropna(
            subset=["magnetism", "stickiness"]
        )

        if janela_anos is None:
            # Último trimestre/ano só depois do dropna: o período corrente vem
            # incompleto (mesmo aviso de `attractiveness` sobre a stickiness de
            # dezembro) e as métricas saem NaN nele pras 4 linguagens.
            snap_rotulo = str(pd.Timestamp(ccr_ncr["snapshot"].max()).date())
            ccr_ncr = ccr_ncr[ccr_ncr["snapshot"] == ccr_ncr["snapshot"].max()]
            ano_rotulo = str(int(anual["year"].max()))
            anual = anual[anual["year"] == anual["year"].max()]
            agrega = lambda df, col: df.set_index("scope_id")[col]  # noqa: E731
            sufixo, titulo_extra = "", f"({snap_rotulo} / {ano_rotulo})"
        else:
            corte_trimestre = ccr_ncr["snapshot"].max() - pd.DateOffset(years=janela_anos)
            ccr_ncr = ccr_ncr[ccr_ncr["snapshot"] > corte_trimestre]
            corte_ano = anual["year"].max() - janela_anos
            anual = anual[anual["year"] > corte_ano]
            agrega = lambda df, col: df.groupby("scope_id")[col].median()  # noqa: E731
            sufixo, titulo_extra = f"_{janela_anos}anos", f"(mediana, últimos {janela_anos} anos)"

        ncr_por_sid = agrega(ccr_ncr, "ncr")
        ccr_por_sid = agrega(ccr_ncr, "ccr")
        sticky_por_sid = agrega(anual, "stickiness")
        magnet_por_sid = agrega(anual, "magnetism")

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 6))
        _desenha_pontos_por_linguagem(
            ax1,
            ids_por_nome,
            cores,
            ncr_por_sid,
            ccr_por_sid,
            "NCR",
            "CCR",
            f"CCR x NCR por linguagem {titulo_extra}",
            linhas_zero=True,
        )
        _desenha_pontos_por_linguagem(
            ax2,
            ids_por_nome,
            cores,
            sticky_por_sid,
            magnet_por_sid,
            "stickiness",
            "magnetismo",
            f"magnetismo x stickiness por linguagem {titulo_extra}",
        )
        fig.suptitle("As 4 linguagens como unidade de análise, competindo entre si", fontsize=13)
        TMP_BASE.mkdir(parents=True, exist_ok=True)
        caminho = TMP_BASE / f"geral_ccr_ncr_magnetismo_stickiness_por_linguagem{sufixo}.png"
        fig.savefig(caminho, dpi=200, bbox_inches="tight")
        plt.close(fig)
        print(f"salvo: {caminho}")
    finally:
        shutil.rmtree(pl.scratch, ignore_errors=True)


GERADORES = {
    "piramide": lambda _pl, ev: gera_piramide_multi(ev),
    "linha-tempo": lambda pl, _ev: gera_linha_tempo(pl),
    "linha-tempo-4": lambda _pl, ev: gera_linha_tempo_4(ev),
    "projecao": lambda pl, _ev: gera_projecao(pl),
    "magnetismo": lambda pl, _ev: gera_magnetismo(pl),
    "stickiness-ano": lambda pl, _ev: gera_stickiness_ano(pl),
    "ccr-ncr": lambda pl, _ev: gera_ccr_ncr(pl),
    "fantasmas": lambda _pl, ev: gera_fantasmas(ev),
    "abandono": lambda _pl, ev: gera_abandono_por_ano(ev),
    "voltas": lambda _pl, ev: gera_voltas_por_ano(ev),
    "contribuintes": lambda _pl, ev: gera_contribuintes_por_ano(ev),
}

# Não usam o pipeline padrão do loop principal: `fantasmas`/`abandono`/`voltas`/
# `contribuintes` não precisam de pipeline nenhum (leem só o CSV bruto);
# `linha-tempo-4` e `piramide` rodam o próprio `roda_pipeline` internamente,
# mais de uma vez, com banda diferente a cada vez.
SEM_PIPELINE_PADRAO = {
    "linha-tempo-4",
    "fantasmas",
    "abandono",
    "voltas",
    "contribuintes",
    "piramide",
}


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--linguagem",
        choices=tuple(LINGUAGENS),
        default=LING.atual.slug,
        help="qual linguagem gerar (default: clojure)",
    )
    ap.add_argument(
        "--rodada",
        type=int,
        choices=(1, 2),
        default=RODADA,
        help="qual coleta usar: 1 (eventos_repositorios.csv, coleta antiga, só existe "
        "para Clojure) ou 2 (eventos_api.csv + eventos_git.csv, coleta corrente, default)",
    )
    ap.add_argument(
        "--figuras",
        default=FIGURAS,
        help="quais figuras gerar, separadas por vírgula (default: all). "
        f"Disponíveis: {', '.join(GERADORES)}",
    )
    ap.add_argument(
        "--geral",
        action="store_true",
        help="em vez de gerar figura de uma linguagem, desenha as comparações "
        "entre linguagens: contribuintes distintos (lê o registro que --figuras "
        "contribuintes já deixou atualizado) e CCR x NCR (lê o CSV que --figuras "
        "ccr-ncr já deixou atualizado). Sai depois. Ignora --linguagem/--rodada/--figuras.",
    )
    ap.add_argument(
        "--comparativa",
        action="store_true",
        help="desenha as 4 pirâmides lado a lado (todas cortadas no mesmo "
        "trimestre, o mais atrasado das 4) e a comparação de CCR/NCR/"
        "magnetismo/stickiness com a linguagem como unidade, e sai. Carrega "
        "as 4 coletas inteiras; ignora --linguagem/--rodada/--figuras.",
    )
    ap.add_argument(
        "--comparativa-metricas",
        action="store_true",
        help="só a comparação de CCR/NCR/magnetismo/stickiness com a "
        "linguagem como unidade (sem redesenhar as pirâmides de "
        "--comparativa), e sai. Carrega as 4 coletas inteiras; ignora "
        "--linguagem/--rodada/--figuras.",
    )
    ap.add_argument(
        "--backtest-anos",
        default="",
        help="ancora a projeção coorte-componente em Q4 de cada ano da lista "
        "(separados por vírgula, ex.: 2016,2019,2024) em vez do último "
        "trimestre da coleta, e compara com o real. Roda pra --linguagem "
        "escolhida, além do --figuras pedido (não substitui).",
    )
    args = ap.parse_args()
    if args.geral:
        gera_geral_contribuintes()
        gera_geral_contribuintes_evolucao()
        gera_geral_ccr_ncr()
        return
    if args.comparativa:
        gera_piramide_comparativa()
        return
    if args.comparativa_metricas:
        eventos_por_lingua = _carrega_todas_linguagens()
        gera_comparacao_metricas_linguagens(eventos_por_lingua)
        gera_comparacao_metricas_linguagens(eventos_por_lingua, janela_anos=5)
        return
    LING.aplica(args.linguagem)

    rodada = args.rodada
    if not LING.atual.tem_rodada_1:
        if rodada == 1:
            raise SystemExit(f"--rodada 1 não existe para {LING.atual.nome}; use --rodada 2.")
        rodada = 2
    CFG.aplica(rodada)  # reaplica com a linguagem/rodada escolhidas; env var ainda vence dentro

    pedidas = (
        list(GERADORES)
        if args.figuras == "all"
        else [f.strip() for f in args.figuras.split(",") if f.strip()]
    )
    desconhecidas = set(pedidas) - set(GERADORES)
    if desconhecidas:
        raise SystemExit(f"--figuras desconhecida: {desconhecidas}. Use: {', '.join(GERADORES)}")

    eventos = carrega_eventos(rodada)
    print(f"{len(eventos)} eventos, {eventos['scope_id'].nunique()} repositórios", file=sys.stderr)

    # Um pipeline por figura, não um só compartilhado: `roda_pipeline` mexe em
    # `config.OUTPUT_DIR` (estado global do módulo `config`), e `linha-tempo-4`
    # roda com banda diferente (24 meses) e apaga o próprio scratch no fim.
    # Compartilhar um `pl` entre chamadas deixava o `OUTPUT_DIR` global
    # apontando pro scratch já apagado da figura anterior. Reextrair de novo
    # por figura custa segundos e evita essa pegadinha de vez.
    for nome in pedidas:
        print(f"--- {nome} ---")
        if nome in SEM_PIPELINE_PADRAO:
            GERADORES[nome](None, eventos)
            continue
        pl = roda_pipeline(eventos, band_months=3)
        try:
            GERADORES[nome](pl, eventos)
        finally:
            shutil.rmtree(pl.scratch, ignore_errors=True)

    for ano_texto in (a.strip() for a in args.backtest_anos.split(",")):
        if not ano_texto:
            continue
        gera_projecao_backtest(eventos, int(ano_texto))


if __name__ == "__main__":
    main()
