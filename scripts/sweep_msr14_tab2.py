import argparse
"""§35 — pontua hipoteses de 'novato'/atividade contra a GRADE INTEIRA da
Tabela 2 do MSR14 (12 projetos x 8 anos), nao contra os 5 projetos nomeados.

Nao escreve nada no repo.
"""
import numpy as np
import pandas as pd

from pyramid.attractiveness import activity, _retained
from pyramid.config import checkpoints, settings
from pyramid.extract import source

LETRA = {"A": "attractive", "F": "floating", "S": "stagnant", "T": "terminal"}
COD = ["commits", "pull_requests"]
TUDO = COD + ["commit_comments", "issue_comments", "pull_request_comments", "issue_events"]


def annual(pairs, first_year, tot=None, min_devs=10, sticky="project", tie="baixo"):
    pairs = pairs.drop_duplicates()
    per = (
        pairs.assign(_nov=pairs["contributor_id"].map(first_year) == pairs["year"])
        .groupby(["scope_id", "year"], as_index=False)
        .agg(devs=("contributor_id", "nunique"), nh=("_nov", "sum"))
    )
    tot = first_year.value_counts() if tot is None else tot
    per["tot"] = per["year"].map(tot).fillna(0).astype("int64")
    ret = (
        _retained(pairs, sticky)
        .groupby(["scope_id", "year"], as_index=False)
        .agg(retained=("contributor_id", "nunique"))
    )
    per = per.merge(ret, on=["scope_id", "year"], how="left")
    per["retained"] = per["retained"].fillna(0).astype("int64")
    per["m"] = np.where(per["tot"] > 0, per["nh"] / per["tot"], np.nan)
    per["s"] = np.where(per["devs"] > 0, per["retained"] / per["devs"], np.nan)
    per.loc[per["year"] >= int(pairs["year"].max()), "s"] = np.nan
    per["el"] = (per["devs"] > min_devs) & per["m"].notna() & per["s"].notna()
    el = per[per["el"]]
    mm = per["year"].map(el.groupby("year")["m"].median())
    ms = per["year"].map(el.groupby("year")["s"].median())
    q = [
        {(1, 1): "attractive", (1, 0): "floating", (0, 1): "stagnant", (0, 0): "terminal"}[
            (int(a > b or (tie == "alto" and a == b)), int(c > d or (tie == "alto" and c == d)))
        ]
        for a, b, c, d in zip(per["m"], mm, per["s"], ms)
    ]
    per["quadrant"] = [x if e else "*" for x, e in zip(q, per["el"])]
    return per


def pontua(per, verbose=False):
    c = checkpoints()["msr14_tab2"]
    anos = list(c["years"])
    src = source()
    por_nome = {src.scope_label(s): s for s in src.list_scopes()}
    cel = {(int(r.scope_id), int(r.year)): r.quadrant for r in per.itertuples()}
    letras_ok = letras_n = est_ok = est_n = 0
    erros = []
    for nome, linha in c["grid"].items():
        sid = por_nome.get(nome)
        for ano, esp in zip(anos, str(linha).split()):
            got = "-" if sid is None else cel.get((int(sid), ano), "-")
            if esp in {"-", "*"}:
                est_n += 1
                est_ok += got == esp
                continue
            letras_n += 1
            alvo = LETRA[esp]
            obtido = LETRA.get(got, got)
            if obtido == alvo:
                letras_ok += 1
            else:
                erros.append(f"{nome} {ano}: artigo {alvo} / obtido {obtido}")
    if verbose:
        print("\n".join("      " + e for e in erros))
    return letras_ok, letras_n, est_ok, est_n


def main():
    p_cod, _ = activity(events=COD)
    p_tudo, _ = activity(events=TUDO)
    fy_cod = p_cod.groupby("contributor_id")["year"].min()
    fy_tudo = p_tudo.groupby("contributor_id")["year"].min()

    # novato local: estreia NESTE projeto; denominador = pares (projeto,novato)
    loc = p_cod.copy()
    loc["_fy"] = loc.groupby(["scope_id", "contributor_id"]).year.transform("min")

    CEN = [
        ("A  atual: novato=1o codigo, global", p_cod, fy_cod, None),
        ("B  novato = 1o evento de qualquer tipo", p_cod, fy_tudo, None),
        ("C  novato e projeto = qualquer evento", p_tudo, fy_tudo, None),
    ]
    print(f"{'variante':<40} {'letras':>10}  {'estrutura':>10}")
    for nome, pairs, fy, tot in CEN:
        per = annual(pairs, fy, tot)
        lo, ln, eo, en = pontua(per)
        print(f"{nome:<40} {lo:>6}/{ln:<3} {eo:>6}/{en:<3}")

    # D: novato local (§15) — precisa de caminho proprio
    per = annual(p_cod, fy_cod)  # placeholder p/ estrutura
    d = p_cod.drop_duplicates().copy()
    d["_nov"] = d.groupby(["scope_id", "contributor_id"]).year.transform("min") == d["year"]
    perd = (
        d.groupby(["scope_id", "year"], as_index=False)
        .agg(devs=("contributor_id", "nunique"), nh=("_nov", "sum"))
    )
    perd["tot"] = perd["year"].map(d.groupby("year")._nov.sum()).fillna(0)
    ret = (
        _retained(p_cod.drop_duplicates(), "project")
        .groupby(["scope_id", "year"], as_index=False)
        .agg(retained=("contributor_id", "nunique"))
    )
    perd = perd.merge(ret, on=["scope_id", "year"], how="left")
    perd["retained"] = perd["retained"].fillna(0)
    perd["m"] = perd["nh"] / perd["tot"]
    perd["s"] = perd["retained"] / perd["devs"]
    perd.loc[perd["year"] >= int(d["year"].max()), "s"] = np.nan
    perd["el"] = (perd["devs"] > 10) & perd["m"].notna() & perd["s"].notna()
    el = perd[perd["el"]]
    mm = perd["year"].map(el.groupby("year")["m"].median())
    ms = perd["year"].map(el.groupby("year")["s"].median())
    perd["quadrant"] = [
        ({(1, 1): "attractive", (1, 0): "floating", (0, 1): "stagnant", (0, 0): "terminal"}[
            (int(a > b), int(c > dd))] if e else "*")
        for a, b, c, dd, e in zip(perd["m"], mm, perd["s"], ms, perd["el"])
    ]
    lo, ln, eo, en = pontua(perd)
    print(f"{'D  novato local (estreia no projeto)':<40} {lo:>6}/{ln:<3} {eo:>6}/{en:<3}")

    print("\nerros da variante A (baseline):")
    pontua(annual(p_cod, fy_cod), verbose=True)


def sweep(args):
    p, _ = activity(events=COD)
    fy = p.groupby("contributor_id")["year"].min()
    per = annual(p, fy, min_devs=args.min_devs, sticky=args.sticky, tie=args.tie)
    lo, ln, eo, en = pontua(per, verbose=args.errors)
    print(f"min_devs={args.min_devs} tie={args.tie} sticky={args.sticky}"
          f"  ->  letras {lo}/{ln}   estrutura {eo}/{en}")


def cli():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--min-devs", type=int, default=10, dest="min_devs")
    ap.add_argument("--tie", choices=["baixo", "alto"], default="baixo")
    ap.add_argument("--sticky", choices=["project", "dataset"], default="project")
    ap.add_argument("--errors", action="store_true")
    ap.add_argument("--novato", action="store_true", help="varre as 4 definicoes de novato (A-D)")
    args = ap.parse_args()
    main() if args.novato else sweep(args)


if __name__ == "__main__":
    cli()
