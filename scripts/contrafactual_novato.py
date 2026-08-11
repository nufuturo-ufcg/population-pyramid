"""Contrafactual do §15: novato do dataset (atual) vs novato do projeto.

Reclassifica os 12 projetos da Tabela 2 do MSR14 (2004-2011) sob as duas
definições e compara com o gabarito publicado. Não toca no repositório.

    DATASET_DIR=$DATASET_DIR .venv/bin/python scripts/contrafactual_novato.py
"""

from __future__ import annotations

from pyramid import attractiveness as at
from pyramid.config import checkpoints
from pyramid.extract import source

cfg = checkpoints()["msr14_tab2"]
anos = cfg["years"]
pairs, _ = at.activity()
pairs = pairs.drop_duplicates()
src = source()
ids = {src.scope_label(s): s for s in src.list_scopes()}


def grid(local: bool) -> dict[tuple[int, int], str]:
    p = pairs.copy()
    if local:
        # novato = primeira aparição NESTE projeto; denominador = pares
        # (projeto, novato) do ano, porque a mesma pessoa pode estrear
        # em dois projetos no mesmo ano.
        fy = p.groupby(["scope_id", "contributor_id"]).year.transform("min")
        p["_nov"] = fy == p.year
        tot = p.groupby("year")._nov.sum()
    else:
        fy = p.contributor_id.map(p.groupby("contributor_id").year.min())
        p["_nov"] = fy == p.year
        tot = p[p._nov].groupby("year").contributor_id.nunique()

    per = p.groupby(["scope_id", "year"], as_index=False).agg(
        devs=("contributor_id", "nunique"), nh=("_nov", "sum")
    )
    per["mag"] = per.nh / per.year.map(tot)

    nxt = p[["scope_id", "contributor_id", "year"]].assign(year=lambda d: d.year - 1)
    ret = (
        p.merge(nxt, on=["scope_id", "contributor_id", "year"])
        .groupby(["scope_id", "year"], as_index=False)
        .contributor_id.nunique()
        .rename(columns={"contributor_id": "ret"})
    )
    per = per.merge(ret, how="left").fillna({"ret": 0})
    per["stk"] = per.ret / per.devs

    out: dict[tuple[int, int], str] = {}
    for y in anos:
        s = per[per.year == y]
        el = s[s.devs > 10]  # mesmo min_active_devs do config
        mm, ms = el.mag.median(), el.stk.median()
        for _, r in s.iterrows():
            # mesma convenção de attractiveness.annual: alto = ESTRITAMENTE
            # maior que a mediana; empate cai do lado baixo.
            if r.devs <= 10:
                out[(int(r.scope_id), y)] = "*"
            elif r.mag > mm:
                out[(int(r.scope_id), y)] = "A" if r.stk > ms else "F"
            else:
                out[(int(r.scope_id), y)] = "S" if r.stk > ms else "T"
    return out


def ancora() -> None:
    """A variante G deste script TEM que ser byte a byte o que o repo faz.

    Sem isto, a comparação G-vs-P mediria a diferença entre duas
    reimplementações, não a diferença entre duas definições de novato.
    """
    mapa = {"attractive": "A", "floating": "F", "stagnant": "S", "terminal": "T"}
    ann = at.annual(pairs.copy(), None)
    repo = {
        (int(r.scope_id), int(r.year)): mapa.get(r.quadrant, "*")
        for _, r in ann.iterrows()
        if int(r.year) in anos
    }
    g = grid(local=False)
    alvo = [(ids[n], y) for n in cfg["grid"] if n in ids for y in anos]
    dif = [k for k in alvo if repo.get(k, "-") != g.get(k, "-")]
    assert not dif, f"variante G diverge de annual() em {dif}"
    print(f"âncora: G == attractiveness.annual() em {len(alvo)}/{len(alvo)} células\n")


def main() -> None:
    ancora()
    for tag, local in [("G global (atual)", False), ("P por projeto", True)]:
        g = grid(local)
        acertos = total = 0
        falhas = []
        for nome, linha in cfg["grid"].items():
            sid = ids.get(nome)
            for y, esperado in zip(anos, str(linha).split(), strict=True):
                if esperado in "-*":
                    continue  # célula não classificada pelo artigo
                got = g.get((sid, y), "-")
                total += 1
                acertos += got == esperado
                if got != esperado:
                    falhas.append(f"{y} {nome.split('/')[-1]}:{got}!={esperado}")
        print(f"{tag:18s} {acertos}/{total} ({acertos / total:.0%})")
        print("   falhas:", ", ".join(falhas), "\n")


if __name__ == "__main__":
    main()
