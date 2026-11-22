"""Teste com dados sintéticos (sem a VM): grade, vazamento, populações e comparação com o script antigo.

  1. Gera uma linguagem sintética (pessoas, repositórios e eventos por dia) e a grava no formato da carga.
  2. P0 com passo de 12 meses: V0 a V4 (ingênua, coorte, pessimista, conservador e otimista) conferem com `projecao-variantes-passos/scripts/variantes_passos.py`
     (rodado sobre os mesmos dados, sem as conferências com a rodada oficial) nas origens de dezembro.
  3. Teste de vazamento em P1 e P2, em todos os passos (12, 6, 3, 2, 1 e 0,5 mês), com os controles de vazamento de propósito: eventos futuros (P1 e P2) e promoções a residente (P1).
     O teste só vale no passo em que o controle difere; o script falha se algum passo tem controle que não difere.
  4. P2 tem pelo menos os ativos de P1 em todo bloco; as faixas somam o total.
  5. Versão B (faixas do passo): em 12 meses A e B têm as mesmas pirâmides e `rodar.py` confere que todos os métodos da B igualam os da A (para se não igualarem);
     a B passa pelo teste de vazamento e pelos controles.

Uso (na raiz do repo): .venv/bin/python <este arquivo> <pasta temporária>
"""

import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

AQUI = Path(__file__).resolve().parent
EXPERIMENTOS = Path.home() / "Documents" / "pyramid-vitalidade"
sys.path.insert(0, str(AQUI))
sys.path.insert(0, "src")
import rodar  # noqa: E402
from estado import FIM, constroi_estado, grade  # noqa: E402

VELHO = EXPERIMENTOS / "projecao-variantes-passos" / "scripts" / "variantes_passos.py"


def gera_linguagem(
    semente: int = 7, n_pessoas: int = 2500, n_repos: int = 120
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Pessoas e eventos (pessoa, codigo, dia) de uma linguagem que cresce de 2008 a 2024."""
    rng = np.random.default_rng(semente)
    anos = np.arange(2008, 2025)
    pesos = 1.18 ** (anos - 2008)
    criacao = np.sort(rng.choice(anos[:-2], size=n_repos))
    linhas = []
    for p in range(n_pessoas):
        chegada = int(rng.choice(anos, p=pesos / pesos.sum()))
        casual = rng.random() < 0.35
        disponiveis = np.where(criacao <= chegada)[0]
        if len(disponiveis) == 0:
            disponiveis = np.array([0])
        casa = int(rng.choice(disponiveis))
        vida = 1 if casual else int(rng.integers(1, 9))
        for ano in range(chegada, min(chegada + vida, 2025)):
            if not casual and rng.random() > 0.65 and ano != chegada:
                continue
            n_eventos = 1 if casual else 1 + int(rng.poisson(5))
            for _ in range(n_eventos):
                dia = np.datetime64(f"{ano}-01-01") + np.timedelta64(int(rng.integers(0, 365)), "D")
                if ano == chegada and not linhas:
                    pass
                repos_ano = np.where(criacao <= ano)[0]
                if len(repos_ano) == 0:
                    repos_ano = np.array([0])
                codigo = casa if rng.random() < 0.7 else int(rng.choice(repos_ano))
                linhas.append((100000 + p, codigo, dia))
        if (
            casual and chegada < 2024 and rng.random() < 0.4
        ):  # volta no ano seguinte: vira residente ao longo do ano seguinte
            dia = np.datetime64(f"{chegada + 1}-01-01") + np.timedelta64(
                int(rng.integers(0, 365)), "D"
            )
            linhas.append((100000 + p, casa, dia))
    eventos = pd.DataFrame(linhas, columns=["pessoa", "codigo", "dia"]).drop_duplicates()
    eventos = eventos[eventos["dia"] <= np.datetime64("2024-12-31")]
    eventos = eventos.sort_values(["pessoa", "dia", "codigo"]).reset_index(drop=True)
    pessoas = []
    for pessoa, g in eventos.groupby("pessoa"):
        ocasioes = g[["codigo", "dia"]].drop_duplicates().sort_values("dia")
        datas_ocasioes = ocasioes["dia"].to_numpy()
        primeiro = g.iloc[0]
        pessoas.append(
            (
                pessoa,
                pd.Timestamp(primeiro["dia"]),
                len(ocasioes),
                int(primeiro["codigo"]),
                pd.Timestamp(datas_ocasioes[1]) if len(ocasioes) > 1 else pd.NaT,
            )
        )
    pessoas = pd.DataFrame(
        pessoas, columns=["pessoa", "primeiro", "ocasioes", "codigo_do_primeiro", "segunda_ocasiao"]
    )
    return pessoas, eventos


def grava_carga(pessoas: pd.DataFrame, eventos: pd.DataFrame, pasta: Path) -> None:
    origem = pasta / "sint" / "origem"
    origem.mkdir(parents=True, exist_ok=True)
    pessoas.to_parquet(origem / "pessoas.parquet", index=False)
    dia = pd.to_datetime(eventos["dia"])
    por_dia = pd.DataFrame(
        {"pessoa": eventos["pessoa"], "codigo": eventos["codigo"], "dia": dia.dt.date}
    )
    por_dia.to_parquet(origem / "pessoas_repos_por_dia.parquet", index=False)
    trimestre = ((dia.dt.year - 2008) * 4 + dia.dt.quarter - 1).astype("int16")
    pd.DataFrame(
        {"pessoa": eventos["pessoa"], "codigo": eventos["codigo"], "trimestre": trimestre}
    ).drop_duplicates().to_parquet(origem / "pessoas_repos_por_trimestre.parquet", index=False)


def roda_script_antigo(pasta: Path) -> pd.DataFrame:
    texto = VELHO.read_text(encoding="utf-8")
    texto = re.sub(r"^(\s*)assert .*$", r"\1pass", texto, flags=re.M)
    inicio = texto.index('                if passo == 12 and q % 4 == 3 and v == "V0":')
    fim = texto.index('    print(f"{LINGUA}: passo {passo} pronto"')
    texto = texto[:inicio] + texto[fim:]
    script = pasta / "velho_sem_conferencias.py"
    script.write_text(texto, encoding="utf-8")
    rodada = pasta / "rodada"
    (
        rodada
        / "sint-mais_de_uma_ocasiao"
        / "csv"
        / "vitalidade"
        / "cenarios-contagem-5anos-recentes"
    ).mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"ano": [2008], "ativos": [0], "novatos": [0]}).to_csv(
        rodada / "sint-mais_de_uma_ocasiao" / "csv" / "vitalidade" / "anual.csv", index=False
    )
    pd.DataFrame({"teto": [], "ano": [], "faixa": []}).to_csv(
        rodada
        / "sint-mais_de_uma_ocasiao"
        / "csv"
        / "vitalidade"
        / "cenarios-contagem-5anos-recentes"
        / "projecao_backtest.csv",
        index=False,
    )
    saida = pasta / "saida_velha"
    subprocess.run(
        [
            sys.executable,
            str(script),
            str(rodada),
            str(pasta / "sint" / "origem"),
            str(saida),
            "sint",
        ],
        check=True,
        capture_output=True,
    )
    return pd.read_csv(saida / "passos_sint.csv")


def main() -> None:
    TMP = Path(sys.argv[1])
    TMP.mkdir(parents=True, exist_ok=True)
    pessoas_brutas, eventos_brutos = gera_linguagem()
    grava_carga(pessoas_brutas, eventos_brutos, TMP)
    print(
        f"sintético: {len(pessoas_brutas)} pessoas, {len(eventos_brutos)} pares pessoa-repositório-dia"
    )
    assert [len(grade(m)) for m in [12, 6, 3, 2, 1, 0.5]] == [17, 34, 68, 102, 204, 408]
    pessoas, eventos = rodar.le_dados(TMP, "sint")
    saida = TMP / "saida_nova"

    # passo de 12 meses, P0, contra o script antigo
    velho = roda_script_antigo(TMP)
    rodar.roda_unidade(pessoas, eventos, "sint", "P0", 12, saida / "unidades", False)
    novo = pd.read_csv(saida / "unidades" / "sint_P0_12_pares.csv.gz")
    velho = velho[
        (velho["passo_meses"] == 12)
        & (velho["medida"] == "total")
        & velho["origem"].str.endswith("-12-31")
    ]
    nome_velho = {
        "coorte": "coorte",
        "conservador": "conservador",
        "pessimista": "pessimista",
        "otimista": "otimista",
        "ingenua": "ingenua",
    }
    comparados, diferentes = 0, []
    for _, linha in velho.iterrows():
        if (
            linha["metodo"] not in nome_velho
            or linha["metodo"] == "repositórios"
            or linha["metodo"] == "so_tendencia"
        ):
            continue
        nome_novo = (
            "ingenua" if linha["metodo"] == "ingenua" else f"{linha['metodo']}_{linha['variante']}"
        )
        achado = novo[(novo["metodo"] == nome_novo) & (novo["origem"] == linha["origem"])]
        assert len(achado) == 1, (nome_novo, linha["origem"])
        a, b = float(achado["previsto"].iloc[0]), float(linha["previsto"])
        comparados += 1
        if not ((np.isnan(a) and np.isnan(b)) or abs(a - b) <= 1e-6 * max(1.0, abs(b))):
            diferentes.append((nome_novo, linha["origem"], a, b))
        # o real também confere
        r_novo, r_velho = float(achado["real"].iloc[0]), float(linha["real"])
        assert abs(r_novo - r_velho) < 1e-9, ("real", nome_novo, linha["origem"], r_novo, r_velho)
    print(
        f"P0, 12 meses, dezembro: {comparados} previsões comparadas com o script antigo, {len(diferentes)} diferentes"
    )
    for d in diferentes[:10]:
        print("   ", d)
    assert comparados > 100 and not diferentes

    # populações e vazamento
    controles = []
    for passo in [12, 6, 3, 2, 1, 0.5]:
        for pop in ["P1", "P2"]:
            rodar.roda_unidade(pessoas, eventos, "sint", pop, passo, saida / "unidades", True)
            teste = pd.read_csv(
                saida / "unidades" / f"sint_{pop}_{rodar.NOME_PASSO[passo]}_vazamento.csv"
            )
            assert (
                len(teste) > 0
                and teste["estados_iguais"].all()
                and (teste["maior_diferenca_relativa"] < 1e-9).all()
            ), teste
            futuros = int(teste["controle_eventos_futuros_difere"].sum())
            texto = f"   {pop} passo {passo}: controle de eventos futuros difere em {futuros} de {len(teste)} origens"
            controles.append((pop, passo, "eventos futuros", futuros))
            if pop == "P1":
                promocoes = int(teste["controle_promocoes_difere"].sum())
                texto += f"; controle de promoções difere em {promocoes} (promoções no ano seguinte: {int(teste['pessoas_promovidas_no_ano_seguinte'].sum())})"
                controles.append((pop, passo, "promoções", promocoes))
            print(texto)
    sem_poder = [c for c in controles if c[3] == 0]
    assert not sem_poder, f"controles que não diferem (teste sem poder nesses passos): {sem_poder}"
    # versão B: com passo de 12 meses as pirâmides de A e B são iguais; nos outros o total de ativos é o mesmo
    p12 = constroi_estado(pessoas, eventos, 12, "P1", FIM)
    for nome in ["pop_p", "pop_r", "N", "R0", "E", "NN", "NE", "PX", "PN"]:
        assert np.array_equal(p12[nome], p12[nome + "_b"]), nome
    for passo in [6, 3, 0.5]:
        est = constroi_estado(pessoas, eventos, passo, "P2", FIM)
        assert est["pop_p_b"].shape[1] == 8 * est["nb"] + 2 and est["pop_p"].shape[1] == 10
        assert np.array_equal(est["pop_p"].sum(axis=1), est["pop_p_b"].sum(axis=1))
        # as faixas finas da B, somadas por ano, ficam perto das faixas de 1 ano da A (idade em passos contra idade em anos)
        por_ano = (
            est["pop_p_b"][:, : 8 * est["nb"]].reshape(len(est["datas"]), 8, est["nb"]).sum(axis=2)
        )
        diferenca = np.abs(por_ano - est["pop_p"][:, :8]).sum(axis=1) / np.maximum(est["ativas"], 1)
        print(
            f"   B contra A, passo {passo}: diferença média entre as faixas de 1 ano da A e as da B somadas por ano: {diferenca[est['ativas'] > 0].mean():.3f} do total de ativos"
        )
    for passo in [12, 3, 0.5]:
        p1 = constroi_estado(pessoas, eventos, passo, "P1", FIM)
        p2 = constroi_estado(pessoas, eventos, passo, "P2", FIM)
        assert (p2["ativas"] >= p1["ativas"]).all(), "P2 tem menos ativos que P1"
        assert np.allclose(p2["pop_p"].sum(axis=1), p2["ativas"])
    print("sintético: tudo confere")


if __name__ == "__main__":
    main()
