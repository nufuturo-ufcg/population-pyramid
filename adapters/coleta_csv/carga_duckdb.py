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
CODIGOS_DE_CODIGO = ("commits", "pull_requests")


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


@dataclass
class Resultado:
    """O que a carga devolve: os eventos, as contagens de cada filtro e as contas apagadas."""

    eventos: pd.DataFrame  # contributor_id, event_type, timestamp, já compactados
    estatisticas: dict[str, int]  # quanto sobrou em cada filtro
    fantasmas: pd.DataFrame  # coluna created_at das contas apagadas, que saem da pirâmide


def _aspas(texto: str | Path) -> str:
    return "'" + str(texto).replace("'", "''") + "'"


def _leitura(caminho: Path, papel: str) -> str:
    """SELECT que lê um CSV e diz, por linha, se segue a regra do git (`eh_commit`)."""
    eh_commit = {"api": "false", "git": "true", "misto": "event_type = 'commit'"}[papel]
    nulos = "[" + ", ".join(_aspas(n) for n in NULOS) + "]"
    return f"""
        SELECT repo_id, event_type, author, author_login, created_at, files, language,
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


def _carrega(con: duckdb.DuckDBPyConnection, pedido: Pedido) -> Resultado:
    stats: dict[str, int] = {}
    nome = pedido.linguagem
    nomes_tipo = sorted(set(pedido.tipos.values()))
    extensoes = "|".join(re.escape(e) for e in pedido.extensoes)
    toca_a_linguagem = _aspas(f"(?:{extensoes})(?:;|$)")

    con.register("repos_pandas", pedido.repos)
    con.execute("CREATE TABLE repos AS SELECT * FROM repos_pandas")
    leituras = [_leitura(caminho, papel) for caminho, papel in pedido.eventos]
    con.execute("CREATE VIEW bruto AS " + " UNION ALL ".join(leituras))

    # Uma leitura só do arquivo inteiro (o custo dominante): todas as linhas que passam no
    # filtro do papel delas, API e git juntas.
    print("duckdb: lendo os eventos", file=sys.stderr)
    autor = "CASE WHEN eh_commit THEN author ELSE author_login END"
    con.execute(f"""
        CREATE TABLE leve AS
        SELECT coalesce(r.codigo, -1) AS codigo, r.criado AS criado, eh_commit,
               {_case_tipo(pedido.tipos, nomes_tipo)} AS tipo,
               {_pessoa(autor)} AS pessoa, {_marca(autor)} AS marca,
               {_ts("created_at")} AS ts,
               CASE WHEN eh_commit THEN hash(author, created_at, files) END AS h
        FROM bruto b LEFT JOIN repos r ON b.repo_id = r.repo_id
        WHERE (NOT eh_commit AND author_login IS NOT NULL
               AND coalesce(b.language, r.principal) = {_aspas(nome)})
           OR (eh_commit AND author IS NOT NULL
               AND regexp_matches(lower(files), {toca_a_linguagem}))
    """)
    stats["eventos_api_desta_linguagem"] = _um(con, "SELECT count(*) FROM leve WHERE NOT eh_commit")
    stats["eventos_git_desta_linguagem"] = _um(con, "SELECT count(*) FROM leve WHERE eh_commit")
    if pedido.contar_brutas:
        print("duckdb: contando as linhas brutas", file=sys.stderr)
        linha = con.execute(
            "SELECT count(*) FILTER (WHERE NOT eh_commit), count(*) FILTER (WHERE eh_commit) "
            "FROM bruto"
        ).fetchone()
        stats["eventos_api_bruto"], stats["eventos_git_bruto"] = (
            (int(linha[0]), int(linha[1])) if linha else (0, 0)
        )

    print("duckdb: commits copiados entre repositórios", file=sys.stderr)
    con.execute("""
        CREATE TABLE git_ok AS
        SELECT codigo, tipo, pessoa, marca, ts
        FROM (SELECT *, min(criado) OVER (PARTITION BY h) AS mais_antigo FROM leve WHERE eh_commit)
        WHERE NOT coalesce(criado > mais_antigo, false)
    """)
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
    con.execute("""
        CREATE TABLE elegiveis AS
        SELECT t.codigo, t.tipo, t.pessoa, t.marca, t.ts FROM (
            SELECT a.codigo, a.tipo, a.pessoa, a.marca, a.ts
            FROM leve a LEFT JOIN piso p ON a.codigo = p.codigo
            WHERE NOT a.eh_commit AND NOT coalesce(a.ts < p.piso, false)
            UNION ALL
            SELECT codigo, tipo, pessoa, marca, ts FROM git_ok
        ) t JOIN repos r ON t.codigo = r.codigo
        WHERE r.elegivel
    """)
    con.execute("DROP TABLE leve")
    con.execute("DROP TABLE git_ok")
    stats["eventos_apos_elegibilidade"] = _um(con, "SELECT count(*) FROM elegiveis")
    return _finaliza(con, pedido, nomes_tipo, stats)


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
        "CREATE TABLE base AS SELECT codigo, tipo, pessoa, ts FROM elegiveis "
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
    if pedido.origem is not None:
        _grava_origem(con, pedido.origem, nomes_tipo)

    print("duckdb: compactando", file=sys.stderr)
    return Resultado(_compacta(con, nomes_tipo), stats, fantasmas)


def _grava_origem(con: duckdb.DuckDBPyConnection, pasta: Path, nomes_tipo: list[str]) -> None:
    """Onde cada pessoa chegou e quantas pessoas cada repositório teve por trimestre.

    `pessoas.parquet`: primeiro e último evento, repositório (`codigo`) e tipo do primeiro, e se
    fez algum commit ou PR, e quantos eventos fez (todos e só de código).
    `repos_por_trimestre.parquet`: pessoas distintas por repositório e trimestre.
    `meses.parquet`: eventos e pessoas distintas por mês, separados em código (commit e PR) e
    discussão (o resto). Os eventos já passaram por todas as regras da carga.
    """
    pasta.mkdir(parents=True, exist_ok=True)
    nomes = "[" + ", ".join(_aspas(n) for n in nomes_tipo) + "]"
    codigos = []
    for i, n in enumerate(nomes_tipo):
        if n in CODIGOS_DE_CODIGO:
            codigos.append(str(i))
    con.execute(f"""
        COPY (
            SELECT pessoa, min(ts) AS primeiro, max(ts) AS ultimo,
                   arg_min(codigo, ts) AS codigo_do_primeiro,
                   list_extract({nomes}, arg_min(tipo, ts) + 1) AS tipo_do_primeiro,
                   bool_or(tipo IN ({", ".join(codigos)})) AS codou,
                   count(*) AS eventos,
                   count(*) FILTER (WHERE tipo IN ({", ".join(codigos)})) AS eventos_de_codigo
            FROM final GROUP BY pessoa
        ) TO {_aspas(pasta / "pessoas.parquet")} (FORMAT parquet)
    """)
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


def _compacta(con: duckdb.DuckDBPyConnection, nomes_tipo: list[str]) -> pd.DataFrame:
    """Mesma redução de `vitalidade.compacta`, em SQL.

    Por trimestre o primeiro e o último evento e o último de código e de discussão; por pessoa
    o primeiro de código e o primeiro de discussão.
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
                   arg_max(tipo, ts) FILTER (WHERE NOT ({eh_codigo})) AS td2
            FROM final GROUP BY pessoa, year(ts) * 4 + (month(ts) - 1) // 3
        ), primeiros AS (
            SELECT pessoa,
                   min(ts) FILTER (WHERE {eh_codigo}) AS c1,
                   arg_min(tipo, ts) FILTER (WHERE {eh_codigo}) AS tc,
                   min(ts) FILTER (WHERE NOT ({eh_codigo})) AS d1,
                   arg_min(tipo, ts) FILTER (WHERE NOT ({eh_codigo})) AS td
            FROM final GROUP BY pessoa
        )
        SELECT DISTINCT pessoa AS contributor_id, tp1 AS tipo, t1 AS timestamp FROM por_trimestre
        UNION SELECT pessoa, tp2, t2 FROM por_trimestre
        UNION SELECT pessoa, tc2, c2 FROM por_trimestre WHERE c2 IS NOT NULL
        UNION SELECT pessoa, td2, d2 FROM por_trimestre WHERE d2 IS NOT NULL
        UNION SELECT pessoa, tc, c1 FROM primeiros WHERE c1 IS NOT NULL
        UNION SELECT pessoa, td, d1 FROM primeiros WHERE d1 IS NOT NULL
    """).df()
    resultado["event_type"] = pd.Categorical.from_codes(
        resultado.pop("tipo").to_numpy(), categories=nomes_tipo
    )
    return resultado[["contributor_id", "event_type", "timestamp"]]
