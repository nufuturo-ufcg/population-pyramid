"""Hashes e duplicatas do arquivo bruto de Python, as duas pendências da checklist de outubro.

Lê em `<pasta>/dados/verificacao-outubro/`:
  - `sha_final.txt`: SHA-256 do arquivo final (`sha256sum`).
  - `partes/<parte>.sha256` e `duplicatas/<parte>.csv`: hash da parte reconstruída do arquivo final e
    as linhas repetidas por repositório e tipo (`duplicatas_eventos.py`).
  - `hashes/<origem>_<arquivo>.sha256`: SHA-256 dos arquivos de origem na AWS e na VM2.
Grava `<pasta>/hashes.md` e `<pasta>/secao_outubro.md`.

Uso (na raiz do repo): .venv/bin/python scripts/granularidade/resumo_outubro.py <correcao-elegibilidade>
"""

import csv
import sys
from pathlib import Path

PASTA = Path(sys.argv[1])
BASE = PASTA / "dados" / "verificacao-outubro"
PARTES = [
    ("aws_api", "parte1 (AWS)", "eventos_api.csv"),
    ("aws_git", "parte1 (AWS)", "eventos_git.csv"),
    ("b2_api", "parte2 (batuta)", "eventos_api.csv"),
    ("b2_git", "parte2 (batuta)", "eventos_git.csv"),
    ("b1_api", "parte1b (batuta)", "eventos_api.csv"),
    ("b1_git", "parte1b (batuta)", "eventos_git.csv"),
    ("vm2_api", "parte1c (VM2)", "eventos_api.csv"),
    ("vm2_git", "parte1c (VM2)", "eventos_git.csv"),
]
ORIGENS = {
    "aws_api": "aws_eventos_api.csv.sha256",
    "aws_git": "aws_eventos_git.csv.sha256",
    "vm2_api": "vm2_eventos_api.csv.sha256",
    "vm2_git": "vm2_eventos_git.csv.sha256",
}
FINAIS = {
    "aws": "aws_merge.sha256",
    "vm2": "vm2_eventos_repositorios.csv.sha256",
}


def milhar(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def le_hash(caminho: Path) -> str:
    texto = caminho.read_text(encoding="utf-8").split()
    return texto[0] if texto else ""


hash_final = le_hash(BASE / "sha_final.txt")
parte = {}
for chave, _, _ in PARTES:
    dados = (BASE / "partes" / f"{chave}.sha256").read_text(encoding="utf-8").split()
    parte[chave] = (dados[0], int(dados[1]))

linhas_hash = [
    "# Hashes do arquivo bruto de eventos de Python",
    "",
    "SHA-256 calculado em 2026-11-23, só com leitura.",
    "",
    "## Arquivo final (batuta, `~/dados-brutos/python/python-completo/eventos_python.csv`)",
    "",
    f"- `{hash_final}`",
    "",
    "## Partes",
    "",
    "A parte reconstruída é o cabeçalho mais o corpo e o trecho anexado dela no arquivo final (`MANIFESTO.txt`).",
    "A origem é o arquivo da própria máquina da coleta, na AWS e na VM2. Na batuta as origens foram apagadas depois de conferidas (`limpeza-parte2.log`, `agregar-b1.log`), e só existe o hash da parte reconstruída.",
    "",
    "| Parte | Arquivo | Bytes | SHA-256 da parte reconstruída | SHA-256 da origem | Igual |",
    "|---|---|---|---|---|---|",
]
resumo_hash = []
for chave, nome_parte, arquivo in PARTES:
    reconstruido, tamanho = parte[chave]
    origem = ""
    igual = "sem origem"
    if chave in ORIGENS:
        origem = le_hash(BASE / "hashes" / ORIGENS[chave])
        igual = "sim" if origem == reconstruido else "NÃO"
    linhas_hash.append(
        f"| {nome_parte} | {arquivo} | {milhar(tamanho)} | `{reconstruido}` | `{origem or 'n/d'}` | {igual} |"
    )
    resumo_hash.append((nome_parte, arquivo, tamanho, igual))
linhas_hash += [
    "",
    "## Arquivo final de cada máquina (junção `eventos_repositorios.csv`)",
    "",
    "| Máquina | SHA-256 |",
    "|---|---|",
]
for maquina, nome in FINAIS.items():
    linhas_hash.append(f"| {maquina} | `{le_hash(BASE / 'hashes' / nome)}` |")
linhas_hash += [
    "",
    "## Hash registrado na junção",
    "",
    "- O `MANIFESTO.txt` e os logs da junção registram só tamanhos em bytes (`esperado 343985220020 real 343985220020`) e a conferência do prefixo.",
    "- Não existe hash registrado para comparar. Os valores acima passam a ser o registro.",
]
(PASTA / "hashes.md").write_text("\n".join(linhas_hash) + "\n", encoding="utf-8")

# Duplicatas
por_parte = {}
repos_da_parte: dict[str, set[str]] = {}
partes_do_par: dict[tuple[str, str], set[str]] = {}
tipos: dict[str, dict[str, int]] = {}
for chave, nome_parte, _arquivo in PARTES:
    linhas_total = 0
    repetidas = 0
    repos_com_repeticao = set()
    repos = repos_da_parte.setdefault(nome_parte, set())
    tipos[chave] = {}
    with (BASE / "duplicatas" / f"{chave}.csv").open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            n = int(r["linhas"])
            rep = int(r["repetidas"])
            linhas_total += n
            repos.add(r["repo_id"])
            partes_do_par.setdefault((r["repo_id"], r["event_type"]), set()).add(nome_parte)
            if rep > 0:
                repetidas += rep
                repos_com_repeticao.add(r["repo_id"])
                tipos[chave][r["event_type"]] = tipos[chave].get(r["event_type"], 0) + rep
    por_parte[chave] = (linhas_total, repetidas, len(repos_com_repeticao))

secao = [
    "## 6. Hashes do arquivo bruto de Python",
    "",
    "Valores completos em `hashes.md`. O registro da junção tem só tamanhos em bytes, então não há hash antigo para comparar.",
    "",
    f"- Arquivo final: `{hash_final[:16]}...` (SHA-256 completo em `hashes.md`).",
    "",
    "| Parte | Arquivo | Bytes | Parte reconstruída igual à origem |",
    "|---|---|---|---|",
]
for nome_parte, arquivo, tamanho, igual in resumo_hash:
    secao.append(f"| {nome_parte} | {arquivo} | {milhar(tamanho)} | {igual} |")

secao += [
    "",
    "## 7. Linhas repetidas no arquivo bruto de Python",
    "",
    "Chave do evento: todas as colunas, menos `collection_started_at` (a de `verificar_duplicatas_eventos.py` da coleta). Conta as linhas além da primeira de cada evento.",
    "",
    "| Parte | Arquivo | Linhas | Repetidas | Repositórios com repetida |",
    "|---|---|---|---|---|",
]
soma_linhas = 0
soma_repetidas = 0
for chave, nome_parte, arquivo in PARTES:
    linhas_total, repetidas, n_repos = por_parte[chave]
    soma_linhas += linhas_total
    soma_repetidas += repetidas
    secao.append(
        f"| {nome_parte} | {arquivo} | {milhar(linhas_total)} | {milhar(repetidas)} | {milhar(n_repos)} |"
    )

nomes_partes = []
for _, nome_parte, _ in PARTES:
    if nome_parte not in nomes_partes:
        nomes_partes.append(nome_parte)
pares_em_duas_partes = 0
for onde_par in partes_do_par.values():
    if len(onde_par) > 1:
        pares_em_duas_partes += 1
em_varias = []
vistos: dict[str, list[str]] = {}
for nome_parte in nomes_partes:
    for repo in repos_da_parte[nome_parte]:
        vistos.setdefault(repo, []).append(nome_parte)
for repo, onde in vistos.items():
    if len(onde) > 1:
        em_varias.append((repo, onde))

secao += [
    "",
    f"- Arquivo final: {milhar(soma_linhas)} linhas, {milhar(soma_repetidas)} repetidas. A chave inclui o `repo_id`, então a contagem do final é a soma das partes quando nenhum repositório está em duas partes.",
    f"- Repositórios em mais de uma parte: {milhar(len(em_varias))}.",
    f"- Repositórios distintos no total: {milhar(len(vistos))}.",
    f"- Pares de repositório e tipo de evento presentes em mais de uma parte: {milhar(pares_em_duas_partes)}. Eventos do mesmo tipo e repositório em duas partes não existem, então não há duplicata entre partes.",
    "",
    "Repetidas por tipo de evento:",
    "",
    "| Parte | Arquivo | Tipo | Repetidas |",
    "|---|---|---|---|",
]
for chave, nome_parte, arquivo in PARTES:
    for tipo, n in sorted(tipos[chave].items(), key=lambda x: -x[1]):
        secao.append(f"| {nome_parte} | {arquivo} | {tipo} | {milhar(n)} |")
if soma_repetidas == 0:
    secao.append("| nenhuma | | | 0 |")
if em_varias:
    secao += [
        "",
        "Repositórios em mais de uma parte (até 20):",
        "",
        "| repo_id | Partes |",
        "|---|---|",
    ]
    for repo, onde in em_varias[:20]:
        secao.append(f"| {repo} | {', '.join(onde)} |")

(PASTA / "secao_outubro.md").write_text("\n".join(secao) + "\n", encoding="utf-8")
print("\n".join(secao))
