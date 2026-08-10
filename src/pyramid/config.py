"""Carga de config/*.yaml. Nenhum parâmetro de método fica no código.

Credencial de banco NÃO mora aqui: é detalhe de uma fonte específica e vive em
sources/msr14.py (seção 8 da spec: o motor de cálculo não conhece a origem
dos dados).
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config"
OUTPUT_DIR = ROOT / "output"
LOG_DIR = ROOT / "logs"


@cache
def settings() -> dict:
    return yaml.safe_load((CONFIG_DIR / "settings.yaml").read_text())


@cache
def checkpoints() -> dict:
    return yaml.safe_load((CONFIG_DIR / "checkpoints.yaml").read_text())


def stage_dir(stage: str) -> Path:
    d = OUTPUT_DIR / stage
    d.mkdir(parents=True, exist_ok=True)
    return d
