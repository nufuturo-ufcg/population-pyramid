"""Log estruturado (JSON lines) + manifesto de retomada por estágio."""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import LOG_DIR, stage_dir


class JsonLines(logging.Formatter):
    """Formata cada registro como uma linha JSON, com os campos do domínio."""

    def format(self, r: logging.LogRecord) -> str:
        """Serializa o registro em JSON de uma linha."""
        d: dict[str, Any] = {
            "ts": datetime.fromtimestamp(r.created, UTC).isoformat(),
            "level": r.levelname,
            "logger": r.name,
            "msg": r.getMessage(),
        }
        for k in ("scope_id", "stage", "contributor_id", "snapshot"):
            if (v := getattr(r, k, None)) is not None:
                d[k] = v
        if r.exc_info:
            d["traceback"] = self.formatException(r.exc_info)
        return json.dumps(d, ensure_ascii=False, default=str)


def setup(level: str = "INFO") -> Path:
    """Liga o log em arquivo JSON e no terminal. Devolve o caminho do arquivo."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = LOG_DIR / f"run_{datetime.now(UTC):%Y%m%dT%H%M%SZ}.log"

    fh = logging.FileHandler(path, encoding="utf-8")
    fh.setFormatter(JsonLines())

    sh = logging.StreamHandler(sys.stderr)
    sh.setFormatter(logging.Formatter("%(levelname)-7s %(name)-22s %(message)s"))

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level.upper())
    root.addHandler(fh)
    root.addHandler(sh)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    return path


# --- manifesto ----------------------------------------------------------------
# Cada estágio grava o que concluiu. `--force` reprocessa tudo; sem ele, unidades
# já feitas são puladas. Falha numa unidade não aborta o run inteiro (a não ser
# com --fail-fast): marca no manifesto e segue, pra saber onde retomar.


def _path(stage: str) -> Path:
    return stage_dir(stage) / "_manifest.json"


def load(stage: str) -> dict:
    """Manifesto do estágio. Devolve um manifesto vazio quando ainda não houver arquivo."""
    p = _path(stage)
    if not p.exists():
        return {"stage": stage, "ok": {}, "failed": {}}
    return json.loads(p.read_text())


def save(stage: str, man: dict) -> None:
    """Grava o manifesto do estágio com o horário da execução."""
    man["updated_at"] = datetime.now(UTC).isoformat()
    # A quebra final deixa o arquivo estável sob o hook end-of-file-fixer: sem
    # ela, hook e pipeline reescreviam o manifesto um atrás do outro.
    _path(stage).write_text(json.dumps(man, indent=2, ensure_ascii=False, default=str) + "\n")


def summarize(stage: str, man: dict) -> str:
    """Linha de resumo do manifesto para o terminal."""
    ok, bad = len(man.get("ok", {})), len(man.get("failed", {}))
    s = f"[{stage}] {ok} ok, {bad} falhas"
    if bad:
        s += " -> " + ", ".join(list(man["failed"])[:5]) + ("..." if bad > 5 else "")
    return s
