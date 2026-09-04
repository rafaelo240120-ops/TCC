# ==============================================================
# TCC — ESG Factor Investing com ações do ISE B3
# Backtest 2016–2025  |  rebalanceamento ANUAL (buy-and-hold)
#
# Estratégia: no fechamento do último pregão do ano N-1 (data do
# sinal) rankeiam-se as ações do universo ISE B3 por 4 fatores.
# A carteira é montada no fechamento do pregão SEGUINTE e mantida
# sem rebalanceamento até o último pregão do ano N.
#
# Fatores:
#   1. Momentum    — maior retorno acumulado no ano anterior
#   2. Baixa Vol   — menor volatilidade anualizada no ano anterior
#   3. Valor (P/VP)— menor preço/valor patrimonial
#   4. Qualidade   — maior ROIC (retorno sobre capital investido)
#
# --------------------------------------------------------------
# CORREÇÕES APLICADAS — plano de trabalho, seções 1 e 2
#
# Cada código abaixo aparece como comentário no ponto exato do
# código onde a correção foi feita. Para localizar:
#     grep -n "CORREÇÃO C1" src/carteira_factor_investing.py
#
# Os efeitos foram medidos por src/ablacao_correcoes.py, que roda o
# backtest ligando uma correção por vez sobre a versão original.
#
#  cód.  assunto        o que estava errado          efeito medido
# ---------------------------------------------------------------
# [C0]  Caminhos       o script vive em src/ e os      não rodava
#                      dados em data/; as leituras
#                      usavam a pasta do script
# [C0b] Token          .env com BOM UTF-8: o token     falha muda
#                      ficava vazio e toda chamada
#                      à API voltava 401 em silêncio
# [C1]  Rebalanceam.   média transversal dos retornos  +1,80 p.p./ano
#                      diários = rebalancear TODO
#                      PREGÃO; o trabalho diz anual
# [C2]  Look-ahead     P/VP e ROIC de um planilhão de  -0,06 p.p./ano
#                      até 15/03 do ano N aplicados
#                      a retornos contados desde 01/01
# [C3]  Execução       o retorno 30/12 -> 02/01 era    +0,48 p.p./ano
#                      embolsado sem a posição existir
# [C4]  Multifator     a união dos top-10 tinha        nova carteira
#                      tamanho variável e não
#                      ponderava fator nenhum
# [C5]  Turnover       giro e custo de negociação      -0,18 p.p./ano
#                      não existiam
# [C6]  Dados          séries truncadas (CCR com 175   0 isolado; só
#                      pregões, Embraer com 44) e      age junto com
#                      mapa de tickers com erros       o C9
# [C7]  Delisting      ações incorporadas sumiam da    —
#                      carteira sem realizar resultado
# [C8]  Menores        pct_change(fill_method=None),   —
#                      TOP_N configurável, mais CSVs,
#                      gráfico de drawdown, main()
# [C10] Buracos        o reparo de série disparava por  ver §5
#                      contagem absoluta e não via furo
#                      no meio: a NATU3 tinha 1.582
#                      pregões mas 2020-2024 vazios
# [C9]  Códigos        o planilhão da API só usa o     -1,20 p.p./ano
#                      ticker ATUAL; o merge descartava
#                      em silêncio, todo ano, as 16
#                      empresas que trocaram de código
# ---------------------------------------------------------------
# Efeito líquido, mesma regra de carteira: 12,78% -> 13,62% ao ano.
# ==============================================================

from __future__ import annotations

import os
import time
from pathlib import Path

import matplotlib
try:
    get_ipython()  # type: ignore[name-defined]  # existe só em kernel Jupyter/Interactive Window
except NameError:
    matplotlib.use("Agg")  # script "puro" (terminal): sem tela, só salva os PNGs
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests

# ──────────────────────────────────────────────────────────────
# CONFIGURAÇÕES
# ──────────────────────────────────────────────────────────────
# [CORREÇÃO C0] Antes: PASTA = Path(__file__).parent, e o código
# procurava .env, precos_historicos_cache.csv e
# base_ise_ibrx_selic.csv dentro de src/. Os três estão na raiz do
# projeto e em data/ — FileNotFoundError garantido.
RAIZ      = Path(__file__).resolve().parents[1]
DIR_DADOS = RAIZ / "data"
DIR_FIG   = RAIZ / "fig"
DIR_DADOS.mkdir(exist_ok=True)
DIR_FIG.mkdir(exist_ok=True)

BASE_URL = "https://laboratoriodefinancas.com/api/v2"

ANO_INI, ANO_FIM = 2016, 2025
TOP_N            = int(os.environ.get("TCC_TOP_N", 10))   # ações por fator
MIN_PREGOES      = 150     # mínimo de pregões no ano de observação
JANELA_PLANILHAO = 150     # dias de busca retroativa do planilhão
MIN_COBERTURA    = 500     # abaixo disso, tenta re-baixar a série

# [CORREÇÃO C5] Custo por lado (corretagem + emolumentos B3 +
# slippage). 20 bps é hipótese conservadora para ações líquidas;
# a sensibilidade a 0/10/20/50 bps é reportada ao final.
CUSTO_POR_LADO = 0.0020
CUSTOS_SENSIB  = [0.0000, 0.0010, 0.0020, 0.0050]

DATA_INI, DATA_FIM = "2014-01-01", "2025-12-31"

# No Interactive Window a figura precisa continuar aberta para o kernel
# renderizá-la inline; como script, fechar evita acúmulo de memória.
NO_NOTEBOOK = matplotlib.get_backend().lower() != "agg"


def mostrar_ou_fechar(fig) -> None:
    if NO_NOTEBOOK:
        plt.show()
    else:
        plt.close(fig)


def carregar_token() -> str:
    """Token do Laboratório de Finanças: variável de ambiente ou .env."""
    if os.environ.get("LAB_FINANCAS_TOKEN"):
        return os.environ["LAB_FINANCAS_TOKEN"].strip()
    # [CORREÇÃO C0] encoding="utf-8-sig": o .env do projeto foi salvo
    # com BOM. Lido como utf-8 puro, a primeira linha vira
    # "﻿LAB_FINANCAS_TOKEN=..." e o startswith NUNCA casa — o
    # token ficava vazio e toda chamada à API voltava 401 em
    # silêncio, sem nenhuma mensagem de erro.
    for caminho in (RAIZ / ".env", Path(__file__).resolve().parent / ".env"):
        if caminho.exists():
            for linha in caminho.read_text(encoding="utf-8-sig").splitlines():
                linha = linha.lstrip("﻿").strip()
                if linha.startswith("LAB_FINANCAS_TOKEN="):
                    return linha.split("=", 1)[1].strip().strip("\"'")
    raise RuntimeError(
        "LAB_FINANCAS_TOKEN não encontrado. Defina a variável de ambiente ou "
        f"crie {RAIZ / '.env'} com a linha LAB_FINANCAS_TOKEN=<seu token>"
    )


TOKEN   = carregar_token()
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

# ──────────────────────────────────────────────────────────────
# UNIVERSO ELEGÍVEL — composição anual do ISE B3
#
# A carteira do ISE do ano N é divulgada em nov/dez de N-1 e vale
# a partir de janeiro de N. Usar universo_ise[N] para formar a
# carteira no fim de N-1 é, portanto, point-in-time.
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

    # [CORREÇÃO C6] TIET11 removido de 2021: as units da AES Tietê
    # foram convertidas em ações AESB3 em dez/2020 e AESB3 já
    # consta desta mesma lista. Mantendo os dois códigos, a mesma
    # empresa entrava DUAS VEZES na carteira, com peso dobrado.
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
# [CORREÇÃO C6] MAPA DE TICKERS RENOMEADOS
#
# Tanto o Yahoo quanto o Laboratório de Finanças arquivam o
# histórico completo da empresa sob o ticker ATUAL. O mapa aponta
# o código antigo para o código onde a série contínua está
# guardada. É a mesma empresa, mesmo preço ajustado.
#
# O que mudou em relação à versão anterior:
#  • SULA11 -> RDOR3  REMOVIDO. A SulAmérica foi INCORPORADA pela
#    Rede D'Or em 2022 — não é renomeação. Usar preço da RDOR3
#    (série que só começa em dez/2020) para a SULA11 em 2016-2021
#    é factualmente errado.
#  • FIBR3 -> SUZB3   REMOVIDO. A Fibria foi incorporada pela
#    Suzano em jan/2019. A FIBR3 tem série própria até lá e o
#    evento passa a ser tratado como delisting [C7].
#  • CESP6 -> AURE3   REMOVIDO. A CESP tem série própria até 2022
#    e só aparece no universo de 2016.
#  • LAME4 -> AMER3   REMOVIDO. Lojas Americanas (LAME4) e B2W
#    (BTOW3) eram empresas distintas até a fusão de 2021; só a
#    BTOW3 se tornou AMER3.
#  • AESB3 -> AURE3   REMOVIDO. A AESB3 tem série própria de 2016
#    a 2024, que é o período em que aparece no universo.
#  • TIET11 -> AESB3  CORRIGIDO (era AURE3). A AES Tietê virou AES
#    Brasil (AESB3, 2020) e só depois Auren (AURE3, 2022). Como a
#    série da AURE3 começa em 2022, a TIET11 ficava SEM PREÇO em
#    todo o período 2016-2021 em que está no universo: a ação
#    sumia silenciosamente do backtest.
#  • AZUL4 -> AZUL3   ACRESCENTADO. A Azul estava simplesmente
#    AUSENTE do cache e do backtest, embora conste do universo de
#    2022 a 2025; o Yahoo devolve 404 para AZUL4.SA.
#  • MRFG3 -> MBRF3   ACRESCENTADO. A Marfrig virou MBRF3 ao
#    incorporar a BRF em 2025 e também estava ausente do cache
#    (universo de 2021, 2022, 2023 e 2025). A série da MBRF3 é
#    distinta da BRFS3, então não há dupla contagem.
#  • EMBR3 -> EMBJ3   MANTIDO e agora funcional. A Embraer trocou
#    de código em 2025; o Yahoo devolve só 44 pregões para
#    EMBR3.SA e o cache guardava esses 44. Sem isso a Embraer era
#    excluída dos anos de 2016 e 2017.
# ──────────────────────────────────────────────────────────────
RENOMEADOS = {                                     # antigo → série arquivada em
    "ELET3":  "AXIA3",   # Eletrobras        → Axia              (2025)
    "TIET11": "AESB3",   # AES Tietê (units) → AES Brasil        (2020)
    "BTOW3":  "AMER3",   # B2W               → Americanas        (2021)
    "VIIA3":  "BHIA3",   # Via               → Grupo Casas Bahia (2023)
    "ALSO3":  "ALOS3",   # Aliansce Sonae    → Allos             (2023)
    "ARZZ3":  "AZZA3",   # Arezzo            → Azzas 2154        (2024)
    "CCRO3":  "MOTV3",   # CCR               → Motiva            (2025)
    "EMBR3":  "EMBJ3",   # Embraer           → novo código       (2025)
    "TIMP3":  "TIMS3",   # TIM Participações → TIM S.A.          (2020)
    "BRDT3":  "VBBR3",   # BR Distribuidora  → Vibra Energia     (2021)
    "DTEX3":  "DXCO3",   # Duratex           → Dexco             (2021)
    "TRPL4":  "ISAE4",   # ISA CTEEP         → ISA Energia       (2024)
    "NTCO3":  "NATU3",   # Natura &Co        → Natura            (2025)
    "GUAR3":  "RIAA3",   # Guararapes        → Riachuelo         (2025)
    "AZUL4":  "AZUL3",   # Azul PN           → Azul ON           (2025)
    "MRFG3":  "MBRF3",   # Marfrig           → MBRF (com a BRF)  (2025)
    "CPLE6":  "CPLE3",   # Copel PNB         → Copel ON          (2025)
}

ARQ_PRECOS = RAIZ / "precos_historicos_cache.csv"


# ──────────────────────────────────────────────────────────────
# PREÇOS HISTÓRICOS — cache local + download
#
# Fonte primária: Laboratório de Finanças (/preco/corrigido,
# fechamento ajustado por proventos e desdobramentos).
# Fallback: Yahoo Finance.
# ──────────────────────────────────────────────────────────────
def baixar_lab(ticker: str) -> pd.Series:
    try:
        resp = requests.get(
            f"{BASE_URL}/preco/corrigido", headers=HEADERS,
            params={"ticker": ticker, "data_ini": DATA_INI, "data_fim": DATA_FIM},
            timeout=90,
        )
        if resp.status_code != 200:
            return pd.Series(dtype=float)
        dados = resp.json()
        if isinstance(dados, dict):
            dados = dados.get("results", dados.get("data", []))
        if not dados:
            return pd.Series(dtype=float)
        df = pd.DataFrame(dados)
        df["data"]       = pd.to_datetime(df["data"])
        df["fechamento"] = pd.to_numeric(df["fechamento"], errors="coerce")
        return (df.dropna(subset=["fechamento"])
                  .set_index("data")["fechamento"].sort_index())
    except Exception:
        return pd.Series(dtype=float)


def baixar_yahoo(ticker: str) -> pd.Series:
    try:
        import yfinance as yf
        hist = yf.Ticker(f"{ticker}.SA").history(
            start=DATA_INI, end=DATA_FIM, auto_adjust=True)
        if hist.empty:
            return pd.Series(dtype=float)
        serie = hist["Close"].dropna()
        if serie.index.tz is not None:
            serie.index = serie.index.tz_localize(None)
        serie.index = pd.to_datetime(serie.index).normalize()
        return serie.sort_index()
    except Exception:
        return pd.Series(dtype=float)


def carregar_precos() -> pd.DataFrame:
    df = (pd.read_csv(ARQ_PRECOS, index_col=0, parse_dates=True)
          if ARQ_PRECOS.exists() else pd.DataFrame())

    necessarios = sorted(
        set(t for lista in universo_ise.values() for t in lista) |
        set(RENOMEADOS.values()))

    def cobertura(t: str) -> int:
        return 0 if t not in df.columns else int(df[t].notna().sum())

    def tem_buraco(t: str) -> bool:
        """Série com furo no meio do próprio intervalo de vida.

        [CORREÇÃO C10] O critério anterior era contagem absoluta
        (`< MIN_COBERTURA`), que não enxerga buraco interno: a NATU3
        tinha 1.582 pregões — acima do corte — mas com 2020 a 2024
        inteiramente vazios, porque nesse período o código era NTCO3.
        A Natura ficava fora de cinco carteiras seguidas, em silêncio.
        Agora compara-se o que a série tem com o que ela deveria ter
        entre o primeiro e o último pregão dela própria.
        """
        if t not in df.columns:
            return False
        s = df[t].dropna()
        if len(s) < 2:
            return False
        esperado = int(((df.index >= s.index[0]) & (df.index <= s.index[-1])).sum())
        return esperado > 0 and len(s) / esperado < 0.90

    # [CORREÇÃO C6] Antes só se baixava o que estava totalmente
    # ausente. Séries truncadas (EMBJ3 com 44 pregões de um total
    # de ~2.980) passavam batido e a empresa era descartada pelo
    # filtro de MIN_PREGOES sem nenhum aviso.
    faltantes = [t for t in necessarios
                 if cobertura(t) < MIN_COBERTURA or tem_buraco(t)]

    if faltantes:
        print(f"Baixando/reparando {len(faltantes)} séries...")
        novas = {}
        for ticker in faltantes:
            serie, fonte = baixar_lab(ticker), "lab"
            if serie.empty:
                serie, fonte = baixar_yahoo(ticker), "yahoo"
            if serie.empty:
                print(f"  SEM DADO: {ticker}")
            elif len(serie) > cobertura(ticker):   # só troca se cobrir mais
                novas[ticker] = serie.rename(ticker)
                print(f"  OK ({fonte:5}): {ticker:7} "
                      f"{cobertura(ticker):5} -> {len(serie):5} pregões")
            else:
                print(f"  mantido  : {ticker:7} ({cobertura(ticker)} pregões)")
            time.sleep(0.15)
        if novas:
            for t, s in novas.items():
                df[t] = s
    else:
        print("Cache de preços completo — nenhum download necessário.")

    # [CORREÇÃO C6] Herança incondicional para tickers renomeados.
    # Antes a série só era herdada se a coluna antiga estivesse
    # VAZIA — mas o Yahoo devolve, sob o código antigo, um pedaço
    # da série do sucessor (TIET11 = AURE3 a partir de 2022). Com
    # 941 pregões a coluna não estava vazia, a herança não ocorria
    # e a TIET11 ficava sem preço em 2016-2021.
    for antigo, novo in RENOMEADOS.items():
        if novo in df.columns and df[novo].notna().any():
            df[antigo] = df[novo]

    df = df.sort_index().sort_index(axis=1)
    df.to_csv(ARQ_PRECOS, encoding="utf-8")
    return df


df_precos = carregar_precos()


# [CORREÇÃO C6] Depois da herança, dois códigos do universo podem
# apontar para a MESMA série (ex.: TIET11 e AESB3 em 2021). Isso
# dobra o peso da empresa. A função abaixo deduplica e avisa.
def universo_efetivo(ano: int) -> list[str]:
    """Universo do ISE do ano, em CÓDIGOS CANÔNICOS (o ticker atual).

    [CORREÇÃO C9] O Laboratório de Finanças arquiva tudo — planilhão,
    estatísticas e preços — sob o ticker ATUAL da empresa. As listas
    do ISE, por serem históricas, usam o código da época. O merge
    `on="Ticker"` entre os fatores de preço e o planilhão descartava,
    em silêncio e TODO ANO, as 16 empresas que trocaram de código:
    CCR, Eletrobras, Embraer, TIM, Duratex, B2W, ISA CTEEP, BR
    Distribuidora, Arezzo, Aliansce, Via, AES Tietê, Azul, Marfrig,
    Guararapes e Natura &Co. Elas nunca chegavam a ser ranqueadas.

    Traduzir o universo para o código canônico antes de qualquer
    junção resolve o problema e ainda torna exata a checagem de
    duplicidade: TIET11 e AESB3, no universo de 2021, colapsam
    naturalmente na mesma entrada.
    """
    saida: list[str] = []
    for t in universo_ise[ano]:
        canon = RENOMEADOS.get(t, t)
        if canon not in df_precos.columns or df_precos[canon].dropna().empty:
            continue
        if canon in saida:
            print(f"  duplicidade {ano}: {t} -> {canon} (já no universo)")
            continue
        saida.append(canon)
    return saida


# ──────────────────────────────────────────────────────────────
# BENCHMARKS — IBrX-100, ISE B3 e Selic
#
# Carregados ANTES dos retornos porque o índice deste arquivo, que
# vem da B3, é o calendário oficial de pregões [CORREÇÃO C11].
# ──────────────────────────────────────────────────────────────
df_bench = (pd.read_csv(DIR_DADOS / "base_ise_ibrx_selic.csv", parse_dates=["data"])
              .sort_values("data").set_index("data"))

# [CORREÇÃO C11] A base de preços da API traz FERIADOS NACIONAIS com
# o preço repetido do pregão anterior — 72 dos ~155 tickers em
# 07/09/2017, 12/10, 02/11, 15/11 e 25/12, contra apenas 1 ticker
# nos mesmos feriados de 2016. Isso cria retornos zero falsos que
# subestimam a volatilidade, e de forma DESIGUAL entre as ações,
# porque só parte delas recebe o preço repetido — o que enviesa
# diretamente o ranking do fator Baixa Volatilidade. Restringir ao
# calendário da B3 elimina o problema e ainda faz o backtest e a
# tabela final trabalharem sobre exatamente os mesmos pregões.
_antes = len(df_precos)
df_precos = df_precos.loc[df_precos.index.isin(df_bench.index)]
print(f"Calendário B3: {_antes} -> {len(df_precos)} pregões "
      f"({_antes - len(df_precos)} datas fora do calendário removidas)")

# [CORREÇÃO] pct_change sem preenchimento implícito: um buraco na
# série não pode virar "retorno de um dia".
df_retornos = df_precos.pct_change(fill_method=None)
print(f"Preços: {df_precos.shape[1]} ações | {len(df_precos)} pregões "
      f"({df_precos.index.min().date()} a {df_precos.index.max().date()})")
df_bench["ret_ise"]   = df_bench["ise_b3"].pct_change(fill_method=None)
df_bench["ret_ibrx"]  = df_bench["ibrx100"].pct_change(fill_method=None)
df_bench["selic_dia"] = (1 + df_bench["selic_aa"] / 100) ** (1 / 252) - 1
selic_dia = df_bench["selic_dia"]

# ──────────────────────────────────────────────────────────────
# [CORREÇÃO C3] CALENDÁRIO DE REBALANCEAMENTO
#
#   d_ini_obs = primeiro pregão de N-1
#   d_sinal   = último pregão de N-1   → fatores medidos AQUI
#   d_compra  = primeiro pregão de N   → execução no fechamento
#   d_fim     = último pregão de N     → fim do período de posse
#
# O primeiro retorno computado é d_compra -> pregão seguinte.
# O retorno d_sinal -> d_compra fica de FORA: nesse intervalo a
# posição ainda não existia. Antes ele era embolsado.
# ──────────────────────────────────────────────────────────────
pregoes = df_precos.index


def calendario(ano: int):
    ant = pregoes[(pregoes >= f"{ano-1}-01-01") & (pregoes <= f"{ano-1}-12-31")]
    cur = pregoes[(pregoes >= f"{ano}-01-01")   & (pregoes <= f"{ano}-12-31")]
    if len(ant) < MIN_PREGOES or len(cur) < 2:
        return None
    return {"d_ini_obs": ant[0], "d_sinal": ant[-1],
            "d_compra": cur[0],  "d_fim": cur[-1]}


# ──────────────────────────────────────────────────────────────
# [CORREÇÃO C2] PLANILHÃO POINT-IN-TIME
#
# Antes: tentava-se 15/01, 20/01, 31/01, 15/02, 01/03 e 15/03 do
# ano N e parava-se na primeira data com dados — mas o retorno era
# contado desde 01/01. Em 2016 o planilhão só respondeu em
# 01/03/2016: a carteira usava fundamentos de MARÇO para render
# desde JANEIRO. Dois meses de look-ahead.
#
# Agora: busca-se para trás a partir da data do sinal e usa-se o
# último planilhão publicado ATÉ ela.
# ──────────────────────────────────────────────────────────────
_cache_planilhao: dict[str, pd.DataFrame] = {}
_planilhao_vazio: set[str] = set()


def buscar_planilhao(data_ref: pd.Timestamp):
    for k in range(JANELA_PLANILHAO):
        data = (data_ref - pd.Timedelta(days=k)).strftime("%Y-%m-%d")
        if data in _cache_planilhao:
            return _cache_planilhao[data], data
        if data in _planilhao_vazio:
            continue
        try:
            resp = requests.get(f"{BASE_URL}/bolsa/planilhao", headers=HEADERS,
                                params={"data_base": data}, timeout=60)
            dados = resp.json() if resp.status_code == 200 else []
        except Exception:
            dados = []
        if isinstance(dados, dict):
            dados = dados.get("results", dados.get("data", []))
        if dados:
            df = pd.DataFrame(dados)
            df.columns   = [str(c).lower() for c in df.columns]
            df["Ticker"] = df["ticker"].astype(str).str.upper()
            for col in ("p_vp", "roic"):
                df[col] = pd.to_numeric(df[col], errors="coerce")
            df = df[["Ticker", "p_vp", "roic", "ano_tri", "setor"]]
            _cache_planilhao[data] = df
            return df, data
        _planilhao_vazio.add(data)
    return pd.DataFrame(), None


# ──────────────────────────────────────────────────────────────
# [CORREÇÃO C1/C3/C7] RETORNO BUY-AND-HOLD
#
# Antes:
#     ret = df_retornos.loc[f"{ano}-01-01":f"{ano}-12-31", tk].mean(axis=1)
#
# A média transversal dos retornos diários equivale a REBALANCEAR
# PARA PESOS IGUAIS TODO PREGÃO. É o oposto do rebalanceamento
# anual descrito no trabalho e embute uma estratégia contrária
# (vende quem subiu, compra quem caiu) que infla o retorno.
#
# Agora: compram-se quantidades fixas no fechamento de d_compra e
# o valor de cada posição flutua livremente até d_fim.
# ──────────────────────────────────────────────────────────────
def retorno_buy_and_hold(tickers, d_compra, d_fim):
    """Retornos diários de uma carteira comprada em d_compra e mantida até d_fim.

    Devolve (retornos, pesos_finais_com_drift, tickers_efetivamente_usados).
    Ação que deixa de negociar é liquidada ao último preço e o valor
    segue em caixa remunerado pela Selic [CORREÇÃO C7] — antes ela
    simplesmente sumia da média, sem realizar resultado.
    """
    tickers = [t for t in tickers if t in df_precos.columns]
    jan = df_precos.loc[d_compra:d_fim]

    validos, preco_compra = [], {}
    for t in tickers:
        hist = df_precos.loc[:d_compra, t].dropna()
        if hist.empty or not jan[t].notna().any():
            continue
        validos.append(t)
        preco_compra[t] = float(hist.iloc[-1])   # fechamento de d_compra

    if not validos:
        return pd.Series(dtype=float), pd.Series(dtype=float), []

    pesos   = pd.Series(1.0 / len(validos), index=validos)
    sel     = selic_dia.reindex(jan.index).fillna(0.0)
    valores = pd.DataFrame(index=jan.index, columns=validos, dtype=float)

    for t in validos:
        qtd   = pesos[t] / preco_compra[t]
        bruto = jan[t]
        # ffill para pregões sem negócio; os dias iniciais sem preço
        # recebem o PREÇO DE COMPRA (nunca um preço futuro).
        valor = qtd * bruto.ffill().fillna(preco_compra[t])
        ultimo = bruto.last_valid_index()
        # [CORREÇÃO C10] exige um buraco de pelo menos 3 pregões: em
        # 2017-12-29 a fonte só tem 73 dos 155 tickers, e sem essa
        # folga 11 ações apareciam como "deslistadas" por um dia.
        falta_no_fim = int((jan.index > ultimo).sum()) if ultimo is not None else 0
        if ultimo is not None and falta_no_fim >= 3:
            depois = jan.index > ultimo
            valor.loc[depois] = (qtd * float(bruto.loc[ultimo])
                                 * (1 + sel[depois]).cumprod())
        valores[t] = valor

    total = valores.sum(axis=1)
    ret   = total.pct_change(fill_method=None)
    ret.iloc[0] = 0.0                    # [C3] dia da compra não rende

    return ret, valores.iloc[-1] / total.iloc[-1], validos


# [CORREÇÃO C12] Anualização pelo tempo de calendário
def anualiza(total: float, idx) -> float:
    """Retorno anualizado pelo tempo de CALENDÁRIO decorrido.

    [CORREÇÃO C12] Antes usava-se (1+total)**(252/n)-1, que supõe
    exatamente 252 pregões por ano. A amostra tem 2.483 pregões em
    dez anos — 248,3 por ano —, então o expoente 252/n anualizava
    como se o período tivesse 9,85 anos em vez de 9,99, inflando
    todo retorno anual em cerca de 0,20 p.p. O viés é igual para
    todas as séries, mas os números absolutos vão para o texto.
    """
    anos = (idx[-1] - idx[0]).days / 365.25
    return (1 + total) ** (1 / anos) - 1 if anos > 0 else float("nan")


# [CORREÇÃO C5] Giro da carteira e custo de negociação
def calcular_turnover(pesos_antes: pd.Series, pesos_alvo: pd.Series) -> float:
    """Turnover one-way: 0,5 * soma |peso_alvo - peso_anterior|.

    pesos_antes são os pesos do fim do ano anterior, JÁ com o drift
    de preço — é contra eles que se mede o giro de um buy-and-hold.
    Na montagem inicial vale 0,5 (só há compras); como o custo é
    cobrado nas duas pontas (2 x turnover x custo/lado), isso dá
    exatamente 1 x custo por lado, que é o correto.
    """
    idx = pesos_antes.index.union(pesos_alvo.index)
    a = pesos_antes.reindex(idx).fillna(0.0)
    b = pesos_alvo.reindex(idx).fillna(0.0)
    return float(0.5 * (b - a).abs().sum())


# ──────────────────────────────────────────────────────────────
# [CORREÇÃO C4] DEFINIÇÃO DAS CARTEIRAS
#
# Antes havia UMA carteira: a união dos top-10 de cada fator.
# Problemas: tamanho variável (15 a 40 ações) e uma ação presente
# em 3 rankings pesava igual a uma presente em 1 — ou seja, a
# "carteira multifatorial" não ponderava fator nenhum.
#
# Agora:
#  • 4 subcarteiras isoladas (top-10 de cada fator), que mostram a
#    contribuição de cada fator separadamente;
#  • Multifator = top-10 do SCORE COMBINADO — média dos rankings
#    percentuais dos 4 fatores, tamanho fixo;
#  • Uniao_TCC = a regra original, mantida apenas para comparação.
#
# Usa-se rank percentual em vez de z-score porque P/VP e ROIC têm
# outliers extremos (ROIC acima de 100%) que dominariam a média.
# ──────────────────────────────────────────────────────────────
def montar_rankings(df_fat: pd.DataFrame) -> dict[str, list[str]]:
    f = df_fat.set_index("Ticker")
    tops = {
        "Momentum":  f["momentum"].dropna().sort_values(ascending=False).head(TOP_N).index.tolist(),
        "Baixa_Vol": f["baixa_vol"].dropna().sort_values(ascending=True).head(TOP_N).index.tolist(),
        "Valor":     f.loc[f["p_vp"] > 0, "p_vp"].sort_values(ascending=True).head(TOP_N).index.tolist(),
        "Qualidade": f["roic"].dropna().sort_values(ascending=False).head(TOP_N).index.tolist(),
    }
    r = pd.DataFrame(index=f.index)
    r["momentum"]  = f["momentum"].rank(pct=True, ascending=True)    # maior é melhor
    r["baixa_vol"] = f["baixa_vol"].rank(pct=True, ascending=False)  # menor é melhor
    r["valor"]     = f["p_vp"].where(f["p_vp"] > 0).rank(pct=True, ascending=False)
    r["qualidade"] = f["roic"].rank(pct=True, ascending=True)
    score = r.mean(axis=1, skipna=False).dropna()    # exige os 4 fatores

    tops["Multifator"] = score.sort_values(ascending=False).head(TOP_N).index.tolist()
    tops["Uniao_TCC"]  = sorted(set(tops["Momentum"] + tops["Baixa_Vol"] +
                                    tops["Valor"] + tops["Qualidade"]))
    return tops


ESTRATEGIAS = ["Momentum", "Baixa_Vol", "Valor", "Qualidade", "Multifator", "Uniao_TCC"]

# ──────────────────────────────────────────────────────────────
# BACKTEST
# ──────────────────────────────────────────────────────────────
def main():
    """Executa o backtest completo e grava tabelas e figuras.

    Fica sob `if __name__` para que outros scripts (comparacao_universos.py,
    ablacao_correcoes.py) possam importar as funcoes e os dados sem
    disparar o backtest inteiro.
    """
    ret_por_estrategia = {e: [] for e in ESTRATEGIAS}
    pesos_anteriores   = {e: pd.Series(dtype=float) for e in ESTRATEGIAS}
    registro_turnover, resumo_anos, composicoes = [], [], []
    setor_por_ticker: dict[str, str] = {}

    for ano in range(ANO_INI, ANO_FIM + 1):
        cal = calendario(ano)
        if cal is None:
            print(f"\n--- {ano}: calendário insuficiente, ano ignorado ---")
            continue

        print(f"\n--- {ano} ---")
        print(f"  sinal={cal['d_sinal'].date()}  compra={cal['d_compra'].date()}  "
              f"fim={cal['d_fim'].date()}")

        # ── Fatores de preço, medidos ATÉ o fechamento do sinal [C3] ──
        linhas = []
        for ticker in universo_efetivo(ano):
            p = df_precos.loc[cal["d_ini_obs"]:cal["d_sinal"], ticker].dropna()
            r = df_retornos.loc[cal["d_ini_obs"]:cal["d_sinal"], ticker].dropna()
            if len(p) < MIN_PREGOES:
                continue
            linhas.append({"Ticker":    ticker,
                           "momentum":  p.iloc[-1] / p.iloc[0] - 1,
                           "baixa_vol": r.std() * np.sqrt(252)})
        df_fat = pd.DataFrame(linhas)
        if df_fat.empty:
            print("  sem fatores de preço — ano ignorado")
            continue

        # ── Fundamentos point-in-time [C2] ─────────────────────────
        df_plan, data_base = buscar_planilhao(cal["d_sinal"])
        if df_plan.empty:
            print(f"  Planilhão: nada até {cal['d_sinal'].date()} — ano ignorado")
            continue
        print(f"  Planilhão: data_base={data_base}  "
              f"(trimestres {sorted(df_plan['ano_tri'].dropna().unique())})")
        setor_por_ticker.update(dict(zip(df_plan["Ticker"], df_plan["setor"])))

        df_fat = pd.merge(df_fat, df_plan[["Ticker", "p_vp", "roic"]],
                          on="Ticker", how="inner")
        if df_fat.empty:
            print("  nenhuma ação com preço E fundamento — ano ignorado")
            continue
        print(f"  universo com dados completos: {len(df_fat)} ações")

        tops = montar_rankings(df_fat)
        for nome in ("Momentum", "Baixa_Vol", "Valor", "Qualidade", "Multifator"):
            print(f"  {nome:10}: {tops[nome]}")
        print(f"  {'Uniao_TCC':10}: {len(tops['Uniao_TCC'])} ações")

        linha = {"Ano": ano, "Data_Sinal": cal["d_sinal"].date(),
                 "Data_Compra": cal["d_compra"].date(), "Planilhao": data_base,
                 "N_universo": len(df_fat)}

        for est in ESTRATEGIAS:
            if not tops[est]:
                continue
            alvo = pd.Series(1.0 / len(tops[est]), index=tops[est])
            giro = calcular_turnover(pesos_anteriores[est], alvo)
            ret, pesos_fim, usados = retorno_buy_and_hold(
                tops[est], cal["d_compra"], cal["d_fim"])
            if ret.empty:
                continue

            # [C5] custo nas duas pontas, cobrado no dia da montagem
            custo = 2.0 * giro * CUSTO_POR_LADO
            ret.iloc[0] -= custo

            ret_por_estrategia[est].append(ret)
            pesos_anteriores[est] = pesos_fim
            registro_turnover.append({"Ano": ano, "Estrategia": est,
                                      "N_acoes": len(usados),
                                      "Turnover": round(giro, 4),
                                      "Custo_bps": round(custo * 1e4, 1)})
            linha[f"{est}_carteira"] = ", ".join(tops[est])
            linha[f"{est}_turnover"] = round(giro, 4)
            for t in tops[est]:
                composicoes.append({"Ano": ano, "Estrategia": est, "Ticker": t,
                                    "Setor": setor_por_ticker.get(t, "n/d"),
                                    "Peso": round(1.0 / len(tops[est]), 4)})

        resumo_anos.append(linha)

    # ──────────────────────────────────────────────────────────────
    # CONSOLIDAÇÃO
    # ──────────────────────────────────────────────────────────────
    df_ret = pd.DataFrame({e: pd.concat(s) for e, s in ret_por_estrategia.items() if s})
    df_ret = (df_ret.join(df_bench[["ret_ise", "ret_ibrx", "selic_dia"]], how="inner")
                    .dropna(subset=["ret_ise", "ret_ibrx"]).sort_index())
    df_ret.index.name = "data"

    COLUNAS = [c for c in ESTRATEGIAS if c in df_ret] + ["ret_ibrx", "ret_ise"]
    ROTULOS = {"Momentum":   "Fator Momentum",     "Baixa_Vol": "Fator Baixa Vol",
               "Valor":      "Fator Valor",        "Qualidade": "Fator Qualidade",
               "Multifator": "Multifator (score)", "Uniao_TCC": "Uniao top-10 (TCC)",
               "ret_ibrx":   "IBrX-100",           "ret_ise":   "ISE B3"}

    df_acum = (1 + df_ret[COLUNAS].fillna(0)).cumprod() * 100

    # ──────────────────────────────────────────────────────────────
    # ESTATÍSTICAS
    # ──────────────────────────────────────────────────────────────
    df_turnover = pd.DataFrame(registro_turnover)
    giro_medio  = df_turnover.groupby("Estrategia")["Turnover"].mean()

    stats = []
    for col in COLUNAS:
        ret   = df_ret[col].dropna()
        total = (1 + ret).prod() - 1
        anual = anualiza(total, ret.index)
        vol   = ret.std() * np.sqrt(252)
        exc   = ret - df_ret["selic_dia"].reindex(ret.index)
        patr  = (1 + ret).cumprod()
        stats.append({
            "Estrategia":        ROTULOS[col],
            "Retorno Total (%)": round(total * 100, 2),
            "Retorno Anual (%)": round(anual * 100, 2),
            "Volatilidade (%)":  round(vol * 100, 2),
            "Sharpe":            round(exc.mean() / exc.std() * np.sqrt(252), 2),
            "Max Drawdown (%)":  round((patr / patr.cummax() - 1).min() * 100, 2),
            "Turnover medio":    round(float(giro_medio.get(col, np.nan)), 3)
                                 if col in giro_medio.index else np.nan,
        })
    df_stats = pd.DataFrame(stats)

    df_ano = ((df_ret[COLUNAS].fillna(0) + 1)
              .groupby(df_ret.index.year).prod() - 1) * 100
    df_ano = df_ano.round(2)
    df_ano.index.name = "Ano"
    df_ano.columns = [ROTULOS[c] for c in df_ano.columns]

    print("\n" + "=" * 92)
    print(f"  Desempenho — backtest {ANO_INI}-{ANO_FIM} | rebalanceamento anual | "
          f"custo {CUSTO_POR_LADO*1e4:.0f} bps por lado")
    print("=" * 92)
    print(df_stats.to_string(index=False))

    print("\n--- Retorno por ano civil (%) ---")
    print(df_ano.to_string())

    print("\n--- Giro anual da carteira (turnover one-way) ---")
    print(df_turnover.pivot(index="Ano", columns="Estrategia",
                            values="Turnover").to_string())

    # [C5] Sensibilidade ao custo de negociação
    print("\n--- Sensibilidade ao custo de negociação (retorno anualizado %) ---")
    linhas_sens = []
    for c in CUSTOS_SENSIB:
        linha_s = {"Custo (bps/lado)": int(c * 1e4)}
        for est in [e for e in ESTRATEGIAS if e in df_ret]:
            r = df_ret[est].dropna().copy()
            for _, row in df_turnover[df_turnover.Estrategia == est].iterrows():
                dias = r.index[r.index.year == row["Ano"]]
                if len(dias):
                    r.loc[dias[0]] -= 2 * row["Turnover"] * (c - CUSTO_POR_LADO)
            tot = (1 + r).prod() - 1
            linha_s[ROTULOS[est]] = round(anualiza(tot, r.index) * 100, 2)
        linhas_sens.append(linha_s)
    df_sens = pd.DataFrame(linhas_sens)
    print(df_sens.to_string(index=False))

    # ──────────────────────────────────────────────────────────────
    # SALVAR RESULTADOS
    # ──────────────────────────────────────────────────────────────
    pd.DataFrame(resumo_anos).to_csv(DIR_DADOS / "carteiras_selecionadas.csv",
                                     index=False, encoding="utf-8-sig")
    pd.DataFrame(composicoes).to_csv(DIR_DADOS / "composicao_carteiras.csv",
                                     index=False, encoding="utf-8-sig")
    df_ret.to_csv(DIR_DADOS / "retornos_diarios_factor.csv", encoding="utf-8-sig")
    df_acum.to_csv(DIR_DADOS / "retornos_acumulados_factor.csv", encoding="utf-8-sig")
    SUF = os.environ.get("TCC_SUFIXO", "")
    df_stats.to_csv(DIR_DADOS / f"performance_comparativa{SUF}.csv",
                    index=False, encoding="utf-8-sig")
    df_ano.to_csv(DIR_DADOS / "retornos_anuais.csv", encoding="utf-8-sig")
    df_turnover.to_csv(DIR_DADOS / "turnover_por_ano.csv",
                       index=False, encoding="utf-8-sig")
    df_sens.to_csv(DIR_DADOS / "sensibilidade_custos.csv",
                   index=False, encoding="utf-8-sig")

    # ──────────────────────────────────────────────────────────────
    # GRÁFICOS — patrimônio e drawdown
    # ──────────────────────────────────────────────────────────────
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 8), sharex=True,
                                   gridspec_kw={"height_ratios": [2, 1]})
    destaque = [c for c in ("Multifator", "Uniao_TCC", "ret_ibrx", "ret_ise")
                if c in df_acum]
    estilos = {"Multifator": "-", "Uniao_TCC": "-", "ret_ibrx": "--", "ret_ise": ":"}
    for col in destaque:
        lw = 2 if col in ("Multifator", "Uniao_TCC") else 1.5
        ax1.plot(df_acum[col], label=ROTULOS[col], linestyle=estilos[col], linewidth=lw)
        ax2.plot((df_acum[col] / df_acum[col].cummax() - 1) * 100,
                 linestyle=estilos[col], linewidth=1.2)
    ax1.set_title(f"Retorno acumulado — carteiras fatoriais ESG vs benchmarks "
                  f"({ANO_INI}-{ANO_FIM})")
    ax1.set_ylabel("Base 100")
    ax1.legend()
    ax1.grid(True, linestyle=":", alpha=0.6)
    ax2.set_title("Drawdown (%)")
    ax2.set_xlabel("Data")
    ax2.grid(True, linestyle=":", alpha=0.6)
    plt.tight_layout()
    plt.savefig(DIR_FIG / "comparacao_performance.png", dpi=150)
    mostrar_ou_fechar(fig)

    fig2, ax = plt.subplots(figsize=(11, 5))
    for est in ESTRATEGIAS:
        if est in df_acum:
            ax.plot(df_acum[est], label=ROTULOS[est], linewidth=1.5)
    ax.plot(df_acum["ret_ise"], label="ISE B3", color="black",
            linestyle=":", linewidth=1.8)
    ax.set_title(f"Carteiras por fator — base 100 ({ANO_INI}-{ANO_FIM})")
    ax.set_ylabel("Base 100")
    ax.legend(ncol=2)
    ax.grid(True, linestyle=":", alpha=0.6)
    plt.tight_layout()
    plt.savefig(DIR_FIG / "carteiras_por_fator.png", dpi=150)
    mostrar_ou_fechar(fig2)

    print(f"\nArquivos salvos em {DIR_DADOS} e {DIR_FIG}")


if __name__ == "__main__":
    main()
