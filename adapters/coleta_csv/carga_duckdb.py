"""Carga em SQL (DuckDB) dos CSV da coleta do GitHub: eventos de uma linguagem, compactados.

Lê os CSV pipe-delimitados da coleta (18 colunas: `eventos_api.csv`, `eventos_git.csv` e os
arquivos que juntam os dois) em paralelo e derrama em disco quando uma etapa não cabe na
memória (a detecção de commit duplicado é a maior). Só o resultado compactado sobe para o
pandas. Serve a coletas de centenas de GB.

Aplica as regras de `scripts/figuras_linguagem_bruta.py` (`carrega_eventos`), em SQL:

  1. API: sem autor sai; `language` vazia usa a linguagem principal do repositório.
  2. Git: sem autor sai; só entra commit que toca arquivo da linguagem; commit idêntico
     (autor, data, arquivos) em mais de um repositório fica no mais antigo.
  3. Evento da API antes do primeiro commit da linguagem no repositório sai.
  4. Só repositório elegível.
  5. Conta apagada (`ghost`) e bot (`[bot]`) saem. Datas ilegíveis, futuras ou anteriores a
     2008 saem.
  6. Ação de `issue_event` listada em `Pedido.acoes_ignoradas` sai. Em `mentioned` e
     `subscribed` o login é o de quem foi marcado ou inscrito, que não fez nada. Padrão: nenhuma.
  7. Com `Pedido.fundir_identidades`, o nome de commit vira o login da mesma pessoa de duas
     formas. Exata: e-mail `[id+]login@users.noreply.github.com`. Heurística (a de
     `candidatos_mesma_pessoa` em `scripts/figuras_linguagem_bruta.py`): quem só commita e quem
     só abre issue/PR, com 5 ou mais eventos cada, 5 ou mais repositórios em comum e Jaccard
     dos repositórios de 0,5 ou mais. Padrão: desligada.
  8. Com `Pedido.autores`, o commit vira o login da conta que o GitHub liga ao e-mail do autor
     (arquivo `autores_commits.csv`, linhas com status `ok`). E-mail noreply também vira login.
     E-mail sem conta segue com o nome do autor. Não usa a heurística da regra 7.

  9. Com `Pedido.repos_fundidos`, cada grupo de repositórios duplicados vira um repositório só,
     com a identidade do criado antes. Todos os eventos dos membros ficam. O commit repetido
     conta uma vez pelo SHA e o evento de API repetido, pela chave (tipo, autor, data e número).
     Para a ocasião, o grupo é um repositório. Se o mantido for inelegível, a identidade passa
     para o membro elegível criado antes. Exige `commits_pelo_sha`.

Diferenças em relação ao motor `pandas` de `scripts/carga_pandas.py`, sem efeito nas métricas:

  - `contributor_id` vem de `hash(autor)` do DuckDB, não do sha1 do script. O id só precisa
    ser estável e distinto por autor.
  - o resultado já sai compactado (`vitalidade.compacta`), com o tipo de cada linha à parte
    nos empates de instante.

Valores que o pandas lê como vazios (`NA`, `null`, `None`, `NaN`...) também são vazios aqui,
para os dois motores descartarem os mesmos autores.

Este módulo não conhece o `scripts/`: recebe um `Pedido` e devolve um `Resultado`.
"""

from __future__ import annotations

import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

import duckdb
import pandas as pd

# Os valores que `pd.read_csv` trata como vazio por padrão.
NULOS = [
    "",
    "#N/A",
    "#N/A N/A",
    "#NA",
    "-1.#IND",
    "-1.#QNAN",
    "-NaN",
    "-nan",
    "1.#IND",
    "1.#QNAN",
    "<NA>",
    "N/A",
    "NA",
    "NULL",
    "NaN",
    "None",
    "n/a",
    "nan",
    "null",
]
# Cada núcleo reserva um buffer proporcional a isto. 256 MB por linha estourou 24 GB com 16 núcleos.
# Um commit com milhares de arquivos cabe em bem menos; linha maior é descartada.
LINHA_MAXIMA = 32 * 1024 * 1024

# Contas que não são pessoas: logins de migração de rastreador e logins de bot sem `[bot]`.
# `sem_contas_de_sistema` tira os eventos delas. UUID é o placeholder de quem não tem conta real.
CONTAS_EXCLUIDAS = ("vicuna", "coqbot")
LOGIN_UUID = "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
# Palavra inteira entre `-`, `_` ou `.`, como em twisted-trac. Sem isso `trac` pegaria tracy.
LOGIN_DE_MIGRACAO = "(^|[-_.])(trac|bugzilla|mantis|jira|import[a-z]*|migrat[a-z]*)($|[-_.0-9])"
# Login que a regra de migração pegaria (`jira` seguido de dígitos) mas é de pessoa.
CONTAS_QUE_SAO_PESSOAS = ("jira44",)
CODIGOS_DE_CODIGO = ("commits", "pull_requests")
# A conversa de um evento: o número da issue ou do PR. Comentário só traz a URL.
CONVERSA = "coalesce(number, regexp_extract(url, '/(?:issues|pull)/([0-9]+)', 1))"


@dataclass
class Pedido:
    """O que a carga precisa saber, sem depender de quem pede."""

    eventos: list[tuple[Path, str]]  # (arquivo, papel: api, git ou misto)
    repos: pd.DataFrame  # codigo, repo_id, principal, criado (UTC sem fuso), elegivel
    linguagem: str  # nome em `language` e `mainLanguage`, como "Python"
    extensoes: tuple[str, ...]  # extensões de arquivo-fonte, como (".py", ".pyi")
    tipos: dict[str, str]  # event_type bruto -> nome do tipo no formato canônico
    trabalho: Path  # pasta em disco para o banco e o derrame
    memoria: str = "30GB"
    threads: int | None = None
    contar_brutas: bool = True  # relê o arquivo inteiro só para contar linhas: minutos por 100 GB
    agora: pd.Timestamp = field(default_factory=pd.Timestamp.now)
    origem: Path | None = None  # pasta para `_grava_origem`; None não grava
    acoes_ignoradas: tuple[str, ...] = ()  # ações de issue_event (coluna message) que saem
    fundir_identidades: bool = False  # nome de commit -> login, regra 7 do topo
    fusao_repos_min: int = 5
    fusao_jaccard_min: float = 0.5
    autores: Path | None = None  # autores_commits.csv: e-mail de commit -> login, regra 8 do topo
    completos: bool = False  # devolve um evento por linha, com repositório, sem compactar
    repos_excluidos: tuple[str, ...] = ()  # repo_id que saem: duplicados de outro repositório
    # repo_id do duplicado -> repo_id do repositório que fica. O grupo vira um repositório só, com
    # a identidade do mantido, e o evento repetido entre os membros conta uma vez (regra 9 do topo).
    repos_fundidos: dict[str, str] = field(default_factory=dict)
    commits_pelo_sha: bool = (
        False  # um commit por SHA, no repositório criado antes (empate: repo_id)
    )
    sem_contas_de_sistema: bool = False  # tira `CONTAS_EXCLUIDAS`, logins UUID e de migração
    contas_extras: tuple[str, ...] = ()  # mais contas que saem, em minúsculas (rodadas de teste)
    # repo_id cujos contribuidores a carga conta à parte, mesmo inelegíveis (só estatística)
    repos_para_contar: tuple[str, ...] = ()
    # repo_id cujos eventos saem da carga (sensibilidade). Não pode estar num grupo de duplicados.
    repos_sem_eventos: tuple[str, ...] = ()


@dataclass
class Resultado:
    """O que a carga devolve: os eventos, as contagens de cada filtro e as contas apagadas."""

    eventos: pd.DataFrame  # contributor_id, event_type, timestamp, já compactados (ou completos)
    estatisticas: dict[str, int]  # quanto sobrou em cada filtro
    fantasmas: pd.DataFrame  # coluna created_at das contas apagadas, que saem da pirâmide


def _aspas(texto: str | Path) -> str:
    return "'" + str(texto).replace("'", "''") + "'"


def _leitura(caminho: Path, papel: str) -> str:
    """SELECT que lê um CSV e diz, por linha, se segue a regra do git (`eh_commit`)."""
    eh_commit = {"api": "false", "git": "true", "misto": "event_type = 'commit'"}[papel]
    nulos = "[" + ", ".join(_aspas(n) for n in NULOS) + "]"
    return f"""
        SELECT repo_id, event_type, author, author_login, author_email, created_at, files, language,
               number, sha, url, message, title,
               {eh_commit} AS eh_commit
        FROM read_csv({_aspas(caminho)}, delim='|', quote='"', escape='"', header=true,
                      all_varchar=true, ignore_errors=true, strict_mode=false,
                      nullstr={nulos}, max_line_size={LINHA_MAXIMA})
    """


def _case_tipo(tipos: dict[str, str], nomes_tipo: list[str]) -> str:
    ramos = [f"WHEN {_aspas(b)} THEN {nomes_tipo.index(n)}" for b, n in tipos.items()]
    return "CASE event_type " + " ".join(ramos) + " ELSE -1 END"


def _ts(coluna: str) -> str:
    """Mesma conversão do pandas: UTC sem fuso, ilegível vira NULL."""
    return f"CAST(try_cast({coluna} AS TIMESTAMPTZ) AS TIMESTAMP)"


def _pessoa(coluna: str) -> str:
    return f"CAST(hash({coluna}) >> 1 AS BIGINT)"


def _marca(coluna: str) -> str:
    return f"CASE WHEN {coluna} = 'ghost' THEN 1 WHEN {coluna} LIKE '%[bot]' THEN 2 ELSE 0 END"


def _ocasiao(repo: str = "b.repo_id") -> str:
    """Em qual ocasião o evento aconteceu, como um número: o mesmo para a mesma ocasião.

    Ocasião é uma conversa (issue ou PR, que dividem a numeração no repositório), um commit
    comentado ou um dia de commits no repositório. Comentário não traz o número da conversa, só a
    URL (`.../issues/12#issuecomment-...`).
    """
    dia = f"CAST(CAST({_ts('created_at')} AS DATE) AS VARCHAR)"
    return (
        f"hash({repo}, CASE WHEN eh_commit THEN 'dia ' || " + dia + " "
        "WHEN event_type = 'commit_comment' THEN 'commit ' || sha "
        "ELSE 'conversa ' || " + CONVERSA + " END)"
    )


def _um(con: duckdb.DuckDBPyConnection, sql: str) -> int:
    linha = con.execute(sql).fetchone()
    return int(linha[0] or 0) if linha else 0


def carrega(pedido: Pedido) -> Resultado:
    """Eventos compactados [contributor_id, event_type, timestamp] da linguagem do pedido."""
    shutil.rmtree(pedido.trabalho, ignore_errors=True)
    pedido.trabalho.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(pedido.trabalho / "carga.duckdb"))
    try:
        con.execute(f"SET memory_limit = {_aspas(pedido.memoria)}")
        con.execute(f"SET temp_directory = {_aspas(pedido.trabalho / 'derrame')}")
        con.execute("SET preserve_insertion_order = false")
        con.execute("SET TimeZone = 'UTC'")
        if pedido.threads:
            con.execute(f"SET threads = {int(pedido.threads)}")
        return _carrega(con, pedido)
    finally:
        con.close()
        shutil.rmtree(pedido.trabalho, ignore_errors=True)


def _quem_commitou(
    con: duckdb.DuckDBPyConnection, pedido: Pedido, stats: dict[str, int]
) -> tuple[str, str]:
    """Quem é a pessoa de um commit (regras 7 e 8 do topo) e o JOIN que essa escolha pede."""
    noreply = (
        "nullif(regexp_extract(author_email, "
        "'^(?:[0-9]+\\+)?([^@]+)@users\\.noreply\\.github\\.com$', 1), '')"
    )
    quem_commitou = "author"
    if pedido.fundir_identidades:
        quem_commitou = f"coalesce({noreply}, author)"
    junta_autores = ""
    if pedido.autores:
        con.execute(f"""
            CREATE TABLE autores AS
            SELECT author_email AS email_autor, any_value(login) AS login_autor
            FROM read_csv({_aspas(pedido.autores)}, delim='|', quote='"', escape='"',
                          header=true, all_varchar=true, ignore_errors=true, strict_mode=false)
            WHERE status = 'ok' AND login IS NOT NULL
            GROUP BY author_email
        """)
        stats["autores_com_login"] = _um(con, "SELECT count(*) FROM autores")
        # Sem `eh_commit AND` no ON: o duckdb trocaria o hash join por laço aninhado (12h+ em
        # python). O CASE WHEN eh_commit em volta de quem_commitou já restringe aos commits.
        junta_autores = "LEFT JOIN autores au ON au.email_autor = lower(trim(b.author_email))"
        quem_commitou = f"coalesce({noreply}, au.login_autor, author)"
    return quem_commitou, junta_autores


def _contas_e_chave(pedido: Pedido, quem_commitou: str) -> tuple[str, str]:
    """O filtro das contas que não são pessoas e a chave que identifica um commit copiado."""
    conta = f"lower(coalesce(CASE WHEN eh_commit THEN {quem_commitou} ELSE author_login END, ''))"
    sistema = ""
    if pedido.sem_contas_de_sistema:
        lista = ", ".join(_aspas(c) for c in CONTAS_EXCLUIDAS)
        pessoas = ", ".join(_aspas(c) for c in CONTAS_QUE_SAO_PESSOAS)
        sistema = (
            f"AND {conta} NOT IN ({lista}) "
            f"AND NOT regexp_matches({conta}, {_aspas(LOGIN_UUID)}) "
            f"AND ({conta} IN ({pessoas}) "
            f"OR NOT regexp_matches({conta}, {_aspas(LOGIN_DE_MIGRACAO)}))"
        )
    if pedido.contas_extras:
        extras = ", ".join(_aspas(c.lower()) for c in pedido.contas_extras)
        bruta = "lower(coalesce(CASE WHEN eh_commit THEN author ELSE author_login END, ''))"
        sistema += f" AND {conta} NOT IN ({extras}) AND {bruta} NOT IN ({extras})"
    # Um commit copiado entre repositórios (fork, espelho) é o mesmo SHA. Sem SHA, o conteúdo.
    chave_do_commit = "hash(author, created_at, files)"
    if pedido.commits_pelo_sha:
        chave_do_commit = "hash(coalesce(sha, concat_ws('|', author, created_at, files)))"
    return sistema, chave_do_commit


def _commits_unicos(con: duckdb.DuckDBPyConnection, pedido: Pedido, stats: dict[str, int]) -> None:
    """A tabela `git_ok`: cada commit copiado entre repositórios fica no repositório mais antigo."""
    if not pedido.commits_pelo_sha:
        con.execute("""
            CREATE TABLE git_ok AS
            SELECT codigo, tipo, pessoa, marca, ts, ocasiao
            FROM (
                SELECT *, min(criado) OVER (PARTITION BY h) AS mais_antigo
                FROM leve WHERE eh_commit
            )
            WHERE NOT coalesce(criado > mais_antigo, false)
        """)
        return
    # Um só por SHA: o do repositório criado antes, e no empate o de menor repo_id. Dentro de um
    # grupo fundido todos têm o mesmo repo_id e o mesmo criado: fica o do repositório mantido.
    grupo = ", em_grupo, rank_membro" if pedido.repos_fundidos else ""
    desempate = ", rank_membro" if pedido.repos_fundidos else ""
    con.execute(f"""
        CREATE TABLE git_ok AS
        SELECT codigo, tipo, pessoa, marca, ts, ocasiao, repetido{grupo}
        FROM (
            SELECT *, count(*) OVER (PARTITION BY h) > 1 AS repetido,
                   row_number() OVER (
                       PARTITION BY h
                       ORDER BY criado NULLS LAST, try_cast(repo_id AS BIGINT), repo_id{desempate}
                   ) AS ordem
            FROM leve WHERE eh_commit
        ) WHERE ordem = 1
    """)
    stats["shas_em_mais_de_um_repositorio"] = _um(con, "SELECT count(*) FROM git_ok WHERE repetido")


def _prepara_grupos(
    con: duckdb.DuckDBPyConnection, pedido: Pedido, stats: dict[str, int]
) -> tuple[str, str, str]:
    """A tabela `grupos` e os trechos de SQL que mandam cada duplicado para o repositório mantido.

    Devolve o JOIN, a expressão do repositório efetivo e as colunas extras de `leve`: se o
    repositório é de um grupo, a posição dele no grupo (0 é o mantido) e a chave do evento de API.
    """
    grupos = pedido.repos_fundidos
    if not grupos:
        return "", "b.repo_id", ""
    if not pedido.commits_pelo_sha:
        raise ValueError("repos_fundidos exige commits_pelo_sha: o commit repetido conta pelo SHA")
    if pedido.repos_excluidos:
        raise ValueError("repos_excluidos e repos_fundidos não valem juntos")
    grupos = _identidade_elegivel(pedido, stats)
    linhas = []
    for duplicado, mantido in grupos.items():
        linhas.append((duplicado, mantido))
        linhas.append((mantido, mantido))
    tabela = pd.DataFrame(linhas, columns=["repo_id", "mantido"]).drop_duplicates()
    con.register("grupos_pandas", tabela)
    con.execute("CREATE TABLE grupos AS SELECT * FROM grupos_pandas")
    stats["repos_fundidos"] = len(grupos)
    stats["grupos_de_duplicados"] = len(set(grupos.values()))
    colunas = (
        ", g.mantido IS NOT NULL AS em_grupo"
        ", CASE WHEN b.repo_id = g.mantido THEN 0"
        " ELSE coalesce(try_cast(b.repo_id AS BIGINT), 1) END AS rank_membro"
        f", CASE WHEN NOT eh_commit THEN hash(event_type, author_login, created_at, {CONVERSA})"
        " END AS chave_api"
    )
    return "LEFT JOIN grupos g ON b.repo_id = g.repo_id", "coalesce(g.mantido, b.repo_id)", colunas


def _identidade_elegivel(pedido: Pedido, stats: dict[str, int]) -> dict[str, str]:
    """Duplicado -> repositório que dá a identidade ao grupo.

    A identidade é a do mantido (o criado antes). Se o mantido for inelegível e algum membro for
    elegível, ela passa para o membro elegível criado antes (empate: menor `repo_id`). Grupo sem
    membro elegível fica com o mantido e sai inteiro na elegibilidade.
    """
    criado = dict(zip(pedido.repos["repo_id"].astype(str), pedido.repos["criado"], strict=True))
    elegivel = dict(zip(pedido.repos["repo_id"].astype(str), pedido.repos["elegivel"], strict=True))
    membros: dict[str, list[str]] = {}
    for duplicado, mantido in pedido.repos_fundidos.items():
        if mantido not in membros:
            membros[mantido] = [mantido]
        membros[mantido].append(duplicado)

    identidade_de: dict[str, str] = {}
    trocados = 0
    sem_elegivel = 0
    for mantido, lista in membros.items():
        identidade = mantido
        if not elegivel.get(mantido, False):
            candidatos = []
            for repo in lista:
                if elegivel.get(repo, False):
                    data = criado.get(repo)
                    sem_data = pd.isna(data)
                    candidatos.append((sem_data, pd.Timestamp.max if sem_data else data, int(repo)))
            if candidatos:
                identidade = str(min(candidatos)[2])
                trocados += 1
            else:
                sem_elegivel += 1
        for repo in lista:
            if repo != identidade:
                identidade_de[repo] = identidade
    stats["grupos_com_identidade_trocada"] = trocados
    stats["grupos_sem_membro_elegivel"] = sem_elegivel
    return identidade_de


def _repetidos_no_grupo(con: duckdb.DuckDBPyConnection, stats: dict[str, int]) -> None:
    """Um evento de API repetido em mais de um membro do grupo fica no membro de menor posição.

    Dentro de um mesmo repositório não se tira nada: só vale entre membros do grupo.
    """
    con.execute("""
        CREATE TABLE donos AS
        SELECT repo_id, chave_api, min(rank_membro) AS dono
        FROM leve WHERE em_grupo AND NOT eh_commit GROUP BY repo_id, chave_api
    """)
    antes = _um(con, "SELECT count(*) FROM leve")
    con.execute("""
        DELETE FROM leve USING donos d
        WHERE leve.em_grupo AND NOT leve.eh_commit
          AND leve.repo_id = d.repo_id AND leve.chave_api = d.chave_api
          AND leve.rank_membro > d.dono
    """)
    con.execute("DROP TABLE donos")
    stats["eventos_api_repetidos_no_grupo"] = antes - _um(con, "SELECT count(*) FROM leve")


def _so_nos_duplicados(
    con: duckdb.DuckDBPyConnection, nomes_tipo: list[str], stats: dict[str, int]
) -> None:
    """Eventos e commits que só existem nos membros que a regra de excluir tiraria."""
    issue_pr = f"{nomes_tipo.index('issues')}, {nomes_tipo.index('pull_requests')}"
    stats["eventos_api_so_nos_duplicados"] = _um(
        con, "SELECT count(*) FROM leve WHERE em_grupo AND NOT eh_commit AND rank_membro > 0"
    )
    stats["issues_e_prs_so_nos_duplicados"] = _um(
        con,
        "SELECT count(*) FROM leve WHERE em_grupo AND NOT eh_commit AND rank_membro > 0 "
        f"AND tipo IN ({issue_pr})",
    )
    stats["commits_so_nos_duplicados"] = _um(
        con, "SELECT count(*) FROM git_ok WHERE em_grupo AND rank_membro > 0"
    )


def _cria_repos(con: duckdb.DuckDBPyConnection, pedido: Pedido, stats: dict[str, int]) -> None:
    """A tabela `repos`, com os duplicados de `repos_excluidos` marcados como inelegíveis."""
    repos = pedido.repos.copy()
    duplicado = repos["repo_id"].astype(str).isin(pedido.repos_excluidos)
    repos.loc[duplicado, "elegivel"] = False
    if duplicado.any():
        stats["repos_duplicados_excluidos"] = int(duplicado.sum())
    if pedido.repos_sem_eventos:
        em_grupo = set(pedido.repos_fundidos) | set(pedido.repos_fundidos.values())
        for repo in pedido.repos_sem_eventos:
            if repo in em_grupo:
                raise ValueError(f"repos_sem_eventos: {repo} está num grupo de duplicados")
        sem_eventos = repos["repo_id"].astype(str).isin(pedido.repos_sem_eventos)
        if int(sem_eventos.sum()) != len(set(pedido.repos_sem_eventos)):
            raise ValueError("repos_sem_eventos: repo_id que não está nos alvos")
        repos.loc[sem_eventos, "elegivel"] = False
        stats["repos_sem_eventos"] = int(sem_eventos.sum())
    con.register("repos_pandas", repos)
    con.execute("CREATE TABLE repos AS SELECT * FROM repos_pandas")


def _pessoas_dos_repos_contados(
    con: duckdb.DuckDBPyConnection, pedido: Pedido, stats: dict[str, int]
) -> None:
    """Pessoas que os `repos_para_contar` teriam, com as regras da carga, mesmo inelegíveis.

    Usa os eventos já filtrados (linguagem, piso, SHA, contas) e os filtros finais (conta apagada,
    bot, tipo, datas). O duplicado de um grupo conta pelo repositório que dá a identidade ao grupo.
    """
    identidade = {}
    if pedido.repos_fundidos:
        identidade = _identidade_elegivel(pedido, {})
    ids = []
    for repo in pedido.repos_para_contar:
        ids.append(identidade.get(repo, repo))
    tabela = pd.DataFrame({"repo_id": sorted(set(ids))})
    con.register("contar_pandas", tabela)
    con.execute("""
        CREATE TABLE contar AS
        SELECT r.codigo FROM repos r JOIN contar_pandas c ON r.repo_id = c.repo_id
    """)
    con.execute(f"""
        CREATE TABLE pessoas_contadas AS
        SELECT DISTINCT pessoa, codigo FROM (
            SELECT a.codigo, a.pessoa, a.marca, a.tipo, a.ts
            FROM leve a LEFT JOIN piso p ON a.codigo = p.codigo
            WHERE NOT a.eh_commit AND NOT coalesce(a.ts < p.piso, false)
            UNION ALL SELECT codigo, pessoa, marca, tipo, ts FROM git_ok
        ) WHERE codigo IN (SELECT codigo FROM contar) AND marca = 0 AND tipo >= 0
          AND ts >= TIMESTAMP '2008-01-01' AND ts <= TIMESTAMP '{pedido.agora}'
    """)
    stats["repos_contados"] = len(tabela)
    stats["repos_contados_com_evento"] = _um(
        con, "SELECT count(DISTINCT codigo) FROM pessoas_contadas"
    )
    con.execute("CREATE TABLE so_pessoas AS SELECT DISTINCT pessoa FROM pessoas_contadas")
    con.execute("DROP TABLE pessoas_contadas")
    con.execute("ALTER TABLE so_pessoas RENAME TO pessoas_contadas")
    stats["contribuidores_nos_repos_contados"] = _um(con, "SELECT count(*) FROM pessoas_contadas")


def _conta_brutas(con: duckdb.DuckDBPyConnection, stats: dict[str, int]) -> None:
    """Relê os arquivos inteiros só para contar as linhas de API e de git."""
    print("duckdb: contando as linhas brutas", file=sys.stderr)
    linha = con.execute(
        "SELECT count(*) FILTER (WHERE NOT eh_commit), count(*) FILTER (WHERE eh_commit) FROM bruto"
    ).fetchone()
    stats["eventos_api_bruto"], stats["eventos_git_bruto"] = (
        (int(linha[0]), int(linha[1])) if linha else (0, 0)
    )


def _carrega(con: duckdb.DuckDBPyConnection, pedido: Pedido) -> Resultado:
    stats: dict[str, int] = {}
    nome = pedido.linguagem
    nomes_tipo = sorted(set(pedido.tipos.values()))
    extensoes = "|".join(re.escape(e) for e in pedido.extensoes)
    toca_a_linguagem = _aspas(f"(?:{extensoes})(?:;|$)")

    _cria_repos(con, pedido, stats)
    leituras = [_leitura(caminho, papel) for caminho, papel in pedido.eventos]
    con.execute("CREATE VIEW bruto AS " + " UNION ALL ".join(leituras))

    # Uma leitura só do arquivo inteiro (o custo dominante): todas as linhas que passam no
    # filtro do papel delas, API e git juntas.
    print("duckdb: lendo os eventos", file=sys.stderr)
    autor = "CASE WHEN eh_commit THEN author ELSE author_login END"
    quem_commitou, junta_autores = _quem_commitou(con, pedido, stats)
    pessoa = _pessoa(f"CASE WHEN eh_commit THEN {quem_commitou} ELSE author_login END")
    sistema, chave_do_commit = _contas_e_chave(pedido, quem_commitou)
    junta_grupo, repo_efetivo, colunas_do_grupo = _prepara_grupos(con, pedido, stats)
    ignora = ""
    if pedido.acoes_ignoradas:
        acoes = ", ".join(_aspas(a) for a in pedido.acoes_ignoradas)
        ignora = f"AND NOT (event_type = 'issue_event' AND coalesce(message, '') IN ({acoes}))"
    con.execute(f"""
        CREATE TABLE leve AS
        SELECT coalesce(r.codigo, -1) AS codigo, r.criado AS criado, eh_commit,
               {_case_tipo(pedido.tipos, nomes_tipo)} AS tipo,
               {pessoa} AS pessoa, {_marca(autor)} AS marca,
               {_ts("created_at")} AS ts,
               CASE WHEN eh_commit THEN {chave_do_commit} END AS h,
               {repo_efetivo} AS repo_id, {_ocasiao(repo_efetivo)} AS ocasiao {colunas_do_grupo}
        FROM bruto b {junta_grupo} LEFT JOIN repos r ON {repo_efetivo} = r.repo_id {junta_autores}
        WHERE ((NOT eh_commit AND author_login IS NOT NULL
                AND coalesce(b.language, r.principal) = {_aspas(nome)} {ignora})
            OR (eh_commit AND author IS NOT NULL
                AND regexp_matches(lower(files), {toca_a_linguagem}))) {sistema}
    """)
    stats["eventos_api_desta_linguagem"] = _um(con, "SELECT count(*) FROM leve WHERE NOT eh_commit")
    stats["eventos_git_desta_linguagem"] = _um(con, "SELECT count(*) FROM leve WHERE eh_commit")
    if pedido.contar_brutas:
        _conta_brutas(con, stats)

    if pedido.repos_fundidos:
        print("duckdb: eventos repetidos entre os membros de cada grupo", file=sys.stderr)
        _repetidos_no_grupo(con, stats)
    print("duckdb: commits copiados entre repositórios", file=sys.stderr)
    _commits_unicos(con, pedido, stats)
    if pedido.repos_fundidos:
        _so_nos_duplicados(con, nomes_tipo, stats)
    duplicados = stats["eventos_git_desta_linguagem"] - _um(con, "SELECT count(*) FROM git_ok")
    stats["commits_duplicados_descartados"] = duplicados
    if duplicados:
        print(
            f"aviso: {duplicados} commits descartados por serem cópia de histórico já contado "
            "num repositório criado antes (fork completo ou clone empurrado pra um repositório "
            "novo)",
            file=sys.stderr,
        )

    print("duckdb: piso por repositório e elegibilidade", file=sys.stderr)
    con.execute("CREATE TABLE piso AS SELECT codigo, min(ts) AS piso FROM git_ok GROUP BY codigo")
    antes_do_piso = _um(
        con,
        """
        SELECT count(*) FROM leve a JOIN piso p ON a.codigo = p.codigo
        WHERE NOT a.eh_commit AND a.ts < p.piso
        """,
    )
    stats["eventos_antes_do_piso_descartados"] = antes_do_piso
    if antes_do_piso:
        print(
            f"aviso: {antes_do_piso} eventos descartados por serem anteriores ao primeiro "
            f"commit que de fato toca {nome} no mesmo repositório (issue/pr/comentário datado "
            "antes do repositório virar essa linguagem)",
            file=sys.stderr,
        )
    if pedido.repos_para_contar:
        _pessoas_dos_repos_contados(con, pedido, stats)
    con.execute("""
        CREATE TABLE elegiveis AS
        SELECT t.codigo, t.tipo, t.pessoa, t.marca, t.ts, t.ocasiao FROM (
            SELECT a.codigo, a.tipo, a.pessoa, a.marca, a.ts, a.ocasiao
            FROM leve a LEFT JOIN piso p ON a.codigo = p.codigo
            WHERE NOT a.eh_commit AND NOT coalesce(a.ts < p.piso, false)
            UNION ALL
            SELECT codigo, tipo, pessoa, marca, ts, ocasiao FROM git_ok
        ) t JOIN repos r ON t.codigo = r.codigo
        WHERE r.elegivel
    """)
    con.execute("DROP TABLE leve")
    con.execute("DROP TABLE git_ok")
    if pedido.fundir_identidades:
        _funde_por_repositorios(con, pedido, nomes_tipo, stats)
    stats["eventos_apos_elegibilidade"] = _um(con, "SELECT count(*) FROM elegiveis")
    return _finaliza(con, pedido, nomes_tipo, stats)


def _funde_por_repositorios(
    con: duckdb.DuckDBPyConnection, pedido: Pedido, nomes_tipo: list[str], stats: dict[str, int]
) -> None:
    """Quem só commita vira o login de quem só abre issue/PR nos mesmos repositórios."""
    commit = nomes_tipo.index("commits")
    issue_pr = f"{nomes_tipo.index('issues')}, {nomes_tipo.index('pull_requests')}"
    minimo = int(pedido.fusao_repos_min)
    con.execute(f"""
        CREATE TABLE perfil AS
        SELECT pessoa, bool_and(tipo = {commit}) AS so_commit,
               bool_and(tipo IN ({issue_pr})) AS so_issue_pr,
               count(DISTINCT codigo) AS n_repos
        FROM elegiveis WHERE marca = 0
        GROUP BY pessoa HAVING count(*) >= {minimo}
    """)
    con.execute(f"""
        CREATE TABLE mapa AS
        WITH repos_de AS (
            SELECT DISTINCT e.pessoa, e.codigo, p.so_commit, p.n_repos
            FROM elegiveis e JOIN perfil p ON e.pessoa = p.pessoa
            WHERE e.marca = 0 AND (p.so_commit OR p.so_issue_pr)
        ), pares AS (
            SELECT c.pessoa AS de, a.pessoa AS para,
                   count(*) / (any_value(c.n_repos) + any_value(a.n_repos) - count(*)) AS jaccard
            FROM repos_de c JOIN repos_de a ON c.codigo = a.codigo
            WHERE c.so_commit AND NOT a.so_commit
            GROUP BY c.pessoa, a.pessoa
            HAVING count(*) >= {minimo}
        )
        SELECT de, arg_max(para, jaccard) AS para FROM pares
        WHERE jaccard >= {float(pedido.fusao_jaccard_min)}
        GROUP BY de
    """)
    stats["identidades_fundidas_por_repositorios"] = _um(con, "SELECT count(*) FROM mapa")
    con.execute("UPDATE elegiveis SET pessoa = m.para FROM mapa m WHERE elegiveis.pessoa = m.de")
    con.execute("DROP TABLE perfil")
    con.execute("DROP TABLE mapa")


def _finaliza(
    con: duckdb.DuckDBPyConnection, pedido: Pedido, nomes_tipo: list[str], stats: dict[str, int]
) -> Resultado:
    """Fantasma, bot, tipo fora do mapa, datas impossíveis; depois a compactação."""
    fantasmas = con.execute("SELECT ts AS created_at FROM elegiveis WHERE marca = 1").df()
    bots = _um(con, "SELECT count(*) FROM elegiveis WHERE marca = 2")
    stats["eventos_fantasma_descartados"] = len(fantasmas)
    stats["eventos_bot_descartados"] = bots
    print(
        f"aviso: {len(fantasmas)} eventos de conta apagada descartados da pirâmide "
        f"(registrados à parte); {bots} eventos de bot descartados",
        file=sys.stderr,
    )

    con.execute(
        "CREATE TABLE base AS SELECT codigo, tipo, pessoa, ts, ocasiao FROM elegiveis "
        "WHERE marca = 0 AND tipo >= 0"
    )
    con.execute("DROP TABLE elegiveis")
    agora = pedido.agora
    descartados = _um(con, "SELECT count(*) FROM base WHERE ts IS NULL")
    stats["eventos_data_ilegivel_descartados"] = descartados
    if descartados:
        print(f"aviso: {descartados} eventos com data ilegível descartados", file=sys.stderr)
    futuros = _um(con, f"SELECT count(*) FROM base WHERE ts > TIMESTAMP '{agora}'")
    stats["eventos_futuro_descartados"] = futuros
    if futuros:
        print(f"aviso: {futuros} eventos com data no futuro descartados", file=sys.stderr)
    stats["eventos_antes_2008_descartados"] = _um(
        con, "SELECT count(*) FROM base WHERE ts < TIMESTAMP '2008-01-01'"
    )
    con.execute(
        f"CREATE TABLE final AS SELECT * FROM base "
        f"WHERE ts >= TIMESTAMP '2008-01-01' AND ts <= TIMESTAMP '{agora}'"
    )
    con.execute("DROP TABLE base")
    stats["eventos_finais"] = _um(con, "SELECT count(*) FROM final")
    stats["repos_finais"] = _um(con, "SELECT count(DISTINCT codigo) FROM final")
    stats["contribuidores_finais"] = _um(con, "SELECT count(DISTINCT pessoa) FROM final")
    if pedido.repos_para_contar:
        stats["contribuidores_so_nos_repos_contados"] = _um(
            con,
            "SELECT count(*) FROM pessoas_contadas WHERE pessoa NOT IN (SELECT pessoa FROM final)",
        )
    if pedido.origem is not None:
        _grava_origem(con, pedido.origem, nomes_tipo)

    if pedido.completos:
        return Resultado(_completos(con, nomes_tipo), stats, fantasmas)
    print("duckdb: compactando", file=sys.stderr)
    return Resultado(_compacta(con, nomes_tipo), stats, fantasmas)


def _completos(con: duckdb.DuckDBPyConnection, nomes_tipo: list[str]) -> pd.DataFrame:
    """Um evento por linha, nas colunas de `carrega_eventos`, para o pipeline do motor."""
    nomes = "[" + ", ".join(_aspas(n) for n in nomes_tipo) + "]"
    return con.execute(f"""
        SELECT f.codigo AS scope_id, f.pessoa AS contributor_id,
               {nomes}[f.tipo + 1] AS event_type, f.ts AS timestamp, r.repo_id
        FROM final f JOIN repos r ON f.codigo = r.codigo
        ORDER BY f.ts
    """).df()


def _grava_origem(con: duckdb.DuckDBPyConnection, pasta: Path, nomes_tipo: list[str]) -> None:
    """Onde cada pessoa chegou e quantas pessoas cada repositório teve por trimestre.

    `pessoas.parquet`: primeiro e último evento, repositório (`codigo`) e tipo do primeiro, e se
    fez algum commit ou PR, quantos eventos fez (todos, de código e commits) e em quantas
    ocasiões (`_ocasiao`) e quando começou a segunda (`segunda_ocasiao`, vazio para casual).
    `repos_por_trimestre.parquet`: pessoas distintas por repositório e trimestre.
    `meses.parquet`: eventos e pessoas distintas por mês, separados em código (commit e PR) e
    discussão (o resto). Os eventos já passaram por todas as regras da carga.
    `tipos_por_ano.parquet`: eventos e primeiro evento de cada tipo em cada ano.
    `tipos_final.parquet`: eventos e pessoas de cada tipo, no total e entre os residentes.
    `pessoas_tipos_por_ano.parquet`: eventos de cada pessoa por ano e tipo.
    `pessoas_repos_por_ano.parquet`: eventos de cada pessoa por repositório (`codigo`) e ano.
    `pessoas_repos_por_trimestre.parquet`: cada par (pessoa, `codigo`) com evento em um trimestre,
    contado desde 2008T1 (`trimestre` = (ano - 2008) * 4 + trimestre do ano - 1).
    `pessoas_repos_por_dia.parquet`: cada par (pessoa, `codigo`) com evento em um dia (`dia`, data).
    """
    pasta.mkdir(parents=True, exist_ok=True)
    nomes = "[" + ", ".join(_aspas(n) for n in nomes_tipo) + "]"
    codigos = []
    for i, n in enumerate(nomes_tipo):
        if n in CODIGOS_DE_CODIGO:
            codigos.append(str(i))
    # Início de cada ocasião da pessoa; a segunda mais antiga diz quando voltou (NULL se casual).
    con.execute("""
        CREATE TABLE segunda AS
        SELECT pessoa, list_sort(list(inicio))[2] AS segunda_ocasiao FROM (
            SELECT pessoa, ocasiao, min(ts) AS inicio FROM final GROUP BY pessoa, ocasiao
        ) GROUP BY pessoa HAVING count(*) > 1
    """)
    con.execute(f"""
        COPY (
            SELECT f.pessoa, min(f.ts) AS primeiro, max(f.ts) AS ultimo,
                   arg_min(f.codigo, f.ts) AS codigo_do_primeiro,
                   list_extract({nomes}, arg_min(f.tipo, f.ts) + 1) AS tipo_do_primeiro,
                   bool_or(f.tipo IN ({", ".join(codigos)})) AS codou,
                   count(*) AS eventos,
                   count(*) FILTER (WHERE f.tipo IN ({", ".join(codigos)})) AS eventos_de_codigo,
                   count(*) FILTER (WHERE f.tipo = {nomes_tipo.index("commits")}) AS commits,
                   count(DISTINCT f.ocasiao) AS ocasioes,
                   any_value(s.segunda_ocasiao) AS segunda_ocasiao
            FROM final f LEFT JOIN segunda s ON f.pessoa = s.pessoa GROUP BY f.pessoa
        ) TO {_aspas(pasta / "pessoas.parquet")} (FORMAT parquet)
    """)
    # Eventos e pessoas de cada tipo, no total e entre os residentes (com a segunda ocasião).
    con.execute(f"""
        COPY (
            SELECT list_extract({nomes}, f.tipo + 1) AS tipo, count(*) AS eventos,
                   count(DISTINCT f.pessoa) AS pessoas,
                   count(*) FILTER (WHERE s.pessoa IS NOT NULL) AS eventos_residentes,
                   count(DISTINCT f.pessoa) FILTER (WHERE s.pessoa IS NOT NULL)
                       AS pessoas_residentes
            FROM final f LEFT JOIN segunda s ON f.pessoa = s.pessoa GROUP BY ALL
        ) TO {_aspas(pasta / "tipos_final.parquet")} (FORMAT parquet)
    """)
    con.execute("DROP TABLE segunda")
    con.execute(f"""
        COPY (
            SELECT codigo, year(ts) AS ano, quarter(ts) AS trimestre,
                   count(DISTINCT pessoa) AS pessoas
            FROM final GROUP BY ALL
        ) TO {_aspas(pasta / "repos_por_trimestre.parquet")} (FORMAT parquet)
    """)
    con.execute(f"""
        COPY (
            SELECT date_trunc('month', ts) AS mes,
                   CASE WHEN tipo IN ({", ".join(codigos)}) THEN 'codigo' ELSE 'discussao' END
                       AS grupo,
                   count(*) AS eventos, count(DISTINCT pessoa) AS pessoas
            FROM final GROUP BY ALL
        ) TO {_aspas(pasta / "meses.parquet")} (FORMAT parquet)
    """)
    con.execute(f"""
        COPY (
            SELECT list_extract({nomes}, tipo + 1) AS tipo, year(ts) AS ano,
                   count(*) AS eventos, min(ts) AS primeiro
            FROM final GROUP BY ALL
        ) TO {_aspas(pasta / "tipos_por_ano.parquet")} (FORMAT parquet)
    """)
    con.execute(f"""
        COPY (
            SELECT pessoa, CAST(year(ts) AS SMALLINT) AS ano,
                   list_extract({nomes}, tipo + 1) AS tipo, count(*) AS eventos
            FROM final GROUP BY ALL
        ) TO {_aspas(pasta / "pessoas_tipos_por_ano.parquet")} (FORMAT parquet)
    """)
    con.execute(f"""
        COPY (
            SELECT pessoa, codigo, CAST(year(ts) AS SMALLINT) AS ano, count(*) AS eventos
            FROM final GROUP BY ALL
        ) TO {_aspas(pasta / "pessoas_repos_por_ano.parquet")} (FORMAT parquet)
    """)
    con.execute(f"""
        COPY (
            SELECT DISTINCT pessoa, codigo,
                   CAST((year(ts) - 2008) * 4 + quarter(ts) - 1 AS SMALLINT) AS trimestre
            FROM final
        ) TO {_aspas(pasta / "pessoas_repos_por_trimestre.parquet")} (FORMAT parquet)
    """)
    con.execute(f"""
        COPY (
            SELECT DISTINCT pessoa, codigo, CAST(ts AS DATE) AS dia FROM final
        ) TO {_aspas(pasta / "pessoas_repos_por_dia.parquet")} (FORMAT parquet)
    """)


def _compacta(con: duckdb.DuckDBPyConnection, nomes_tipo: list[str]) -> pd.DataFrame:
    """Mesma redução de `vitalidade.compacta`, em SQL.

    Por trimestre o primeiro e o último evento e o último de código e de discussão; por pessoa
    o primeiro de código e o primeiro de discussão. A coluna `n` leva a contagem de cada lado no
    trimestre, no último evento do lado.
    """
    codigos = [i for i, n in enumerate(nomes_tipo) if n in CODIGOS_DE_CODIGO]
    eh_codigo = "tipo IN (" + ", ".join(str(c) for c in codigos) + ")"
    resultado = con.execute(f"""
        WITH por_trimestre AS (
            SELECT pessoa, min(ts) AS t1, arg_min(tipo, ts) AS tp1,
                   max(ts) AS t2, arg_max(tipo, ts) AS tp2,
                   max(ts) FILTER (WHERE {eh_codigo}) AS c2,
                   arg_max(tipo, ts) FILTER (WHERE {eh_codigo}) AS tc2,
                   max(ts) FILTER (WHERE NOT ({eh_codigo})) AS d2,
                   arg_max(tipo, ts) FILTER (WHERE NOT ({eh_codigo})) AS td2,
                   count(*) FILTER (WHERE {eh_codigo}) AS nc,
                   count(*) FILTER (WHERE NOT ({eh_codigo})) AS nd
            FROM final GROUP BY pessoa, year(ts) * 4 + (month(ts) - 1) // 3
        ), primeiros AS (
            SELECT pessoa,
                   min(ts) FILTER (WHERE {eh_codigo}) AS c1,
                   arg_min(tipo, ts) FILTER (WHERE {eh_codigo}) AS tc,
                   min(ts) FILTER (WHERE NOT ({eh_codigo})) AS d1,
                   arg_min(tipo, ts) FILTER (WHERE NOT ({eh_codigo})) AS td
            FROM final GROUP BY pessoa
        )
        SELECT pessoa AS contributor_id, tipo, ts AS timestamp, sum(n)::BIGINT AS n FROM (
            SELECT pessoa, tp1 AS tipo, t1 AS ts, 0 AS n FROM por_trimestre
            UNION ALL SELECT pessoa, tp2, t2, 0 FROM por_trimestre
            UNION ALL SELECT pessoa, tc2, c2, nc FROM por_trimestre WHERE c2 IS NOT NULL
            UNION ALL SELECT pessoa, td2, d2, nd FROM por_trimestre WHERE d2 IS NOT NULL
            UNION ALL SELECT pessoa, tc, c1, 0 FROM primeiros WHERE c1 IS NOT NULL
            UNION ALL SELECT pessoa, td, d1, 0 FROM primeiros WHERE d1 IS NOT NULL
        ) GROUP BY pessoa, tipo, ts
    """).df()
    resultado["event_type"] = pd.Categorical.from_codes(
        resultado.pop("tipo").to_numpy(), categories=nomes_tipo
    )
    return resultado[["contributor_id", "event_type", "timestamp", "n"]]
