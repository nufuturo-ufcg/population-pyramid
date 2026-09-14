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
  piramide-veteranos  a mesma pirâmide, mas tirando ANTES de rodar o pipeline
                 quem tem menos de MESES_MIN_VETERANO meses de idade (default:
                 3 e 12). A pirâmide normal só mostra quem está ativo, e quem
                 chegou há pouco passa nesse filtro quase de graça; esta
                 versão mostra a população sem quem chegou ontem.
  linha-tempo    linha do tempo automática (ULTIMOS_ANOS, PASSO_ANOS, banda 3 meses)
  linha-tempo-4  linha do tempo com ANOS_ESCOLHIDOS e banda de BANDA_ANOS anos,
                 gerada duas vezes: janela de população de 3 meses e de 12 meses
  projecao       projeção coorte-componente (tabela impressa + figura)
  stickiness-ano stickiness por ano (barra). Magnetismo NÃO entra aqui:
                 com 1 linguagem só, `unit: language` não tem contra quem
                 competir por atenção e o valor trava em 1,0 (sem análise
                 nenhuma pra tirar disso). Comparação de verdade fica em
                 `--comparativa`/`--comparativa-metricas`, que rodam as 4
                 linguagens juntas no mesmo pipeline.
  ccr-ncr        CCR x NCR por trimestre (scatter), linguagem inteira como
                 unidade (unit=language)
  ccr-ncr-projeto  CCR x NCR por repositório de verdade (unit=project), um
                 ponto por repositório elegível. Fora de `--figuras all`:
                 reclassifica cada repositório do zero, minutos por
                 linguagem em vez de segundos
  fantasmas      contas apagadas ('ghost') por ano: não entram na pirâmide,
                 só o registro de quantas existiram ao longo do tempo
  abandono       pessoas com conta de verdade sem contribuição nos últimos 3
                 meses (referência fixa: o evento mais recente da coleta),
                 por ano da última contribuição, mais as versões acumuladas
  voltas         quantas voltas (retorno após 3+ meses sumido) por ano
  contribuintes  contribuinte distinto por ano
  idade-morte    pirâmide de quem já abandonou (sem contribuição nos últimos
                 3 meses, mesmo corte de `abandono`): não conta ano-calendário,
                 conta a IDADE que a pessoa tinha na última contribuição.
                 Cumulativa desde sempre (todo mundo que já abandonou, em
                 qualquer ano)
  idade-morte-recente  a mesma pirâmide, só com quem abandonou nos últimos
                 IDADE_MORTE_RECENTE_MESES meses (default: 12): a versão
                 cumulativa é dominada por quem saiu há mais tempo, esta
                 mostra quem está saindo agora
  idade-morte-tempo  a mesma pirâmide de idade-morte, um painel por
                 ano-snapshot (`ANOS_GRADE_ANOS_DISTINTOS`), só com quem já
                 tinha abandonado até aquele ano

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
from contextlib import contextmanager
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

# Mesma divisão que `classify.py` usa internamente (coding/moved/non_coding):
# código de verdade é commit ou pull request; o resto (issue, comentário,
# evento de issue) é discussão.
TIPOS_CODING = {"commits", "pull_requests"}

# Rótulo de legenda das pirâmides deste script (não é metodologia auditada,
# esse texto não tem compromisso com o artigo). Não mexe em `plots.PT_LABEL`:
# aquele é usado pelas figuras oficiais da replicação (`pyramid plot` sobre
# dado real do ghapi), e "non-coding" ali é o termo exato do artigo
# (IEICE16/ESEM14). Pedido do usuário: "non-coding" confunde nesse contexto,
# vira "discussion" em toda pirâmide que este script desenha.
ROTULO_LEGENDA = {
    "non_coding": "discussion",
    "moved": "moved to coding",
    "coding": "coding",
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


class _EstadoLinhaTempo4:
    """`--teto-proprio-timeline`, mutável (atributo, não `global`: mesmo
    padrão de `_EstadoLinguagem`/`_Config`). Default é o motor auditado
    (teto comum, igual ESEM14 Fig.3); só muda quando o usuário pede."""

    teto_proprio: bool = False


class _EstadoMetricas5Anos:
    """`--metricas-5anos`, mutável (mesmo padrão de `_EstadoLinhaTempo4`).
    Default não desenha a versão de 5 anos (mediana, suaviza oscilação de
    curto prazo): pedido explícito do usuário, "não quero isso por agora",
    depois de perguntar pra que serve. Só desenha quando pedida."""

    ativo: bool = False


class _EstadoParalelo:
    """`--processos N`, mutável (mesmo padrão das outras `_Estado*`).
    `None` (default) deixa `roda_pipeline_paralelo` decidir sozinho
    (`os.cpu_count()`); só existe pra quem quer segurar a máquina pra
    outra coisa ao mesmo tempo, ou testar com menos processos."""

    n_workers: int | None = None


LING = _EstadoLinguagem()
ESTADO_LINHA_TEMPO_4 = _EstadoLinhaTempo4()
ESTADO_METRICAS_5ANOS = _EstadoMetricas5Anos()
ESTADO_PARALELO = _EstadoParalelo()
LING.aplica(os.environ.get("LINGUAGEM", "clojure"))

# Pasta temporária única do projeto, não do dataset: cada linguagem tem a
# própria subpasta (`clojure/`, `elixir/`, `zig/`, ...), pra achar a figura sem
# lembrar de qual rodada ela veio. Um plot que compare linguagens entre si
# vai em `PASTA_GERAL` (`TMP_BASE/geral/`), fora da subpasta de qualquer
# linguagem específica.
TMP_BASE = Path.home() / "Documents" / "pyramid-tmp"
PASTA_GERAL = TMP_BASE / "geral"


class _EstadoPastaGeral:
    """Pra onde `_caminho_geral` escreve agora. Default é `PASTA_GERAL`; só
    muda dentro de `_rodada_sem_linguagem` (ver mais abaixo), pra uma rodada
    tipo `--geral-exclude-python` não misturar arquivo com o `geral/` de
    sempre."""

    pasta: Path = PASTA_GERAL


ESTADO_PASTA_GERAL = _EstadoPastaGeral()


def _caminho_geral(nome: str) -> Path:
    ESTADO_PASTA_GERAL.pasta.mkdir(parents=True, exist_ok=True)
    return ESTADO_PASTA_GERAL.pasta / nome


@contextmanager
def _rodada_sem_linguagem(slug: str):
    """Roda um bloco inteiro de geração "geral" sem `slug`. A maioria das
    `gera_geral_*`/`gera_piramide_comparativa` não precisa mudar nenhuma
    linha: todas leem `LINGUAGENS.items()` por referência, então tirar
    `slug` dele antes de chamá-las (e repor depois, mesmo com exceção) já
    as faz ignorar essa linguagem sozinhas. Exceção: quem monta a grade de
    painéis com `plt.subplots(2, 2, ...)` fixo (ver `_grade_para_linguagens`)
    quebrava com 3 linguagens em vez de 4; corrigido pra dimensionar pelo
    `len(LINGUAGENS)` do momento. `_caminho_geral` desvia pra
    `geral-exclude-<slug>/` no mesmo intervalo, pra não sobrescrever o
    `geral/` de sempre."""
    linguagem = LINGUAGENS.pop(slug, None)
    pasta_anterior = ESTADO_PASTA_GERAL.pasta
    ESTADO_PASTA_GERAL.pasta = TMP_BASE / f"geral-exclude-{slug}"
    try:
        yield
    finally:
        if linguagem is not None:
            LINGUAGENS[slug] = linguagem
        ESTADO_PASTA_GERAL.pasta = pasta_anterior


def _grade_para_linguagens() -> tuple[plt.Figure, list]:
    """`(fig, eixos)` com 2 colunas e linhas o bastante pro `len(LINGUAGENS)`
    do momento (4 de costume, 3 num `--geral-exclude-<slug>`). Sem isso, todo
    `plt.subplots(2, 2, ...)` fixo quebrava (`zip(..., strict=True)` contra
    um número de linguagens menor que 4) assim que uma rodada excluía
    alguma. Painel sobrando (grade ímpar) sai desligado, não em branco cru."""
    n = len(LINGUAGENS)
    colunas = min(2, n) or 1
    linhas = -(-n // colunas)
    fig, matriz = plt.subplots(linhas, colunas, figsize=(7 * colunas, 7 * linhas), squeeze=False)
    eixos = list(matriz.flat)
    for sobra in eixos[n:]:
        sobra.axis("off")
    return fig, eixos[:n]


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
    caminho = _caminho_csv("fantasmas/fantasmas_por_ano.csv")
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

# Caracterização dos dados: quanto sobra em cada etapa do filtro de
# `carrega_eventos`, por linguagem. Populado como efeito colateral da carga
# normal (cada função de filtro grava o próprio número); `gera_
# caracterizacao_dados` só lê no final. Pedido do usuário: quantidade de
# dado antes e depois de cada filtro, não só o resultado final.
ESTATISTICAS_CARGA: dict[str, dict[str, int]] = {}


def _stats() -> dict[str, int]:
    return ESTATISTICAS_CARGA.setdefault(LING.atual.slug, {})


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
    _stats()["repos_total"] = len(alvo)
    _stats()["repos_excluidos_share"] = excluidos
    _stats()["repos_elegiveis"] = len(alvo) - excluidos
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
    _stats()["eventos_api_bruto"] = len(df)
    df = df[df["author_login"].notna()].copy()
    df["language"] = df["language"].fillna(df["repo_id"].map(main_lang))
    df = df[df["language"] == LING.atual.nome]
    _stats()["eventos_api_desta_linguagem"] = len(df)
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
    _stats()["eventos_git_bruto"] = len(df)
    df = df[df["author"].notna()].copy()
    df = df[df["files"].map(_e_arquivo_da_linguagem)]
    _stats()["eventos_git_desta_linguagem"] = len(df)

    df["_criado"] = df["repo_id"].map(_repo_created_at())
    chave = ["author", "created_at", "files"]
    mais_antigo = df.groupby(chave)["_criado"].transform("min")
    duplicado = df["_criado"] > mais_antigo
    _stats()["commits_duplicados_descartados"] = int(duplicado.sum())
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
    _stats()["eventos_antes_do_piso_descartados"] = int(antes_do_piso.sum())
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

    _stats()["eventos_fantasma_descartados"] = int(fantasma.sum())
    _stats()["eventos_bot_descartados"] = int(bot.sum())
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
    _stats()["eventos_data_ilegivel_descartados"] = int(descartados)
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
    _stats()["eventos_futuro_descartados"] = futuros
    if futuros:
        print(f"aviso: {futuros} eventos com data no futuro descartados", file=sys.stderr)
    antes_2008 = int((df["timestamp"] < pd.Timestamp("2008-01-01")).sum())
    _stats()["eventos_antes_2008_descartados"] = antes_2008
    df = df[(df["timestamp"] >= "2008-01-01") & (df["timestamp"] <= agora)]
    df["contributor_id"] = df["identidade"].map(_id_estavel)
    df["scope_id"] = df["repo_id"].map(_id_estavel)
    return df[["scope_id", "contributor_id", "event_type", "timestamp", "repo_id"]].reset_index(
        drop=True
    )


def _stats_erros_coleta() -> None:
    """Quantos repositórios ficaram com status "error" durante a coleta, por
    etapa. Quem escreve `reports/etapa_2A_progresso.json` e
    `etapa_2B_progresso.json` é o coletor, fora deste script e fora do
    motor auditado; aqui só lê o que já está gravado em `CFG.dados`, não
    refaz a coleta nem reinterpreta o status. "error" marca uma chamada de
    rede ou de git que falhou (timeout, GitHub devolvendo 422, encoding
    quebrado, disco cheio no clone); o repositório costuma continuar no
    `repositorios_*_alvo.csv` final mesmo assim, só que com o pedaço que
    falhou faltando (achado em Clojure: os 4 erros da etapa 2A estão todos
    no alvo.csv final). `repos_erro_uniao` é a união dos `repo_id` com erro
    nas duas etapas, não a soma: um repositório pode errar nas duas ao
    mesmo tempo (achado em Zig), e somar contaria ele 2 vezes."""
    ids_com_erro: set[str] = set()
    for etapa in ("etapa_2A", "etapa_2B"):
        caminho = CFG.dados / "reports" / f"{etapa}_progresso.json"
        if not caminho.exists():
            continue
        repos = json.loads(caminho.read_text()).get("repositories", {})
        erros = {rid for rid, r in repos.items() if r.get("status") == "error"}
        _stats()[f"{etapa}_total"] = len(repos)
        _stats()[f"{etapa}_erros"] = len(erros)
        ids_com_erro |= erros
    _stats()["repos_erro_uniao"] = len(ids_com_erro)


def carrega_eventos(rodada: int = RODADA) -> pd.DataFrame:
    ESTATISTICAS_CARGA.pop(LING.atual.slug, None)
    _stats_erros_coleta()
    elegiveis = _repos_elegiveis(rodada)
    if rodada == 1:
        bruto, mapa_tipo = _carrega_r1(), MAPA_TIPO_R1
    else:
        bruto, mapa_tipo = _carrega_r2(), MAPA_TIPO_R2
    bruto = bruto[bruto["repo_id"].isin(elegiveis)]
    _stats()["eventos_apos_elegibilidade"] = len(bruto)
    resultado = _finaliza_eventos(bruto, mapa_tipo)
    _stats()["eventos_finais"] = len(resultado)
    _stats()["repos_finais"] = int(resultado["repo_id"].nunique())
    _stats()["contribuidores_finais"] = int(resultado["contributor_id"].nunique())
    return resultado


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
    unit: str = "language",
) -> None:
    alvo = scratch / "config" / "settings.yaml"
    cfg = yaml.safe_load(alvo.read_text(encoding="utf-8"))
    cfg["analysis"]["unit"] = unit
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
    eventos: pd.DataFrame,
    band_months: int,
    fim_forcado: pd.Timestamp | None = None,
    unit: str = "language",
) -> SimpleNamespace:
    """Extract/classify/snapshots/metrics numa config de rascunho.

    `fim_forcado` sobrepõe o último trimestre da série (ver `gera_piramide_comparativa`,
    que precisa das 4 linguagens no mesmo corte em vez do próprio máximo de cada uma).
    `unit="project"` (default "language"): cada repositório elegível vira o
    próprio escopo (`units.scopes_of_unit`), em vez de somar todos os
    repositórios da linguagem num escopo só. Só assim CCR/NCR sai por
    projeto de verdade; com `unit="language"`, `extract` já soma tudo antes
    de classificar, e não sobra escopo de repositório nenhum pra ler depois.
    `pl.sid` não existe nesse modo (não há "o" projeto); quem chama lê
    `pl.metrics.load_all()` direto, todos os `scope_id` de uma vez.
    Devolve os módulos e o scope id.
    """
    scratch = Path(tempfile.mkdtemp(prefix="pyr_lang_fig_"))
    shutil.copytree(ROOT / "config", scratch / "config")
    escreve_config(scratch, eventos, band_months, fim_forcado, unit=unit)

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

    sid = units.id_da_linguagem(LING.atual.nome) if unit == "language" else None
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


# --- unit=project em paralelo -------------------------------------------------
#
# extract/classify/snapshots/metrics.run() já aceitam `scopes=<lista de ids>`
# (ver src/pyramid/*.py): cada escopo lê e escreve só o próprio parquet, sem
# tocar no arquivo de nenhum outro. Com unit="project" (cada repositório
# elegível é o próprio escopo, `roda_pipeline` acima), isso é
# embaraçosamente paralelo por repositório. É exatamente o "for sid in
# targets" sequencial, um repositório de cada vez, que fez ccr-ncr-projeto
# levar minutos por linguagem hoje.
#
# threading padrão não ajuda aqui: profile()/pyramid_frame()/from_pyramids()
# são laço Python + pandas em cima, presos no GIL. Por isso
# ProcessPoolExecutor (processo, não thread) via concurrent.futures.
#
# ProcessPoolExecutor usa spawn no macOS (default desde Python 3.8): o
# processo filho NÃO herda o monkeypatch de `extract.source` feito no pai
# (aquilo é estado do processo pai, um lambda fechando sobre um dict local,
# nem pickla). Cada worker recebe só a fatia de `eventos` dos repositórios
# dele e monta a própria fonte, do zero, via `monta_fonte` (função pública
# do módulo, essa sim pickla por referência).
#
# Cada worker grava num OUTPUT_DIR PRÓPRIO, não no compartilhado: os
# parquets em si não colidiriam (um arquivo por escopo), mas o
# `_manifest.json` do estágio é UM arquivo por estágio sem lock nenhum, e
# `estagio.run()` regrava ele a cada escopo processado. N workers escrevendo
# concorrente nesse mesmo arquivo corrompe a leitura de qualquer um deles no
# meio do caminho (visto na prática: `JSONDecodeError` num worker lendo o
# manifesto que outro estava com o `write_text` pela metade). Isolar o
# OUTPUT_DIR por worker elimina o compartilhamento por completo; o
# orquestrador copia os parquets pro destino comum depois que a fatia termina.
def _worker_estagio(
    nome_estagio: str,
    scratch_dir: str,
    worker_id: int,
    eventos_fatia: pd.DataFrame,
    scopes: list[int],
) -> tuple[dict, str]:
    """Roda UM estágio (extract/classify/snapshots/metrics) só pra `scopes`,
    num processo e num OUTPUT_DIR próprios. Devolve (manifesto da fatia,
    caminho do artifact_dir desse estágio dentro do OUTPUT_DIR do worker)."""
    from pyramid import config

    saida_worker = Path(scratch_dir) / "workers" / str(worker_id) / "output"
    config.CONFIG_DIR = Path(scratch_dir) / "config"
    config.OUTPUT_DIR = saida_worker
    config.LOG_DIR = Path(scratch_dir) / "workers" / str(worker_id) / "logs"
    config.settings.cache_clear()
    config.checkpoints.cache_clear()

    from pyramid import classify, extract, metrics, snapshots

    fonte_cls = monta_fonte(eventos_fatia)
    fabrica = lambda: fonte_cls(config.settings())  # noqa: E731
    extract.source = fabrica
    classify.source = fabrica
    snapshots.source = fabrica
    metrics.source = fabrica

    modulo = {"extract": extract, "classify": classify, "snapshots": snapshots, "metrics": metrics}
    man = modulo[nome_estagio].run(scopes=scopes, force=True, fail_fast=True)
    return man, str(config.artifact_dir(nome_estagio))


def roda_pipeline_paralelo(
    eventos: pd.DataFrame,
    band_months: int,
    n_workers: int | None = None,
    fim_forcado: pd.Timestamp | None = None,
) -> SimpleNamespace:
    """Mesma saída de `roda_pipeline(unit="project")`, mas fatiando os
    repositórios elegíveis em `n_workers` pedaços e rodando cada estágio
    (extract, depois classify, depois snapshots, depois metrics) num
    `ProcessPoolExecutor`, uma fatia por processo. Os 4 estágios continuam
    em SÉRIE entre si (classify lê o parquet que extract escreveu pro mesmo
    escopo, snapshots lê o de classify, e por aí vai); só o `for sid in
    scopes` DENTRO de cada estágio vira paralelo.

    `n_workers=None` usa `os.cpu_count()`.

    `_manifest.json` de cada estágio é UM arquivo por estágio, sem lock; se
    cada worker gravasse o próprio direto (como `estagio.run` faz sozinho),
    quem salvasse por último apagava as fatias dos outros, e
    `metrics.load_all()` (que lê só o que o manifesto lista, não escaneia o
    diretório) devolvia 1/N dos resultados sem erro nenhum: bug real, visto
    no benchmark (12030 linhas sequencial contra 3063 em paralelo). Por
    isso o merge explícito abaixo: cada worker devolve o próprio manifesto,
    o processo pai junta os `ok`/`failed` das N fatias num só e grava ele
    de volta antes do próximo estágio começar."""
    from concurrent.futures import ProcessPoolExecutor, as_completed

    from pyramid import config as _cfg
    from pyramid import logging_config as runlog

    scratch = Path(tempfile.mkdtemp(prefix="pyr_lang_fig_par_"))
    shutil.copytree(ROOT / "config", scratch / "config")
    escreve_config(scratch, eventos, band_months, fim_forcado, unit="project")

    _cfg.CONFIG_DIR = scratch / "config"
    _cfg.OUTPUT_DIR = scratch / "output"
    _cfg.LOG_DIR = scratch / "logs"
    _cfg.settings.cache_clear()
    _cfg.checkpoints.cache_clear()
    runlog.LOG_DIR = _cfg.LOG_DIR

    scope_ids = sorted(eventos["scope_id"].unique().tolist())
    n_workers = n_workers or os.cpu_count() or 1
    n_workers = max(1, min(n_workers, len(scope_ids)))
    fatias = [scope_ids[i::n_workers] for i in range(n_workers)]

    for nome_estagio in ("extract", "classify", "snapshots", "metrics"):
        destino = _cfg.artifact_dir(nome_estagio)
        destino.mkdir(parents=True, exist_ok=True)
        with ProcessPoolExecutor(max_workers=n_workers) as pool:
            futuros = [
                pool.submit(
                    _worker_estagio,
                    nome_estagio,
                    str(scratch),
                    i,
                    eventos[eventos["scope_id"].isin(fatia)],
                    fatia,
                )
                for i, fatia in enumerate(fatias)
            ]
            resultados = [fut.result() for fut in as_completed(futuros)]

        manifestos = [man for man, _ in resultados]
        falhas = {k: v for m in manifestos for k, v in m.get("failed", {}).items()}
        if falhas:
            raise SystemExit(f"{nome_estagio} falhou: {falhas}")

        # Cada worker gravou no PRÓPRIO output_dir (ver `_worker_estagio`);
        # junta os parquets no destino comum antes do próximo estágio ler.
        for _, origem_dir in resultados:
            origem = Path(origem_dir)
            if not origem.is_dir():
                continue
            for arquivo in origem.iterdir():
                if arquivo.name == "_manifest.json":
                    continue  # é o manifesto da FATIA; o merge abaixo grava o de verdade
                shutil.copy2(arquivo, destino / arquivo.name)

        merge = {"stage": nome_estagio, "ok": {}, "failed": {}}
        for m in manifestos:
            merge["ok"].update(m.get("ok", {}))
        runlog.save(nome_estagio, merge)

    from pyramid import attractiveness as attr
    from pyramid import metrics, plots, projection, snapshots

    fonte_cls = monta_fonte(eventos)
    fabrica = lambda: fonte_cls(_cfg.settings())  # noqa: E731
    snapshots.source = fabrica
    metrics.source = fabrica
    attr.source = fabrica

    return SimpleNamespace(
        config=_cfg,
        plots=plots,
        snapshots=snapshots,
        metrics=metrics,
        projection=projection,
        attractiveness=attr,
        scratch=scratch,
        sid=None,
    )


def _salva_fig(fig: object, nome: str) -> None:
    """`nome` pode ter subpasta (`"backtest/foo.png"`): cria o que faltar."""
    caminho = CFG.saida / nome
    caminho.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(caminho, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"salvo: {caminho}")


def _caminho_csv(nome: str) -> Path:
    """CSV separado das figuras (pedido explícito): fica em `csv/` dentro da
    pasta da linguagem, não solto ao lado do PNG. `nome` pode ter subpasta
    dentro de `csv/` (`"backtest/foo.csv"`), pra espelhar a organização do
    PNG correspondente."""
    caminho = CFG.saida / "csv" / nome
    caminho.parent.mkdir(parents=True, exist_ok=True)
    return caminho


def _legenda_discussion(fig: object, plots_mod: object) -> None:
    """Mesma legenda de `plots._legend` (Patch com FILL/HATCH do motor
    auditado), com rótulo próprio deste script (`ROTULO_LEGENDA`: "discussion"
    em vez de "non-coding"). Não reusa `plots._legend` porque aquela função é
    privada do módulo auditado e trava no `PT_LABEL` exato do artigo."""
    from matplotlib.patches import Patch

    handles = [
        Patch(
            facecolor=plots_mod.FILL[c],
            hatch=plots_mod.HATCH[c],
            edgecolor="#4D4D4D",
            label=ROTULO_LEGENDA[c],
        )
        for c in ("non_coding", "moved", "coding")
    ]
    fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False, fontsize=8)


def gera_piramide_multi(eventos: pd.DataFrame) -> None:
    """Uma pirâmide por valor de `BANDAS_MESES_PIRAMIDE` (default: 3 e 12 meses
    de banda). 3 meses é a divisão em quarter da metodologia; qualquer outro
    valor não é. O nome do arquivo carrega os dois: se é quarter ou não, e a
    largura de banda exata, pra nenhuma versão pisar na outra.

    Monta a figura na mão (`pyramid_frame` + `draw_pyramid`, as mesmas peças
    públicas que `plots.figure_pyramid` usa por dentro) em vez de chamar
    `pl.plots.figure_pyramid` direto: aquela função já salva com a legenda do
    artigo ("non-coding"), e o PNG que ela devolve já está gravado, sem
    Figure pra reabrir e trocar o texto. Não toca em `plots.figure_pyramid`
    (usada pela replicação real sobre dado ghapi, precisa do termo exato do
    artigo)."""
    for banda_meses in BANDAS_MESES_PIRAMIDE:
        pl = roda_pipeline(eventos, band_months=banda_meses)
        try:
            t = pd.Timestamp(pl.snapshots.classification_snapshot())
            frame = pl.plots.pyramid_frame(pl.snapshots.load(pl.sid), t)
            fig, ax = plt.subplots(figsize=(4.2, 3.4))
            pl.plots.draw_pyramid(ax, frame)
            ax.set_title(f"{LING.atual.nome}, {t.date()}", fontsize=9)
            ax.set_xlabel("contribuidores", fontsize=8)
            ax.set_ylabel(pl.plots.rotulo_da_idade(), fontsize=8)
            _legenda_discussion(fig, pl.plots)
            rotulo = "comquarter" if banda_meses == 3 else "semquarter"
            nome = (
                f"piramide/piramide_{LING.atual.slug}_metodologia_{rotulo}_banda{banda_meses}m.png"
            )
            fig.tight_layout(rect=(0, 0.06, 1, 1))
            _salva_fig(fig, nome)
        finally:
            shutil.rmtree(pl.scratch, ignore_errors=True)


MESES_MIN_VETERANO = (3, 12)


def gera_piramide_veteranos(eventos: pd.DataFrame) -> None:
    """A pirâmide padrão só mostra quem está ATIVO no snapshot
    (`plots.pyramid_population = active`), e quem chegou há pouco passa nesse
    filtro quase de graça (o único evento que tem já É recente). Quem chegou
    há anos, a maioria já ficou quieto e cai fora. Resultado: a base da
    pirâmide normal é dominada por gente recém-chegada, mesmo essa gente
    sendo uma fração pequena do total histórico (medido: 1,4% dos 51 mil
    contribuintes do Clojure têm menos de 3 meses de idade, mas isso ainda
    assim é quase metade da população ATIVA num dado instante).

    Esta função tira do evento bruto todo mundo cujo primeiro evento na
    linguagem é mais recente que `MESES_MIN_VETERANO` meses (idade desde a
    PRIMEIRA contribuição, a mesma base de idade que a pirâmide usa
    internamente), antes de rodar o pipeline: não é cortar a barra da
    pirâmide normal, é perguntar como fica a população SEM quem chegou
    ontem. Uma pirâmide por valor de `MESES_MIN_VETERANO` (default: 3 e 12
    meses, pedido explícito do usuário)."""
    primeiro = eventos.groupby("contributor_id")["timestamp"].min()
    fim = eventos["timestamp"].max()
    for meses_min in MESES_MIN_VETERANO:
        corte = fim - pd.DateOffset(months=meses_min)
        veteranos = primeiro[primeiro <= corte].index
        filtrado = eventos[eventos["contributor_id"].isin(veteranos)]
        excluidos = eventos["contributor_id"].nunique() - len(veteranos)
        print(
            f"aviso: {excluidos} contribuidores com menos de {meses_min} meses de "
            f"idade excluídos da pirâmide veteranos_{meses_min}m",
            file=sys.stderr,
        )
        pl = roda_pipeline(filtrado, band_months=3)
        try:
            t = pd.Timestamp(pl.snapshots.classification_snapshot())
            frame = pl.plots.pyramid_frame(pl.snapshots.load(pl.sid), t)
            fig, ax = plt.subplots(figsize=(4.2, 3.4))
            pl.plots.draw_pyramid(ax, frame)
            ax.set_title(
                f"{LING.atual.nome}, {t.date()} (>= {meses_min} meses de idade)", fontsize=9
            )
            ax.set_xlabel("contribuidores", fontsize=8)
            ax.set_ylabel(pl.plots.rotulo_da_idade(), fontsize=8)
            _legenda_discussion(fig, pl.plots)
            fig.tight_layout(rect=(0, 0.06, 1, 1))
            nome = f"piramide-veteranos/piramide_{LING.atual.slug}_veteranos_min{meses_min}m.png"
            _salva_fig(fig, nome)
        finally:
            shutil.rmtree(pl.scratch, ignore_errors=True)


def _frame_por_anos_contribuicao(
    eventos: pd.DataFrame, snapshot: pd.Timestamp, window_meses: int = 3
) -> pd.DataFrame:
    """`band` = quantidade de anos-calendário DISTINTOS em que o contribuinte
    teve pelo menos 1 evento até `snapshot`, não o tempo de calendário desde
    o primeiro evento. Alguém que contribuiu em 2011, 2014 e 2015 cai em
    band=2 (3 anos, 0-indexado como as outras pirâmides), não em band=3
    (2015-2011=4 anos de calendário). Só entra quem está ativo (evento
    dentro de `window_meses` de `snapshot`, mesma leitura de
    `plots.pyramid_population = active`). Categoria replica a regra do
    motor (`snapshots.py`): codou alguma vez = coding, ou moved se discutiu
    antes do primeiro commit/PR; só discussão = non_coding."""
    ev = eventos[eventos["timestamp"] <= snapshot]
    anos = ev.groupby("contributor_id")["timestamp"].apply(lambda s: s.dt.year.nunique())
    ultimo = ev.groupby("contributor_id")["timestamp"].max()
    coding_mask = ev["event_type"].isin(TIPOS_CODING)
    primeiro_coding = ev[coding_mask].groupby("contributor_id")["timestamp"].min()
    primeiro_discussao = ev[~coding_mask].groupby("contributor_id")["timestamp"].min()

    pessoas = pd.DataFrame({"band": anos - 1, "ultimo": ultimo})
    pessoas["ativo"] = pessoas["ultimo"] >= (snapshot - pd.DateOffset(months=window_meses))
    pessoas["primeiro_coding"] = primeiro_coding
    pessoas["primeiro_discussao"] = primeiro_discussao
    codou = pessoas["primeiro_coding"].notna()
    moveu = codou & pessoas["primeiro_discussao"].notna()
    moveu &= pessoas["primeiro_discussao"] < pessoas["primeiro_coding"]
    pessoas["categoria"] = "non_coding"
    pessoas.loc[codou, "categoria"] = "coding"
    pessoas.loc[moveu, "categoria"] = "moved"

    pessoas = pessoas[pessoas["ativo"]]
    tabela = pessoas.groupby(["band", "categoria"]).size().unstack(fill_value=0)
    for coluna in ("non_coding", "moved", "coding"):
        if coluna not in tabela.columns:
            tabela[coluna] = 0
    banda_max = int(pessoas["band"].max()) if len(pessoas) else 0
    tabela = tabela.reindex(range(banda_max + 1), fill_value=0)
    tabela.index.name = "band"
    return tabela[["non_coding", "moved", "coding"]].reset_index()


def gera_piramide_anos_distintos(eventos: pd.DataFrame) -> None:
    """Pirâmide com uma base de idade que o motor auditado não tem: em vez de
    `calendar_tenure` (tempo de calendário desde o primeiro evento, EM VIGOR
    em toda outra figura deste script) ou `accumulated_active` (soma de dias
    de atividade contínua, refutada no motor por esvaziar os tipos C/D), aqui
    a idade é a CONTAGEM de anos-calendário distintos com evento. Pedido
    explícito do usuário: "contribuiu em 2011, 2014, 2015 = 3 anos de
    contribuição", não 4.

    Só a pirâmide muda de base aqui. CCR/NCR, magnetismo/stickiness,
    projeção e backtest continuam em `calendar_tenure`: são metodologia
    auditada contra o artigo, e essa idade nova não tem correspondente
    testado ali (reimplementar cada um deles sob essa base seria escrever
    metodologia nova sem nada pra validar contra). Por isso esta função não
    reusa `classify`/`snapshots`: monta a tabela na mão
    (`_frame_por_anos_contribuicao`) e desenha com `plots.draw_pyramid`, a
    mesma rotina visual das outras pirâmides, sem o resto do pipeline.
    `roda_pipeline(band_months=12)` entra só pelo efeito colateral de deixar
    `config.settings()` e `plots` prontos pro desenho (1 unidade de banda =
    12 meses, que é exatamente como essa idade já vem contada: em anos)."""
    snapshot = eventos["timestamp"].max()
    tabela = _frame_por_anos_contribuicao(eventos, snapshot)
    pl = roda_pipeline(eventos, band_months=12)
    try:
        fig, ax = plt.subplots(figsize=(6.5, max(4.0, 0.32 * len(tabela))))
        pl.plots.draw_pyramid(ax, tabela.astype({"band": int}))
        ax.set_xlabel("contribuidores")
        ax.set_ylabel("anos-calendário distintos de contribuição")
        ax.set_title(
            f"{LING.atual.nome}, {snapshot.date()} (idade = anos distintos, não calendário)"
        )
        from matplotlib.patches import Patch

        handles = [
            Patch(
                facecolor=pl.plots.FILL[c],
                hatch=pl.plots.HATCH[c],
                edgecolor="#4D4D4D",
                label=ROTULO_LEGENDA[c],
            )
            for c in ("non_coding", "moved", "coding")
        ]
        ax.legend(handles=handles, loc="lower right", fontsize=8)
        _salva_fig(fig, f"piramide-anos-distintos/piramide_{LING.atual.slug}_anos_distintos.png")
    finally:
        shutil.rmtree(pl.scratch, ignore_errors=True)


MORTE_JANELA_MESES = 3


def _idade_morte_por_ano(
    eventos: pd.DataFrame, janela_meses: int = MORTE_JANELA_MESES
) -> pd.DataFrame:
    """Idade (anos) na última contribuição, mediana e média, por ano da
    última contribuição: a versão CONTÍNUA de "idade-morte ao longo do tempo",
    companheira de `gera_abandono_por_ano` (mesma população: sem
    contribuição nos últimos `janela_meses` meses, referência fixa no
    evento mais recente da coleta; mesmo agrupamento por ano da última
    contribuição). `gera_piramide_idade_morte_evolucao` já cobre "ao longo
    do tempo" como grade de pirâmides-snapshot (2016/2019/2022/2026);
    esta é o par contínuo, ano a ano, sem pular nenhum: abandono conta
    QUANTOS morreram por ano, esta conta COM QUE IDADE (o equivalente de
    "expectativa de vida por ano" ao lado da pirâmide de idade de morte)."""
    primeiro = eventos.groupby("contributor_id")["timestamp"].min()
    ultimo = eventos.groupby("contributor_id")["timestamp"].max()
    agora = eventos["timestamp"].max()
    limite = agora - pd.Timedelta(days=janela_meses * DAYS_PER_MONTH)
    mortos = ultimo[ultimo < limite].index

    pessoas = pd.DataFrame({"primeiro": primeiro, "ultimo": ultimo}).loc[mortos]
    pessoas["idade_anos"] = (pessoas["ultimo"] - pessoas["primeiro"]).dt.days / DAYS_PER_MONTH / 12
    pessoas["ano_morte"] = pessoas["ultimo"].dt.year
    return (
        pessoas.groupby("ano_morte")["idade_anos"]
        .agg(idade_mediana="median", idade_media="mean", n="count")
        .reset_index()
    )


def _frame_idade_morte(
    eventos: pd.DataFrame,
    janela_meses: int = MORTE_JANELA_MESES,
    recorte_meses: int | None = None,
) -> pd.DataFrame:
    """Pra quem já "morreu" (sem contribuição nos últimos `janela_meses`
    meses, mesmo corte de `gera_abandono_por_ano`: referência fixa é o
    evento mais recente da coleta, não a data de hoje), a idade que tinha na
    ÚLTIMA contribuição: quantos anos de calendário se passaram entre a
    primeira e a última. `band` = esses anos, inteiro (0 = morreu com menos
    de 1 ano de idade). Mesma régua de banda do motor auditado (`age_months
    // band_months`, aqui com band_months=12: floor de meses sobre 12).
    Categoria replica a regra das outras pirâmides manuais deste script
    (`_frame_por_anos_contribuicao`): codou alguma vez = coding, ou moved se
    discutiu antes do primeiro commit/PR; só discussão = non_coding.

    `recorte_meses`, quando dado, restringe ainda mais: só entra quem
    morreu nos últimos `recorte_meses` meses (mesmo `agora` fixo como
    referência). Sem isso, a pirâmide acumula quem morreu em QUALQUER ano
    desde sempre, e o formato final é dominado por quem morreu há mais
    tempo, já que a população acumulada só cresce: mostra "quem já saiu,
    alguma vez", não "quem está saindo agora". Pedido do usuário."""
    primeiro = eventos.groupby("contributor_id")["timestamp"].min()
    ultimo = eventos.groupby("contributor_id")["timestamp"].max()
    agora = eventos["timestamp"].max()
    limite = agora - pd.Timedelta(days=janela_meses * DAYS_PER_MONTH)
    morreu = ultimo < limite
    if recorte_meses is not None:
        corte_recente = agora - pd.Timedelta(days=recorte_meses * DAYS_PER_MONTH)
        morreu &= ultimo >= corte_recente
    mortos = ultimo[morreu].index

    coding_mask = eventos["event_type"].isin(TIPOS_CODING)
    primeiro_coding = eventos[coding_mask].groupby("contributor_id")["timestamp"].min()
    primeiro_discussao = eventos[~coding_mask].groupby("contributor_id")["timestamp"].min()

    pessoas = pd.DataFrame({"primeiro": primeiro, "ultimo": ultimo}).loc[mortos]
    meses_vividos = (pessoas["ultimo"] - pessoas["primeiro"]).dt.days / DAYS_PER_MONTH
    pessoas["band"] = (meses_vividos // 12).astype(int)
    pessoas["primeiro_coding"] = primeiro_coding
    pessoas["primeiro_discussao"] = primeiro_discussao
    codou = pessoas["primeiro_coding"].notna()
    moveu = codou & pessoas["primeiro_discussao"].notna()
    moveu &= pessoas["primeiro_discussao"] < pessoas["primeiro_coding"]
    pessoas["categoria"] = "non_coding"
    pessoas.loc[codou, "categoria"] = "coding"
    pessoas.loc[moveu, "categoria"] = "moved"

    tabela = pessoas.groupby(["band", "categoria"]).size().unstack(fill_value=0)
    for coluna in ("non_coding", "moved", "coding"):
        if coluna not in tabela.columns:
            tabela[coluna] = 0
    banda_max = int(pessoas["band"].max()) if len(pessoas) else 0
    tabela = tabela.reindex(range(banda_max + 1), fill_value=0)
    tabela.index.name = "band"
    return tabela[["non_coding", "moved", "coding"]].reset_index()


def _desenha_piramide_idade_morte(
    eventos: pd.DataFrame, tabela: pd.DataFrame, nome_arquivo: str, subtitulo: str
) -> None:
    """Desenho compartilhado por `gera_piramide_idade_morte` e
    `gera_piramide_idade_morte_recente`: só a tabela e o texto mudam entre
    as duas. `roda_pipeline(band_months=12)` só deixa `plots`/`config`
    prontos pro desenho (`draw_pyramid`), a tabela já vem pronta de
    `_frame_idade_morte`."""
    pl = roda_pipeline(eventos, band_months=12)
    try:
        fig, ax = plt.subplots(figsize=(6.5, max(4.0, 0.32 * len(tabela))))
        pl.plots.draw_pyramid(ax, tabela.astype({"band": int}))
        ax.set_xlabel("contribuidores que já abandonaram")
        ax.set_ylabel("idade na última contribuição (anos)")
        ax.set_title(f"{LING.atual.nome}: idade na última contribuição, {subtitulo}")
        _legenda_discussion(fig, pl.plots)
        fig.tight_layout(rect=(0, 0.06, 1, 1))
        _salva_fig(fig, nome_arquivo)
    finally:
        shutil.rmtree(pl.scratch, ignore_errors=True)


def gera_piramide_idade_morte(eventos: pd.DataFrame) -> None:
    """ "A pirâmide de quando a gente morre", pedido do usuário depois de ver
    um gráfico de idade-na-morte humana: em vez de "quantos contribuidores
    ativos existem em cada idade" (a pirâmide padrão), "com que idade os
    contribuidores que já abandonaram estavam quando contribuíram pela
    última vez". Mesma população de `gera_abandono_por_ano` (sem
    contribuição nos últimos `MORTE_JANELA_MESES` meses); o que muda é o
    eixo: lá é ANO da última contribuição, aqui é IDADE (calendar_tenure) na
    última contribuição. Cumulativa desde sempre: quem quiser só a
    dinâmica recente usa `gera_piramide_idade_morte_recente`."""
    tabela = _frame_idade_morte(eventos)
    _desenha_piramide_idade_morte(
        eventos,
        tabela,
        f"idade-morte/piramide_{LING.atual.slug}_idade_morte.png",
        f"de quem já não contribui há mais de {MORTE_JANELA_MESES} meses (histórico completo)",
    )


IDADE_MORTE_RECENTE_MESES = 12


def gera_piramide_idade_morte_recente(eventos: pd.DataFrame) -> None:
    """`gera_piramide_idade_morte` restrita a quem morreu nos últimos
    `IDADE_MORTE_RECENTE_MESES` meses: pedido explícito do usuário. A
    versão cumulativa mistura quem saiu em qualquer ano desde sempre,
    dominada por quem saiu há mais tempo (a população acumulada só
    cresce); esta responde "quem está saindo agora", não "quem já saiu,
    alguma vez"."""
    tabela = _frame_idade_morte(eventos, recorte_meses=IDADE_MORTE_RECENTE_MESES)
    if tabela[["non_coding", "moved", "coding"]].to_numpy().sum() == 0:
        print(
            f"aviso: ninguém morreu nos últimos {IDADE_MORTE_RECENTE_MESES} meses em "
            f"{LING.atual.nome}; idade-morte-recente pulada",
            file=sys.stderr,
        )
        return
    _desenha_piramide_idade_morte(
        eventos,
        tabela,
        f"idade-morte/piramide_{LING.atual.slug}_idade_morte_recente.png",
        f"de quem morreu nos últimos {IDADE_MORTE_RECENTE_MESES} meses",
    )


def gera_piramide_idade_morte_evolucao(eventos: pd.DataFrame) -> None:
    """`gera_piramide_idade_morte` ao longo do tempo: um painel por
    ano-snapshot (`ANOS_GRADE_ANOS_DISTINTOS`), cada um só com quem já tinha
    "morrido" até aquele ano (corta os eventos em 31/dez daquele ano, ou o
    último dado real, o que vier primeiro; mesmo `min()` de
    `gera_grade_anos_distintos`, senão o ano corrente aparece sempre "sem
    dado"). Largura (X) compartilhada entre os painéis, mesmo motivo de
    `gera_grade_anos_distintos`: honestidade de tamanho de população. Teto
    de idade (Y) NÃO compartilhado: não é figura auditada, sem compromisso
    de mostrar "crescimento de altura" tipo ESEM14 Fig.3."""
    anos = ANOS_GRADE_ANOS_DISTINTOS
    tabelas: dict[int, pd.DataFrame | None] = {}
    for ano in anos:
        limite = pd.Timestamp(f"{ano}-12-31")
        corte = min(limite, eventos["timestamp"].max())
        if corte < eventos["timestamp"].min():
            tabelas[ano] = None
            continue
        tabelas[ano] = _frame_idade_morte(eventos[eventos["timestamp"] <= corte])

    validas = [t for t in tabelas.values() if t is not None and len(t)]
    if not validas:
        print(
            f"aviso: nenhum de {anos} tem gente que já abandonou em "
            f"{LING.atual.nome}; idade-morte-tempo pulada",
            file=sys.stderr,
        )
        return
    xmax = max(t[["non_coding", "moved", "coding"]].sum(axis=1).max() for t in validas)

    pl = roda_pipeline(eventos, band_months=12)
    try:
        fig, eixos = plt.subplots(1, len(anos), figsize=(3.4 * len(anos), 4.6))
        for eixo, ano in zip(eixos, anos, strict=True):
            eixo.set_title(str(ano), fontsize=10)
            tabela = tabelas[ano]
            if tabela is None or tabela.empty:
                eixo.axis("off")
                eixo.text(0.5, 0.5, "sem dado", ha="center", va="center", transform=eixo.transAxes)
                continue
            pl.plots.draw_pyramid(eixo, tabela.astype({"band": int}), xmax=xmax)
            eixo.set_xlabel("abandonaram", fontsize=8)
        eixos[0].set_ylabel("idade na última contribuição (anos)", fontsize=9)
        _legenda_discussion(fig, pl.plots)
        fig.suptitle(
            f"{LING.atual.nome}: idade na última contribuição, ao longo do tempo", fontsize=12
        )
        fig.tight_layout(rect=(0, 0.1, 1, 0.9))
        _salva_fig(fig, f"idade-morte/piramide_{LING.atual.slug}_idade_morte_evolucao.png")
    finally:
        shutil.rmtree(pl.scratch, ignore_errors=True)

    # Par contínuo da grade acima: ano a ano, sem pular, em vez de só 4
    # anos-snapshot. Ver `_idade_morte_por_ano`.
    tendencia = _idade_morte_por_ano(eventos)
    caminho_csv = _caminho_csv("idade-morte/idade_morte_por_ano.csv")
    tendencia.to_csv(caminho_csv, index=False)
    print(f"salvo: {caminho_csv}", file=sys.stderr)

    # Média, não mediana: a maioria de quem "morre" fez uma única
    # contribuição na vida inteira (idade = 0), e essa maioria domina a
    # mediana em quase todo ano, fixando-a em 0 até ela pular de uma vez
    # quando finalmente deixa de ser maioria. A média sobe aos poucos, ano a
    # ano, e mostra a tendência real sem esse efeito de salto.
    fig2, ax2 = plt.subplots(figsize=(max(7.0, 0.45 * len(tendencia)), 4.5))
    ax2.plot(
        tendencia["ano_morte"],
        tendencia["idade_media"],
        marker="o",
        markersize=5,
        color="black",
    )
    from matplotlib.ticker import MaxNLocator

    ax2.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax2.set_xlabel("ano da última contribuição")
    ax2.set_ylabel("idade média na última contribuição (anos)")
    ax2.set_title(f"{LING.atual.nome}: idade na última contribuição, por ano (média)")
    _salva_fig(fig2, f"idade-morte/idade_morte_media_{LING.atual.slug}_por_ano.png")


def gera_geral_idade_morte(eventos_por_lingua: dict[str, pd.DataFrame]) -> None:
    """`gera_piramide_idade_morte` das 4 linguagens lado a lado, sem corte de
    data comum (idade-morte já usa referência fixa própria: o evento mais
    recente da COLETA daquela linguagem). Largura (X) NÃO compartilhada
    entre painéis: linguagens têm população de sempre muito diferente
    (Elixir e Clojure têm ordens de grandeza mais gente que Zig), e um teto
    comum esmagaria as menores num traço fino."""
    fig, eixos = _grade_para_linguagens()
    plots_mod = None
    for eixo, (slug, linguagem) in zip(eixos, LINGUAGENS.items(), strict=True):
        eventos = eventos_por_lingua[slug]
        tabela = _frame_idade_morte(eventos)
        if tabela.empty:
            eixo.axis("off")
            eixo.text(0.5, 0.5, "sem dado", ha="center", va="center", transform=eixo.transAxes)
            eixo.set_title(linguagem.nome)
            continue
        pl = roda_pipeline(eventos, band_months=12)
        try:
            pl.plots.draw_pyramid(eixo, tabela.astype({"band": int}))
            plots_mod = pl.plots
        finally:
            shutil.rmtree(pl.scratch, ignore_errors=True)
        eixo.set_title(linguagem.nome)
        eixo.set_xlabel("contribuidores que já abandonaram", fontsize=8)
        eixo.set_ylabel("idade na última contribuição (anos)", fontsize=8)
    if plots_mod is not None:
        _legenda_discussion(fig, plots_mod)
    fig.suptitle(
        f"Idade na última contribuição, de quem já não contribui há mais de "
        f"{MORTE_JANELA_MESES} meses, {len(LINGUAGENS)} linguagens",
        fontsize=13,
    )
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    caminho = _caminho_geral("piramides_4_linguagens_idade_morte.png")
    fig.savefig(caminho, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"salvo: {caminho}")


def _monta_linha_tempo(
    pl: SimpleNamespace,
    *,
    anos: list[int] | None = None,
    ultimos_anos: int | None = None,
    passo_anos: int = 1,
) -> object | None:
    """Mesma lógica de `plots.figure_pyramid_timeline` (teto comum entre os
    anos, de propósito: mostra a pirâmide crescendo de altura, ver comentário
    em `plots.figure_fig3`), sem a legenda travada no termo do artigo. Monta
    a Figure na mão com as mesmas peças públicas (`snapshots.snapshot_dates`,
    `snapshots.load`, `plots.pyramid_frame`, `plots.draw_pyramid`) em vez de
    chamar `figure_pyramid_timeline` direto, pelo mesmo motivo de
    `gera_piramide_multi`: aquela função já salva com "non-coding" na
    legenda, sem Figure pra reabrir depois. Não toca em
    `figure_pyramid_timeline`/`figure_fig3`. Devolve `None` se nenhum ano
    pedido tem contribuidor ativo; quem chama decide o aviso."""
    serie = pl.snapshots.snapshot_dates()
    if anos is not None:
        alvo = set(anos)
        candidatas = [d for d in serie if d.year in alvo]
    else:
        limite = serie[-1] - pd.DateOffset(years=ultimos_anos)
        candidatas = [d for d in serie if d >= limite]
    por_ano: dict[int, pd.Timestamp] = {}
    for d in candidatas:
        por_ano[d.year] = d  # serie é crescente: fica a última data de cada ano
    if passo_anos > 1 and por_ano:
        ultimo_ano = max(por_ano)
        por_ano = {a: d for a, d in por_ano.items() if (ultimo_ano - a) % passo_anos == 0}
    historico = pl.snapshots.load(pl.sid)
    quadros = {d: pl.plots.pyramid_frame(historico, d) for d in sorted(por_ano.values())}
    datas = [
        d
        for d, f in quadros.items()
        if not f.empty and (f["non_coding"].sum() + f["moved"].sum() + f["coding"].sum()) > 0
    ]
    if not datas:
        return None

    vivos = [quadros[d] for d in datas]
    xmax = max(max(f["non_coding"].max(), (f["moved"] + f["coding"]).max()) for f in vivos)
    ymax = max(int(f["band"].max()) for f in vivos)
    fig, axes = plt.subplots(1, len(datas), figsize=(3.0 * len(datas), 4.2), squeeze=False)
    for j, d in enumerate(datas):
        ax = axes[0][j]
        pl.plots.draw_pyramid(ax, quadros[d], xmax=float(xmax), ymax=ymax)
        ax.set_title(str(d.date()), fontsize=9)
        if j == 0:
            ax.set_ylabel(f"{LING.atual.nome}\n{pl.plots.rotulo_da_idade()}", fontsize=8)
        else:
            ax.tick_params(axis="y", labelleft=False)
        ax.set_xlabel("contribuidores", fontsize=8)
    _legenda_discussion(fig, pl.plots)
    fig.suptitle(f"{LING.atual.nome}: pirâmide ao longo do tempo", fontsize=10)
    fig.tight_layout(rect=(0, 0.08, 1, 0.92))
    return fig


def gera_linha_tempo(pl: SimpleNamespace) -> None:
    fig = _monta_linha_tempo(pl, ultimos_anos=ULTIMOS_ANOS, passo_anos=PASSO_ANOS)
    if fig is None:
        print(
            f"aviso: nenhum dos últimos {ULTIMOS_ANOS} anos tem contribuidor ativo em "
            f"{LING.atual.nome}; linha-tempo pulada",
            file=sys.stderr,
        )
        return
    nome = (
        f"linha-tempo/linha_do_tempo_{LING.atual.slug}_metodologia_"
        f"{ULTIMOS_ANOS}anos_passo{PASSO_ANOS}.png"
    )
    _salva_fig(fig, nome)


def gera_linha_tempo_4(eventos: pd.DataFrame) -> None:
    """Banda de eixo Y customizada: precisa rodar snapshots de novo com outro band_months."""
    pl = roda_pipeline(eventos, band_months=BANDA_ANOS_TIMELINE * 12)
    for janela in (3, 12):
        alvo = pl.scratch / "config" / "settings.yaml"
        cfg = yaml.safe_load(alvo.read_text(encoding="utf-8"))
        cfg["plots"]["pyramid_window_months"] = janela
        alvo.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")
        pl.config.settings.cache_clear()
        fig = _monta_linha_tempo(pl, anos=ANOS_ESCOLHIDOS)
        if fig is None:
            print(
                f"aviso: nenhum de {ANOS_ESCOLHIDOS} tem contribuidor ativo em "
                f"{LING.atual.nome} (janela {janela}m); painel pulado",
                file=sys.stderr,
            )
            continue
        anos_txt = "-".join(str(a) for a in ANOS_ESCOLHIDOS)
        nome = (
            f"linha-tempo-4/linha_do_tempo_{LING.atual.slug}_4anos_{anos_txt}"
            f"_banda{BANDA_ANOS_TIMELINE}a_janela{janela}m.png"
        )
        _salva_fig(fig, nome)
    shutil.rmtree(pl.scratch, ignore_errors=True)


def gera_linha_tempo_4_teto_proprio(eventos: pd.DataFrame) -> None:
    """Mesma ideia de `gera_linha_tempo_4` (pirâmide nos mesmos
    `ANOS_ESCOLHIDOS`, lado a lado), mas cada painel com o PRÓPRIO teto de
    idade, não o teto emprestado do ano mais recente.

    `figure_pyramid_timeline`/`figure_fig3` (motor auditado) usam de
    propósito um teto comum entre os anos: a ESEM14 Fig.3 é sobre a
    pirâmide crescer de ALTURA ao longo do tempo, e um teto próprio por
    painel apagaria esse crescimento visual (ver comentário em
    `plots.figure_fig3`). Pedido explícito do usuário: quando ele pede
    teto próprio via `--teto-proprio-timeline`, quer o oposto — 2016 não
    mostra espaço pra uma idade que não existia ainda naquele ano.

    Não toca em `figure_pyramid_timeline`/`figure_fig3`: monta os painéis
    na mão com as mesmas peças públicas do motor (`snapshots.snapshot_dates`,
    `snapshots.load`, `plots.pyramid_frame`, `plots.draw_pyramid`), sem
    arriscar a fidelidade da Fig.3 oficial."""
    pl = roda_pipeline(eventos, band_months=BANDA_ANOS_TIMELINE * 12)
    try:
        for janela in (3, 12):
            alvo = pl.scratch / "config" / "settings.yaml"
            cfg = yaml.safe_load(alvo.read_text(encoding="utf-8"))
            cfg["plots"]["pyramid_window_months"] = janela
            alvo.write_text(
                yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding="utf-8"
            )
            pl.config.settings.cache_clear()

            serie = pl.snapshots.snapshot_dates()
            alvo_anos = set(ANOS_ESCOLHIDOS)
            por_ano: dict[int, pd.Timestamp] = {}
            for d in serie:
                if d.year in alvo_anos:
                    por_ano[d.year] = d  # serie é crescente: fica a última data de cada ano
            historico = pl.snapshots.load(pl.sid)
            quadros = {d: pl.plots.pyramid_frame(historico, d) for d in sorted(por_ano.values())}
            datas = [
                d
                for d, f in quadros.items()
                if not f.empty
                and (f["non_coding"].sum() + f["moved"].sum() + f["coding"].sum()) > 0
            ]
            if not datas:
                print(
                    f"aviso: nenhum de {ANOS_ESCOLHIDOS} tem contribuidor ativo em "
                    f"{LING.atual.nome} (janela {janela}m); painel pulado",
                    file=sys.stderr,
                )
                continue

            xmax = max(
                max(
                    quadros[d]["non_coding"].max(),
                    (quadros[d]["moved"] + quadros[d]["coding"]).max(),
                )
                for d in datas
            )
            fig, axes = plt.subplots(1, len(datas), figsize=(3.0 * len(datas), 4.2), squeeze=False)
            for j, d in enumerate(datas):
                ax = axes[0][j]
                # ymax=None (default): cada painel usa o próprio teto daquele ano.
                pl.plots.draw_pyramid(ax, quadros[d], xmax=float(xmax))
                ax.set_title(str(d.date()), fontsize=9)
                if j == 0:
                    ax.set_ylabel(f"{LING.atual.nome}\n{pl.plots.rotulo_da_idade()}", fontsize=8)
                ax.set_xlabel("contribuidores", fontsize=8)
            fig.suptitle(
                f"{LING.atual.nome}: pirâmide ao longo do tempo (teto próprio de cada ano)",
                fontsize=10,
            )
            anos_txt = "-".join(str(a) for a in ANOS_ESCOLHIDOS)
            nome = (
                f"linha-tempo-4-teto-proprio/linha_do_tempo_{LING.atual.slug}_4anos_{anos_txt}"
                f"_banda{BANDA_ANOS_TIMELINE}a_janela{janela}m_tetoproprio.png"
            )
            _salva_fig(fig, nome)
    finally:
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
    saida = _caminho_csv(f"projecao/projecao_{LING.atual.slug}_metodologia_numeros.csv")
    linha.to_csv(saida, index=False)
    print(f"salvo: {saida}")


def _agrupa_por_anos(todos: pd.DataFrame, anos: int, band_months: int = 3) -> pd.DataFrame:
    """Soma banda a banda (cada banda = `band_months` meses de idade) dentro
    de janelas de `anos` anos, pra um gráfico com menos barras. Contribuidor
    não conta duas vezes: banda é idade NUM instante (quem tem 3 anos não
    também "é" quem tem 2), então somar bandas adjacentes é somar gente de
    idade diferente dentro da mesma janela, não duplicar ninguém."""
    bandas_por_grupo = round(anos * 12 / band_months)
    grupo = todos["band"] // bandas_por_grupo
    agregado = todos.groupby(grupo)[["actual", "cohort_pred", "baseline_pred"]].sum()
    agregado["rotulo"] = [f"{int(g) * anos}-{(int(g) + 1) * anos} anos" for g in agregado.index]
    return agregado.reset_index(drop=True)


def _desenha_barra_projecao(
    todos: pd.DataFrame, rotulos: pd.Series, titulo: str, nome: str
) -> None:
    """Real x previsto (coorte) x previsto (baseline), uma barra tripla por
    banda ou grupo de bandas. Compartilhado pela versão trimestral e pelas
    versões agrupadas de `gera_projecao_backtest`."""
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
    ax.set_xticklabels(rotulos, rotation=90 if n > 15 else 0)
    ax.set_xlabel("banda (idade)")
    ax.set_ylabel("contribuidores")
    ax.set_title(titulo)
    ax.legend()
    _salva_fig(fig, nome)


def _avalia_direcao(todos: pd.DataFrame) -> pd.DataFrame:
    """O "jogo" pedido: a previsão (coorte) disse que ia subir/descer/ficar
    igual em relação à mesma coorte um passo antes (`baseline_pred` da banda
    anterior, que é a contagem real dessa gente no snapshot base); acertou
    quando a direção real bate com a prevista, não precisa acertar o número
    exato. Banda 0 (novato) não tem "banda anterior" nessa coorte, porque não
    é sobrevivência (é média dos dois novatos mais recentes): fica de fora."""
    t = todos.sort_values("band").reset_index(drop=True)
    antes = t["baseline_pred"].shift(1)
    sinal = lambda serie: (serie > 1e-9).astype(int) - (serie < -1e-9).astype(int)  # noqa: E731
    t["acertou"] = sinal(t["cohort_pred"] - antes) == sinal(t["actual"] - antes)
    return t.loc[t["band"] > 0, ["band", "actual", "cohort_pred", "acertou"]]


def _projecao_piramide_linha(pl: SimpleNamespace, linha: pd.DataFrame, ano_base: int) -> None:
    """Mesmo desenho de `plots.figure_projection_overlay` (IEICE16 Fig.8):
    pirâmide real em barra, linha vermelha tracejada sobreposta com o
    previsto (coorte). Aqui pra 1 linguagem/1 ano-âncora só, fora do conjunto
    fixo de projetos auditados que a Fig.8 original usa."""
    real = pl.plots._projection_frame(linha, "actual")
    pred = pl.plots._projection_frame(linha, "cohort_pred")
    fig, ax = plt.subplots(figsize=(7.0, 5.5))
    lim, _ = pl.plots.draw_pyramid(ax, real.astype({"band": int}))
    y = pred["band"].to_numpy()
    esq = -pred["non_coding"].to_numpy()
    dirr = (pred["moved"] + pred["coding"]).to_numpy()
    for serie in (esq, dirr):
        ax.plot(
            serie,
            y,
            color="#B03A2E",
            linewidth=1.4,
            linestyle="--",
            marker="o",
            markersize=3,
            zorder=6,
        )
    pico = float(max(abs(esq).max(initial=0.0), dirr.max(initial=0.0)))
    if pico > lim:
        ax.set_xlim(-pico * 1.08, pico * 1.08)
    ax.set_xlabel("contribuidores")
    ax.set_ylabel(pl.plots.rotulo_da_idade())
    ax.set_title(f"{LING.atual.nome}: backtest {ano_base} (barra=real, linha vermelha=previsto)")
    _salva_fig(fig, f"backtest/projecao_{LING.atual.slug}_backtest_{ano_base}_piramide.png")


def _anos_backtest_possiveis(eventos: pd.DataFrame) -> range:
    """Todo `ano_base` em que dá pra tentar o backtest: do primeiro ano com
    evento até o último em que o alvo (Q1 do ano seguinte) ainda cai dentro
    da coleta. Ano cedo demais (poucos contribuidores ativos na base) não
    quebra: `gera_projecao_backtest` já reporta e pula, é só custo de
    computar à toa. Ano tarde demais projetaria pra um trimestre que a
    coleta não tem, o que geraria número fantasma; esse sim fica de fora."""
    ano_min = int(eventos["timestamp"].min().year)
    ultimo = eventos["timestamp"].max()
    ano_max = (
        ultimo.year - 1
        if ultimo.month < 3 or (ultimo.month == 3 and ultimo.day < 31)
        else ultimo.year
    )
    return range(ano_min, ano_max + 1)


def _backtest_resumo(eventos: pd.DataFrame, ano_base: int) -> dict | None:
    """ABRE mediana (categoria "all") e taxa de acerto de direção pro
    `ano_base`, sem gravar PNG/CSV: usado por `gera_backtest_todos_anos` pra
    varrer muitos anos rápido. `None` quando o ano não passa no critério de
    elegibilidade (`gera_projecao_backtest` já cobre o caso avulso com
    aviso; aqui é silencioso, o resumo final já mostra quem ficou de fora)."""
    alvo_forcado = pd.Timestamp(f"{ano_base + 1}-03-31")
    pl = roda_pipeline(eventos, band_months=3, fim_forcado=alvo_forcado)
    try:
        df = pl.projection.compute()
        linha = df[df["scope_id"] == pl.sid]
        if linha.empty:
            return None
        todos = linha[linha["category"] == "all"].sort_values("band").reset_index(drop=True)
        direcao = _avalia_direcao(todos)
        return {
            "ano_base": ano_base,
            "abre_cohort": todos["abre_cohort"].median(),
            "abre_baseline": todos["abre_baseline"].median(),
            "taxa_acerto_direcao": direcao["acertou"].mean() if len(direcao) else float("nan"),
            "n_bandas": len(todos),
        }
    finally:
        shutil.rmtree(pl.scratch, ignore_errors=True)


def gera_backtest_todos_anos(eventos: pd.DataFrame) -> None:
    """Backtest pra TODO ano possível (`_anos_backtest_possiveis`), não só
    2016/2019/2024: um resumo (`_backtest_resumo`) por ano, não o conjunto
    pesado de figuras de `gera_projecao_backtest` (seriam dezenas de PNG por
    linguagem). Pra ver o backtest completo de um ano específico, usa
    `--backtest-anos`."""
    anos = _anos_backtest_possiveis(eventos)
    print(f"{LING.atual.nome}: testando {anos.start}-{anos.stop - 1}", file=sys.stderr)
    linhas = [r for ano in anos if (r := _backtest_resumo(eventos, ano)) is not None]
    fora = anos.stop - anos.start - len(linhas)
    if fora:
        print(
            f"aviso: {fora} anos fora do critério de elegibilidade, sem linha no resumo",
            file=sys.stderr,
        )
    resumo = pd.DataFrame(linhas)

    saida_csv = _caminho_csv(f"backtest/projecao_{LING.atual.slug}_backtest_todos_anos.csv")
    resumo.to_csv(saida_csv, index=False)
    print(f"salvo: {saida_csv}")

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(max(8.0, 0.5 * len(resumo)), 8), sharex=True)
    ax1.plot(resumo["ano_base"], resumo["abre_cohort"], marker="o", color="#3b6fa0", label="coorte")
    ax1.plot(
        resumo["ano_base"], resumo["abre_baseline"], marker="o", color="#aaaaaa", label="baseline"
    )
    ax1.set_ylabel("mediana do ABRE\n(menor = melhor)")
    ax1.set_title(f"{LING.atual.nome}: backtest da projeção, todo ano-âncora possível")
    ax1.legend()

    ax2.plot(resumo["ano_base"], resumo["taxa_acerto_direcao"], marker="o", color="black")
    ax2.axhline(0.5, color="#888888", lw=0.8, linestyle="--")
    ax2.set_ylim(0, 1)
    ax2.set_xlabel("ano-âncora")
    ax2.set_ylabel("taxa de acerto\nde direção")
    _salva_fig(fig, f"backtest/projecao_{LING.atual.slug}_backtest_todos_anos.png")


def gera_projecao_backtest(eventos: pd.DataFrame, ano_base: int) -> None:
    """Mesma projeção coorte-componente de `gera_projecao`, mas ancorada em Q4
    de `ano_base` (T-1 = Q3, T = Q4, alvo = Q1 do ano seguinte) em vez do
    último trimestre da coleta: `roda_pipeline`/`escreve_config` já sabem
    forçar esse corte (`fim_forcado`, criado pra `gera_piramide_comparativa`).
    Mostra se a taxa de sobrevivência calculada num ponto passado da história
    ainda acerta o real, não só no trimestre mais recente.

    Gera: a barra tripla trimestral (como antes), a mesma barra agrupada em
    janelas de 2 e 3 anos, o jogo de acerto de direção (`_avalia_direcao`) e
    a pirâmide com linha vermelha (`_projecao_piramide_linha`)."""
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

        saida_csv = _caminho_csv(f"backtest/projecao_{LING.atual.slug}_backtest_{ano_base}.csv")
        linha.to_csv(saida_csv, index=False)
        print(f"salvo: {saida_csv}")

        todos = linha[linha["category"] == "all"].sort_values("band").reset_index(drop=True)
        _desenha_barra_projecao(
            todos,
            todos["band"].astype(int),
            f"{LING.atual.nome}: backtest {ano_base} -> {alvo_real}",
            f"backtest/projecao_{LING.atual.slug}_backtest_{ano_base}.png",
        )
        for anos in (2, 3):
            agrupado = _agrupa_por_anos(todos, anos)
            _desenha_barra_projecao(
                agrupado,
                agrupado["rotulo"],
                f"{LING.atual.nome}: backtest {ano_base} -> {alvo_real} "
                f"(agrupado em janelas de {anos} anos)",
                f"backtest/projecao_{LING.atual.slug}_backtest_{ano_base}_agrupado{anos}anos.png",
            )

        direcao = _avalia_direcao(todos)
        taxa = direcao["acertou"].mean() if len(direcao) else float("nan")
        print(
            f"acerto de direção (coorte, subiu/desceu igual ao real): "
            f"{int(direcao['acertou'].sum())}/{len(direcao)} ({taxa:.0%})"
        )
        saida_direcao = _caminho_csv(
            f"backtest/projecao_{LING.atual.slug}_backtest_{ano_base}_direcao.csv"
        )
        direcao.to_csv(saida_direcao, index=False)
        print(f"salvo: {saida_direcao}")

        _projecao_piramide_linha(pl, linha, ano_base)
    finally:
        shutil.rmtree(pl.scratch, ignore_errors=True)


def _rotulo(pl: SimpleNamespace) -> str:
    return pl.plots.labels().get(pl.sid, str(pl.sid))


def gera_stickiness_ano(pl: SimpleNamespace) -> None:
    pairs, coverage = pl.attractiveness.activity(scopes=[pl.sid])
    df = pl.attractiveness.annual(pairs, coverage_end=coverage)
    df = df[df["scope_id"] == pl.sid].dropna(subset=["stickiness"]).sort_values("year")
    fig, ax = plt.subplots(figsize=(max(7.0, 0.45 * len(df)), 4))
    ax.bar(df["year"].astype(int).astype(str), df["stickiness"], color="black")
    ax.tick_params(axis="x", rotation=90)  # senão o rótulo de ano cola um no outro
    ax.set_ylabel("stickiness")
    ax.set_title(f"{_rotulo(pl)}: stickiness por ano (magnetismo omitido, degenerado em 1,0)")
    _salva_fig(fig, f"stickiness-ano/stickiness_por_ano_{LING.atual.slug}_metodologia.png")


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
    # Eixos travados na escala simétrica: sem isso, autoescala corta pro
    # quadrante onde os dados caem, e um quadrante inteiro sem trimestre
    # nenhum desaparece do desenho em vez de aparecer vazio.
    ax.set_xlim(-1.05, 1.05)
    ax.set_ylim(-1.05, 1.05)
    ax.set_xlabel("CCR")
    ax.set_ylabel("NCR")
    ax.set_title(f"{_rotulo(pl)}: CCR x NCR por trimestre")
    _salva_fig(fig, f"ccr-ncr/tipos_ccr_ncr_{LING.atual.slug}_metodologia.png")

    # CSV ao lado do PNG: sem isso, comparar CCR/NCR entre linguagens por ano
    # (`gera_geral_ccr_ncr_por_ano`) precisaria rodar o pipeline de novo pra
    # cada linguagem só pra reler o que essa figura já calculou.
    caminho_csv = _caminho_csv(f"ccr-ncr/tipos_ccr_ncr_{LING.atual.slug}_metodologia.csv")
    df[["snapshot", "ccr", "ncr", "type"]].to_csv(caminho_csv, index=False)
    print(f"salvo: {caminho_csv}")


def gera_fantasmas(ev: pd.DataFrame) -> None:  # noqa: ARG001
    """Lê o CSV que `carrega_eventos` já gravou e desenha a barra. Não recalcula."""
    caminho_csv = _caminho_csv("fantasmas/fantasmas_por_ano.csv")
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
    _salva_fig(fig, "fantasmas/fantasmas_por_ano.png")


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

    caminho_csv = _caminho_csv("abandono/abandono_por_ano.csv")
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
    _salva_fig(fig, "abandono/abandono_por_ano.png")

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
    _salva_fig(fig3, "abandono/abandono_por_ano_mesma_escala.png")

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
    _salva_fig(fig2, "abandono/abandono_acumulado_por_ano.png")


def gera_voltas_por_ano(ev: pd.DataFrame) -> None:
    """Quantas VOLTAS aconteceram em cada ano: pessoa que ficou mais de 3 meses
    sem contribuir e depois contribuiu de novo. Cada retorno é um evento próprio
    (uma pessoa pode voltar várias vezes ao longo da história), contado no ano em
    que o retorno aconteceu, não confundir com `gera_abandono_por_ano`, que é
    uma foto fixa de hoje. Usa `classify.profile`, o mesmo cálculo de span que o
    motor usa pra decidir quem está vivo."""
    from pyramid import classify

    gap_days = 3 * DAYS_PER_MONTH
    perfil = classify.profile(ev, TIPOS_CODING, gap_days)
    voltas = perfil[perfil["span_idx"] > 0]  # span 0 é a primeira aparição, não é volta
    por_ano = pd.Series(voltas["span_start"]).dt.year.value_counts().sort_index()

    caminho_csv = _caminho_csv("voltas/voltas_por_ano.csv")
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
    _salva_fig(fig, "voltas/voltas_por_ano.png")


def gera_contribuintes_por_ano(ev: pd.DataFrame) -> None:
    """Contribuinte distinto por ano: quem teve pelo menos 1 evento (código ou
    discussão) naquele ano, contando só uma vez mesmo com vários eventos. A
    mesma pessoa aparece em vários anos se contribuiu em vários anos; isso não
    é sobre banda de idade nem sobre abandono, é presença simples ano a ano."""
    anos_evento = ev["timestamp"].dt.year
    por_ano = ev.assign(ano=anos_evento).groupby("ano")["contributor_id"].nunique()
    total = ev["contributor_id"].nunique()

    # Novo por ano = quantidade de gente cujo PRIMEIRO evento na vida foi
    # naquele ano; soma corrida disso é o total distinto de sempre até ali,
    # sempre crescente. `por_ano` não serve pra isso: conta quem apareceu
    # NAQUELE ano (veterano que voltou inclusive), somar daria gente repetida.
    primeiro_ano = ev.groupby("contributor_id")["timestamp"].min().dt.year
    novos_por_ano = primeiro_ano.value_counts().reindex(por_ano.index, fill_value=0).sort_index()
    acumulado = novos_por_ano.cumsum()

    caminho_csv = _caminho_csv("contribuintes/contribuintes_por_ano.csv")
    tabela = pd.DataFrame(
        {
            "contribuintes_distintos": por_ano,
            "contribuintes_novos": novos_por_ano,
            "contribuintes_acumulado": acumulado,
        }
    )
    tabela.to_csv(caminho_csv, index_label="ano")
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
    ax.set_ylabel("ativos NAQUELE ano (pode cair de um ano pro outro)")
    ax.set_title(f"{LING.atual.nome}: contribuintes ATIVOS por ano (total de sempre: {total})")
    _salva_fig(fig, "contribuintes/contribuintes_por_ano.png")

    fig2, ax2 = plt.subplots(figsize=(max(7.0, 0.45 * len(por_ano)), 4))
    ax2.plot(anos, acumulado.to_numpy(), color="#a6431f", linewidth=1.6, marker="o", markersize=5)
    ax2.tick_params(axis="x", rotation=90)
    ax2.set_xlabel("ano")
    ax2.set_ylabel("total histórico ATÉ aquele ano (nunca cai)")
    ax2.set_title(f"{LING.atual.nome}: contribuintes ACUMULADOS até cada ano (total: {total})")
    _salva_fig(fig2, "contribuintes/contribuintes_acumulado_por_ano.png")

    _registra_total_geral(total)


def gera_resumo_contribuintes(ev: pd.DataFrame) -> None:
    """Por contribuinte: quantos eventos de coding, quantos de discussão
    (`TIPOS_CODING` e o resto), o total geral, primeira e última data, e o
    intervalo entre as duas. Não desenha nada sozinho: é o material que
    `gera_geral_histograma_eventos` combina das 4 linguagens sem recarregar
    o CSV bruto de novo. Serve também pra achar caso suspeito na mão: gente
    com poucos eventos espalhados por um intervalo grande de tempo (ver
    `span_dias`) é candidato a olhar de perto antes de decidir um corte
    mínimo de eventos."""
    coding = ev["event_type"].isin(TIPOS_CODING)
    n_coding = ev[coding].groupby("contributor_id").size()
    n_discussao = ev[~coding].groupby("contributor_id").size()
    primeiro = ev.groupby("contributor_id")["timestamp"].min()
    ultimo = ev.groupby("contributor_id")["timestamp"].max()
    resumo = pd.DataFrame(
        {"n_coding": n_coding, "n_discussao": n_discussao, "primeiro": primeiro, "ultimo": ultimo}
    )
    resumo[["n_coding", "n_discussao"]] = resumo[["n_coding", "n_discussao"]].fillna(0).astype(int)
    resumo["n_total"] = resumo["n_coding"] + resumo["n_discussao"]
    resumo["span_dias"] = (resumo["ultimo"] - resumo["primeiro"]).dt.days

    caminho = _caminho_csv("resumo-contribuintes/contribuintes_resumo.csv")
    resumo.rename_axis("contributor_id").reset_index().to_csv(caminho, index=False)
    print(f"salvo: {caminho} ({len(resumo)} contribuintes)", file=sys.stderr)


NOVATO_JANELA_MESES = 3

# Também usada por `gera_geral_backtest_evolucao`, mais abaixo no arquivo.
ANOS_BACKTEST_PADRAO = (2016, 2019, 2024)


def _novatos_por_ano(
    eventos: pd.DataFrame, anos_base: tuple[int, ...] | None = None
) -> pd.DataFrame:
    """Quantos contribuintes tinham menos de `NOVATO_JANELA_MESES` de idade
    (desde o primeiro evento) em cada ano, e a fração disso sobre o total de
    sempre até aquele ponto. Corte de data: 31/dez do ano, ou o último dado
    real quando o ano ainda não fechou (`min` evita marcar o ano corrente
    como "sem dado" por não ter chegado no fim).

    `anos_base=None` (default) cobre todo ano entre a primeira contribuição
    e o fim da coleta, um ponto por ano, sem pular nenhum: antes esta função
    só rodava nos 3 anos do backtest (`ANOS_BACKTEST_PADRAO`), o que deixava
    o gráfico com 6 anos vazios no meio, sem mostrar tendência nenhuma."""
    primeiro = eventos.groupby("contributor_id")["timestamp"].min()
    fim_dataset = eventos["timestamp"].max()
    if anos_base is None:
        anos_base = tuple(range(primeiro.min().year, fim_dataset.year + 1))
    linhas = []
    for ano in anos_base:
        snapshot = min(pd.Timestamp(f"{ano}-12-31"), fim_dataset)
        if snapshot < primeiro.min():
            continue
        existentes = primeiro[primeiro <= snapshot]
        janela = pd.Timedelta(days=NOVATO_JANELA_MESES * DAYS_PER_MONTH)
        novatos = existentes[(snapshot - existentes) < janela]
        linhas.append(
            {
                "ano_base": ano,
                "snapshot": snapshot,
                "novatos": len(novatos),
                "total_ate_ali": len(existentes),
                "fracao": len(novatos) / len(existentes) if len(existentes) else float("nan"),
            }
        )
    return pd.DataFrame(linhas)


def gera_novatos_por_ano(ev: pd.DataFrame) -> None:
    """Desenha e salva `_novatos_por_ano`, um ponto por ano (ver docstring de
    `_novatos_por_ano`: antes rodava só nos 3 anos do backtest, deixando o
    gráfico com anos vazios no meio)."""
    tabela = _novatos_por_ano(ev)
    caminho_csv = _caminho_csv("novatos-por-ano/novatos_por_ano.csv")
    tabela.to_csv(caminho_csv, index=False)
    print(f"salvo: {caminho_csv}", file=sys.stderr)

    fig, ax = plt.subplots(figsize=(7, 4.5))
    rotulos = tabela["ano_base"].astype(str)
    ax.bar(rotulos, tabela["novatos"], color="black")
    for i, (n, frac) in enumerate(zip(tabela["novatos"], tabela["fracao"], strict=True)):
        ax.annotate(
            f"{frac:.1%}",
            (i, n),
            ha="center",
            va="bottom",
            fontsize=9,
            xytext=(0, 3),
            textcoords="offset points",
        )
    ax.set_xlabel("ano")
    ax.set_ylabel(f"contribuintes com <{NOVATO_JANELA_MESES} meses de idade")
    ax.set_title(f"{LING.atual.nome}: novatos por ano (rótulo = % do total até ali)")
    _salva_fig(fig, "novatos-por-ano/novatos_por_ano.png")


REGISTRO_GERAL = PASTA_GERAL / "contribuintes_por_linguagem.json"


def _registra_total_geral(total: int) -> None:
    """Guarda o total de contribuintes desta linguagem num arquivo compartilhado,
    lido depois por `gera_geral_contribuintes`. Lê e regrava (não é concorrente:
    cada linguagem roda a própria vez), então uma linguagem não apaga o registro
    das outras."""
    registro = {}
    if REGISTRO_GERAL.exists():
        registro = json.loads(REGISTRO_GERAL.read_text(encoding="utf-8"))
    registro[LING.atual.slug] = total
    PASTA_GERAL.mkdir(parents=True, exist_ok=True)
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
    caminho = _caminho_geral("geral_contribuintes_por_linguagem.png")
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


def gera_ccr_ncr_projeto(eventos: pd.DataFrame) -> None:
    """CCR x NCR por PROJETO de verdade (repositório elegível), não pela
    linguagem inteira: um ponto por repositório, no snapshot de
    classificação. Substituiu `geral_ccr_ncr_por_linguagem.png` (nuvem de
    trimestres da linguagem inteira, confundia com nuvem de projetos e não
    respondia nada de verdade). `unit="project"` faz `extract` NÃO somar os
    repositórios da linguagem antes de classificar (ver `roda_pipeline`);
    cada `scope_id` que sobra depois é um repositório real, exatamente a
    unidade que IEICE16 Fig.5 usa.

    Bem mais pesado que as outras figuras: classifica cada repositório
    elegível, não um escopo só por linguagem. Por isso `roda_pipeline_paralelo`
    (fatia os repositórios entre processos, ver a função pra detalhe e
    o porquê) em vez do `roda_pipeline` sequencial padrão."""
    pl = roda_pipeline_paralelo(eventos, band_months=3, n_workers=ESTADO_PARALELO.n_workers)
    try:
        t = pd.Timestamp(pl.snapshots.classification_snapshot())
        todos = pl.metrics.load_all()
        cut = todos[todos["snapshot"] == t].dropna(subset=["ccr", "ncr"]).copy()
        print(f"{len(cut)} projetos classificados em {t.date()}", file=sys.stderr)

        caminho_csv = _caminho_csv(f"ccr-ncr-projeto/ccr_ncr_projeto_{LING.atual.slug}.csv")
        cut[["scope_id", "ccr", "ncr", "type"]].to_csv(caminho_csv, index=False)
        print(f"salvo: {caminho_csv}")

        fig, ax = plt.subplots(figsize=(7.5, 6.5))
        ax.axhline(0, color="#888888", lw=0.7)
        ax.axvline(0, color="#888888", lw=0.7)
        ax.scatter(cut["ccr"], cut["ncr"], color="black", s=10, alpha=0.5)
        ax.set_xlim(-1.05, 1.05)
        ax.set_ylim(-1.05, 1.05)
        ax.set_xlabel("CCR")
        ax.set_ylabel("NCR")
        ax.set_title(f"{LING.atual.nome}: CCR x NCR por projeto, {t.date()} ({len(cut)} projetos)")
        _salva_fig(fig, f"ccr-ncr-projeto/ccr_ncr_projeto_{LING.atual.slug}.png")
    finally:
        shutil.rmtree(pl.scratch, ignore_errors=True)


def gera_geral_ccr_ncr_por_projeto() -> None:
    """CCR x NCR por projeto, as 4 linguagens no mesmo plano. Lê o CSV que
    `--figuras ccr-ncr-projeto` já deixou em cada subpasta; não reclassifica
    nada (isso já custou ~2-3 min por linguagem lá)."""
    partes = []
    faltando = []
    for slug, linguagem in LINGUAGENS.items():
        caminho_csv = TMP_BASE / slug / "csv" / "ccr-ncr-projeto" / f"ccr_ncr_projeto_{slug}.csv"
        if not caminho_csv.exists():
            faltando.append(slug)
            continue
        df = pd.read_csv(caminho_csv)
        df["linguagem"] = linguagem.nome
        partes.append(df)
    if faltando:
        print(
            f"aviso: sem CSV de CCR/NCR por projeto ainda para {', '.join(sorted(faltando))}",
            file=sys.stderr,
        )
    if not partes:
        raise SystemExit(
            "nenhum ccr_ncr_projeto_*.csv encontrado. Rode `--figuras "
            "ccr-ncr-projeto` (ou `all`) em cada linguagem antes."
        )
    pontos = pd.concat(partes, ignore_index=True)

    fig, ax = plt.subplots(figsize=(8.5, 7.5))
    ax.axhline(0, color="#888888", lw=0.7)
    ax.axvline(0, color="#888888", lw=0.7)
    for slug, grupo in pontos.groupby("linguagem"):
        cor = CORES_LINGUAGEM[next(k for k, v in LINGUAGENS.items() if v.nome == slug)]
        ax.scatter(grupo["ccr"], grupo["ncr"], color=cor, s=10, alpha=0.5, label=slug)
    ax.set_xlim(*ESCALA_METRICA)
    ax.set_ylim(*ESCALA_METRICA)
    ax.set_xlabel("CCR")
    ax.set_ylabel("NCR")
    ax.set_title(f"CCR x NCR por projeto, {len(LINGUAGENS)} linguagens")
    ax.legend(loc="best", fontsize=9, markerscale=2)
    caminho = _caminho_geral("geral_ccr_ncr_por_projeto.png")
    fig.savefig(caminho, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"salvo: {caminho}")


def gera_geral_contribuintes_evolucao() -> None:
    """Contribuintes distintos por ano, as 4 linguagens no mesmo plano, uma
    linha por linguagem. Lê `contribuintes_por_ano.csv`, que `--figuras
    contribuintes` (ou `all`) já deixa em cada subpasta; não recalcula nada.

    `drawstyle="steps-mid"`, não reta ligando os pontos: ano é inteiro, não
    tem "2011,5 contribuinte", e uma reta entre dois anos sugere um valor
    fracionário no meio que não existe. Degrau (constante dentro do ano,
    salto na virada) representa o dado discreto sem inventar interpolação."""
    fig, ax = plt.subplots(figsize=(10, 6))
    faltando = []
    for slug, linguagem in LINGUAGENS.items():
        caminho_csv = TMP_BASE / slug / "csv" / "contribuintes" / "contribuintes_por_ano.csv"
        if not caminho_csv.exists():
            faltando.append(slug)
            continue
        df = pd.read_csv(caminho_csv)
        ax.plot(
            df["ano"],
            df["contribuintes_distintos"],
            drawstyle="steps-mid",
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
    from matplotlib.ticker import MaxNLocator

    # Ano é inteiro: sem isso o matplotlib põe tick fracionário (2010.5)
    # quando o intervalo é largo, pedido explícito do usuário pra não ter.
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_xlabel("ano")
    ax.set_ylabel("ativos NAQUELE ano (pode cair de um ano pro outro)")
    ax.set_title(f"Contribuintes ATIVOS por ano, {len(LINGUAGENS)} linguagens")
    ax.legend(loc="best")
    caminho = _caminho_geral("geral_contribuintes_evolucao_por_ano.png")
    fig.savefig(caminho, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"salvo: {caminho}")


def gera_geral_contribuintes_acumulado_evolucao() -> None:
    """Contribuintes distintos ACUMULADOS por ano (total de sempre até ali,
    sempre crescente), as 4 linguagens no mesmo plano. Lê a mesma
    `contribuintes_por_ano.csv` de `gera_geral_contribuintes_evolucao`, só a
    coluna muda; não recalcula nada."""
    fig, ax = plt.subplots(figsize=(10, 6))
    faltando = []
    for slug, linguagem in LINGUAGENS.items():
        caminho_csv = TMP_BASE / slug / "csv" / "contribuintes" / "contribuintes_por_ano.csv"
        if not caminho_csv.exists():
            faltando.append(slug)
            continue
        df = pd.read_csv(caminho_csv)
        ax.plot(
            df["ano"],
            df["contribuintes_acumulado"],
            drawstyle="steps-mid",
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
    from matplotlib.ticker import MaxNLocator

    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_xlabel("ano")
    ax.set_ylabel("total histórico ATÉ aquele ano (nunca cai)")
    ax.set_title(f"Contribuintes ACUMULADOS até cada ano, {len(LINGUAGENS)} linguagens")
    ax.legend(loc="best")
    caminho = _caminho_geral("geral_contribuintes_acumulado_evolucao_por_ano.png")
    fig.savefig(caminho, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"salvo: {caminho}")


def gera_geral_abandono_por_ano() -> None:
    """Quantas pessoas abandonaram por ano da última contribuição, as 4
    linguagens no mesmo plano. Lê `abandono_por_ano.csv` de cada linguagem
    (`--figuras abandono` ou `all`); não recalcula nada."""
    fig, ax = plt.subplots(figsize=(10, 6))
    faltando = []
    for slug, linguagem in LINGUAGENS.items():
        caminho_csv = TMP_BASE / slug / "csv" / "abandono" / "abandono_por_ano.csv"
        if not caminho_csv.exists():
            faltando.append(slug)
            continue
        df = pd.read_csv(caminho_csv)
        ax.plot(
            df["ano_da_ultima_contribuicao"],
            df["pessoas_que_abandonaram"],
            drawstyle="steps-mid",
            marker="o",
            markersize=4,
            color=CORES_LINGUAGEM[slug],
            label=linguagem.nome,
        )
    if faltando:
        print(
            f"aviso: sem abandono_por_ano.csv ainda para {', '.join(sorted(faltando))}",
            file=sys.stderr,
        )
    from matplotlib.ticker import MaxNLocator

    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_xlabel("ano da última contribuição")
    ax.set_ylabel("pessoas naquele ano")
    ax.set_title(f"Abandono por ano da última contribuição, {len(LINGUAGENS)} linguagens")
    ax.legend(loc="best")
    caminho = _caminho_geral("geral_abandono_por_ano.png")
    fig.savefig(caminho, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"salvo: {caminho}")


def gera_geral_abandono_acumulado() -> None:
    """Abandono ACUMULADO por ano (nunca cai), as 4 linguagens no mesmo
    plano. Lê a mesma `abandono_por_ano.csv` de `gera_geral_abandono_por_ano`,
    soma corrida calculada na hora; não recalcula nada da coleta."""
    fig, ax = plt.subplots(figsize=(10, 6))
    faltando = []
    for slug, linguagem in LINGUAGENS.items():
        caminho_csv = TMP_BASE / slug / "csv" / "abandono" / "abandono_por_ano.csv"
        if not caminho_csv.exists():
            faltando.append(slug)
            continue
        df = pd.read_csv(caminho_csv).sort_values("ano_da_ultima_contribuicao")
        ax.plot(
            df["ano_da_ultima_contribuicao"],
            df["pessoas_que_abandonaram"].cumsum(),
            drawstyle="steps-mid",
            marker="o",
            markersize=4,
            color=CORES_LINGUAGEM[slug],
            label=linguagem.nome,
        )
    if faltando:
        print(
            f"aviso: sem abandono_por_ano.csv ainda para {', '.join(sorted(faltando))}",
            file=sys.stderr,
        )
    from matplotlib.ticker import MaxNLocator

    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_xlabel("ano da última contribuição")
    ax.set_ylabel("total histórico ATÉ aquele ano (nunca cai)")
    ax.set_title(f"Abandono ACUMULADO até cada ano, {len(LINGUAGENS)} linguagens")
    ax.legend(loc="best")
    caminho = _caminho_geral("geral_abandono_acumulado_por_ano.png")
    fig.savefig(caminho, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"salvo: {caminho}")


def gera_geral_idade_morte_por_ano() -> None:
    """`_idade_morte_por_ano` das 4 linguagens no mesmo plano: idade média
    na última contribuição, ano a ano. Média, não mediana: a maioria de quem
    "morre" fez uma única contribuição na vida inteira (idade = 0), essa
    maioria domina a mediana até ela pular de uma vez quando deixa de ser
    maioria (ver `gera_piramide_idade_morte_evolucao`). Lê
    `idade_morte_por_ano.csv` de cada linguagem (`--figuras
    idade-morte-tempo` ou `all`); não recalcula nada."""
    fig, ax = plt.subplots(figsize=(10, 6))
    faltando = []
    for slug, linguagem in LINGUAGENS.items():
        caminho_csv = TMP_BASE / slug / "csv" / "idade-morte" / "idade_morte_por_ano.csv"
        if not caminho_csv.exists():
            faltando.append(slug)
            continue
        df = pd.read_csv(caminho_csv)
        ax.plot(
            df["ano_morte"],
            df["idade_media"],
            marker="o",
            markersize=4,
            color=CORES_LINGUAGEM[slug],
            label=linguagem.nome,
        )
    if faltando:
        print(
            f"aviso: sem idade_morte_por_ano.csv ainda para {', '.join(sorted(faltando))}",
            file=sys.stderr,
        )
    from matplotlib.ticker import MaxNLocator

    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_xlabel("ano da última contribuição")
    ax.set_ylabel("idade média na última contribuição (anos)")
    ax.set_title(f"Idade na última contribuição, por ano (média), {len(LINGUAGENS)} linguagens")
    ax.legend(loc="best")
    caminho = _caminho_geral("geral_idade_morte_por_ano.png")
    fig.savefig(caminho, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"salvo: {caminho}")


def gera_geral_novatos_por_ano() -> None:
    """`_novatos_por_ano` das 4 linguagens, uma linha por linguagem, um
    ponto por ano (ver docstring de `_novatos_por_ano`: antes só cobria os 3
    anos do backtest, com linha desligada porque os pontos eram esparsos
    demais pra conectar; ano a ano isso deixou de ser verdade). Lê
    `novatos_por_ano.csv` de cada linguagem (`--figuras novatos-por-ano` ou
    `all`); não recalcula nada."""
    partes = []
    faltando = []
    for slug in LINGUAGENS:
        caminho = TMP_BASE / slug / "csv" / "novatos-por-ano" / "novatos_por_ano.csv"
        if not caminho.exists():
            faltando.append(slug)
            continue
        df = pd.read_csv(caminho)
        df["linguagem"] = slug
        partes.append(df)
    if faltando:
        print(
            f"aviso: sem novatos_por_ano.csv ainda para {', '.join(sorted(faltando))}",
            file=sys.stderr,
        )
    if not partes:
        raise SystemExit(
            "nenhum novatos_por_ano.csv encontrado. Rode `--figuras "
            "novatos-por-ano` (ou `all`) em cada linguagem antes."
        )
    todos = pd.concat(partes, ignore_index=True)

    fig, ax = plt.subplots(figsize=(8, 5.5))
    for slug, linguagem in LINGUAGENS.items():
        grupo = todos[todos["linguagem"] == slug].sort_values("ano_base")
        if grupo.empty:
            continue
        ax.plot(
            grupo["ano_base"],
            grupo["fracao"],
            marker="o",
            markersize=4,
            color=CORES_LINGUAGEM[slug],
            label=linguagem.nome,
        )
    from matplotlib.ticker import MaxNLocator

    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set_ylim(0, None)
    ax.set_xlabel("ano")
    ax.set_ylabel(f"% com <{NOVATO_JANELA_MESES} meses de idade, do total até ali")
    ax.set_title(f"Novatos por ano, {len(LINGUAGENS)} linguagens")
    ax.legend(fontsize=9)
    caminho = _caminho_geral("geral_novatos_por_ano.png")
    fig.savefig(caminho, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"salvo: {caminho}")


def gera_geral_backtest_evolucao(anos_base: tuple[int, ...] = ANOS_BACKTEST_PADRAO) -> None:
    """Como o erro do backtest (mediana do ABRE, categoria "all") evolui de
    ano-âncora pra ano-âncora, as 4 linguagens num grid 2x2. Lê os CSVs que
    `--backtest-anos` já deixou em cada subpasta; não recalcula nada.

    Sem linha ligando os pontos: os anos-âncora são esparsos e não
    consecutivos (2016, 2019, 2024, por padrão), e uma reta entre eles
    fingiria saber o que aconteceu nos anos vazios no meio, que não foram
    testados. Só o ponto, no ano exato que tem número de verdade."""
    fig, eixos = _grade_para_linguagens()
    for eixo, (slug, linguagem) in zip(eixos, LINGUAGENS.items(), strict=True):
        anos_disponiveis, cohort_por_ano, baseline_por_ano = [], [], []
        for ano in anos_base:
            caminho = TMP_BASE / slug / "csv" / "backtest" / f"projecao_{slug}_backtest_{ano}.csv"
            if not caminho.exists():
                continue
            todos = pd.read_csv(caminho)
            todos = todos[todos["category"] == "all"]
            anos_disponiveis.append(ano)
            cohort_por_ano.append(todos["abre_cohort"].median())
            baseline_por_ano.append(todos["abre_baseline"].median())
        if not anos_disponiveis:
            eixo.axis("off")
            eixo.set_title(f"{linguagem.nome} (sem backtest ainda)")
            continue
        eixo.scatter(anos_disponiveis, cohort_por_ano, color="#3b6fa0", s=50, label="coorte")
        eixo.scatter(anos_disponiveis, baseline_por_ano, color="#aaaaaa", s=50, label="baseline")
        eixo.set_xticks(anos_disponiveis)
        eixo.set_xlabel("ano-âncora")
        eixo.set_ylabel("mediana do ABRE (menor = melhor)")
        eixo.set_title(linguagem.nome)
        eixo.legend(fontsize=8)
    fig.suptitle(
        f"Backtest da projeção: erro por ano-âncora, {len(LINGUAGENS)} linguagens", fontsize=13
    )
    fig.tight_layout()
    caminho = _caminho_geral("geral_backtest_evolucao_por_linguagem.png")
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


def _rotulo_banda(banda_meses: int) -> str:
    """Banda em meses, em texto legível: "3 meses" (a banda de quarter, não
    fecha ano redondo) ou "N anos" pra qualquer banda múltipla de 12. Existe
    porque o título da figura mostrava "banda 36m", que exige fazer a conta
    de cabeça pra saber que são 3 anos."""
    if banda_meses % 12 == 0:
        anos = banda_meses // 12
        return "1 ano" if anos == 1 else f"{anos} anos"
    return f"{banda_meses} meses"


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

    # 3 e 12: mesma convenção de `gera_piramide_multi` (quarter da metodologia,
    # e a versão "sem quarter" em ano). 24, 36 e 60: agrupamento de 2, 3 e 5
    # anos, pedido explícito do usuário pra essa comparação entre linguagens.
    # Nome do arquivo só com a banda em meses: "comquarter"/"semquarter"/
    # "agrupado2anos" era jargão interno que não ajudava a achar o arquivo.
    for banda_meses in (3, 12, 24, 36, 60):
        fig, eixos = _grade_para_linguagens()
        for eixo, slug in zip(eixos, LINGUAGENS, strict=True):
            LING.aplica(slug)
            CFG.aplica(2)
            pl = roda_pipeline(
                eventos_por_lingua[slug], band_months=banda_meses, fim_forcado=fim_comum
            )
            try:
                # Desenha na mão (`pyramid_frame` + `draw_pyramid`) em vez de
                # embutir o PNG de `pl.plots.figure_pyramid`: aquele PNG já
                # vem gravado com a legenda do artigo ("non-coding"), sem
                # Figure pra reabrir e trocar pelo rótulo deste script
                # (`ROTULO_LEGENDA`: "discussion"). Mesma solução de
                # `gera_piramide_multi`.
                t = pd.Timestamp(pl.snapshots.classification_snapshot())
                frame = pl.plots.pyramid_frame(pl.snapshots.load(pl.sid), t)
                pl.plots.draw_pyramid(eixo, frame)
                eixo.set_title(LING.atual.nome)
            finally:
                shutil.rmtree(pl.scratch, ignore_errors=True)

        _legenda_discussion(fig, pl.plots)
        fig.suptitle(
            f"Pirâmide por linguagem, mesmo corte de data ({fim_comum.date()}), "
            f"banda de {_rotulo_banda(banda_meses)}",
            fontsize=14,
        )
        fig.tight_layout(rect=(0, 0.04, 1, 0.96))
        caminho = _caminho_geral(f"piramides_4_linguagens_banda{banda_meses}m.png")
        fig.savefig(caminho, dpi=200, bbox_inches="tight")
        plt.close(fig)
        print(f"salvo: {caminho}")

    gera_comparacao_metricas_linguagens(eventos_por_lingua)
    if ESTADO_METRICAS_5ANOS.ativo:
        gera_comparacao_metricas_linguagens(eventos_por_lingua, janela_anos=5)
    gera_piramide_anos_distintos_comparativa(eventos_por_lingua, fim_comum)
    gera_grade_anos_distintos(eventos_por_lingua)
    gera_geral_idade_morte(eventos_por_lingua)


def gera_piramide_anos_distintos_comparativa(
    eventos_por_lingua: dict[str, pd.DataFrame], fim_comum: pd.Timestamp
) -> None:
    """`gera_piramide_anos_distintos` das 4 linguagens lado a lado, no mesmo
    corte de data que as outras pirâmides de `gera_piramide_comparativa`
    (recebido pronto, não recalcula). `roda_pipeline` entra só pelo efeito
    colateral de deixar `plots`/`config` prontos pro desenho (band_months=12,
    igual à versão avulsa); os dados de cada painel vêm de
    `_frame_por_anos_contribuicao`, não do pipeline."""
    from matplotlib.patches import Patch

    pl = roda_pipeline(next(iter(eventos_por_lingua.values())), band_months=12)
    try:
        fig, eixos = _grade_para_linguagens()
        for eixo, (slug, linguagem) in zip(eixos, LINGUAGENS.items(), strict=True):
            tabela = _frame_por_anos_contribuicao(eventos_por_lingua[slug], fim_comum)
            pl.plots.draw_pyramid(eixo, tabela.astype({"band": int}))
            eixo.set_xlabel("contribuidores")
            eixo.set_ylabel("anos-calendário distintos")
            eixo.set_title(linguagem.nome)

        handles = [
            Patch(
                facecolor=pl.plots.FILL[c],
                hatch=pl.plots.HATCH[c],
                edgecolor="#4D4D4D",
                label=ROTULO_LEGENDA[c],
            )
            for c in ("non_coding", "moved", "coding")
        ]
        fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False)
        fig.suptitle(
            f"Pirâmide por linguagem, anos-calendário distintos, mesmo corte ({fim_comum.date()})",
            fontsize=14,
        )
        fig.tight_layout(rect=(0, 0.04, 1, 0.96))
        caminho = _caminho_geral("piramides_4_linguagens_anos_distintos.png")
        fig.savefig(caminho, dpi=200, bbox_inches="tight")
        plt.close(fig)
        print(f"salvo: {caminho}")
    finally:
        shutil.rmtree(pl.scratch, ignore_errors=True)


ANOS_GRADE_ANOS_DISTINTOS = (2016, 2019, 2022, 2026)


def gera_grade_anos_distintos(
    eventos_por_lingua: dict[str, pd.DataFrame], anos: tuple[int, ...] = ANOS_GRADE_ANOS_DISTINTOS
) -> None:
    """Evolução da pirâmide de anos-calendário distintos ao longo do tempo,
    as 4 linguagens juntas: uma linha por linguagem, uma coluna por
    ano-snapshot (31/dez de cada `anos`). Cada célula é a mesma tabela de
    `_frame_por_anos_contribuicao`, só que cortada num ano do passado em vez
    do último dado disponível. Ano anterior à primeira coleta daquela
    linguagem fica em branco (não existe dado antes disso, não é zero).

    Largura (X, contribuidores) compartilhada dentro de cada LINHA
    (linguagem): sem isso, auto-escala faria uma pirâmide de 2016 do tamanho
    de uma de 2026 mesmo crescendo 10x, e o crescimento real viraria ilusão
    de ótica. Altura (Y, teto de idade) NÃO é compartilhada: cada coluna usa
    o próprio teto, o maior número de anos distintos que existia NAQUELE
    ano. Uma pirâmide de 2016 não pode ter teto de 19 anos só porque a de
    2026 tem: em 2016 esse teto fisicamente não existia ainda.

    Título e rótulo não se repetem célula a célula: o ano vira cabeçalho de
    coluna (só na linha de cima) e a linguagem vira rótulo de linha (só na
    coluna da esquerda), em vez de "Linguagem, Ano" escrito nas 16 células."""
    from matplotlib.patches import Patch

    pl = roda_pipeline(next(iter(eventos_por_lingua.values())), band_months=12)
    try:
        fig, eixos = plt.subplots(
            len(LINGUAGENS), len(anos), figsize=(4.2 * len(anos), 4.2 * len(LINGUAGENS))
        )
        for linha, (slug, linguagem) in enumerate(LINGUAGENS.items()):
            eventos = eventos_por_lingua[slug]
            tabelas = {}
            for ano in anos:
                # min(31/dez, último dado real): o último `ano` pedido costuma
                # ser o ano corrente, sem 31/dez ainda; sem o min(), a coluna
                # inteira caía em "sem dado" mesmo tendo dado parcial do ano.
                limite = pd.Timestamp(f"{ano}-12-31")
                snapshot = min(limite, eventos["timestamp"].max())
                tabelas[ano] = (
                    _frame_por_anos_contribuicao(eventos, snapshot)
                    if snapshot >= eventos["timestamp"].min()
                    else None
                )
            validas = [t for t in tabelas.values() if t is not None and len(t)]
            somas = [t[["non_coding", "moved", "coding"]].sum(axis=1).max() for t in validas]
            xmax = max(somas, default=1.0)

            for coluna, ano in enumerate(anos):
                eixo = eixos[linha][coluna]
                tabela = tabelas[ano]
                if linha == 0:
                    eixo.set_title(str(ano), fontsize=11)
                if tabela is None or tabela.empty:
                    eixo.axis("off")
                    eixo.text(
                        0.5, 0.5, "sem dado", ha="center", va="center", transform=eixo.transAxes
                    )
                    continue
                # ymax=None (default): cada coluna usa o próprio teto, não o da linha.
                pl.plots.draw_pyramid(eixo, tabela.astype({"band": int}), xmax=xmax)
                if linha == len(LINGUAGENS) - 1:
                    eixo.set_xlabel("contribuidores", fontsize=8)
                if coluna == 0:
                    eixo.set_ylabel(f"{linguagem.nome}\nanos distintos", fontsize=9)

        handles = [
            Patch(
                facecolor=pl.plots.FILL[c],
                hatch=pl.plots.HATCH[c],
                edgecolor="#4D4D4D",
                label=ROTULO_LEGENDA[c],
            )
            for c in ("non_coding", "moved", "coding")
        ]
        fig.legend(handles=handles, loc="lower center", ncol=3, frameon=False)
        fig.suptitle(
            f"Pirâmide (anos-calendário distintos) ao longo do tempo, {len(LINGUAGENS)} linguagens",
            fontsize=14,
        )
        fig.tight_layout(rect=(0, 0.03, 1, 0.96))
        caminho = _caminho_geral("piramides_4_linguagens_anos_distintos_ao_longo_do_tempo.png")
        fig.savefig(caminho, dpi=200, bbox_inches="tight")
        plt.close(fig)
        print(f"salvo: {caminho}")
    finally:
        shutil.rmtree(pl.scratch, ignore_errors=True)


def gera_geral_ccr_ncr_por_ano() -> None:
    """CCR x NCR por linguagem, um painel por ano (`ANOS_GRADE_ANOS_DISTINTOS`,
    os mesmos anos da grade de anos-distintos). Lê o CSV que `--figuras ccr-ncr`
    já deixou em cada subpasta: mesmo CCR/NCR por trimestre da linguagem
    inteira (`unit="language"`), aqui recortado num ano por vez em vez de
    todo trimestre. Não é por projeto; pra isso, ver
    `gera_geral_ccr_ncr_por_projeto` (lê o CSV de `--figuras ccr-ncr-projeto`).

    Um painel por ano, não um ponto rotulado "Linguagem - Ano" só no plano
    inteiro: com as 4 linguagens e os 4 anos no mesmo desenho, os rótulos se
    empilham e ficam ilegíveis (pontos de anos e linguagens diferentes caem
    perto o bastante no plano CCR/NCR pra colidir o texto). Cada painel só
    tem 4 pontos, um por linguagem, com espaço de sobra pro rótulo.

    Eixos travados em `ESCALA_METRICA`, simétrica em torno de zero, em TODOS
    os painéis: os quatro quadrantes de CCR/NCR aparecem sempre, mesmo que um
    deles fique vazio para as 4 linguagens naquele ano."""
    linhas = []
    faltando = []
    for slug, linguagem in LINGUAGENS.items():
        caminho_csv = TMP_BASE / slug / "csv" / "ccr-ncr" / f"tipos_ccr_ncr_{slug}_metodologia.csv"
        if not caminho_csv.exists():
            faltando.append(slug)
            continue
        df = pd.read_csv(caminho_csv, parse_dates=["snapshot"]).sort_values("snapshot")
        for ano in ANOS_GRADE_ANOS_DISTINTOS:
            limite = min(pd.Timestamp(f"{ano}-12-31"), df["snapshot"].max())
            candidatos = df[df["snapshot"] <= limite]
            if candidatos.empty:
                continue  # ano anterior à primeira coleta desta linguagem
            escolhido = candidatos.iloc[-1]
            linhas.append(
                {
                    "linguagem": linguagem.nome,
                    "slug": slug,
                    "ano": ano,
                    "ccr": escolhido["ccr"],
                    "ncr": escolhido["ncr"],
                }
            )
    if faltando:
        print(
            f"aviso: sem CSV de CCR/NCR ainda para {', '.join(sorted(faltando))}", file=sys.stderr
        )
    if not linhas:
        raise SystemExit(
            "nenhum tipos_ccr_ncr_*_metodologia.csv encontrado. Rode `--figuras "
            "ccr-ncr` (ou `all`) em cada linguagem antes."
        )
    pontos = pd.DataFrame(linhas)

    fig, eixos = plt.subplots(
        1, len(ANOS_GRADE_ANOS_DISTINTOS), figsize=(4.4 * len(ANOS_GRADE_ANOS_DISTINTOS), 4.6)
    )
    for ax, ano in zip(eixos, ANOS_GRADE_ANOS_DISTINTOS, strict=True):
        ax.axhline(0, color="#888888", lw=0.7)
        ax.axvline(0, color="#888888", lw=0.7)
        do_ano = pontos[pontos["ano"] == ano]
        for _, row in do_ano.iterrows():
            ax.scatter(row["ccr"], row["ncr"], color=CORES_LINGUAGEM[row["slug"]], s=70, zorder=3)
            ax.annotate(
                row["linguagem"],
                (row["ccr"], row["ncr"]),
                fontsize=8,
                xytext=(6, 5),
                textcoords="offset points",
            )
        ax.set_xlim(*ESCALA_METRICA)
        ax.set_ylim(*ESCALA_METRICA)
        ax.set_xlabel("CCR")
        ax.set_title(str(ano))
    eixos[0].set_ylabel("NCR")
    handles = [
        plt.Line2D(
            [0], [0], marker="o", linestyle="none", color=CORES_LINGUAGEM[slug], markersize=8
        )
        for slug in LINGUAGENS
    ]
    fig.legend(
        handles,
        [linguagem.nome for linguagem in LINGUAGENS.values()],
        loc="lower center",
        ncol=4,
        frameon=False,
    )
    fig.suptitle("CCR x NCR por linguagem, nos anos da grade de anos-distintos")
    fig.tight_layout(rect=(0, 0.06, 1, 0.95))
    caminho = _caminho_geral("geral_ccr_ncr_por_ano.png")
    fig.savefig(caminho, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"salvo: {caminho}")


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
    escala: tuple[float, float] = ESCALA_METRICA,
) -> None:
    """Um ponto rotulado por linguagem, eixos em `escala` (default:
    `ESCALA_METRICA`, comum aos dois painéis de
    `gera_comparacao_metricas_linguagens`). CCR/NCR vivem em [-1, 1] e usam a
    escala comum de propósito, pra comparar os 3 plots de relance; magnetismo
    e stickiness vivem só em [0, 1] e usam `escala` própria, senão os 4
    pontos ficam espremidos num quarto do desenho com o resto vazio."""
    if linhas_zero:
        ax.axhline(0, color="#888888", lw=0.7)
        ax.axvline(0, color="#888888", lw=0.7)
    for nome, sid in ids_por_nome.items():
        if sid not in x_por_sid.index:
            continue
        x, y = x_por_sid[sid], y_por_sid[sid]
        ax.scatter(x, y, color=cores[nome], s=70, zorder=3)
        ax.annotate(nome, (x, y), fontsize=9, xytext=(6, 6), textcoords="offset points")
    ax.set_xlim(*escala)
    ax.set_ylim(*escala)
    ax.set_xlabel(rotulo_x)
    ax.set_ylabel(rotulo_y)
    ax.set_title(titulo)


def gera_comparacao_metricas_linguagens(
    eventos_por_lingua: dict[str, pd.DataFrame], janela_anos: int | None = None
) -> None:
    """CCR/NCR e magnetismo/stickiness com a LINGUAGEM como unidade, um ponto
    por linguagem, dentro do MESMO pipeline (as 4 juntas numa fonte só, com
    `eventos["idioma"]` dizendo a linguagem de origem por linha; ver
    `monta_fonte`). Rodar cada linguagem sozinha deixa magnetismo travado em
    1,0: `unit: language` com 1 linguagem só não tem contra quem competir por
    atenção, e por isso não existe uma figura de magnetismo por linguagem
    isolada (não daria nenhuma análise pra tirar). Junto, magnetismo compara
    as 4 de verdade.

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
            escala=(-0.05, 1.05),
        )
        fig.suptitle(
            f"As {len(eventos_por_lingua)} linguagens como unidade de análise, competindo entre si",
            fontsize=13,
        )
        caminho = _caminho_geral(f"geral_ccr_ncr_magnetismo_stickiness_por_linguagem{sufixo}.png")
        fig.savefig(caminho, dpi=200, bbox_inches="tight")
        plt.close(fig)
        print(f"salvo: {caminho}")
    finally:
        shutil.rmtree(pl.scratch, ignore_errors=True)


GERADORES = {
    "piramide": lambda _pl, ev: gera_piramide_multi(ev),
    "piramide-veteranos": lambda _pl, ev: gera_piramide_veteranos(ev),
    "piramide-anos-distintos": lambda _pl, ev: gera_piramide_anos_distintos(ev),
    "idade-morte": lambda _pl, ev: gera_piramide_idade_morte(ev),
    "idade-morte-recente": lambda _pl, ev: gera_piramide_idade_morte_recente(ev),
    "idade-morte-tempo": lambda _pl, ev: gera_piramide_idade_morte_evolucao(ev),
    "linha-tempo": lambda pl, _ev: gera_linha_tempo(pl),
    "linha-tempo-4": lambda _pl, ev: (
        gera_linha_tempo_4_teto_proprio(ev)
        if ESTADO_LINHA_TEMPO_4.teto_proprio
        else gera_linha_tempo_4(ev)
    ),
    "projecao": lambda pl, _ev: gera_projecao(pl),
    "stickiness-ano": lambda pl, _ev: gera_stickiness_ano(pl),
    "ccr-ncr": lambda pl, _ev: gera_ccr_ncr(pl),
    "ccr-ncr-projeto": lambda _pl, ev: gera_ccr_ncr_projeto(ev),
    "fantasmas": lambda _pl, ev: gera_fantasmas(ev),
    "abandono": lambda _pl, ev: gera_abandono_por_ano(ev),
    "voltas": lambda _pl, ev: gera_voltas_por_ano(ev),
    "contribuintes": lambda _pl, ev: gera_contribuintes_por_ano(ev),
    "resumo-contribuintes": lambda _pl, ev: gera_resumo_contribuintes(ev),
    "novatos-por-ano": lambda _pl, ev: gera_novatos_por_ano(ev),
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
    "resumo-contribuintes",
    "novatos-por-ano",
    "piramide",
    "piramide-veteranos",
    "piramide-anos-distintos",
    "idade-morte",
    "idade-morte-recente",
    "idade-morte-tempo",
    "ccr-ncr-projeto",
}

# Fora de `--figuras all`: reclassifica cada repositório elegível do zero
# (`unit="project"`), minutos por linguagem em vez de segundos (Zig, a menor
# das 4, ~2-3 min sozinha). Só roda com `--figuras ccr-ncr-projeto` explícito.
FORA_DE_ALL = {"ccr-ncr-projeto"}


def _executa_geral() -> None:
    gera_geral_contribuintes()
    gera_geral_contribuintes_evolucao()
    gera_geral_contribuintes_acumulado_evolucao()
    gera_geral_abandono_por_ano()
    gera_geral_abandono_acumulado()
    gera_geral_idade_morte_por_ano()
    gera_geral_ccr_ncr_por_ano()
    gera_geral_novatos_por_ano()


def _fmt_milhar(n: int) -> str:
    return f"{n:,}".replace(",", ".")


# (rótulo da linha, chave em ESTATISTICAS_CARGA, nota de rodapé se a soma
# não é uma contagem exata). Uma linha por etapa do filtro de
# `carrega_eventos`, na mesma ordem em que os cortes acontecem no código.
_LINHAS_CARACTERIZACAO = [
    ("Eventos coletados", "eventos_api_bruto", None),
    ("Eventos inválidos (autor nulo ou linguagem não confere)", "_eventos_api_invalidos", None),
    ("Eventos válidos", "eventos_api_desta_linguagem", None),
    ("Commits coletados", "eventos_git_bruto", None),
    ("Commits inválidos (autor nulo ou linguagem não confere)", "_commits_invalidos", None),
    ("Commits válidos", "eventos_git_desta_linguagem", None),
]


def gera_caracterizacao_dados() -> None:
    """Coletado vs inválido vs válido, pra eventos de API e pra commits git,
    numa tabela com uma coluna por linguagem e uma coluna Total à direita
    (pedido explícito do usuário, cortando o resto da caracterização
    anterior por ser irrelevante pro que ele queria ver). "Inválido" é
    autor nulo ou linguagem que não confere, o mesmo filtro que já
    acontecia dentro de `_carrega_api`/`_carrega_git`; esta função só lê o
    que já foi contado, não refiltra nada.

    Lê `ESTATISTICAS_CARGA`, que `carrega_eventos` já povoa como efeito
    colateral da carga normal; não chama `carrega_eventos` de novo aqui
    (por isso só faz sentido chamar esta função depois de alguma outra que
    já carregou as linguagens correntes, como `gera_piramide_comparativa`).
    A coluna Total é soma simples entre linguagens."""
    slugs = list(LINGUAGENS)
    valores: dict[str, dict[str, int]] = {}
    for slug in slugs:
        s = dict(ESTATISTICAS_CARGA.get(slug, {}))
        s["_eventos_api_invalidos"] = s.get("eventos_api_bruto", 0) - s.get(
            "eventos_api_desta_linguagem", 0
        )
        s["_commits_invalidos"] = s.get("eventos_git_bruto", 0) - s.get(
            "eventos_git_desta_linguagem", 0
        )
        valores[slug] = s

    cabecalho = ["Etapa"] + [LINGUAGENS[s].nome for s in slugs] + ["Total"]
    linhas = [
        "# Caracterização dos dados",
        "",
        "Quantidade de dado em cada etapa do filtro de `carrega_eventos`, "
        "por linguagem, com o total à direita. Cada linha é uma etapa do "
        "filtro; o número mostra quantos elementos restam depois dela. A "
        "explicação de cada corte está no código, junto da função que faz "
        "o corte (`scripts/figuras_linguagem_bruta.py`).",
        "",
        "| " + " | ".join(cabecalho) + " |",
        "|" + "---|" * len(cabecalho),
    ]
    notas: list[str] = []
    for rotulo, chave, nota in _LINHAS_CARACTERIZACAO:
        celulas = [valores[slug].get(chave, 0) for slug in slugs]
        total = _fmt_milhar(sum(celulas))
        if nota:
            total += f" {nota}"
            if nota not in notas:
                notas.append(nota)
        linha = [rotulo] + [_fmt_milhar(v) for v in celulas] + [total]
        linhas.append("| " + " | ".join(linha) + " |")
    if "*" in notas:
        linhas.append("")
        linhas.append(
            "*Soma simples entre linguagens: quem contribui em mais de uma "
            "linguagem é contado uma vez em cada uma. Não há deduplicação "
            "de `contributor_id` entre linguagens neste total."
        )

    caminho = _caminho_geral("caracterizacao_dados.md")
    caminho.write_text("\n".join(linhas), encoding="utf-8")
    print(f"salvo: {caminho}", file=sys.stderr)


def _executa_geral_exclude_python() -> None:
    """Todo o conteúdo de `--geral` mais `--comparativa`, sem Python: mesmas
    funções, cada uma já lê `LINGUAGENS` (ver `_rodada_sem_linguagem`), só
    que escrevendo em `geral-exclude-python/` em vez de `geral/`. Pedido
    explícito do usuário: a coleta de Python está sendo refeita do zero (a
    caminho de ~400 mil repositórios) enquanto o resto do script roda, e
    misturar o Python velho, pequeno, com as outras 3 linguagens de sempre
    não compara nada de verdade até a coleta nova terminar."""
    with _rodada_sem_linguagem("python"):
        _executa_geral()
        gera_geral_ccr_ncr_por_projeto()
        gera_piramide_comparativa()
        gera_caracterizacao_dados()


def _executa_comparativa_metricas() -> None:
    eventos_por_lingua = _carrega_todas_linguagens()
    gera_comparacao_metricas_linguagens(eventos_por_lingua)
    if ESTADO_METRICAS_5ANOS.ativo:
        gera_comparacao_metricas_linguagens(eventos_por_lingua, janela_anos=5)


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
        "--teto-proprio-timeline",
        action="store_true",
        help="em `linha-tempo-4`, cada painel usa o próprio teto de idade "
        "daquele ano em vez do teto comum (o motor auditado usa teto comum "
        "de propósito, igual ESEM14 Fig.3, pra mostrar a pirâmide crescendo "
        "de altura; sem essa flag o comportamento não muda).",
    )
    ap.add_argument(
        "--metricas-5anos",
        action="store_true",
        help="em --comparativa/--comparativa-metricas, desenha também a "
        "versão de CCR/NCR/magnetismo/stickiness com mediana dos últimos 5 "
        "anos (suaviza oscilação de curto prazo). Default não desenha; só "
        "com essa flag.",
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
        "--geral-exclude-python",
        action="store_true",
        help="tudo que --geral e --comparativa juntos desenham, sem Python "
        "(a coleta de Python está sendo refeita do zero, ~400 mil "
        "repositórios; misturar com a coleta velha não compara nada de "
        "verdade). Vai em geral-exclude-python/, não em geral/. Sai depois. "
        "Ignora --linguagem/--rodada/--figuras.",
    )
    ap.add_argument(
        "--processos",
        type=int,
        default=None,
        help="quantos processos usar em --figuras ccr-ncr-projeto (unit=project "
        "paralelo). Default: os.cpu_count().",
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
    ap.add_argument(
        "--backtest-todos-anos",
        action="store_true",
        help="backtest pra todo ano-âncora possível (não só os de "
        "--backtest-anos): resumo leve (ABRE + taxa de acerto de direção) "
        "por ano, não o conjunto completo de figuras por ano. Roda pra "
        "--linguagem escolhida, além do --figuras pedido (não substitui).",
    )
    ap.add_argument(
        "--backtest-geral",
        action="store_true",
        help="desenha como o erro do backtest evolui por ano-âncora, as 4 "
        "linguagens num grid 2x2 (lê os CSVs que --backtest-anos já deixou "
        "em cada subpasta), e sai. Ignora --linguagem/--rodada/--figuras.",
    )
    args = ap.parse_args()
    ESTADO_LINHA_TEMPO_4.teto_proprio = args.teto_proprio_timeline
    ESTADO_METRICAS_5ANOS.ativo = args.metricas_5anos
    ESTADO_PARALELO.n_workers = args.processos
    modos_sem_linguagem = {
        "backtest_geral": gera_geral_backtest_evolucao,
        "geral": _executa_geral,
        "geral_exclude_python": _executa_geral_exclude_python,
        "comparativa": gera_piramide_comparativa,
        "comparativa_metricas": _executa_comparativa_metricas,
    }
    for flag, roda in modos_sem_linguagem.items():
        if getattr(args, flag):
            roda()
            return
    LING.aplica(args.linguagem)

    rodada = args.rodada
    if not LING.atual.tem_rodada_1:
        if rodada == 1:
            raise SystemExit(f"--rodada 1 não existe para {LING.atual.nome}; use --rodada 2.")
        rodada = 2
    CFG.aplica(rodada)  # reaplica com a linguagem/rodada escolhidas; env var ainda vence dentro

    pedidas = (
        [f for f in GERADORES if f not in FORA_DE_ALL]
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
    if args.backtest_todos_anos:
        gera_backtest_todos_anos(eventos)


if __name__ == "__main__":
    main()
