"""CSV de duas rodadas lado a lado (`antigo → novo`), para as tabelas da RQ2 refeitas com a carga nova.

Casa as linhas pelas colunas de chave. Grava o CSV completo (`<chave>`, `<coluna>_antigo`, `<coluna>_novo`) e devolve
o Markdown das linhas pedidas. Não interpreta nenhum número.

Uso como módulo: `from compara_csv import compara`.
"""

from pathlib import Path

import numpy as np
import pandas as pd


def numero(x: float) -> str:
    if pd.isna(x):
        return "n/d"
    if float(x).is_integer():
        return f"{int(x):,}".replace(",", ".")
    return f"{x:.4g}".replace(".", ",")


def celula(a: object, b: object) -> str:
    """`a` se iguais; `a → b` se diferentes. Número com tolerância relativa de 1e-9."""
    if isinstance(a, float | np.floating | int | np.integer) and isinstance(
        b, float | np.floating | int | np.integer
    ):
        if (
            (pd.isna(a) and pd.isna(b))
            or a == b
            or (not pd.isna(a) and not pd.isna(b) and abs(a - b) <= 1e-9 * max(1.0, abs(a)))
        ):
            return numero(a)
        return f"{numero(a)} → {numero(b)}"
    if (pd.isna(a) and pd.isna(b)) or a == b:
        return "n/d" if pd.isna(a) else str(a)
    return f"{'n/d' if pd.isna(a) else a} → {'n/d' if pd.isna(b) else b}"


def compara(
    antigo: Path,
    novo: Path,
    chaves: list[str],
    saida_csv: Path,
    consulta: str | None = None,
    colunas: list[str] | None = None,
) -> tuple[list[str], int, int]:
    """Linhas de Markdown das linhas pedidas, quantas linhas existem e quantas diferem em algum valor."""
    a = pd.read_csv(antigo)
    n = pd.read_csv(novo)
    juntos = a.merge(n, on=chaves, how="outer", suffixes=("_antigo", "_novo"))
    valores = [c for c in a.columns if c not in chaves and c in n.columns]
    diferentes = pd.Series(False, index=juntos.index)
    for coluna in valores:
        for i in juntos.index:
            texto = celula(juntos.at[i, f"{coluna}_antigo"], juntos.at[i, f"{coluna}_novo"])
            if "→" in texto:
                diferentes.at[i] = True
    juntos["mudou"] = diferentes
    saida_csv.parent.mkdir(parents=True, exist_ok=True)
    juntos.to_csv(saida_csv, index=False)
    mostra = juntos.query(consulta) if consulta else juntos
    colunas_mostradas = colunas or valores
    linhas = ["| " + " | ".join([*chaves, *colunas_mostradas]) + " |"]
    linhas.append("|" + "|".join("---" for _ in [*chaves, *colunas_mostradas]) + "|")
    for _, linha in mostra.iterrows():
        celulas = [str(linha[c]) for c in chaves]
        for coluna in colunas_mostradas:
            celulas.append(celula(linha[f"{coluna}_antigo"], linha[f"{coluna}_novo"]))
        linhas.append("| " + " | ".join(celulas) + " |")
    return linhas, len(juntos), int(diferentes.sum())
