# ==============================================================
# TCC — ESG Factor Investing com ações do ISE B3
# Backtest anual: 2016–2025
#
# Estratégia: a cada virada de ano, rankeiam-se as ações do
# universo ISE B3 por 4 fatores e forma-se uma carteira com a
# união das top-10 de cada fator, ponderada igualmente.
#
# Fatores:
#   1. Momentum    — maior retorno acumulado no ano anterior
#   2. Baixa Vol   — menor volatilidade anualizada no ano anterior
#   3. Valor (P/VP)— menor preço/valor patrimonial
#   4. Qualidade   — maior ROIC (retorno sobre capital investido)
# ==============================================================

import numpy as np
import pandas as pd
import requests
import yfinance as yf
import matplotlib.pyplot as plt
from pathlib import Path

# ──────────────────────────────────────────────────────────────
# CONFIGURAÇÕES
# ──────────────────────────────────────────────────────────────
PASTA    = Path(__file__).resolve().parent
BASE_URL = "https://laboratoriodefinancas.com/api/v2"
TOP_N    = 10   # ações selecionadas por fator

TOKEN = ""
for linha in (PASTA / ".env").read_text(encoding="utf-8").splitlines():
    if linha.startswith("LAB_FINANCAS_TOKEN="):
        TOKEN = linha.split("=", 1)[1].strip()

# ──────────────────────────────────────────────────────────────
# UNIVERSO ELEGÍVEL — composição anual do ISE B3
#
# O ano N-1 é o período de observação dos fatores de preço.
# O ano N define quais empresas podem entrar na carteira.
# ──────────────────────────────────────────────────────────────
universo_ise = {
    2015: ["KLBN11","CPFE3","LAME4","SULA11","EVEN3","BRFS3","COCE5","TIMP3",
           "LREN3","GOAU4","ELET3","CMIG4","ITSA4","GGBR4","WEGE3",
           "SBSP3","ELPL3","TIET11","BBDC4","SANB11","BBAS3","CCRO3","VIVT3",
           "BRKM5","ITUB4","FLRY3","VALE3","EMBR3","FIBR3","ENBR3","DTEX3",
           "ECOR3","CPLE6","BTOW3","LIGT3","CIEL3","JSLG3","NATU3"],
           # BICB4 removido (fechamento de capital em 2015)
           # TLES3 removido (extinto pré-2015, era Telebrás)

    2016: ["KLBN11","EGIE3","CPFE3","LAME4","SULA11","EVEN3","BRFS3","TIMP3",
           "LREN3","ELET3","CMIG4","ITSA4","WEGE3","ELPL3","CESP6","TIET11",
           "BBDC4","SANB11","BBAS3","CCRO3","VIVT3","BRKM5","ITUB4","FLRY3",
           "EMBR3","FIBR3","ENBR3","DTEX3","ECOR3","CPLE6","BTOW3","LIGT3",
           "CIEL3","NATU3"],

    2017: ["KLBN11","CPFE3","LAME4","SULA11","BRFS3","TIMP3","LREN3","ELET3",
           "CMIG4","ITSA4","WEGE3","CLSC4","ELPL3","TIET11","BBDC4","SANB11",
           "BBAS3","CCRO3","VIVT3","BRKM5","ITUB4","FLRY3","EMBR3","FIBR3",
           "ENBR3","DTEX3","ECOR3","CPLE6","BTOW3","MRVE3","LIGT3","CIEL3",
           "EGIE3","NATU3"],

    2018: ["KLBN11","CPFE3","LAME4","TIMP3","LREN3","CMIG4","ITSA4","WEGE3",
           "CLSC4","ELPL3","TIET11","BBDC4","SANB11","BBAS3","CCRO3","VIVT3",
           "BRKM5","ITUB4","FLRY3","FIBR3","ENBR3","DTEX3","ECOR3","CPLE6",
           "BTOW3","MRVE3","LIGT3","CIEL3","EGIE3","NATU3"],

    2019: ["KLBN11","LAME4","TIMP3","LREN3","ELET3","CMIG4","ITSA4","WEGE3",
           "ELPL3","TIET11","BBDC4","SANB11","BBAS3","CCRO3","VIVT3","BRKM5",
           "ITUB4","FLRY3","ENBR3","DTEX3","ECOR3","CPLE6","BTOW3","MRVE3",
           "LIGT3","CIEL3","EGIE3","NATU3"],

    2020: ["KLBN11","LAME4","BRFS3","TIMP3","LREN3","ELET3","CMIG4","ITSA4",
           "WEGE3","TIET11","BBDC4","SANB11","BBAS3","CCRO3","VIVT3","BRKM5",
           "ITUB4","FLRY3","BRDT3","ENBR3","DTEX3","ECOR3","CPLE6","BTOW3",
           "MOVI3","MRVE3","LIGT3","CIEL3","EGIE3","NATU3"],

    2021: ["KLBN11","CPFE3","LAME4","BRFS3","TIMP3","LREN3","ELET3","CMIG4",
           "ITSA4","WEGE3","BBDC4","SANB11","BBAS3","CCRO3","VIVT3","BRKM5",
           "ITUB4","FLRY3","CSAN3","PCAR3","BPAC11","BRDT3","ENBR3","PETR4",
           "DTEX3","ECOR3","CPLE6","BTOW3","MDIA3","MRFG3","MOVI3","MRVE3",
           "LIGT3","ASAI3","CIEL3","SUZB3","EGIE3","BEEF3","NATU3","AESB3","NEOE3"],

    2022: ["KLBN11","CPFE3","BRFS3","SULA11","AMER3","TIMP3","LREN3","ELET3",
           "CMIG4","ITSA4","WEGE3","ARZZ3","BBDC4","SANB11","BBAS3","CCRO3",
           "VIVT3","BRKM5","ITUB4","FLRY3","CSAN3","SIMH3","PCAR3","BPAC11",
           "ENBR3","MYPK3","ECOR3","CPLE6","MDIA3","AZUL4","DXCO3","MGLU3",
           "MRFG3","MOVI3","MRVE3","VBBR3","AMBP3","LIGT3","CIEL3","SUZB3",
           "EGIE3","BEEF3","RADL3","NATU3","AESB3","NEOE3","RAIL3","VIIA3"],

    2023: ["KLBN11","CPFE3","BRFS3","AMER3","TIMS3","LREN3","ELET3","CMIG4",
           "ITSA4","WEGE3","ARZZ3","B3SA3","BBDC4","SANB11","BBAS3","CCRO3",
           "VIVT3","ITUB4","FLRY3","CSAN3","SIMH3","PCAR3","BPAC11","CBAV3",
           "MYPK3","ECOR3","CPLE6","MDIA3","AZUL4","DXCO3","MGLU3","MRFG3",
           "MOVI3","MRVE3","TRPL4","VBBR3","STBP3","AMBP3","LIGT3","RANI3",
           "ASAI3","CIEL3","COGN3","HYPE3","SUZB3","DASA3","EGIE3","VAMO3",
           "RAIZ4","BEEF3","RADL3","NATU3","BPAN4","AESB3","AERI3","NEOE3",
           "ALSO3","ENEV3","RDOR3","RAIL3","GUAR3","SAPR11","GRND3","SLCE3",
           "ABEV3","GFSA3","VIIA3"],

    2024: ["KLBN11","CPFE3","BRFS3","TIMS3","LREN3","ELET3","CMIG4","ITSA4",
           "WEGE3","B3SA3","BBDC4","SANB11","BBAS3","CCRO3","VIVT3","ITUB4",
           "FLRY3","CSAN3","SIMH3","PCAR3","BPAC11","CBAV3","MYPK3","ECOR3",
           "CPLE6","MDIA3","AZUL4","DXCO3","MGLU3","MOVI3","MRVE3","VBBR3",
           "STBP3","AMBP3","RANI3","ASAI3","COGN3","HYPE3","SUZB3","DASA3",
           "EGIE3","VAMO3","RAIZ4","BEEF3","RADL3","NATU3","BPAN4","ISAE4",
           "AERI3","NEOE3","ALSO3","ENEV3","RDOR3","PSSA3","RAIL3","GUAR3",
           "SAPR11","GRND3","SLCE3","ABEV3","GFSA3","CSMG3","SRNA3","IGTI11",
           "CAML3","CRFB3","JSLG3","AURE3","YDUQ3","UGPA3","AZZA3","USIM5",
           "MTRE3","CEAB3","BHIA3"],

    2025: ["ALOS3","AURE3","AXIA3","AZZA3","B3SA3","BBAS3","BBDC4","BRKM5",
           "BPAC11","CEAB3","CAML3","BHIA3","CMIG4","CBAV3","COGN3","CSMG3",
           "CPLE6","CSAN3","CPFE3","CYRE3","DXCO3","ECOR3","ENEV3","EGIE3",
           "EQTL3","FLRY3","GFSA3","GUAR3","HBSA3","HYPE3","IGTI11","MYPK3",
           "RANI3","ISAE4","ITUB4","ITSA4","JSLG3","KLBN11","LJQQ3","LREN3",
           "MDIA3","MGLU3","MRFG3","BEEF3","MTRE3","MOTV3","MOVI3","MRVE3",
           "NTCO3","OPCT3","ODPV3","PTBL3","PSSA3","RADL3","RDOR3","RAIL3",
           "SBSP3","SAPR11","SANB11","SIMH3","SLCE3","VIVT3","TIMS3","TTEN3",
           "UGPA3","USIM5","VAMO3","VBBR3","WEGE3","YDUQ3","AZUL4","CRFB3",
           "BRFS3","STBP3","AMBP3","SRNA3","PORT3","BPAN4","NEOE3","PCAR3","RAIZ4"],
}

# ──────────────────────────────────────────────────────────────
# PREÇOS HISTÓRICOS — cache local + download automático
#
# Tenta primeiro o Yahoo Finance; se falhar, usa o Lab de Finanças.
# O resultado é salvo em CSV para evitar re-download a cada execução.
#
# Tickers renomeados/fundidos: empresas que mudaram de código na B3
# recebem a série de preços do ticker atual (mesma empresa,
# mesmo histórico de preços ajustados).
# ──────────────────────────────────────────────────────────────
ARQ_PRECOS = PASTA / "precos_historicos_cache.csv"
df_precos  = pd.read_csv(ARQ_PRECOS, index_col=0, parse_dates=True) if ARQ_PRECOS.exists() else pd.DataFrame()
atualizado = False

RENOMEADOS = {                                       # ticker antigo → ticker atual
    "ELET3":"AXIA3",  "TIET11":"AURE3", "CESP6":"AURE3",  "AESB3":"AURE3",   # Energia
    "BTOW3":"AMER3",  "LAME4":"AMER3",  "VIIA3":"BHIA3",  "ALSO3":"ALOS3",   # Varejo
    "ARZZ3":"AZZA3",  "CCRO3":"MOTV3",  "EMBR3":"EMBJ3",  "SULA11":"RDOR3",  # Outros
    "FIBR3":"SUZB3",  "TIMP3":"TIMS3",  "BRDT3":"VBBR3",  "DTEX3":"DXCO3",   # Renomeados
    "TRPL4":"ISAE4",  "NTCO3":"NATU3",  "GUAR3":"RIAA3",
}

todos_tickers = sorted(set(t for lista in universo_ise.values() for t in lista))
faltantes = sorted(set(
    [t for t in todos_tickers       if t not in df_precos.columns or df_precos[t].dropna().empty] +
    [t for t in RENOMEADOS.values() if t not in df_precos.columns or df_precos[t].dropna().empty]
))

if faltantes:
    print(f"Baixando {len(faltantes)} tickers faltantes...")
    novas_series = {}
    for ticker in faltantes:
        serie = pd.Series(dtype=float)

        try:  # 1) Yahoo Finance
            tkr  = yf.Ticker(f"{ticker}.SA")
            df_h = tkr.history(start="2015-01-01", end="2025-12-31", auto_adjust=True)
            if not df_h.empty:
                ch = df_h["Close"].dropna()
                if ch.index.tz is not None:
                    ch.index = ch.index.tz_localize(None)
                serie = ch.rename(ticker)
        except Exception:
            pass

        if serie.empty:  # 2) Laboratório de Finanças (fallback)
            resp = requests.get(f"{BASE_URL}/preco/corrigido",
                                headers={"Authorization": f"Bearer {TOKEN}"},
                                params={"ticker": ticker, "data_ini": "2015-01-01", "data_fim": "2025-12-31"},
                                timeout=30)
            if resp.status_code == 200:
                dados_p = resp.json()
                if isinstance(dados_p, dict):
                    dados_p = dados_p.get("results", dados_p.get("data", []))
                if dados_p:
                    df_tmp = pd.DataFrame(dados_p)
                    df_tmp["data"]       = pd.to_datetime(df_tmp["data"])
                    df_tmp["fechamento"] = pd.to_numeric(df_tmp["fechamento"], errors="coerce")
                    serie = df_tmp.dropna(subset=["fechamento"]).set_index("data")["fechamento"]

        if not serie.empty:
            novas_series[ticker] = serie.rename(ticker)
            print(f"  OK: {ticker}")
        else:
            print(f"  SEM DADO: {ticker}")

    if novas_series:
        df_precos = pd.concat([df_precos, pd.DataFrame(novas_series)], axis=1, sort=True)
        atualizado = True

for antigo, novo in RENOMEADOS.items():
    if (antigo not in df_precos.columns or df_precos[antigo].dropna().empty) \
       and novo in df_precos.columns and not df_precos[novo].dropna().empty:
        df_precos[antigo] = df_precos[novo]
        print(f"  Renomeado: {antigo} <- {novo}")
        atualizado = True

if atualizado:
    df_precos.sort_index().sort_index(axis=1).to_csv(ARQ_PRECOS, encoding="utf-8")

df_retornos = df_precos.pct_change()
print(f"Preços: {df_precos.shape[1]} ações | {len(df_precos)} pregões")

# ──────────────────────────────────────────────────────────────
# BENCHMARKS — IBrX-100, ISE B3 e Selic
#
# Fonte: base_ise_ibrx_selic.csv (arquivo pré-carregado com os
# níveis diários dos índices e a taxa Selic anual).
# IBrX-100 e ISE B3 são benchmarks passivos — nenhum fator
# é aplicado a eles. A Selic diária serve como taxa livre de
# risco no cálculo do Sharpe ratio.
# ──────────────────────────────────────────────────────────────
df_bench = pd.read_csv(PASTA / "base_ise_ibrx_selic.csv", parse_dates=["data"])
df_bench = df_bench.sort_values("data").reset_index(drop=True)

df_bench["ret_ise"]   = df_bench["ise_b3"].pct_change()
df_bench["ret_ibrx"]  = df_bench["ibrx100"].pct_change()
df_bench["selic_dia"] = (1 + df_bench["selic_aa"] / 100) ** (1 / 252) - 1

# ──────────────────────────────────────────────────────────────
# BACKTEST — loop anual 2016–2025
#
# A cada iteração:
#   1. Fatores de preço   → calculados com dados do ano N-1
#   2. Fatores fundamentais → consultados no Planilhão do ano N
#   3. MERGE 1            → une os dois blocos por ticker
#   4. Ranking e carteira → top-10 por fator, união sem duplicatas
#   5. Retorno da carteira → média diária igual-ponderada no ano N
# ──────────────────────────────────────────────────────────────
retornos_anuais = []
resumo_anos     = []

for ano in range(2016, 2026):
    print(f"\n--- {ano} ---")

    # ── Fatores de preço: Momentum e Baixa Volatilidade ───────
    # Observação: pregões do ano anterior (ano-1).
    # Momentum  = preço final / preço inicial − 1  (retorno acumulado)
    # Baixa Vol = desvio padrão dos retornos diários × √252  (vol anualizada)
    linhas_preco = []
    for ticker in universo_ise[ano]:
        if ticker not in df_precos.columns:
            print(f"  sem preço: {ticker}")
            continue
        p = df_precos.loc[f"{ano-1}-01-01":f"{ano-1}-12-31", ticker].dropna()
        r = df_retornos.loc[f"{ano-1}-01-01":f"{ano-1}-12-31", ticker].dropna()
        if len(p) < 150:   # mínimo de 150 pregões para cálculo confiável
            continue
        linhas_preco.append({
            "Ticker":    ticker,
            "momentum":  p.iloc[-1] / p.iloc[0] - 1,
            "baixa_vol": r.std() * np.sqrt(252),
        })
    df_fat = pd.DataFrame(linhas_preco)

    # ── Fatores fundamentais: Valor (P/VP) e Qualidade (ROIC) ─
    # Fonte: endpoint /bolsa/planilhao do Laboratório de Finanças.
    # Consultado na virada do ano N; tenta datas crescentes até
    # encontrar um pregão com dados disponíveis.
    datas_tentativa = [
        f"{ano}-01-15", f"{ano}-01-20", f"{ano}-01-31",
        f"{ano}-02-15", f"{ano}-03-01", f"{ano}-03-15",
    ]
    df_plan = pd.DataFrame()
    for data_base in datas_tentativa:
        resp  = requests.get(f"{BASE_URL}/bolsa/planilhao",
                             headers={"Authorization": f"Bearer {TOKEN}"},
                             params={"data_base": data_base},
                             timeout=30)
        dados = resp.json()
        if isinstance(dados, dict):
            dados = dados.get("results", dados.get("data", []))
        if dados:
            df_plan = pd.DataFrame(dados)
            print(f"  Planilhão {ano}: dados de {data_base}")
            break

    if df_plan.empty:
        print(f"  Planilhão {ano}: sem dados — ano ignorado")
        continue

    df_plan.columns   = [str(c).lower() for c in df_plan.columns]
    df_plan["ticker"] = df_plan["ticker"].str.upper()
    df_plan           = df_plan.rename(columns={"ticker": "Ticker"})
    df_plan["p_vp"]   = pd.to_numeric(df_plan["p_vp"], errors="coerce")
    df_plan["roic"]   = pd.to_numeric(df_plan["roic"], errors="coerce")

    # ── MERGE 1: fatores de preço + fatores fundamentais ──────
    # Inner join por Ticker: mantém apenas ações com dados
    # completos nos dois blocos (preço histórico + Planilhão).
    # Resultado: df_fat com colunas momentum, baixa_vol, p_vp, roic.
    df_fat = pd.merge(df_fat, df_plan[["Ticker", "p_vp", "roic"]], on="Ticker", how="inner")

    # ── Ranking: top 10 por fator ──────────────────────────────
    # Momentum  → maior retorno acumulado no ano anterior (desc)
    # Baixa Vol → menor volatilidade anualizada          (asc)
    # Valor     → menor P/VP positivo                    (asc)
    # Qualidade → maior ROIC                             (desc)
    top_momentum  = (df_fat.dropna(subset=["momentum"])
                           .sort_values("momentum",  ascending=False)
                           .head(TOP_N)["Ticker"].tolist())
    top_baixa_vol = (df_fat.dropna(subset=["baixa_vol"])
                           .sort_values("baixa_vol", ascending=True)
                           .head(TOP_N)["Ticker"].tolist())
    top_valor     = (df_fat[df_fat["p_vp"] > 0]
                           .sort_values("p_vp",      ascending=True)
                           .head(TOP_N)["Ticker"].tolist())
    top_qualidade = (df_fat.dropna(subset=["roic"])
                           .sort_values("roic",      ascending=False)
                           .head(TOP_N)["Ticker"].tolist())

    # Carteira = união dos 4 rankings (sem duplicatas, ordem alfabética)
    carteira = sorted(set(top_momentum + top_baixa_vol + top_valor + top_qualidade))

    print(f"  Momentum   : {top_momentum}")
    print(f"  Baixa Vol  : {top_baixa_vol}")
    print(f"  Valor P/VP : {top_valor}")
    print(f"  Qualidade  : {top_qualidade}")
    print(f"  Carteira   : {len(carteira)} ações → {carteira}")

    # Retorno diário da carteira no ano N: média igual-ponderada
    tickers_ok = [t for t in carteira if t in df_retornos.columns]
    ret_ano    = df_retornos.loc[f"{ano}-01-01":f"{ano}-12-31", tickers_ok].mean(axis=1)
    retornos_anuais.append(ret_ano)

    resumo_anos.append({
        "Ano":       ano,
        "N_acoes":   len(carteira),
        "Momentum":  ", ".join(top_momentum),
        "Baixa_Vol": ", ".join(top_baixa_vol),
        "Valor_PVP": ", ".join(top_valor),
        "Qualidade": ", ".join(top_qualidade),
        "Carteira":  ", ".join(carteira),
    })

# ──────────────────────────────────────────────────────────────
# CONSOLIDAÇÃO DOS RETORNOS
# ──────────────────────────────────────────────────────────────
ret_carteira = pd.concat(retornos_anuais).rename("Carteira_Factor_ESG")
df_cart      = ret_carteira.reset_index().rename(columns={"index": "data"})

# ── MERGE 2: retornos da carteira + benchmarks ────────────────
# Inner join por data: garante que carteira e benchmarks sejam
# comparados exatamente nos mesmos pregões, eliminando gaps de
# calendário entre a série da carteira e o arquivo de benchmarks.
df_result = pd.merge(df_cart, df_bench[["data", "ret_ise", "ret_ibrx", "selic_dia"]],
                     on="data", how="inner")
df_result = df_result.dropna().set_index("data").sort_index()

# Retorno acumulado base 100 (para o gráfico)
df_acum = (1 + df_result[["Carteira_Factor_ESG", "ret_ibrx", "ret_ise"]]).cumprod() * 100

# ──────────────────────────────────────────────────────────────
# ESTATÍSTICAS DE PERFORMANCE
# ──────────────────────────────────────────────────────────────
stats = []
for col, nome in [("Carteira_Factor_ESG", "Carteira Factor ESG"),
                  ("ret_ibrx",            "IBrX-100"),
                  ("ret_ise",             "ISE B3")]:
    ret      = df_result[col].dropna()
    total    = (1 + ret).prod() - 1
    anual    = (1 + total) ** (252 / len(ret)) - 1
    vol      = ret.std() * np.sqrt(252)
    exc      = ret - df_result["selic_dia"].reindex(ret.index)
    sharpe   = exc.mean() / exc.std() * np.sqrt(252)
    patr     = (1 + ret).cumprod()
    drawdown = (patr / patr.cummax() - 1).min()
    stats.append({
        "Estrategia":        nome,
        "Retorno Total (%)": round(total    * 100, 2),
        "Retorno Anual (%)": round(anual    * 100, 2),
        "Volatilidade (%)":  round(vol      * 100, 2),
        "Sharpe":            round(sharpe,         2),
        "Max Drawdown (%)":  round(drawdown * 100, 2),
    })

df_stats = pd.DataFrame(stats)

print("\n========================================")
print("  Desempenho — Backtest 2016–2025")
print("========================================")
print(df_stats.to_string(index=False))

# ──────────────────────────────────────────────────────────────
# SALVAR RESULTADOS
# ──────────────────────────────────────────────────────────────
pd.DataFrame(resumo_anos).to_csv("carteiras_selecionadas.csv",  index=False, encoding="utf-8-sig")
df_result.to_csv("retornos_diarios_factor.csv",                               encoding="utf-8-sig")
df_acum.to_csv("retornos_acumulados_factor.csv",                              encoding="utf-8-sig")
df_stats.to_csv("performance_comparativa.csv",  index=False,                  encoding="utf-8-sig")

# ──────────────────────────────────────────────────────────────
# GRÁFICO — retorno acumulado base 100
# ──────────────────────────────────────────────────────────────
plt.figure(figsize=(11, 5))
plt.plot(df_acum["Carteira_Factor_ESG"], label="Carteira Factor ESG", linewidth=2)
plt.plot(df_acum["ret_ibrx"],            label="IBrX-100",  linestyle="--")
plt.plot(df_acum["ret_ise"],             label="ISE B3",    linestyle=":")
plt.title("Retorno Acumulado — Carteira Factor ESG vs Benchmarks (2016–2025)")
plt.xlabel("Data")
plt.ylabel("Base 100")
plt.legend()
plt.grid(True, linestyle=":", alpha=0.6)
plt.tight_layout()
plt.savefig("comparacao_performance.png", dpi=150)
plt.show()
