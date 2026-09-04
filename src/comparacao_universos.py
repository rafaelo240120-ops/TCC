# ==============================================================
# TCC — Comparação de universos: ISE B3 vs IBrX-100
# Plano de trabalho, seção 2 ("Melhorar a comparação das carteiras")
#
# O que este script responde
# --------------------------
# [2.1] Aplica EXATAMENTE a mesma estratégia fatorial a dois
#       universos — o do ISE B3 e o do mercado amplo (IBrX-100) —
#       para separar o efeito da seleção fatorial do efeito da
#       restrição ESG.
#
# [2.2] Compara carteiras com a MESMA regra de ponderação. Além das
#       carteiras fatoriais, calcula-se uma carteira de peso igual
#       com TODO o universo elegível de cada índice. Assim a
#       comparação ISE x IBrX deixa de misturar "peso igual" com
#       "peso por capitalização/score" (ver doc/ponderacao_indices.md).
#
# A decomposição resultante é um 2x2:
#
#                        universo ISE     universo IBrX-100
#   carteira fatorial        A                   B
#   universo todo (EW)       C                   D
#
#   A - C  efeito da seleção fatorial dentro do universo ESG
#   B - D  efeito da seleção fatorial no mercado amplo
#   C - D  efeito da restrição ESG, com ponderação idêntica
#   (A-C) - (B-D)  o fator funciona melhor ou pior sob a restrição ESG
#
# Toda a mecânica (calendário de sinal/compra, planilhão
# point-in-time, buy-and-hold, turnover, custos) é importada de
# carteira_factor_investing.py — não há segunda implementação.
# ==============================================================

from __future__ import annotations

import sys
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import carteira_factor_investing as cfi   # noqa: E402

RAIZ      = cfi.RAIZ
DIR_DADOS = cfi.DIR_DADOS
DIR_FIG   = cfi.DIR_FIG

ANO_INI, ANO_FIM = cfi.ANO_INI, cfi.ANO_FIM
TAMANHO_IBRX     = 100     # o IBrX-100 tem 100 ativos
ESTRATEGIAS      = cfi.ESTRATEGIAS + ["Universo_EW"]


# ──────────────────────────────────────────────────────────────
# [2.1] UNIVERSO DO IBrX-100 — proxy por liquidez
#
# A B3 seleciona o IBrX-100 pelos 100 ativos de maior Índice de
# Negociabilidade (IN) nas três carteiras anteriores, com presença
# em pelo menos 95% dos pregões. O IN combina número de negócios e
# volume financeiro, e a B3 não publica a série histórica do IN.
#
# Usa-se aqui o volume financeiro dos 12 meses anteriores à data do
# sinal (campo volume1y do endpoint /preco/estatistica), que é a
# componente dominante do IN e está disponível point-in-time. É uma
# APROXIMAÇÃO do IBrX-100, não a carteira oficial — o que basta
# para o propósito de ter um universo amplo comparável, construído
# com a mesma informação disponível na data de formação.
# ──────────────────────────────────────────────────────────────
_cache_estat: dict[str, pd.DataFrame] = {}
_estat_vazio: set[str] = set()


def buscar_estatistica(data_ref: pd.Timestamp):
    """Último /preco/estatistica publicado ATÉ a data do sinal."""
    for k in range(30):
        data = (data_ref - pd.Timedelta(days=k)).strftime("%Y-%m-%d")
        if data in _cache_estat:
            return _cache_estat[data], data
        if data in _estat_vazio:
            continue
        try:
            resp = requests.get(f"{cfi.BASE_URL}/preco/estatistica",
                                headers=cfi.HEADERS,
                                params={"data_base": data}, timeout=90)
            dados = resp.json() if resp.status_code == 200 else []
        except Exception:
            dados = []
        if isinstance(dados, dict):
            dados = dados.get("results", dados.get("data", []))
        if dados:
            df = pd.DataFrame(dados)
            df["Ticker"] = df["ticker"].astype(str).str.upper()
            df["vol1y"]  = pd.to_numeric(df["volume1y"], errors="coerce")
            _cache_estat[data] = df[["Ticker", "vol1y"]]
            return _cache_estat[data], data
        _estat_vazio.add(data)
    return pd.DataFrame(), None


def universo_ibrx(d_sinal: pd.Timestamp) -> tuple[list[str], str | None]:
    est, data = buscar_estatistica(d_sinal)
    if est.empty:
        return [], None
    top = (est.dropna(subset=["vol1y"]).query("vol1y > 0")
              .sort_values("vol1y", ascending=False)
              .head(TAMANHO_IBRX)["Ticker"].tolist())
    return top, data


# ──────────────────────────────────────────────────────────────
# PREÇOS — completa o cache com os tickers do universo amplo
# ──────────────────────────────────────────────────────────────
def garantir_precos(tickers: set[str]) -> None:
    faltam = sorted(t for t in tickers
                    if t not in cfi.df_precos.columns
                    or cfi.df_precos[t].notna().sum() < cfi.MIN_PREGOES)
    if not faltam:
        print("Cache já cobre o universo amplo.")
        return
    print(f"Baixando {len(faltam)} séries do universo amplo...")
    novas = {}
    for t in faltam:
        s, fonte = cfi.baixar_lab(t), "lab"
        if s.empty:
            s, fonte = cfi.baixar_yahoo(t), "yahoo"
        if s.empty:
            print(f"  SEM DADO: {t}")
        else:
            novas[t] = s.rename(t)
            print(f"  OK ({fonte:5}): {t:7} n={len(s)}")
        time.sleep(0.15)
    if novas:
        # concat de uma vez só: evita fragmentar o DataFrame
        extra = pd.DataFrame(novas)
        base  = cfi.df_precos.drop(columns=[c for c in extra.columns
                                            if c in cfi.df_precos.columns])
        cfi.df_precos = pd.concat([base, extra], axis=1).sort_index(axis=1)
        cfi.df_retornos = cfi.df_precos.pct_change(fill_method=None)
        cfi.df_precos.sort_index().to_csv(cfi.ARQ_PRECOS, encoding="utf-8")
        print(f"Cache atualizado: {cfi.df_precos.shape[1]} ações.")


# ──────────────────────────────────────────────────────────────
# BACKTEST DE UM UNIVERSO
# ──────────────────────────────────────────────────────────────
def backtest_universo(nome: str, tickers_por_ano: dict[int, list[str]]):
    """Roda as 6 carteiras fatoriais + a carteira EW do universo inteiro."""
    retornos  = {e: [] for e in ESTRATEGIAS}
    pesos_ant = {e: pd.Series(dtype=float) for e in ESTRATEGIAS}
    registros, composicoes = [], []

    for ano in range(ANO_INI, ANO_FIM + 1):
        cal = cfi.calendario(ano)
        if cal is None:
            continue
        universo = tickers_por_ano.get(ano, [])
        if not universo:
            continue

        # fatores de preço, medidos até o fechamento do sinal
        linhas = []
        for t in universo:
            if t not in cfi.df_precos.columns:
                continue
            p = cfi.df_precos.loc[cal["d_ini_obs"]:cal["d_sinal"], t].dropna()
            r = cfi.df_retornos.loc[cal["d_ini_obs"]:cal["d_sinal"], t].dropna()
            if len(p) < cfi.MIN_PREGOES:
                continue
            linhas.append({"Ticker": t,
                           "momentum": p.iloc[-1] / p.iloc[0] - 1,
                           "baixa_vol": r.std() * np.sqrt(252)})
        df_fat = pd.DataFrame(linhas)
        if df_fat.empty:
            continue

        # fundamentos point-in-time (mesma função do script principal)
        df_plan, data_base = cfi.buscar_planilhao(cal["d_sinal"])
        if df_plan.empty:
            continue
        df_fat = pd.merge(df_fat, df_plan[["Ticker", "p_vp", "roic"]],
                          on="Ticker", how="inner")
        if df_fat.empty:
            continue

        tops = cfi.montar_rankings(df_fat)
        # [2.2] o comparador de mesma ponderação: TODO o universo
        # elegível, peso igual, mesmo rebalanceamento, mesmos custos
        tops["Universo_EW"] = df_fat["Ticker"].tolist()

        print(f"  {nome} {ano}: universo={len(df_fat)} "
              f"planilhao={data_base}")

        for est in ESTRATEGIAS:
            if not tops.get(est):
                continue
            alvo = pd.Series(1.0 / len(tops[est]), index=tops[est])
            giro = cfi.calcular_turnover(pesos_ant[est], alvo)
            ret, pesos_fim, usados = cfi.retorno_buy_and_hold(
                tops[est], cal["d_compra"], cal["d_fim"])
            if ret.empty:
                continue
            custo = 2.0 * giro * cfi.CUSTO_POR_LADO
            ret.iloc[0] -= custo
            retornos[est].append(ret)
            pesos_ant[est] = pesos_fim
            registros.append({"Universo": nome, "Ano": ano, "Estrategia": est,
                              "N_acoes": len(usados), "Turnover": round(giro, 4)})
            for t in tops[est]:
                composicoes.append({"Universo": nome, "Ano": ano,
                                    "Estrategia": est, "Ticker": t})

    serie = {f"{nome}_{e}": pd.concat(s) for e, s in retornos.items() if s}
    return pd.DataFrame(serie), pd.DataFrame(registros), pd.DataFrame(composicoes)


def metricas(ret: pd.Series, selic: pd.Series) -> dict:
    ret   = ret.dropna()
    total = (1 + ret).prod() - 1
    anual = cfi.anualiza(total, ret.index)   # [C12] anos de calendário
    vol   = ret.std() * np.sqrt(252)
    exc   = ret - selic.reindex(ret.index).fillna(0)
    patr  = (1 + ret).cumprod()
    return {"Retorno Total (%)": round(total * 100, 2),
            "Retorno Anual (%)": round(anual * 100, 2),
            "Volatilidade (%)":  round(vol * 100, 2),
            "Sharpe":            round(float(exc.mean() / exc.std() * np.sqrt(252)), 2),
            "Max Drawdown (%)":  round(float((patr / patr.cummax() - 1).min() * 100), 2)}


def main() -> None:
    print("=" * 78)
    print("  Comparação de universos — ISE B3 vs IBrX-100 (proxy por liquidez)")
    print("=" * 78)

    # ── monta os dois universos, ano a ano ────────────────────
    uni_ise, uni_ibrx = {}, {}
    todos_ibrx: set[str] = set()
    for ano in range(ANO_INI, ANO_FIM + 1):
        cal = cfi.calendario(ano)
        if cal is None:
            continue
        uni_ise[ano] = cfi.universo_efetivo(ano)
        lista, base  = universo_ibrx(cal["d_sinal"])
        uni_ibrx[ano] = lista
        todos_ibrx |= set(lista)
        print(f"{ano}: ISE={len(uni_ise[ano]):3} | IBrX-proxy={len(lista):3} "
              f"(liquidez de {base})")

    garantir_precos(todos_ibrx)

    print("\n--- backtest universo ISE B3 ---")
    ret_ise, reg_ise, comp_ise = backtest_universo("ISE", uni_ise)
    print("\n--- backtest universo IBrX-100 (proxy) ---")
    ret_ibx, reg_ibx, comp_ibx = backtest_universo("IBRX", uni_ibrx)

    df = ret_ise.join(ret_ibx, how="outer")
    df = df.join(cfi.df_bench[["ret_ise", "ret_ibrx", "selic_dia"]], how="inner")
    df = df.dropna(subset=["ret_ise", "ret_ibrx"]).sort_index()
    df.index.name = "data"
    selic = df["selic_dia"]

    # ── tabela de desempenho ──────────────────────────────────
    ROTULO = {"Momentum": "Momentum", "Baixa_Vol": "Baixa Vol", "Valor": "Valor",
              "Qualidade": "Qualidade", "Multifator": "Multifator",
              "Uniao_TCC": "Uniao top-10", "Universo_EW": "Universo inteiro (EW)"}
    linhas = []
    for uni, rot in [("ISE", "ISE B3"), ("IBRX", "IBrX-100")]:
        for est in ESTRATEGIAS:
            col = f"{uni}_{est}"
            if col in df:
                linhas.append({"Universo": rot, "Carteira": ROTULO[est],
                               **metricas(df[col], selic)})
    for col, rot in [("ret_ise", "ISE B3 (índice oficial)"),
                     ("ret_ibrx", "IBrX-100 (índice oficial)")]:
        linhas.append({"Universo": "Índice", "Carteira": rot,
                       **metricas(df[col], selic)})
    tabela = pd.DataFrame(linhas)

    print("\n" + "=" * 78)
    print("  Desempenho por universo — mesma estratégia, mesma ponderação")
    print("=" * 78)
    print(tabela.to_string(index=False))

    # ── decomposição 2x2 ──────────────────────────────────────
    def anual(col):
        return metricas(df[col], selic)["Retorno Anual (%)"]

    dec = []
    for est in cfi.ESTRATEGIAS:
        a, b = f"ISE_{est}", f"IBRX_{est}"
        if a in df and b in df:
            dec.append({
                "Fator": ROTULO[est],
                "ISE: fator - universo EW":  round(anual(a) - anual("ISE_Universo_EW"), 2),
                "IBrX: fator - universo EW": round(anual(b) - anual("IBRX_Universo_EW"), 2),
                "Diferença (ESG - amplo)":   round((anual(a) - anual("ISE_Universo_EW"))
                                                   - (anual(b) - anual("IBRX_Universo_EW")), 2),
            })
    df_dec = pd.DataFrame(dec)

    print("\n--- Efeito da seleção fatorial em cada universo (p.p. ao ano) ---")
    print(df_dec.to_string(index=False))

    esg_ew = anual("ISE_Universo_EW") - anual("IBRX_Universo_EW")
    esg_of = anual("ret_ise") - anual("ret_ibrx")
    print("\n--- Efeito da restrição ESG (p.p. ao ano) ---")
    print(f"  Peso igual, mesma regra dos dois lados : {esg_ew:+.2f}")
    print(f"  Índices oficiais (ponderações distintas): {esg_of:+.2f}")
    print("  A diferença entre as duas linhas é efeito de PONDERAÇÃO,")
    print("  não de seleção ESG — ver doc/ponderacao_indices.md.")

    # ── salvar ────────────────────────────────────────────────
    tabela.to_csv(DIR_DADOS / "comparacao_universos.csv", index=False, encoding="utf-8-sig")
    df_dec.to_csv(DIR_DADOS / "decomposicao_fator_esg.csv", index=False, encoding="utf-8-sig")
    df.to_csv(DIR_DADOS / "retornos_diarios_universos.csv", encoding="utf-8-sig")
    pd.concat([reg_ise, reg_ibx]).to_csv(DIR_DADOS / "turnover_universos.csv",
                                         index=False, encoding="utf-8-sig")
    pd.concat([comp_ise, comp_ibx]).to_csv(DIR_DADOS / "composicao_universos.csv",
                                           index=False, encoding="utf-8-sig")
    pd.DataFrame({"Ano": list(uni_ibrx), "N": [len(v) for v in uni_ibrx.values()],
                  "Tickers": [", ".join(v) for v in uni_ibrx.values()]}
                 ).to_csv(DIR_DADOS / "universo_ibrx_proxy.csv",
                          index=False, encoding="utf-8-sig")

    # ── gráfico ───────────────────────────────────────────────
    cols = ["ISE_Multifator", "IBRX_Multifator",
            "ISE_Universo_EW", "IBRX_Universo_EW", "ret_ise", "ret_ibrx"]
    cols = [c for c in cols if c in df]
    acum = (1 + df[cols].fillna(0)).cumprod() * 100
    est_ = {"ISE_Multifator": ("-", 2.2), "IBRX_Multifator": ("-", 2.2),
            "ISE_Universo_EW": ("--", 1.5), "IBRX_Universo_EW": ("--", 1.5),
            "ret_ise": (":", 1.5), "ret_ibrx": (":", 1.5)}
    nome_ = {"ISE_Multifator": "Multifator no ISE B3",
             "IBRX_Multifator": "Multifator no IBrX-100",
             "ISE_Universo_EW": "ISE B3 — universo EW",
             "IBRX_Universo_EW": "IBrX-100 — universo EW",
             "ret_ise": "ISE B3 (índice oficial)",
             "ret_ibrx": "IBrX-100 (índice oficial)"}
    fig, ax = plt.subplots(figsize=(11, 5.5))
    for c in cols:
        ls, lw = est_[c]
        ax.plot(acum[c], label=nome_[c], linestyle=ls, linewidth=lw)
    ax.set_title(f"Mesma estratégia, dois universos — base 100 ({ANO_INI}-{ANO_FIM})")
    ax.set_ylabel("Base 100")
    ax.legend(ncol=2, fontsize=9)
    ax.grid(True, linestyle=":", alpha=0.6)
    plt.tight_layout()
    plt.savefig(DIR_FIG / "comparacao_universos.png", dpi=150)
    plt.close(fig)

    print(f"\nArquivos salvos em {DIR_DADOS} e {DIR_FIG}")


if __name__ == "__main__":
    main()
