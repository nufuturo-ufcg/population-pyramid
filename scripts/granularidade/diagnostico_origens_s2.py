"""Diagnóstico das origens do S2 (projecao-rq3, parte 2a): por origem de dezembro, que faixa com gente fica sem taxa de permanência e quanto a parada de repositórios soma.

Uso (na raiz do repo, na VM): .venv/bin/python scripts/granularidade/diagnostico_origens_s2.py <carga> clojure elixir ocaml python zig
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, "src")
from estado import FIM, constroi_estado
from estado import junta_aberta_vet as junta
from previsao import taxas, taxas_sem_parada
from rodar import le_dados

carga = Path(sys.argv[1])
for lingua in sys.argv[2:]:
    pessoas, eventos = le_dados(carga, lingua)
    est = constroi_estado(
        pessoas, eventos, 12, "P1", FIM, janela_blocos=None, idade="descontada", com_parada=True
    )
    datas, ativas = est["datas"], est["ativas"]
    primeiro_ativo = int(np.argmax(ativas > 0))
    print(
        f"== {lingua}: recortes {datas[0]} a {datas[-1]}, primeiro recorte com ativos: {datas[primeiro_ativo]}"
    )
    for k in range(primeiro_ativo + 1, len(datas)):
        atual = junta(est["pop_p_b"][k])
        sr = taxas(est["pop_p_b"][k], est["pop_p_b"][k - 1])
        bloqueia = [int(i) for i in np.where((atual > 0) & np.isnan(sr))[0]]
        ocupadas = [int(i) for i in np.where(atual > 0)[0]]
        if k - 1 >= primeiro_ativo + 1:
            sr2 = taxas_sem_parada(est["pop_p_b"][k], est["pop_p_b"][k - 1], est["ORF_b"][k])
            bloqueia_sp = [int(i) for i in np.where((atual > 0) & np.isnan(sr2))[0]]
        else:
            bloqueia_sp = None
        q = est["Q_b"][k]
        print(
            f"  origem {datas[k]}: ativos {int(ativas[k])}, faixas com gente {ocupadas}, sem taxa (coorte) {bloqueia}, sem taxa (sem parada) {bloqueia_sp}, saída por parada somada {float(q.sum()):.1f}"
        )
