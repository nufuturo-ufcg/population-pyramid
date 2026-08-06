"""Fonte MSR14 (GHTorrent, MySQL 5.5 dump rodando em MariaDB 10.11).

Cada atividade vira um SELECT com a mesma forma (scope, contribuidor, timestamp)
e tudo é unido por UNION ALL. Os pontos delicados estão comentados no lugar —
são exatamente as pegadinhas do schema que fazem a contagem sair errada em
silêncio se ignoradas.
"""

from __future__ import annotations

import logging
import os
from functools import cache

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import Engine, create_engine, text

from ..config import ROOT
from .base import EVENT_COLUMNS, ActivityDataSource, validate_canonical_schema

log = logging.getLogger(__name__)


@cache
def engine() -> Engine:
    """Engine do dump. Mora aqui porque MySQL é detalhe DESTA fonte — nenhum
    estágio do motor de cálculo pode importar driver de banco (§8 da spec).
    Pool pequeno: o pipeline é sequencial por projeto."""
    load_dotenv(ROOT / ".env")
    u = os.getenv("DB_USER", "root")
    p = os.getenv("DB_PASSWORD", "root")
    h = os.getenv("DB_HOST", "127.0.0.1")
    port = os.getenv("DB_PORT", "3306")
    name = os.getenv("DB_NAME", "msr14")
    url = f"mysql+pymysql://{u}:{p}@{h}:{port}/{name}"
    eng = create_engine(url, pool_pre_ping=True, pool_size=4, max_overflow=2)
    _ping(eng, f"{h}:{port}/{name}")
    return eng


def _ping(eng: Engine, alvo: str) -> None:
    """Erro claro se o banco não está de pé, em vez de stacktrace de driver."""
    try:
        with eng.connect() as cx:
            cx.execute(text("SELECT 1"))
    except Exception as e:  # noqa: BLE001
        raise SystemExit(
            f"nao consegui conectar em {alvo}.\n"
            "  container de pe?   docker start msr14\n"
            "  credenciais certas? confira o .env\n"
            f"  causa: {type(e).__name__}: {e}"
        ) from e


# --- escopo de commits --------------------------------------------------------
# `commits.project_id` é onde o commit foi ORIGINALMENTE registrado. Forks têm
# cópia do histórico do projeto-mãe em `project_commits`. Ver settings.commit_scope.
_COMMIT_SCOPE_SQL = {
    "root": """
        SELECT c.author_id AS contributor_id, c.created_at AS ts
        FROM commits c WHERE c.project_id = :sid
    """,
    "family_project_commits": """
        SELECT c.author_id AS contributor_id, c.created_at AS ts
        FROM project_commits pc
        JOIN projects p ON p.id = pc.project_id AND COALESCE(p.forked_from, p.id) = :sid
        JOIN commits c ON c.id = pc.commit_id
    """,
    "family_project_id": """
        SELECT c.author_id AS contributor_id, c.created_at AS ts
        FROM commits c
        JOIN projects p ON p.id = c.project_id AND COALESCE(p.forked_from, p.id) = :sid
    """,
}

# --- demais atividades --------------------------------------------------------
_ACTIVITY_SQL = {
    # `pull_requests` NÃO tem created_at. A data de abertura vive em
    # `pull_request_history` com action='opened'. INNER JOIN aqui é intencional:
    # 3 PRs não têm evento 'opened' (78.952 vs 78.955) e não têm data nenhuma.
    "pull_requests": """
        SELECT pr.user_id AS contributor_id, h.created_at AS ts
        FROM pull_requests pr
        JOIN pull_request_history h ON h.pull_request_id = pr.id AND h.action = 'opened'
        WHERE pr.base_repo_id = :sid
    """,
    "commit_comments": """
        SELECT cc.user_id AS contributor_id, cc.created_at AS ts
        FROM commit_comments cc
        JOIN commits c2 ON c2.id = cc.commit_id
        WHERE c2.project_id = :sid
    """,
    # `issues` mistura issues de verdade com PRs: 80.729 das 150.362 linhas têm
    # pull_request=1. O artigo trata `issues` como abertura de discussão, então
    # NÃO filtramos pull_request=0 — a abertura de um PR também gera discussão.
    # Isso é escolha de método, não descuido; ver docs/discrepancias.md.
    "issues": """
        SELECT i.reporter_id AS contributor_id, i.created_at AS ts
        FROM issues i WHERE i.repo_id = :sid
    """,
    "issue_comments": """
        SELECT ic.user_id AS contributor_id, ic.created_at AS ts
        FROM issue_comments ic
        JOIN issues i2 ON i2.id = ic.issue_id
        WHERE i2.repo_id = :sid
    """,
    "pull_request_comments": """
        SELECT prc.user_id AS contributor_id, prc.created_at AS ts
        FROM pull_request_comments prc
        JOIN pull_requests pr2 ON pr2.id = prc.pull_request_id
        WHERE pr2.base_repo_id = :sid
    """,
    "issue_events": """
        SELECT ie.actor_id AS contributor_id, ie.created_at AS ts
        FROM issue_events ie
        JOIN issues i3 ON i3.id = ie.issue_id
        WHERE i3.repo_id = :sid
    """,
}


class MSR14Source(ActivityDataSource):
    """Escopo = projeto raiz."""

    def __init__(self, settings: dict, engine_: Engine | None = None):
        self.engine = engine_ if engine_ is not None else engine()
        self.settings = settings
        p = settings["projects"]
        self.exclude_ids = list(p.get("exclude_ids") or [])
        self.expected = p.get("expected_count")
        self.commit_scope = settings["commit_scope"]

        variant = settings["taxonomy"]["variant"]
        spec = settings["taxonomy"]["variants"][variant]
        self.variant = variant
        self.coding = list(spec["coding"])
        self.non_coding = list(spec["non_coding"])
        self.activities = self.coding + self.non_coding
        self._labels: dict[int, str] = {}

    # -- escopos ---------------------------------------------------------------
    def _load_labels(self) -> dict[int, str]:
        """id -> "owner/name" dos escopos raiz. Memoizado por instância."""
        if self._labels:
            return self._labels

        excl = ""
        if self.exclude_ids:
            excl = " AND p.id NOT IN :excl"

        sql = text(
            f"""
            SELECT p.id, CONCAT(u.login, '/', p.name) AS label
            FROM projects p JOIN users u ON u.id = p.owner_id
            WHERE p.forked_from IS NULL{excl}
            ORDER BY p.id
            """
        )
        if self.exclude_ids:
            sql = sql.bindparams(**{"excl": tuple(self.exclude_ids)})

        with self.engine.connect() as cx:
            rows = cx.execute(sql).fetchall()

        self._labels = {r.id: r.label for r in rows}
        return self._labels

    def list_scopes(self) -> list[int]:
        ids = list(self._load_labels())

        # Nunca confiar que o banco apontado é o certo só porque conectou.
        if self.expected and len(ids) != self.expected:
            raise RuntimeError(
                f"esperava {self.expected} projetos raiz, achei {len(ids)}. "
                "Banco errado, import incompleto, ou exclude_ids desatualizado."
            )
        return ids

    def scope_label(self, scope_id: int) -> str:
        """Nome legível do escopo.

        Carrega o mapa sob demanda: antes isto dependia de `list_scopes()` ter
        sido chamado na mesma instância, e quem chamasse direto (metrics.table,
        a legenda da Fig.5) recebia o id de volta como se fosse o nome — sem
        erro, só uma tabela de projetos numerados. Id desconhecido continua
        virando string, mas aí é um escopo que realmente não é raiz.
        """
        return self._load_labels().get(scope_id, str(scope_id))

    # -- eventos ---------------------------------------------------------------
    def _build_query(self) -> str:
        parts = []
        for act in self.activities:
            body = (
                _COMMIT_SCOPE_SQL[self.commit_scope]
                if act == "commits"
                else _ACTIVITY_SQL[act]
            )
            parts.append(f"SELECT '{act}' AS event_type, contributor_id, ts FROM ({body}) AS _{act}")
        return "\nUNION ALL\n".join(parts)

    def get_events(self, scope_id: int) -> pd.DataFrame:
        sql = self._build_query()
        with self.engine.connect() as cx:
            df = pd.read_sql(text(sql), cx, params={"sid": scope_id})

        n_raw = len(df)

        # commits.author_id e issues.reporter_id são NULL em parte das linhas
        # (usuário deletado / não resolvido pelo GHTorrent). Sem contribuidor
        # não há pirâmide: descarta.
        df = df[df["contributor_id"].notna()]

        # A linha de `issues` com created_at='0000-00-00 00:00:00' vira NaT no
        # pandas. Legal no MariaDB, inútil aqui.
        df["ts"] = pd.to_datetime(df["ts"], errors="coerce")
        df = df[df["ts"].notna()]

        if n_raw and (dropped := n_raw - len(df)):
            log.debug("scope %s: %d/%d eventos descartados (id ou data nula)", scope_id, dropped, n_raw)

        df = df.rename(columns={"ts": "timestamp"})
        df["scope_id"] = scope_id
        df["contributor_id"] = df["contributor_id"].astype("int64")
        df = df[EVENT_COLUMNS].reset_index(drop=True)
        return validate_canonical_schema(df, scope_id=scope_id)
