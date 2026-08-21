"""Carga de config/*.yaml. Nenhum parâmetro de método fica no código.

Credencial de banco NÃO mora aqui: é detalhe de um adaptador específico e vive
em `adapters/<nome>/source.py`, porque o motor de cálculo não conhece a origem
dos dados.
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime
from functools import cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config"
OUTPUT_DIR = ROOT / "output"
RUNS_DIR = OUTPUT_DIR / "runs"
LOG_DIR = ROOT / "logs"


class _Estado:
    """O que vale só para esta execução e não está versionado em `config/`.

    `run = None` significa saída canônica: `output/<estágio>/`, que é o que os
    docs embutem e o que o validate compara.

    `janela = (None, None)` significa a janela de tempo de `settings.yaml`.
    """

    run: Path | None = None
    janela: tuple[str | None, str | None] = (None, None)


_estado = _Estado()


@cache
def settings() -> dict:
    """Parâmetros de método, lidos uma vez por processo de `config/settings.yaml`."""
    return yaml.safe_load((CONFIG_DIR / "settings.yaml").read_text())


UNITS_IMPLEMENTADAS = ("project", "language")


def analysis_unit() -> str:
    """Unidade de análise da saída, de `analysis.unit`.

    Valor sem agregador implementado falha aqui. Quem soma os escopos de cada
    unidade é `pyramid.units.scopes_of_unit`, e aceitar um valor sem agregador
    entregaria uma pirâmide por projeto com o nome de outra coisa.
    """
    unit = str(settings().get("analysis", {}).get("unit", "project"))
    if unit not in UNITS_IMPLEMENTADAS:
        raise ValueError(
            f"analysis.unit={unit!r} sem agregador. "
            f"Implementadas: {', '.join(UNITS_IMPLEMENTADAS)}."
        )
    return unit


def set_window(inicio: str | None = None, fim: str | None = None) -> None:
    """Guarda a janela de tempo pedida na linha de comando, válida nesta execução.

    Mora no estado do processo em vez de entrar em `settings()`. `settings()` é
    o YAML lido do disco, e um pedido de terminal não pode se disfarçar de
    valor versionado: o que a pessoa digitou some quando o processo acaba, e o
    arquivo continua descrevendo a janela publicada. `snapshots.window()` junta
    os dois na hora de gerar a série.

    Data vazia mantém a ponta correspondente como está na config, então dá para
    mexer só no começo ou só no fim.
    """
    _estado.janela = (inicio or None, fim or None)


def window_override() -> tuple[str | None, str | None]:
    """Janela pedida na CLI, `(None, None)` quando ninguém pediu nada."""
    return _estado.janela


@cache
def checkpoints() -> dict:
    """Valores publicados nos artigos e travas da replicação, de `config/checkpoints.yaml`."""
    return yaml.safe_load((CONFIG_DIR / "checkpoints.yaml").read_text())


def _pasta_da_unidade() -> Path | None:
    """Subpasta que separa a saída de cada unidade de análise, ou `None`.

    O nome do parquet é `<scope_id>.parquet` em todo estágio. Id de projeto e id
    de linguagem são inteiros pequenos e colidem nesse nome, então a saída de
    duas unidades na mesma pasta se sobrescreve em silêncio. Pior: `_ids_gravados`
    lista o diretório com `glob("*.parquet")` e leria as duas como se fossem uma
    população só.

    `project` devolve `None` e a saída fica exatamente onde sempre esteve. É o
    que mantém a replicação MSR14 byte a byte no mesmo caminho.
    """
    unit = analysis_unit()
    return None if unit == "project" else Path(f"by-{unit}")


def _pasta_do_adaptador() -> Path | None:
    """Subpasta que separa a saída de cada fonte de dados, ou `None`.

    Dois adaptadores gravam `<scope_id>.parquet` no mesmo estágio. Os ids não se
    sobrescrevem, porque cada fonte numera do jeito dela, e é por isso que o modo
    de falha é pior: `_ids_gravados` lista o diretório e empilha as duas
    populações como se fossem uma, produzindo pirâmide de gente que nunca esteve
    junta.

    Qual adaptador fica na raiz de `output/` é decisão de dado, então mora em
    `config/settings.yaml`, na chave `output.adapter_sem_subpasta`. O motor não
    carrega nome de dataset.
    """
    cfg = settings()
    adaptador = str((cfg.get("input") or {}).get("adapter", ""))
    na_raiz = str((cfg.get("output") or {}).get("adapter_sem_subpasta", ""))
    if not adaptador or adaptador == na_raiz:
        return None
    return Path(adaptador)


def _com_unidade(base: Path, stage: str) -> Path:
    """Caminho do estágio, com a subpasta da fonte e a da unidade quando houver.

    A ordem é `output/[<adaptador>/][by-<unidade>/]<estágio>/`. A fonte declarada
    em `output.adapter_sem_subpasta` rodando em `project` devolve `output/<estágio>/`,
    que é onde a replicação sempre gravou.
    """
    d = base
    for pasta in (_pasta_do_adaptador(), _pasta_da_unidade()):
        if pasta is not None:
            d = d / pasta
    d = d / stage
    d.mkdir(parents=True, exist_ok=True)
    return d


def stage_dir(stage: str) -> Path:
    """Diretório canônico do estágio, criado na primeira chamada.

    É onde ficam os parquets que os estágios seguintes leem como entrada. Uma
    execução isolada (ver `start_run`) não move esses arquivos de lugar: mover
    quebraria a cadeia extract -> snapshots -> classify -> metrics.
    """
    return _com_unidade(OUTPUT_DIR, stage)


def artifact_dir(stage: str) -> Path:
    """Onde este estágio grava entregável (figura, tabela, relatório).

    Sem execução aberta devolve o mesmo que `stage_dir`. Com uma execução
    aberta devolve `output/runs/<carimbo>/<estágio>/`, e aí a execução anterior
    continua inteira no lugar dela.

    Leva a mesma subpasta de unidade que `stage_dir`, porque o manifesto mora
    aqui (`logging_config._path`). Sem isso, uma execução por linguagem
    sobrescreveria o `_manifest.json` da execução por projeto, e o
    `extract.scope_meta()` passaria a descrever os escopos errados.
    """
    return _com_unidade(_estado.run or OUTPUT_DIR, stage)


def run_dir() -> Path | None:
    """Pasta da execução aberta, ou `None` quando a saída é a canônica."""
    return _estado.run


def start_run(rotulo: str = "", *, comando: str = "") -> Path:
    """Abre `output/runs/<AAAAMMDD-HHMMSS>[-rótulo]/` para receber os entregáveis.

    Serve para rodar sem sobrescrever o resultado publicado: comparar duas
    configurações, guardar a saída de uma auditoria, testar uma hipótese. O
    ponteiro `output/runs/latest` passa a apontar para a pasta criada.
    """
    carimbo = datetime.now().strftime("%Y%m%d-%H%M%S")
    nome = f"{carimbo}-{rotulo}" if rotulo else carimbo
    destino = RUNS_DIR / nome
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "_run.json").write_text(
        json.dumps(_metadados(nome, comando), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    _estado.run = destino
    _apontar_latest(destino)
    return destino


def end_run() -> None:
    """Fecha a execução aberta. A saída volta a ser a canônica."""
    _estado.run = None


def _metadados(nome: str, comando: str) -> dict:
    """O mínimo para alguém entender de onde veio a pasta seis meses depois."""
    return {
        "run": nome,
        "criado_em": datetime.now().astimezone().isoformat(timespec="seconds"),
        "comando": comando,
        "commit": _commit(),
        "dataset_source": os.environ.get("DATASET_SOURCE", ""),
    }


def _commit() -> str:
    """Hash do commit em que a execução rodou. Vazio fora de um clone git."""
    try:
        r = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def _apontar_latest(destino: Path) -> None:
    """`output/runs/latest` aponta para a execução mais recente.

    Sistema de arquivos sem symlink cai no `latest.txt` com o nome da pasta.
    O ponteiro é conveniência de terminal, então falhar aqui não derruba a
    execução que já está gravando.
    """
    link = RUNS_DIR / "latest"
    try:
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(destino.name)
    except OSError:
        (RUNS_DIR / "latest.txt").write_text(destino.name + "\n", encoding="utf-8")
