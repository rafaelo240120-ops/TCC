# -*- coding: utf-8 -*-
# TCC - O Efeito dos Critérios ESG nas Estratégias de Factor Investing
# ISE B3 vs IBrX-100 (2016-2024) | Autor: Rafael Diniz
#
# O objetivo deste código é comparar carteiras montadas por 4 fatores
# (Momentum, Valor, Low Vol, Qualidade) dentro de dois universos:
#   - ISE B3: ações com selo ESG
#   - IBrX-100: ações do mercado geral (benchmark)
# Se a carteira ESG performar melhor, isso indica que o selo ESG
# agrega valor à estratégia de factor investing.

# ============================================================
# PARTE 1 – BIBLIOTECAS
# ============================================================
import pandas as pd       # manipulação de tabelas
import numpy as np        # cálculos matemáticos
import yfinance as yf     # download de preços da B3
import matplotlib.pyplot as plt  # gráficos
import seaborn as sns     # gráfico de correlação (heatmap)
import statsmodels.api as sm     # regressão linear (Alfa de Jensen)
import requests           # chamadas à API do Lab de Finanças
import json               # salvar/ler arquivos de cache
import os                 # verificar se arquivo existe

# ============================================================
# PARTE 2 – BASE DE DADOS
# ============================================================
# Planilha com os índices ISE, IBrX-100 e Selic diários
# Usada pra calcular o retorno do mercado e a taxa livre de risco
base = pd.read_excel("base_ise_ibrx.xlsx")
base["data"] = pd.to_datetime(base["data"])
base["ise_b3"] = base["ise_b3"].astype(float)
base["ibrx100"] = base["ibrx100"].astype(float)
base["selic_aa"] = base["selic_aa"].astype(float)

# ============================================================
# PARTE 3 – COMPOSIÇÃO DOS ÍNDICES
# ============================================================
# Para cada ano, precisamos saber quais ações faziam parte de cada índice.
# Assim conseguimos montar carteiras usando só ações daquele universo.

# 3.1 ISE B3 — composição oficial por ano (fonte: site da B3)
# Essas são as empresas que a B3 certificou como ESG em cada ano.
carteiras_ise = {
    2015: ['KLBN11', 'CPFE3', 'LAME4', 'SULA11', 'EVEN3', 'BRFS3', 'COCE5', 'TIMP3', 'TLES3', 'LREN3', 'GOAU4', 'ELET3', 'CMIG4', 'ITSA4', 'GGBR4', 'WEGE3', 'SBSP3', 'ELPL3', 'TIET11', 'BBDC4', 'SANB11', 'BBAS3', 'CCRO3', 'VIVT3', 'BRKM5', 'ITUB4', 'FLRY3', 'VALE3', 'EMBR3', 'FIBR3', 'ENBR3', 'DTEX3', 'ECOR3', 'CPLE6', 'BTOW3', 'LIGT3', 'CIEL3', 'JSLG3', 'NATU3', 'BICB4'],
    2016: ['KLBN11', 'EGIE3', 'CPFE3', 'LAME4', 'SULA11', 'EVEN3', 'BRFS3', 'TIMP3', 'LREN3', 'ELET3', 'CMIG4', 'ITSA4', 'WEGE3', 'ELPL3', 'CESP6', 'TIET11', 'BBDC4', 'SANB11', 'BBAS3', 'CCRO3', 'VIVT3', 'BRKM5', 'ITUB4', 'FLRY3', 'EMBR3', 'FIBR3', 'ENBR3', 'DTEX3', 'ECOR3', 'CPLE6', 'BTOW3', 'LIGT3', 'CIEL3', 'NATU3'],
    2017: ['KLBN11', 'CPFE3', 'LAME4', 'SULA11', 'BRFS3', 'TIMP3', 'LREN3', 'ELET3', 'CMIG4', 'ITSA4', 'WEGE3', 'CLSC4', 'ELPL3', 'TIET11', 'BBDC4', 'SANB11', 'BBAS3', 'CCRO3', 'VIVT3', 'BRKM5', 'ITUB4', 'FLRY3', 'EMBR3', 'FIBR3', 'ENBR3', 'DTEX3', 'ECOR3', 'CPLE6', 'BTOW3', 'MRVE3', 'LIGT3', 'CIEL3', 'EGIE3', 'NATU3'],
    2018: ['KLBN11', 'CPFE3', 'LAME4', 'TIMP3', 'LREN3', 'CMIG4', 'ITSA4', 'WEGE3', 'CLSC4', 'ELPL3', 'TIET11', 'BBDC4', 'SANB11', 'BBAS3', 'CCRO3', 'VIVT3', 'BRKM5', 'ITUB4', 'FLRY3', 'FIBR3', 'ENBR3', 'DTEX3', 'ECOR3', 'CPLE6', 'BTOW3', 'MRVE3', 'LIGT3', 'CIEL3', 'EGIE3', 'NATU3'],
    2019: ['KLBN11', 'LAME4', 'TIMP3', 'LREN3', 'ELET3', 'CMIG4', 'ITSA4', 'WEGE3', 'ELPL3', 'TIET11', 'BBDC4', 'SANB11', 'BBAS3', 'CCRO3', 'VIVT3', 'BRKM5', 'ITUB4', 'FLRY3', 'ENBR3', 'DTEX3', 'ECOR3', 'CPLE6', 'BTOW3', 'MRVE3', 'LIGT3', 'CIEL3', 'EGIE3', 'NATU3'],
    2020: ['KLBN11', 'LAME4', 'BRFS3', 'TIMP3', 'LREN3', 'ELET3', 'CMIG4', 'ITSA4', 'WEGE3', 'TIET11', 'BBDC4', 'SANB11', 'BBAS3', 'CCRO3', 'VIVT3', 'BRKM5', 'ITUB4', 'FLRY3', 'BRDT3', 'ENBR3', 'DTEX3', 'ECOR3', 'CPLE6', 'BTOW3', 'MOVI3', 'MRVE3', 'LIGT3', 'CIEL3', 'EGIE3', 'NATU3'],
    2021: ['KLBN11', 'CPFE3', 'LAME4', 'BRFS3', 'TIMP3', 'LREN3', 'ELET3', 'CMIG4', 'ITSA4', 'WEGE3', 'BBDC4', 'SANB11', 'BBAS3', 'CCRO3', 'VIVT3', 'BRKM5', 'ITUB4', 'FLRY3', 'CSAN3', 'PCAR3', 'BPAC11', 'BRDT3', 'ENBR3', 'PETR4', 'DTEX3', 'ECOR3', 'CPLE6', 'BTOW3', 'MDIA3', 'MRFG3', 'MOVI3', 'MRVE3', 'LIGT3', 'ASAI3', 'CIEL3', 'SUZB3', 'EGIE3', 'BEEF3', 'NATU3', 'AESB3', 'NEOE3'],
    2022: ['KLBN11', 'CPFE3', 'BRFS3', 'SULA11', 'AMER3', 'TIMP3', 'LREN3', 'ELET3', 'CMIG4', 'ITSA4', 'WEGE3', 'ARZZ3', 'BBDC4', 'SANB11', 'BBAS3', 'CCRO3', 'VIVT3', 'BRKM5', 'ITUB4', 'FLRY3', 'CSAN3', 'SIMH3', 'PCAR3', 'BPAC11', 'ENBR3', 'MYPK3', 'ECOR3', 'CPLE6', 'MDIA3', 'AZUL4', 'DXCO3', 'MGLU3', 'MRFG3', 'MOVI3', 'MRVE3', 'VBBR3', 'AMBP3', 'LIGT3', 'CIEL3', 'SUZB3', 'EGIE3', 'BEEF3', 'RADL3', 'NATU3', 'AESB3', 'NEOE3', 'RAIL3', 'VIIA3'],
    2023: ['KLBN11', 'CPFE3', 'BRFS3', 'AMER3', 'TIMS3', 'LREN3', 'ELET3', 'CMIG4', 'ITSA4', 'WEGE3', 'ARZZ3', 'B3SA3', 'BBDC4', 'SANB11', 'BBAS3', 'CCRO3', 'VIVT3', 'ITUB4', 'FLRY3', 'CSAN3', 'SIMH3', 'PCAR3', 'BPAC11', 'CBAV3', 'MYPK3', 'ECOR3', 'CPLE6', 'MDIA3', 'AZUL4', 'DXCO3', 'MGLU3', 'MRFG3', 'MOVI3', 'MRVE3', 'TRPL4', 'VBBR3', 'STBP3', 'AMBP3', 'LIGT3', 'RANI3', 'ASAI3', 'CIEL3', 'COGN3', 'HYPE3', 'SUZB3', 'DASA3', 'EGIE3', 'VAMO3', 'RAIZ4', 'BEEF3', 'RADL3', 'NATU3', 'BPAN4', 'AESB3', 'AERI3', 'NEOE3', 'ALSO3', 'ENEV3', 'RDOR3', 'RAIL3', 'GUAR3', 'SAPR11', 'GRND3', 'SLCE3', 'ABEV3', 'GFSA3', 'VIIA3'],
    2024: ['KLBN11', 'CPFE3', 'BRFS3', 'TIMS3', 'LREN3', 'ELET3', 'CMIG4', 'ITSA4', 'WEGE3', 'B3SA3', 'BBDC4', 'SANB11', 'BBAS3', 'CCRO3', 'VIVT3', 'ITUB4', 'FLRY3', 'CSAN3', 'SIMH3', 'PCAR3', 'BPAC11', 'CBAV3', 'MYPK3', 'ECOR3', 'CPLE6', 'MDIA3', 'AZUL4', 'DXCO3', 'MGLU3', 'MOVI3', 'MRVE3', 'VBBR3', 'STBP3', 'AMBP3', 'RANI3', 'ASAI3', 'COGN3', 'HYPE3', 'SUZB3', 'DASA3', 'EGIE3', 'VAMO3', 'RAIZ4', 'BEEF3', 'RADL3', 'NATU3', 'BPAN4', 'ISAE4', 'AERI3', 'NEOE3', 'ALSO3', 'ENEV3', 'RDOR3', 'PSSA3', 'RAIL3', 'GUAR3', 'SAPR11', 'GRND3', 'SLCE3', 'ABEV3', 'GFSA3', 'CSMG3', 'SRNA3', 'IGTI11', 'CAML3', 'CRFB3', 'JSLG3', 'AURE3', 'YDUQ3', 'UGPA3', 'AZZA3', 'USIM5', 'MTRE3', 'CEAB3', 'BHIA3']
}

# 3.2 IBrX-100 — como a B3 não disponibiliza a composição histórica,
# criamos uma proxy: as 100 ações com maior volume negociado em cada ano.
# Usamos o planilhão do Laboratório de Finanças pra pegar o volume.
base_url = "https://laboratoriodefinancas.com/api/v2"
token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzgyMzg2NjUwLCJpYXQiOjE3Nzk3OTQ2NTAsImp0aSI6IjU4NWE0ZTAzN2UzMjRkZGRiMzFlNjFkOGM0NzBhN2I3IiwidXNlcl9pZCI6Ijk5In0.pRFEQ_F0wkxat7GVgQr8sM4ipDltUmT7P2kTqlbFKuU"  # token do Laboratório de Finanças (mesmo da aula)

# Primeiro dia útil de cada ano — data de consulta do planilhão
datas_base = {
    2015: "2015-01-02", 2016: "2016-01-04", 2017: "2017-01-02",
    2018: "2018-01-02", 2019: "2019-01-02", 2020: "2020-01-02",
    2021: "2021-01-04", 2022: "2022-01-03", 2023: "2023-01-02",
    2024: "2024-01-02",
}

# Se já buscou antes, carrega do arquivo. Senão, consulta a API.
if os.path.exists("carteiras_historicas_ibrx.json"):
    with open("carteiras_historicas_ibrx.json", "r") as f:
        carteiras_ibrx = {int(k): v for k, v in json.load(f).items()}
else:
    carteiras_ibrx = {}
    for ano, dt in datas_base.items():
        resp = requests.get(f"{base_url}/bolsa/planilhao",
            headers={"Authorization": f"Bearer {token}"},
            params={"data_base": dt})
        df_plan = pd.DataFrame(resp.json())
        df_plan["volume"] = pd.to_numeric(df_plan["volume"], errors="coerce")
        # Ordena por volume e pega as 100 maiores
        carteiras_ibrx[ano] = df_plan.dropna(subset=["volume"]).sort_values(
            "volume", ascending=False)["ticker"].head(100).tolist()
    # Salva pra não precisar consultar de novo
    with open("carteiras_historicas_ibrx.json", "w") as f:
        json.dump(carteiras_ibrx, f)

# Junta todos os tickers dos dois índices pra baixar os preços de uma vez
todos = set()
for lst in list(carteiras_ise.values()) + list(carteiras_ibrx.values()):
    todos.update(lst)

# ============================================================
# PARTE 4 – PREÇOS HISTÓRICOS
# ============================================================
# Baixa os preços de fechamento de todas as ações via Yahoo Finance.
# Começa em 2014 porque o Momentum precisa de 12 meses de histórico
# antes de 2016 (primeiro ano de análise).
# Se já baixou antes, carrega do CSV pra poupar tempo.
if os.path.exists("precos_historicos_cache.csv"):
    fechamento = pd.read_csv("precos_historicos_cache.csv", index_col=0, parse_dates=True)
else:
    dados_yf = yf.download(
        [t + ".SA" for t in todos],  # .SA = sufixo da B3 no Yahoo
        start="2014-01-01", end="2025-01-01",
        auto_adjust=True, progress=True)
    fechamento = dados_yf["Close"].copy()
    fechamento.columns = [str(c).replace(".SA", "") for c in fechamento.columns]
    fechamento.to_csv("precos_historicos_cache.csv")
    fechamento = pd.read_csv("precos_historicos_cache.csv", index_col=0, parse_dates=True)

# Converte preços diários em mensais (último preço de cada mês)
preco_mensal = fechamento.resample("ME").last()

# Calcula o retorno percentual de cada mês: (preço atual / preço anterior) - 1
ret_mensal = preco_mensal.pct_change()

# ============================================================
# PARTE 5 – DADOS FUNDAMENTALISTAS (API)
# ============================================================
# Busca P/VP e ROIC no planilhão do Lab de Finanças pra cada ano.
# P/VP será usado no fator Valor e ROIC no fator Qualidade.
pvp_ano = {}
roic_ano = {}
for ano in range(2016, 2025):
    resp = requests.get(f"{base_url}/bolsa/planilhao",
        headers={"Authorization": f"Bearer {token}"},
        params={"data_base": datas_base[ano]})
    df_plan = pd.DataFrame(resp.json())
    df_plan["p_vp"] = pd.to_numeric(df_plan["p_vp"], errors="coerce")
    df_plan["roic"] = pd.to_numeric(df_plan["roic"], errors="coerce")
    # Remove tickers duplicados e coloca o ticker como índice
    df_plan = df_plan.drop_duplicates(subset="ticker", keep="first").set_index("ticker")
    pvp_ano[ano] = df_plan["p_vp"]    # Preço / Valor Patrimonial
    roic_ano[ano] = df_plan["roic"]    # Retorno sobre Capital Investido

# ============================================================
# PARTE 6 – SCORES DOS FATORES
# ============================================================
# Cada fator atribui um "score" (nota) pra cada ação.
# Na Parte 7, usamos esses scores pra selecionar as 10 melhores.

# 6.1 MOMENTUM — retorno acumulado nos 12 meses anteriores
# Ideia: ações que subiram muito tendem a continuar subindo (Carhart, 1997)
# Ex: pra montar a carteira de 2020, olha o retorno de jan/2019 a dez/2019
score_momentum = {}
for ano in range(2016, 2025):
    ret_form = ret_mensal.loc[f"{ano-1}-01":f"{ano-1}-12"]
    # Multiplica (1 + ret) de cada mês → retorno acumulado do período
    score_momentum[ano] = (1 + ret_form).prod() - 1

# 6.2 VALOR — P/VP (Preço / Valor Patrimonial)
# Ideia: ações com P/VP baixo estão "baratas" em relação ao patrimônio (Fama e French, 1993)
# Quanto MENOR o P/VP, melhor
score_valor = pvp_ano  # já baixado na Parte 5

# 6.3 BAIXA VOLATILIDADE — desvio padrão dos retornos mensais de 12 meses
# Ideia: ações que oscilam menos entregam melhor retorno ajustado (Baker, Bradley e Wurgler, 2011)
# Quanto MENOR a volatilidade, melhor
score_lowvol = {}
for ano in range(2016, 2025):
    ret_form = ret_mensal.loc[f"{ano-1}-01":f"{ano-1}-12"]
    score_lowvol[ano] = ret_form.std()  # desvio padrão = medida de oscilação

# 6.4 QUALIDADE — ROIC (Retorno sobre Capital Investido)
# Ideia: empresas que geram mais lucro com o capital investido são melhores (Novy-Marx, 2013)
# Quanto MAIOR o ROIC, melhor
score_qualidade = roic_ano  # já baixado na Parte 5

# Resume a configuração: pra cada fator, qual score usar e qual direção
# ascending=True  → quanto MENOR o score, melhor (Valor, Low Vol)
# ascending=False → quanto MAIOR o score, melhor (Momentum, Qualidade)
config_fatores = {
    "Momentum":  {"score": score_momentum,  "asc": False},
    "Valor":     {"score": score_valor,     "asc": True},
    "Low Vol":   {"score": score_lowvol,    "asc": True},
    "Qualidade": {"score": score_qualidade, "asc": False},
}

# ============================================================
# PARTE 7 – MONTAGEM DAS CARTEIRAS
# ============================================================
# Pra cada fator e cada ano:
# 1. Pega os scores das ações do ISE e do IBrX
# 2. Rankeia e seleciona as 10 melhores (top 10)
# 3. Calcula o retorno mensal da carteira (equal-weight = peso igual)
# 4. Guarda os retornos pra análise posterior
# Mesma lógica da Magic Formula que fizemos em aula.

n_acoes = 10       # quantas ações em cada carteira
ret_ise = {}       # vai guardar a série de retornos mensais de cada fator (ISE)
ret_ibrx = {}      # idem pro IBrX
tab_anual = {}     # tabela de retornos anuais pra imprimir

for fator, cfg in config_fatores.items():
    lst_ise = []    # lista temporária de séries mensais (ISE)
    lst_ibrx = []   # idem pro IBrX
    tabela = []     # lista temporária de retornos anuais

    for ano in range(2016, 2025):
        if ano not in cfg["score"]:
            continue
        score = cfg["score"][ano]   # score de cada ação nesse ano
        asc = cfg["asc"]           # direção do ranking

        ise_ano = carteiras_ise.get(ano, [])    # ações do ISE nesse ano
        ibrx_ano = carteiras_ibrx.get(ano, [])  # ações do IBrX nesse ano

        # Filtra só ações que têm score disponível
        # Pra Valor e Qualidade, exige score > 0 (P/VP ou ROIC negativo não faz sentido)
        # Pra Momentum e Low Vol, aceita qualquer valor
        if fator in ["Valor", "Qualidade"]:
            disp_ise = [t for t in ise_ano if t in score.index and pd.notna(score[t]) and score[t] > 0]
            disp_ibrx = [t for t in ibrx_ano if t in score.index and pd.notna(score[t]) and score[t] > 0]
        else:
            disp_ise = [t for t in ise_ano if t in score.index and pd.notna(score[t])]
            disp_ibrx = [t for t in ibrx_ano if t in score.index and pd.notna(score[t])]

        # Rankeia pelo score e pega as 10 melhores
        # rank(ascending=True) → rank 1 = menor valor → bom pra Valor e Low Vol
        # rank(ascending=False) → rank 1 = maior valor → bom pra Momentum e Qualidade
        top_ise = score[disp_ise].rank(ascending=asc).sort_values().head(n_acoes).index.tolist() if disp_ise else []
        top_ibrx = score[disp_ibrx].rank(ascending=asc).sort_values().head(n_acoes).index.tolist() if disp_ibrx else []

        # Pega os retornos mensais do ano de holding (o ano seguinte à formação)
        ret_hold = ret_mensal.loc[f"{ano}-01":f"{ano}-12"]

        # Remove ações que não têm dados de preço nesse período
        top_ise = [t for t in top_ise if t in ret_hold.columns]
        top_ibrx = [t for t in top_ibrx if t in ret_hold.columns]
        if len(top_ise) == 0 or len(top_ibrx) == 0:
            continue

        # Calcula o retorno da carteira: média simples dos retornos das ações
        # (equal-weight = cada ação tem o mesmo peso, como fizemos na Magic Formula)
        r_ise = ret_hold[top_ise].mean(axis=1)
        r_ibrx_ = ret_hold[top_ibrx].mean(axis=1)
        lst_ise.append(r_ise)
        lst_ibrx.append(r_ibrx_)

        # Calcula o retorno acumulado do ano inteiro
        ra_ise = (1 + r_ise).prod() - 1
        ra_ibrx = (1 + r_ibrx_).prod() - 1
        tabela.append({"ano": ano, "ise_%": round(ra_ise * 100, 2), "ibrx_%": round(ra_ibrx * 100, 2)})

    # Junta todos os anos numa série contínua de retornos mensais
    ret_ise[fator] = pd.concat(lst_ise)
    ret_ibrx[fator] = pd.concat(lst_ibrx)
    tab_anual[fator] = pd.DataFrame(tabela)

# ============================================================
# PARTE 8 – MÉTRICAS DE DESEMPENHO
# ============================================================
# Calcula indicadores pra avaliar cada carteira:
# - Retorno total: quanto rendeu no período inteiro
# - Volatilidade anual: quanto oscilou (risco)
# - Sharpe: retorno acima da Selic por unidade de risco (quanto maior, melhor)
# - Drawdown máximo: maior queda do pico ao fundo (pior momento)

# Prepara dados do mercado e da Selic em base mensal
base_m = base.set_index("data").resample("ME").last()
ret_mercado = base_m["ibrx100"].pct_change().dropna()  # retorno mensal do IBrX-100
selic_m = (1 + base_m["selic_aa"] / 100) ** (1/12) - 1  # Selic anual → mensal
fatores = ["Momentum", "Valor", "Low Vol", "Qualidade"]

# Imprime a tabela de retornos anuais de cada fator
print("=== RETORNOS ANUAIS ===")
for fator in fatores:
    print(f"\n--- {fator} ---")
    print(tab_anual[fator].to_string(index=False))

# Calcula e imprime as métricas
print("\n=== MÉTRICAS ===")
for fator in fatores:
    for nome, s in [("ISE", ret_ise[fator]), ("IBrX", ret_ibrx[fator])]:
        rt = (1 + s).prod() - 1                          # retorno total acumulado
        vol = s.std() * np.sqrt(12)                       # volatilidade anualizada
        exc = (s - selic_m).dropna()                      # retorno acima da Selic
        sharpe = (exc.mean() / exc.std()) * np.sqrt(12)   # Sharpe anualizado
        cum = (1 + s).cumprod()                           # curva de patrimônio
        dd = (cum / cum.cummax() - 1).min()               # maior queda
        print(f"{fator:12s} {nome:5s}  Ret={rt*100:.2f}%  Vol={vol*100:.2f}%  Sharpe={sharpe:.4f}  DD={dd*100:.2f}%")

# ============================================================
# PARTE 9 – REGRESSÃO: ALFA DE JENSEN
# ============================================================
# O Alfa de Jensen mede se a carteira gerou retorno acima do esperado
# pelo CAPM. Se alfa > 0 e p-valor < 0.05, a carteira bateu o mercado
# de forma estatisticamente significativa.
#
# Fórmula: (ret_carteira - selic) = alfa + beta × (ret_mercado - selic)
# alfa = excesso de retorno não explicado pelo mercado
# beta = sensibilidade ao mercado (beta > 1 = mais arriscado)
# Erros HAC (Newey-West) pra corrigir autocorrelação nas séries temporais

modelos = {}
print("\n=== ALFA DE JENSEN ===")
for fator in fatores:
    for nome, s in [("ISE", ret_ise[fator]), ("IBrX", ret_ibrx[fator])]:
        # Alinha as datas das três séries (carteira, mercado, selic)
        dt = s.index.intersection(ret_mercado.index).intersection(selic_m.index)
        # Variável X: excesso de retorno do mercado (com constante pro alfa)
        X = sm.add_constant(ret_mercado.loc[dt] - selic_m.loc[dt])
        # Variável Y: excesso de retorno da carteira
        mod = sm.OLS(s.loc[dt] - selic_m.loc[dt], X).fit(cov_type='HAC', cov_kwds={'maxlags': 1})
        modelos[(fator, nome)] = mod
        sig = " *" if mod.pvalues.iloc[0] < 0.05 else ""  # asterisco se significativo
        print(f"{fator:12s} {nome:5s}  alfa={mod.params.iloc[0]*100:.4f}%  p={mod.pvalues.iloc[0]:.4f}{sig}  beta={mod.params.iloc[1]:.3f}")

# Imprime o resumo completo da regressão (apenas carteiras ISE)
for fator in fatores:
    print(f"\n--- {fator} ISE ---")
    print(modelos[(fator, "ISE")].summary())

# ============================================================
# PARTE 10 – CRISES
# ============================================================
# Compara como as carteiras ISE e IBrX se comportaram em períodos de crise.
# Se a carteira ESG caiu menos, isso sugere maior resiliência.
crises = {
    "Recessão 2015-16":  ("2016-01", "2016-12"),
    "COVID-19 (2020)":   ("2020-01", "2020-12"),
    "Aperto Mon. 21-22": ("2021-06", "2022-12"),
}
print("\n=== CRISES ===")
for fator in fatores:
    print(f"\n--- {fator} ---")
    for periodo, (ini, fim) in crises.items():
        ri = ret_ise[fator].loc[ini:fim]
        rb = ret_ibrx[fator].loc[ini:fim]
        if len(ri) == 0:
            continue
        # Retorno acumulado no período da crise
        print(f"  {periodo:20s}  ISE={(1+ri).prod()-1:.2%}  IBrX={(1+rb).prod()-1:.2%}")

# ============================================================
# PARTE 11 – GRÁFICOS
# ============================================================
# Cores diferentes pra cada fator (azul/laranja, verde/roxo, etc.)
cores = {"Momentum": ("#2196F3", "#FF9800"), "Valor": ("#4CAF50", "#9C27B0"),
         "Low Vol": ("#00BCD4", "#E91E63"), "Qualidade": ("#795548", "#607D8B")}

# GRÁFICO 1 — Evolução de R$1 investido em cada carteira
# Mostra como o patrimônio cresceu ao longo dos 9 anos
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
for ax, f in zip(axes.flat, fatores):
    ax.plot((1 + ret_ise[f]).cumprod(), label="ISE (ESG)", lw=2, color=cores[f][0])
    ax.plot((1 + ret_ibrx[f]).cumprod(), label="IBrX", lw=2, color=cores[f][1])
    ax.set_title(f); ax.set_ylabel("R$"); ax.legend(fontsize=9); ax.grid(alpha=0.3)
fig.suptitle("Evolução de R$1 Investido (2016-2024)", fontsize=14)
plt.tight_layout(); plt.savefig("grafico_retorno_acumulado.png", dpi=150); plt.show()

# GRÁFICO 2 — Drawdown: quanto caiu do pico ao fundo
# Quanto mais perto de 0%, menos a carteira caiu
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
for ax, f in zip(axes.flat, fatores):
    for s, label, cor in [(ret_ise[f], "ISE", cores[f][0]), (ret_ibrx[f], "IBrX", cores[f][1])]:
        cum = (1 + s).cumprod()
        ax.fill_between(cum.index, (cum / cum.cummax() - 1) * 100, alpha=0.4, label=label, color=cor)
    ax.set_title(f); ax.set_ylabel("%"); ax.legend(fontsize=9); ax.grid(alpha=0.3)
fig.suptitle("Drawdown (2016-2024)", fontsize=14)
plt.tight_layout(); plt.savefig("grafico_drawdown.png", dpi=150); plt.show()

# GRÁFICO 3 — Retorno anual: barras lado a lado ISE vs IBrX
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
for ax, f in zip(axes.flat, fatores):
    t = tab_anual[f]; x = np.arange(len(t))
    ax.bar(x - 0.175, t["ise_%"], 0.35, label="ISE", color=cores[f][0])
    ax.bar(x + 0.175, t["ibrx_%"], 0.35, label="IBrX", color=cores[f][1])
    ax.set_xticks(x); ax.set_xticklabels(t["ano"])
    ax.set_title(f); ax.set_ylabel("%"); ax.axhline(0, color="k", lw=0.5)
    ax.legend(fontsize=9); ax.grid(axis="y", alpha=0.3)
fig.suptitle("Retorno Anual por Fator (2016-2024)", fontsize=14)
plt.tight_layout(); plt.savefig("grafico_retornos_anuais.png", dpi=150); plt.show()

# GRÁFICO 4 — Correlação entre os retornos mensais de todas as carteiras
# Mostra se as estratégias se movem juntas ou de forma independente
dados_corr = {}
for f in fatores:
    dados_corr[f"{f} ISE"] = ret_ise[f]
    dados_corr[f"{f} IBrX"] = ret_ibrx[f]
dados_corr["Mercado"] = ret_mercado
plt.figure(figsize=(10, 8))
sns.heatmap(pd.DataFrame(dados_corr).dropna().corr(), annot=True, cmap="coolwarm", center=0, fmt=".2f")
plt.title("Correlação entre Retornos Mensais", fontsize=14)
plt.tight_layout(); plt.savefig("grafico_correlacao.png", dpi=150); plt.show()

# ============================================================
# PARTE 12 – RESULTADO FINAL
# ============================================================
# Resumo dos alfas de Jensen: principal resultado do TCC.
# Se o alfa da carteira ISE é positivo e significativo, o ESG agregou valor.
print("\n" + "=" * 60)
print("RESULTADO FINAL (2016-2024)")
print("=" * 60)
for fator in fatores:
    mi = modelos[(fator, "ISE")]
    mb = modelos[(fator, "IBrX")]
    print(f"\n{fator}:")
    print(f"  Alfa ISE  = {mi.params.iloc[0]*100:.4f}%  (p={mi.pvalues.iloc[0]:.4f})")
    print(f"  Alfa IBrX = {mb.params.iloc[0]*100:.4f}%  (p={mb.pvalues.iloc[0]:.4f})")
    print(f"  Beta ISE  = {mi.params.iloc[1]:.3f}   R² = {mi.rsquared:.3f}")

print("\n" + "=" * 60)
print("FIM")
print("=" * 60)
