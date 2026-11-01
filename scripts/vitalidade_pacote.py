"""Junta os resultados de vitalidade num `.tar.gz` e abre o pacote em outra máquina.

Os cálculos pesados rodam onde os dados estão (a batuta). O pacote leva só o que
`--so-figuras` precisa para desenhar em qualquer lugar:

  <linguagem>/resultados/vitalidade/   tabelas em parquet e meta.json
  <linguagem>/csv/vitalidade/          as mesmas tabelas em CSV
  geral/resultados/vitalidade/         as comparações entre linguagens
  geral/csv/vitalidade/

Ficam de fora o cache dos eventos (GB), a pasta de trabalho e as figuras (se redesenham).
"""

from __future__ import annotations

import json
import subprocess
import tarfile
from datetime import datetime
from pathlib import Path

PADROES = [
    "*/resultados/vitalidade",
    "*/csv/vitalidade",
]


def _pastas_do_pacote(base: Path) -> list[Path]:
    pastas = []
    for padrao in PADROES:
        pastas.extend(sorted(base.glob(padrao)))
    return pastas


def _commit(repositorio: Path) -> str:
    try:
        saida = subprocess.run(
            ["git", "-C", str(repositorio), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "desconhecido"
    return saida.stdout.strip()


def empacota(base: Path, destino: Path | None = None) -> Path:
    """Cria o `.tar.gz` com os resultados de `base` e devolve o caminho."""
    pastas = _pastas_do_pacote(base)
    if not pastas:
        raise SystemExit(f"{base}: sem resultados para empacotar. Rode as métricas antes.")
    if destino is None:
        destino = base / f"vitalidade-resultados-{datetime.now():%Y-%m-%d-%H%M}.tar.gz"
    arquivos = []
    for pasta in pastas:
        for arquivo in sorted(pasta.rglob("*")):
            if arquivo.is_file():
                arquivos.append(arquivo)
    manifesto = {
        "criado_em": datetime.now().isoformat(timespec="seconds"),
        "commit": _commit(Path(__file__).resolve().parent.parent),
        "pastas": [str(p.relative_to(base)) for p in pastas],
        "arquivos": len(arquivos),
        "bytes": sum(a.stat().st_size for a in arquivos),
    }
    caminho_manifesto = base / "MANIFESTO-vitalidade.json"
    caminho_manifesto.write_text(json.dumps(manifesto, indent=2, ensure_ascii=False))
    with tarfile.open(destino, "w:gz") as tar:
        tar.add(caminho_manifesto, arcname=caminho_manifesto.name)
        for arquivo in arquivos:
            tar.add(arquivo, arcname=str(arquivo.relative_to(base)))
    print(f"pacote: {destino} ({destino.stat().st_size / 1e6:.1f} MB, {len(arquivos)} arquivos)")
    return destino


def importa(pacote: Path, base: Path) -> None:
    """Abre o pacote dentro de `base`. Só aceita caminhos relativos, sem sair de `base`."""
    base.mkdir(parents=True, exist_ok=True)
    with tarfile.open(pacote, "r:gz") as tar:
        tar.extractall(base, filter="data")
    print(f"pacote aberto em {base}")
