# ==========================================================================================
# TCC — ESTRATÉGIAS DE FACTOR INVESTING NO UNIVERSO DO ISE B3 (2016–2025)
# Backtest com rebalanceamento ANUAL, comparado ao IBrX-100 e ao ISE B3
#
# Estratégia: no fechamento do último pregão do ano N-1 (data do sinal), as ações do
# universo são ordenadas por quatro fatores. A carteira é comprada no fechamento do pregão
# SEGUINTE (data de execução) e mantida, sem rebalanceamento, até o último pregão do ano N.
#
# Carteiras, todas com pesos iguais na compra:
#   Momentum ............ as 10 de maior retorno no ano anterior
#   Baixa volatilidade .. as 10 de menor volatilidade no ano anterior
#   Valor ............... as 10 de menor P/VP positivo
#   Qualidade ........... as 10 de maior ROIC
#   Multifator .......... as 10 de maior média dos percentis dos quatro fatores
#   União ............... a reunião das quatro listas (regra da primeira versão do TCC)
#   Universo_EW ......... todas as ações elegíveis (separa o efeito do fator do da ponderação)
# Tudo é feito em dois universos: ISE (lista do ISE B3 de cada ano) e AMPLO_PROXY (as cem
# ações de maior volume negociado, aproximação do IBrX-100).
#
# O QUE MUDOU DESDE A PRIMEIRA VERSÃO (plano de trabalho do orientador)
#   - rebalanceamento de fato anual: compra no início do ano e pesos livres até dezembro;
#   - sinal no fechamento de D e compra no fechamento de D+1; o retorno entre os dois não conta;
#   - P/VP e ROIC só da consulta com data até o sinal (nenhuma informação futura);
#   - Multifator por pontuação combinada; a União fica só para comparar com a versão original;
#   - custo de 0,20% por lado pago pela própria carteira, giro medido a cada rebalanceamento;
#   - eventos societários documentados; ação que para de negociar vira caixa com Selic;
#   - mesmas regras no universo amplo e carteiras de pesos iguais nos dois universos;
#   - testes de Sharpe, de médias e de interação, alfas com fatores NEFIN e correção de Holm;
#   - conferência de séries, métricas, posições e ordens antes de gravar qualquer resultado.
#
# COMO EXECUTAR, nesta pasta:
#   python carteira_factor_investing.py            estudo completo (cerca de 2 minutos)
#   python carteira_factor_investing.py --testar   só os testes internos (segundos)
# O estudo roda sem token. Para baixar de novo P/VP e ROIC da API do Laboratório de Finanças,
# cole o token em TOKEN_LAB_FINANCAS e use ATUALIZAR_FUNDAMENTOS = True (Parte 1).
#
# O ESTUDO, NA ORDEM EM QUE ACONTECE (cada passo é uma parte deste arquivo)
#   Parte 1   Configuração ................................ parâmetros do estudo
#   Parte 2   Dados: as ações de cada ano, preços,
#             índices, Selic e fundamentos ................ TCC 4.2
#   Parte 3   Formação das carteiras, ano a ano ........... TCC 4.3, Equações 1 a 4
#   Parte 4   Simulação: compra, caixa, eventos e custos .. TCC 4.4, Equações 5 a 7
#   Parte 5   Desempenho .................................. TCC 4.5 e 5.1 a 5.4, Equações 8 a 12
#   Parte 6   Conferências (dados oficiais, séries, ordens) TCC 4.2, 4.4 e 5.6
#   Parte 7   Testes estatísticos e alfas ................. TCC 4.5 e 5.3, Equação 13
#   Parte 8   Robustez .................................... TCC 4.6 e 5.6
#   Parte 9   Gráficos .................................... Gráficos 1 a 4
#   Parte 10  Execução: roda as partes acima e grava tudo em resultados/; ao lado de cada
#             arquivo gravado está a tabela do TCC que sai dele
#   Parte 11  Testes internos (só com --testar)
# ==========================================================================================

# %% PARTE 1 — CONFIGURAÇÃO
# ──────────────────────────────────────────────────────────────────────────────────────────
# Tudo o que define o estudo: período, ações por fator, filtro de pregões, custo de
# negociação e bootstrap. No TCC: seções 4.2 a 4.5.
# ──────────────────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
from matplotlib.dates import MonthLocator, num2date
from matplotlib.ticker import FuncFormatter

# Pastas: os dados ficam em dados/, ao lado deste arquivo; as saídas vão para resultados/.
if "__file__" in globals():
    ARQUIVO_CODIGO = Path(__file__).resolve()
else:  # execução por células, sem __file__: abra esta pasta antes de rodar
    ARQUIVO_CODIGO = Path.cwd() / "carteira_factor_investing.py"
RAIZ = ARQUIVO_CODIGO.parent
ENTRADA = RAIZ / "dados" / "entrada"
CACHE = RAIZ / "dados" / "cache"
FONTES = RAIZ / "dados" / "fontes"
RESULTADOS = RAIZ / "resultados"

ANO_INI, ANO_FIM = 2016, 2025          # período analisado (TCC 4.2)
TOP_N = 10                             # ações por fator (TCC 4.3)
MIN_PREGOES = 150                      # pregões mínimos com preço na janela de formação (4.2)
CUSTO_POR_LADO = 0.002                 # 0,20% = 20 pontos-base por lado (TCC 4.4)
CUSTOS_SENSIBILIDADE = (0.0, 0.001, 0.002, 0.005)   # 0, 10, 20 e 50 pontos-base (TCC 4.6)
N_BOOTSTRAP = 4999                     # réplicas do bootstrap (TCC 4.5)
BLOCOS_BOOTSTRAP = (5, 10, 20)         # blocos de pregões; o de 5 é o das tabelas (4.5 e 4.6)
SEMENTE = 20260909                     # semente fixa: o sorteio do bootstrap é reprodutível

# TOKEN DO LABORATÓRIO DE FINANÇAS: cole o seu token entre as aspas abaixo.
# O estudo roda sem ele, porque as consultas de P/VP e ROIC já estão guardadas em dados/cache.
# O token só é usado para baixar essas consultas de novo da API, com ATUALIZAR_FUNDAMENTOS = True.
# Não publique o código com o token preenchido.
TOKEN_LAB_FINANCAS = ""
ATUALIZAR_FUNDAMENTOS = False          # True: baixa de novo as consultas guardadas em dados/cache

ESTRATEGIAS = ("Momentum", "Baixa_Vol", "Valor", "Qualidade", "Multifator", "Uniao_TCC")
NOMES = {"Momentum": "Momentum", "Baixa_Vol": "Baixa volatilidade", "Valor": "Valor",
         "Qualidade": "Qualidade", "Multifator": "Multifator", "Uniao_TCC": "União"}
PRINCIPAIS = ("Uniao_TCC", "Multifator", "Baixa_Vol")  # carteiras das sensibilidades (4.6)


class ErroAuditoria(ValueError):
    """Inconsistência encontrada numa conferência: a execução para antes de gravar."""


def exigir_colunas(df, colunas, nome):
    faltam = sorted(set(colunas) - set(df.columns))
    if faltam:
        raise ErroAuditoria(f"{nome}: colunas obrigatórias ausentes: {faltam}")


# %% PARTE 2 — DADOS: AS AÇÕES DE CADA ANO, PREÇOS, ÍNDICES, SELIC E FUNDAMENTOS
# ──────────────────────────────────────────────────────────────────────────────────────────
# Universo ISE: em cada ano, a última carteira do ISE B3 anunciada até a data do sinal, já sem
# as exclusões conhecidas até ali (TCC 4.2). A data ao lado de cada ano é quando aquela lista
# passou a ser conhecida; o código recusa usar uma lista posterior ao sinal. Fontes: portal
# histórico do ISE B3 e boletins diários da B3 (dados/fontes; detalhes em
# dados/LISTAS_ISE_E_PONDERACAO.md).
# Universo amplo: as cem ações de maior volume negociado em cada ano, aproximação do IBrX-100,
# em dados/entrada/universo_amplo.csv.
# ──────────────────────────────────────────────────────────────────────────────────────────
LISTAS_ISE = {
    # ano: (lista conhecida desde, ações)
    # 2016 a 2022: 11ª a 17ª carteiras, do portal histórico do ISE B3; as classes das ações
    # ainda não foram conferidas nos boletins (pendência COMPOSICOES_ISE).
    2016: ("2015-11-26", [  # 34 ações
        "BBAS3", "BBDC4", "BRFS3", "BRKM5", "BTOW3", "CCRO3", "CESP6", "CIEL3", "CMIG4", "CPFE3",
        "CPLE6", "DTEX3", "ECOR3", "EGIE3", "ELET3", "ELPL3", "EMBR3", "ENBR3", "EVEN3", "FIBR3",
        "FLRY3", "ITSA4", "ITUB4", "KLBN11", "LAME4", "LIGT3", "LREN3", "NATU3", "SANB11", "SULA11",
        "TIET11", "TIMP3", "VIVT3", "WEGE3",
    ]),
    2017: ("2016-11-24", [  # 34 ações
        "BBAS3", "BBDC4", "BRFS3", "BRKM5", "BTOW3", "CCRO3", "CIEL3", "CLSC4", "CMIG4", "CPFE3",
        "CPLE6", "DTEX3", "ECOR3", "EGIE3", "ELET3", "ELPL3", "EMBR3", "ENBR3", "FIBR3", "FLRY3",
        "ITSA4", "ITUB4", "KLBN11", "LAME4", "LIGT3", "LREN3", "MRVE3", "NATU3", "SANB11", "SULA11",
        "TIET11", "TIMP3", "VIVT3", "WEGE3",
    ]),
    2018: ("2017-11-23", [  # 30 ações
        "BBAS3", "BBDC4", "BRKM5", "BTOW3", "CCRO3", "CIEL3", "CLSC4", "CMIG4", "CPFE3", "CPLE6",
        "DTEX3", "ECOR3", "EGIE3", "ELPL3", "ENBR3", "FIBR3", "FLRY3", "ITSA4", "ITUB4", "KLBN11",
        "LAME4", "LIGT3", "LREN3", "MRVE3", "NATU3", "SANB11", "TIET11", "TIMP3", "VIVT3", "WEGE3",
    ]),
    2019: ("2018-11-29", [  # 28 ações
        "BBAS3", "BBDC4", "BRKM5", "BTOW3", "CCRO3", "CIEL3", "CMIG4", "CPLE6", "DTEX3", "ECOR3",
        "EGIE3", "ELET3", "ELPL3", "ENBR3", "FLRY3", "ITSA4", "ITUB4", "KLBN11", "LAME4", "LIGT3",
        "LREN3", "MRVE3", "NATU3", "SANB11", "TIET11", "TIMP3", "VIVT3", "WEGE3",
    ]),
    2020: ("2019-11-29", [  # 30 ações
        "BBAS3", "BBDC4", "BRDT3", "BRFS3", "BRKM5", "BTOW3", "CCRO3", "CIEL3", "CMIG4", "CPLE6",
        "DTEX3", "ECOR3", "EGIE3", "ELET3", "ENBR3", "FLRY3", "ITSA4", "ITUB4", "KLBN11", "LAME4",
        "LIGT3", "LREN3", "MOVI3", "MRVE3", "NATU3", "SANB11", "TIET11", "TIMP3", "VIVT3", "WEGE3",
    ]),
    2021: ("2020-12-01", [  # 40 ações; ASAI3 fica de fora: só entrou em 01/03/2021
        "AESB3", "BBAS3", "BBDC4", "BEEF3", "BPAC11", "BRDT3", "BRFS3", "BRKM5", "BTOW3", "CCRO3",
        "CIEL3", "CMIG4", "CPFE3", "CPLE6", "CSAN3", "DTEX3", "ECOR3", "EGIE3", "ELET3", "ENBR3",
        "FLRY3", "ITSA4", "ITUB4", "KLBN11", "LAME4", "LIGT3", "LREN3", "MDIA3", "MOVI3", "MRFG3",
        "MRVE3", "NATU3", "NEOE3", "PCAR3", "PETR4", "SANB11", "SUZB3", "TIMP3", "VIVT3", "WEGE3",
    ]),
    2022: ("2021-12-29", [  # 48 ações
        "AESB3", "AMBP3", "AMER3", "ARZZ3", "AZUL4", "BBAS3", "BBDC4", "BEEF3", "BPAC11", "BRFS3",
        "BRKM5", "CCRO3", "CIEL3", "CMIG4", "CPFE3", "CPLE6", "CSAN3", "DXCO3", "ECOR3", "EGIE3",
        "ELET3", "ENBR3", "FLRY3", "ITSA4", "ITUB4", "KLBN11", "LIGT3", "LREN3", "MDIA3", "MGLU3",
        "MOVI3", "MRFG3", "MRVE3", "MYPK3", "NATU3", "NEOE3", "PCAR3", "RADL3", "RAIL3", "SANB11",
        "SIMH3", "SULA11", "SUZB3", "TIMP3", "VBBR3", "VIIA3", "VIVT3", "WEGE3",
    ]),
    # 2023 a 2025: conferidas nos boletins diários da B3 (dados/fontes/bdi_*.pdf).
    2023: ("2022-12-28", [  # 70 ações; 18ª carteira, anunciada antes do sinal
        "ABEV3", "AERI3", "AESB3", "ALSO3", "AMBP3", "AMER3", "ARZZ3", "ASAI3", "AZUL4", "B3SA3",
        "BBAS3", "BBDC4", "BEEF3", "BPAC11", "BPAN4", "BRFS3", "BRKM5", "CBAV3", "CCRO3", "CIEL3",
        "CMIG4", "COGN3", "CPFE3", "CPLE6", "CSAN3", "DASA3", "DXCO3", "ECOR3", "EGIE3", "ELET3",
        "ENBR3", "ENEV3", "FLRY3", "GFSA3", "GRND3", "GUAR3", "HYPE3", "ITSA4", "ITUB4", "KLBN11",
        "LIGT3", "LREN3", "MDIA3", "MGLU3", "MOVI3", "MRFG3", "MRVE3", "MYPK3", "NATU3", "NEOE3",
        "PCAR3", "RADL3", "RAIL3", "RAIZ4", "RANI3", "RDOR3", "SANB11", "SAPR11", "SIMH3", "SLCE3",
        "STBP3", "SUZB3", "TIMS3", "TRPL4", "USIM5", "VAMO3", "VBBR3", "VIIA3", "VIVT3", "WEGE3",
    ]),
    2024: ("2023-12-08", [  # 66 ações; 18ª carteira sem AMER3, LIGT3, ENBR3 e BRKM5
        "ABEV3", "AERI3", "AESB3", "ALSO3", "AMBP3", "ARZZ3", "ASAI3", "AZUL4", "B3SA3", "BBAS3",
        "BBDC4", "BEEF3", "BPAC11", "BPAN4", "BRFS3", "CBAV3", "CCRO3", "CIEL3", "CMIG4", "COGN3",
        "CPFE3", "CPLE6", "CSAN3", "DASA3", "DXCO3", "ECOR3", "EGIE3", "ELET3", "ENEV3", "FLRY3",
        "GFSA3", "GRND3", "GUAR3", "HYPE3", "ITSA4", "ITUB4", "KLBN11", "LREN3", "MDIA3", "MGLU3",
        "MOVI3", "MRFG3", "MRVE3", "MYPK3", "NATU3", "NEOE3", "PCAR3", "RADL3", "RAIL3", "RAIZ4",
        "RANI3", "RDOR3", "SANB11", "SAPR11", "SIMH3", "SLCE3", "STBP3", "SUZB3", "TIMS3", "TRPL4",
        "USIM5", "VAMO3", "VBBR3", "VIIA3", "VIVT3", "WEGE3",
    ]),
    2025: ("2024-10-31", [  # 76 ações; 19ª carteira atualizada, com CYRE3 e sem AESB3
        "ABEV3", "AERI3", "ALSO3", "AMBP3", "ASAI3", "AURE3", "AZUL4", "AZZA3", "B3SA3", "BBAS3",
        "BBDC4", "BEEF3", "BHIA3", "BPAC11", "BPAN4", "BRFS3", "CAML3", "CBAV3", "CCRO3", "CEAB3",
        "CMIG4", "COGN3", "CPFE3", "CPLE6", "CRFB3", "CSAN3", "CSMG3", "CYRE3", "DASA3", "DXCO3",
        "ECOR3", "EGIE3", "ELET3", "ENEV3", "FLRY3", "GFSA3", "GRND3", "GUAR3", "HYPE3", "IGTI11",
        "ISAE4", "ITSA4", "ITUB4", "JSLG3", "KLBN11", "LREN3", "MDIA3", "MGLU3", "MOVI3", "MRVE3",
        "MTRE3", "MYPK3", "NATU3", "NEOE3", "PCAR3", "PSSA3", "RADL3", "RAIL3", "RAIZ4", "RANI3",
        "RDOR3", "SANB11", "SAPR11", "SIMH3", "SLCE3", "SRNA3", "STBP3", "SUZB3", "TIMS3", "UGPA3",
        "USIM5", "VAMO3", "VBBR3", "VIVT3", "WEGE3", "YDUQ3",
    ]),
}

# Códigos que mudaram: o histórico de preços da empresa fica guardado sob o código atual.
# Incorporações (SulAmérica, Fibria, AES Brasil, BRF, Copel) não entram aqui: são eventos
# societários, tratados na simulação (Parte 4) com os documentos de dados/entrada/eventos.json.
RENOMEADOS = {                          # código da época → código atual
    "ELET3": "AXIA3",    # Eletrobras        → Axia              (2025)
    "TIET11": "AESB3",   # AES Tietê (units) → AES Brasil        (2020)
    "BTOW3": "AMER3",    # B2W               → Americanas        (2021)
    "VIIA3": "BHIA3",    # Via               → Grupo Casas Bahia (2023)
    "ALSO3": "ALOS3",    # Aliansce Sonae    → Allos             (2023)
    "ARZZ3": "AZZA3",    # Arezzo            → Azzas 2154        (2024)
    "CCRO3": "MOTV3",    # CCR               → Motiva            (2025)
    "EMBR3": "EMBJ3",    # Embraer           → novo código       (2025)
    "TIMP3": "TIMS3",    # TIM Participações → TIM S.A.          (2020)
    "BRDT3": "VBBR3",    # BR Distribuidora  → Vibra Energia     (2021)
    "DTEX3": "DXCO3",    # Duratex           → Dexco             (2021)
    "TRPL4": "ISAE4",    # ISA CTEEP         → ISA Energia       (2024)
    "NTCO3": "NATU3",    # Natura &Co        → Natura            (2025)
    "GUAR3": "RIAA3",    # Guararapes        → Riachuelo         (2025)
    "AZUL4": "AZUL3",    # Azul PN           → Azul ON           (2025)
    "MRFG3": "MBRF3",    # Marfrig           → MBRF (com a BRF)  (2025)
}


def ler_universos(caminho):
    """Lê uma lista de universos em CSV (ações de cada universo e ano, com a data de anúncio)."""
    universos = pd.read_csv(caminho, parse_dates=["Disponivel_em"])
    exigir_colunas(universos, ["Universo", "Ano", "Ticker", "Disponivel_em"], "universos")
    return universos


def montar_universos():
    """Junta o universo amplo (CSV) e as listas do ISE (acima) num único quadro."""
    ise = pd.DataFrame([{"Universo": "ISE", "Ano": ano, "Ticker": ticker,
                         "Disponivel_em": pd.Timestamp(data)}
                        for ano, (data, tickers) in LISTAS_ISE.items() for ticker in tickers])
    return pd.concat([ler_universos(ENTRADA / "universo_amplo.csv"), ise], ignore_index=True)


def carregar_mercado():
    """Níveis do ISE B3 e do IBrX-100, Selic anual e preços ajustados de fechamento."""
    bench = (pd.read_csv(ENTRADA / "base_ise_ibrx_selic.csv", parse_dates=["data"])
             .set_index("data").sort_index())
    exigir_colunas(bench, ["ise_b3", "ibrx100", "selic_aa"], "benchmarks")
    if bench.index.has_duplicates or bench.isna().any().any():
        raise ErroAuditoria("Benchmarks com datas repetidas ou dados ausentes.")
    px = pd.read_csv(ENTRADA / "precos.csv", index_col=0, parse_dates=True).sort_index()
    if px.index.has_duplicates or px.columns.has_duplicates:
        raise ErroAuditoria("Preços duplicados.")
    px = px.reindex(bench.index)
    if (px <= 0).any().any() or np.isinf(px.to_numpy()).any():
        raise ErroAuditoria("Preços não positivos ou infinitos.")
    return px, bench


def carregar_token():
    """Token do Laboratório de Finanças; nunca é impresso.

    Procura, nesta ordem: TOKEN_LAB_FINANCAS (Parte 1), a variável de ambiente
    LAB_FINANCAS_TOKEN e um arquivo .env nesta pasta com a linha LAB_FINANCAS_TOKEN=...
    """
    token = TOKEN_LAB_FINANCAS.strip() or os.environ.get("LAB_FINANCAS_TOKEN", "").strip()
    arquivo = RAIZ / ".env"
    if not token and arquivo.exists():
        for linha in arquivo.read_text(encoding="utf-8-sig").splitlines():
            if linha.strip().startswith("LAB_FINANCAS_TOKEN="):
                token = linha.split("=", 1)[1].strip().strip("\"'")
    if not token:
        raise ValueError("Cole o token do Laboratório de Finanças em TOKEN_LAB_FINANCAS, "
                         "na Parte 1 do código.")
    return token


def obter_fundamentos(bench, atualizar=False):
    """Garante uma consulta do Planilhão (P/VP, ROIC, setor) para cada data de sinal.

    As consultas ficam em dados/cache, cada uma com endereço, data e SHA-256. A execução normal
    só lê o que está guardado; baixar de novo exige o token e ATUALIZAR_FUNDAMENTOS = True.
    """
    for ano in range(ANO_INI, ANO_FIM + 1):
        sinal = f"{bench.index[bench.index.year == ano - 1].max():%Y-%m-%d}"
        caminho = CACHE / f"planilhao_{sinal}.json"
        if caminho.exists() and not atualizar:
            continue
        url = ("https://laboratoriodefinancas.com/api/v2/bolsa/planilhao?"
               + urllib.parse.urlencode({"data_base": sinal}))
        pedido = urllib.request.Request(url, headers={
            "Authorization": "Bearer " + carregar_token(), "User-Agent": "TCC-revisao/1.0"})
        with urllib.request.urlopen(pedido, timeout=60) as resposta:
            bruto = resposta.read()
        obj = json.loads(bruto)
        linhas = obj.get("results", obj.get("data", [])) if isinstance(obj, dict) else obj
        if not linhas:
            raise ValueError(f"Fundamentos vazios em {sinal}; nenhum ano é omitido em silêncio.")
        caminho.write_bytes(bruto)
        caminho.with_suffix(".meta.json").write_text(json.dumps({
            "url": url, "data_base": sinal, "obtido_em": datetime.now(timezone.utc).isoformat(),
            "sha256": hashlib.sha256(bruto).hexdigest(), "linhas": len(linhas),
            "publicacao_original_verificada": False}, indent=2), encoding="utf-8")
        print(f"Fundamentos de {sinal}: {len(linhas)} registros salvos.", flush=True)


def fundamentos(sinal):
    """P/VP, ROIC e setor da consulta de uma data de sinal.

    Confere o SHA-256 do arquivo e recusa qualquer indicador com data-base posterior ao sinal.
    """
    caminho = CACHE / f"planilhao_{sinal:%Y-%m-%d}.json"
    if not caminho.exists():
        raise ErroAuditoria(f"Falta a consulta {caminho.name}; use ATUALIZAR_FUNDAMENTOS = True.")
    metadados = caminho.with_suffix(".meta.json")
    if not metadados.exists():
        raise ErroAuditoria(f"Consulta sem origem e hash: {caminho.name}.")
    meta = json.loads(metadados.read_text(encoding="utf-8"))
    if hashlib.sha256(caminho.read_bytes()).hexdigest() != meta.get("sha256"):
        raise ErroAuditoria(f"Consulta modificada desde sua obtenção: {caminho.name}.")
    obj = json.loads(caminho.read_bytes())
    linhas = obj.get("results", obj.get("data", [])) if isinstance(obj, dict) else obj
    df = pd.DataFrame(linhas).rename(columns={"ticker": "Ticker", "setor": "Setor"})
    exigir_colunas(df, ["Ticker", "Setor", "p_vp", "roic", "data_base"], "fundamentos")
    if df.Ticker.duplicated().any():
        raise ErroAuditoria("Fundamentos com tickers duplicados.")
    if (pd.to_datetime(df.data_base) > sinal).any():
        raise ErroAuditoria("Fundamento posterior ao sinal.")
    for campo in ("p_vp", "roic"):
        df[campo] = pd.to_numeric(df[campo], errors="coerce")
    return df.set_index("Ticker")


# %% PARTE 3 — FORMAÇÃO DAS CARTEIRAS, ANO A ANO
# ──────────────────────────────────────────────────────────────────────────────────────────
# Para cada universo e ano: filtros de elegibilidade, os quatro fatores medidos na data do
# sinal e a escolha das ações de cada estratégia. No TCC: seção 4.3, Equações 1 a 4.
# ──────────────────────────────────────────────────────────────────────────────────────────
def calendario(indice, ano):
    """Datas-chave de um ano (TCC 4.4).

    sinal: último pregão de N-1, quando os fatores são medidos; execucao: primeiro pregão de
    N, quando a carteira é comprada; inicio_observacao a sinal é a janela de formação.
    """
    anterior = indice[indice.year == ano - 1]
    atual = indice[indice.year == ano]
    if len(anterior) < MIN_PREGOES or len(atual) < 2:
        raise ErroAuditoria(f"Calendário incompleto para {ano}.")
    return {"sinal": anterior[-1], "execucao": atual[0],
            "inicio_observacao": anterior[0], "fim": atual[-1]}


def rankings(fatores):
    """Ações escolhidas por estratégia; empates são desfeitos pela ordem do ticker (TCC 4.3)."""
    f = fatores.sort_values("Ticker").set_index("Ticker")

    def escolher(s, menor):
        return s.dropna().sort_values(ascending=menor, kind="stable").head(TOP_N).index.tolist()

    # Equação 4 do TCC: percentil de cada fator, orientado para que maior seja melhor.
    r = pd.DataFrame({
        "Momentum": f.momentum.rank(pct=True),
        "Baixa_Vol": f.baixa_vol.rank(pct=True, ascending=False),
        "Valor": f.p_vp.where(f.p_vp > 0).rank(pct=True, ascending=False),
        "Qualidade": f.roic.rank(pct=True),
    })
    tops = {
        "Momentum": escolher(f.momentum, False),
        "Baixa_Vol": escolher(f.baixa_vol, True),
        "Valor": escolher(f.p_vp.where(f.p_vp > 0), True),
        "Qualidade": escolher(f.roic, False),
        # Multifator: média dos quatro percentis; só entram ações com os quatro fatores.
        "Multifator": escolher(r.mean(axis=1, skipna=False), False),
    }
    tops["Uniao_TCC"] = sorted(
        set().union(*(tops[n] for n in ("Momentum", "Baixa_Vol", "Valor", "Qualidade"))))
    tops["Universo_EW"] = f.index.tolist()
    return tops


def formar_carteiras(px, bench, universos, renomeados, exigir_lista_anunciada=True):
    """Forma as carteiras de todos os anos, nos universos presentes em `universos`.

    Para cada universo e ano: aplica os filtros de elegibilidade, registrando o motivo de cada
    exclusão; calcula os fatores na data do sinal; escolhe as ações e marca a compra, com pesos
    iguais, para a data de execução. exigir_lista_anunciada=False só é usado na sensibilidade
    às listas da versão anterior do estudo (Parte 8).
    """
    agendas, composicoes, fatores_salvos, exclusoes = {}, [], [], []
    for universo in sorted(universos.Universo.unique()):
        for ano in range(ANO_INI, ANO_FIM + 1):
            cal = calendario(bench.index, ano)
            uni = universos[(universos.Universo == universo) & (universos.Ano == ano)]
            if uni.empty:
                raise ErroAuditoria(f"Universo ausente: {universo} {ano}.")
            # A lista usada precisa ter sido anunciada até a data do sinal (TCC 4.2).
            if exigir_lista_anunciada and (uni.Disponivel_em.isna().any()
                                           or (uni.Disponivel_em > cal["sinal"]).any()):
                raise ErroAuditoria(f"{universo} {ano}: composição não disponível no sinal.")
            fund = fundamentos(cal["sinal"])
            vistos, linhas = set(), []
            for t in uni.Ticker:
                serie = renomeados.get(t, t)  # código sob o qual o histórico de preços está
                # Fundamento da própria classe quando existe: nunca trocar CPLE6 por CPLE3.
                chave = t if t in fund.index else serie
                razao = None
                if serie in vistos:
                    razao = "alias duplicado"
                elif serie not in px:
                    razao = "sem série de preços"
                elif chave not in fund.index:
                    razao = "sem fundamento da identidade solicitada"
                else:
                    vistos.add(serie)
                    p = px.loc[cal["inicio_observacao"]:cal["sinal"], serie]
                    validos = p.dropna()
                    if len(validos) < MIN_PREGOES:
                        razao = f"menos de {MIN_PREGOES} preços no período de observação"
                    elif pd.isna(p.iloc[-1]):  # não medir o sinal com cotação desatualizada
                        razao = "sem preço na data do sinal"
                if razao:
                    exclusoes.append({"Universo": universo, "Ano": ano, "Ticker": t,
                                      "Motivo": razao})
                    continue
                dados = fund.loc[chave]
                linhas.append({
                    "Ticker": serie, "Ticker_original": t, "Ticker_fundamento": chave,
                    "Setor": dados.Setor,
                    # Equação 2 do TCC: momentum = retorno acumulado na janela de formação.
                    "momentum": validos.iloc[-1] / validos.iloc[0] - 1,
                    # Equações 1 e 3: desvio-padrão dos retornos diários vezes raiz de 252.
                    "baixa_vol": p.pct_change(fill_method=None).std() * np.sqrt(252),
                    "p_vp": dados.p_vp, "roic": dados.roic, "Observacoes": len(validos),
                    "Data_sinal": cal["sinal"], "Data_execucao": cal["execucao"],
                })
            if not linhas:
                raise ErroAuditoria(f"Nenhum ativo elegível: {universo} {ano}.")
            fatores = pd.DataFrame(linhas)
            setores = fatores.set_index("Ticker").Setor
            for estrategia, tickers in rankings(fatores).items():
                if not tickers:
                    raise ErroAuditoria(f"Carteira vazia: {universo} {ano} {estrategia}.")
                # Pesos iguais, marcados para a data de execução, e não para a do sinal.
                agendas.setdefault((universo, estrategia), {})[cal["execucao"]] = {
                    t: 1 / len(tickers) for t in tickers}
                for ticker in tickers:
                    composicoes.append({
                        "Universo": universo, "Estrategia": estrategia, "Ano": ano,
                        "Ticker": ticker,
                        "Setor": setores[ticker] if pd.notna(setores[ticker]) else "Não informado",
                        "Peso": 1 / len(tickers),
                        "Data_sinal": cal["sinal"], "Data_execucao": cal["execucao"],
                    })
            fatores_salvos.append(fatores.assign(Universo=universo, Ano=ano))
    return (agendas, pd.DataFrame(composicoes), pd.concat(fatores_salvos, ignore_index=True),
            pd.DataFrame(exclusoes))


def mostrar_carteiras(composicoes, fatores):
    """Mostra no terminal, ano a ano, as ações escolhidas no universo do ISE (Quadros 4 a 6).

    As ações aparecem com o código da época (por exemplo, ELET3, e não AXIA3).
    """
    ise = fatores[fatores.Universo == "ISE"]
    codigo_da_epoca = ise.set_index(["Ano", "Ticker"]).Ticker_original
    for ano, grupo in composicoes[composicoes.Universo == "ISE"].groupby("Ano"):
        linha = grupo.iloc[0]
        print(f"\n  {ano} | sinal em {linha.Data_sinal:%d/%m/%Y}, compra em "
              f"{linha.Data_execucao:%d/%m/%Y} | lista do ISE: {len(LISTAS_ISE[ano][1])} ações, "
              f"{(ise.Ano == ano).sum()} elegíveis")
        for estrategia in ESTRATEGIAS:
            acoes = [codigo_da_epoca[ano, t] for t in grupo[grupo.Estrategia == estrategia].Ticker]
            texto = (", ".join(acoes) if estrategia != "Uniao_TCC"
                     else f"{len(acoes)} ações (reunião das quatro listas)")
            print(f"    {NOMES[estrategia]:<20}{texto}")
    print()


# %% PARTE 4 — SIMULAÇÃO: COMPRA, CAIXA, EVENTOS E CUSTOS
# ──────────────────────────────────────────────────────────────────────────────────────────
# Compra no pregão seguinte ao sinal, posição mantida até dezembro sem reequilíbrio, custo
# pago pela própria carteira, caixa remunerado pela Selic e eventos societários documentados
# (dados/entrada/eventos.json). No TCC: seção 4.4, Equações 5 a 7.
# ──────────────────────────────────────────────────────────────────────────────────────────
def periodo_simulacao(bench):
    """Pregões do estudo e Selic diária (TCC 4.4, Equação 7)."""
    datas = bench.index[(bench.index.year >= ANO_INI) & (bench.index.year <= ANO_FIM)]
    # Equação 7 do TCC: Selic anual convertida em taxa diária equivalente.
    selic = (1 + bench.loc[datas, "selic_aa"] / 100) ** (1 / 252) - 1
    selic.iloc[0] = 0  # o caixa só começa a render depois da montagem
    return datas, selic


def retornos_benchmarks(bench, datas):
    """Retornos diários do ISE B3 e do IBrX-100 (Equação 1); zero no dia da montagem."""
    retornos = bench.loc[datas, ["ise_b3", "ibrx100"]].pct_change(fill_method=None)
    retornos.iloc[0] = 0
    return retornos.rename(columns={"ise_b3": "ret_ise", "ibrx100": "ret_ibrx"})


@dataclass
class ResultadoSimulacao:
    retornos: pd.Series
    patrimonio: pd.Series
    posicoes: pd.DataFrame
    operacoes: pd.DataFrame
    rebalanceamentos: pd.DataFrame
    ocorrencias: pd.DataFrame


def executar_rebalanceamento(valores, caixa, pesos_alvo, custo_por_lado):
    """Refaz a carteira pagando o custo com o próprio patrimônio (TCC 4.4, Equação 5).

    Resolve V_final + c * soma(|peso_alvo * V_final - valor_antes|) = V_antes. Caixa não paga
    corretagem; se os pesos-alvo somam menos de 1, a diferença fica em caixa.
    """
    if not 0 <= custo_por_lado < 1:
        raise ValueError("Custo por lado inválido.")
    if caixa < -1e-10 or any(v < 0 for v in valores.values()):
        raise ValueError("Esta implementação exige posições compradas, sem alavancagem.")
    if any(w < 0 for w in pesos_alvo.values()) or sum(pesos_alvo.values()) > 1 + 1e-12:
        raise ValueError("Pesos-alvo inválidos.")
    tickers = sorted(set(valores) | set(pesos_alvo))
    antigo = np.array([valores.get(t, 0.0) for t in tickers])
    alvo = np.array([pesos_alvo.get(t, 0.0) for t in tickers])
    inicial = float(antigo.sum() + caixa)
    if inicial <= 0:
        raise ValueError("Patrimônio não positivo.")
    # Equação 5 do TCC, resolvida por bisseção.
    inferior, superior = 0.0, inicial
    for _ in range(70):
        meio = (inferior + superior) / 2
        residuo = meio + custo_por_lado * np.abs(alvo * meio - antigo).sum() - inicial
        if residuo > 0:
            superior = meio
        else:
            inferior = meio
    final = (inferior + superior) / 2
    novos = alvo * final
    ordens = novos - antigo
    custos = float(custo_por_lado * np.abs(ordens).sum())
    caixa_final = final - float(novos.sum())
    return dict(zip(tickers, novos)), caixa_final, dict(zip(tickers, ordens)), custos


def simular(precos, selic, agenda, *, custo_por_lado=CUSTO_POR_LADO, eventos=None):
    """Simula uma carteira dia a dia, do primeiro ao último pregão (TCC 4.4).

    agenda = {data_de_execução: {ticker: peso}}. Em cada pregão: o caixa rende a Selic,
    créditos a receber são pagos, eventos societários documentados são aplicados, as posições
    são valoradas e, nas datas da agenda, a carteira é refeita com custo. Uma ação que passa
    três pregões sem preço depois do último negócio, sem evento documentado, vira caixa ao
    último preço (regra aproximada, registrada nas ocorrências).

    Os eventos precisam estar na mesma base de preços da simulação (fator_cotas e
    caixa_por_cota ajustados), com data e fonte.
    """
    if not precos.index.equals(selic.index) or precos.index.has_duplicates:
        raise ValueError("Calendários de preços e Selic incompatíveis.")
    if not precos.index.is_monotonic_increasing or selic.isna().any():
        raise ValueError("Calendário desordenado ou Selic ausente.")
    if not agenda or min(agenda) != precos.index[0] or not set(agenda).issubset(precos.index):
        raise ValueError("A agenda deve começar na primeira data da simulação.")
    por_data = {}
    for evento in eventos or []:
        if (not evento.get("validado") or not evento.get("fonte")
                or evento.get("base") != "mesma_dos_precos"):
            raise ValueError("Evento sem validação financeira e base de cotação explícita.")
        data_evento = pd.Timestamp(evento["data"])
        fatores_evento = [float(evento.get("fator_cotas", 0)),
                          float(evento.get("caixa_por_cota", 0))]
        if (pd.isna(data_evento) or not np.isfinite(fatores_evento).all()
                or min(fatores_evento) < 0):
            raise ValueError("Data ou contrapartida financeira inválida no evento.")
        if precos.index[0] <= data_evento <= precos.index[-1] and data_evento not in precos.index:
            raise ValueError("Evento dentro da janela, mas fora do calendário de negociação.")
        if any(e["ticker"] == evento["ticker"] for e in por_data.get(data_evento, [])):
            raise ValueError("Dois eventos para o mesmo ativo no mesmo dia; consolide-os.")
        por_data.setdefault(data_evento, []).append(evento)

    ultimos = {t: precos[t].last_valid_index() for t in precos}
    cotas, ultimos_precos = {}, {}
    recebiveis = {}  # dinheiro de eventos: entra no patrimônio, mas só rende após o pagamento
    caixa = anterior = 1.0
    diarios, posicoes, operacoes, rebals, ocorrencias = [], [], [], [], []
    for i, (data, linha) in enumerate(precos.iterrows()):
        if i:
            caixa *= 1 + float(selic.loc[data])  # Equação 7: o caixa rende a Selic diária
        for chave, (pagamento, valor) in list(recebiveis.items()):
            if data >= pagamento:
                caixa += valor
                del recebiveis[chave]

        # Eventos societários documentados: a posição é convertida, sem venda fictícia.
        for ev in por_data.get(data, []):
            ticker = ev["ticker"]
            quantidade = cotas.pop(ticker, 0.0)
            if quantidade == 0:
                continue
            destino = ev.get("destino")
            valor_anterior = quantidade * ultimos_precos[ticker]
            dinheiro = quantidade * float(ev.get("caixa_por_cota", 0))
            pagamento = pd.Timestamp(ev.get("data_pagamento", ev["data"]))
            if pagamento < data:
                raise ValueError("Pagamento anterior ao reconhecimento do evento.")
            if dinheiro and pagamento > data:
                recebiveis[f"RECEBER_{ticker}_{data:%Y%m%d}"] = (pagamento, dinheiro)
            else:
                caixa += dinheiro
            if destino:
                cotas[destino] = cotas.get(destino, 0.0) + quantidade * float(ev["fator_cotas"])
                if pd.isna(linha.get(destino, np.nan)):
                    raise ValueError(f"{data.date()}: falta preço do ativo recebido {destino}.")
            ocorrencias.append({
                "Data": data, "Ticker": ticker, "Tipo": "evento_validado", "Detalhe": ev["fonte"],
                "Valor_antes": valor_anterior, "Peso_fechamento_anterior": valor_anterior / anterior,
                "Data_pagamento": pagamento})

        # Valoração. Sem preço, vale o último; no terceiro pregão sem negócio, vira caixa.
        for t in list(cotas):
            valor = linha.get(t, np.nan)
            if pd.notna(valor) and float(valor) > 0:
                ultimos_precos[t] = float(valor)
                continue
            if t not in ultimos_precos:
                raise ValueError(f"Não há preço para valorar {t} em {data.date()}.")
            ocorrencias.append({"Data": data, "Ticker": t, "Tipo": "preco_ausente",
                                "Detalhe": "Posição valorada pelo último preço."})
            ultimo = ultimos.get(t)
            if ultimo is not None and data > ultimo:
                atraso = int(((precos.index > ultimo) & (precos.index <= data)).sum())
                if atraso >= 3:
                    valor_liquidado = cotas.pop(t) * ultimos_precos[t]
                    caixa += valor_liquidado
                    ocorrencias.append({
                        "Data": data, "Ticker": t, "Tipo": "liquidacao_aproximada",
                        "Detalhe": "Caixa ao último preço no terceiro pregão sem cotação.",
                        "Valor_antes": valor_liquidado,
                        "Peso_fechamento_anterior": valor_liquidado / anterior})

        valores = {t: q * ultimos_precos[t] for t, q in cotas.items()}
        direitos = {t: v for t, (_, v) in recebiveis.items()}
        antes = sum(valores.values()) + caixa + sum(direitos.values())

        # Rebalanceamento anual, nas datas da agenda.
        if data in agenda:
            if direitos:
                raise ValueError("Há recebíveis pendentes; não usar dinheiro ainda indisponível.")
            alvos = dict(agenda[data])
            cancelados = []
            # Compra sem preço é cancelada e o orçamento fica em caixa; não se escolhe outra
            # ação olhando dados da execução.
            for t in list(alvos):
                if pd.isna(linha.get(t, np.nan)) or float(linha[t]) <= 0:
                    if t in cotas:
                        raise ValueError(f"{data.date()}: rebalanceamento de {t} sem preço.")
                    cancelados.append(t)
                    alvos.pop(t)
                    ocorrencias.append({"Data": data, "Ticker": t, "Tipo": "compra_cancelada",
                                        "Detalhe": "Sem preço na execução; orçamento em caixa."})
            for t in cotas:
                if pd.isna(linha.get(t, np.nan)):
                    raise ValueError(f"{data.date()}: venda de {t} sem preço executável.")
            novos, caixa, ordens, custo = executar_rebalanceamento(
                valores, caixa, alvos, custo_por_lado)
            cotas = {t: v / float(linha[t]) for t, v in novos.items() if v > 1e-14}
            for t in cotas:
                ultimos_precos[t] = float(linha[t])
            compras = sum(max(v, 0) for v in ordens.values())
            vendas = sum(max(-v, 0) for v in ordens.values())
            rebals.append({
                "Data": data, "Ano": data.year, "Patrimonio_antes": antes,
                "Compras": compras, "Vendas": vendas,
                "Volume_negociado": (compras + vendas) / antes,
                # Equação 6 do TCC: giro = metade de compras mais vendas, sobre o patrimônio.
                "Turnover": 0.5 * (compras + vendas) / antes,
                "Custo": custo, "Custo_bps": custo / antes * 10000, "Caixa_depois": caixa,
                "Compras_canceladas": ",".join(cancelados)})
            for t, v in ordens.items():
                if abs(v) > 1e-14:
                    operacoes.append({"Data": data, "Ticker": t, "Valor": v,
                                      "Custo": abs(v) * custo_por_lado})
            valores = {t: q * ultimos_precos[t] for t, q in cotas.items()}

        total = sum(valores.values()) + caixa + sum(direitos.values())
        if not np.isfinite(total) or total <= 0:
            raise ValueError("Patrimônio inválido.")
        # Retorno do dia = variação do patrimônio total: ações, caixa e valores a receber.
        diarios.append({"Data": data, "Patrimonio": total, "Retorno": total / anterior - 1})
        for t, v in {**valores, **direitos, "CAIXA": caixa}.items():
            posicoes.append({"Data": data, "Ticker": t, "Valor": v, "Peso": v / total})
        anterior = total

    diario = pd.DataFrame(diarios).set_index("Data")
    colunas = ["Data", "Ticker", "Tipo", "Detalhe", "Valor_antes", "Peso_fechamento_anterior",
               "Data_pagamento"]
    return ResultadoSimulacao(diario.Retorno, diario.Patrimonio, pd.DataFrame(posicoes),
                              pd.DataFrame(operacoes), pd.DataFrame(rebals),
                              pd.DataFrame(ocorrencias, columns=colunas))


def simular_todas(precos, selic, agendas, eventos):
    """Simula as 14 carteiras (7 estratégias x 2 universos) e junta os registros."""
    series = {}
    registros = {nome: [] for nome in ("posicoes", "operacoes", "rebalanceamentos", "ocorrencias")}
    for (universo, estrategia), agenda in agendas.items():
        print(f"  {universo} / {estrategia}", flush=True)
        resultado = simular(precos, selic, agenda, eventos=eventos)
        series[f"{universo}_{estrategia}"] = resultado.retornos
        for campo, destino in registros.items():
            destino.append(getattr(resultado, campo).assign(Universo=universo,
                                                            Estrategia=estrategia))
    return (pd.DataFrame(series, index=precos.index),
            {nome: pd.concat(partes, ignore_index=True) for nome, partes in registros.items()})


# %% PARTE 5 — DESEMPENHO
# ──────────────────────────────────────────────────────────────────────────────────────────
# Retorno, volatilidade, Sharpe e drawdown (Tabela 3), retornos anuais (Tabela 4), setores
# (Tabela 5), episódios de estresse (Tabela 9), captura de alta e de baixa (Gráfico 3) e a
# parte da diferença entre os índices que vem da ponderação (Tabela 10).
# No TCC: seções 4.5 e 5.1 a 5.4, Equações 8 a 12.
# ──────────────────────────────────────────────────────────────────────────────────────────
def validar_retornos(retornos):
    """Recusa séries vazias, fora de ordem, com valores não finitos ou perdas de 100%."""
    if retornos.empty or not isinstance(retornos.index, pd.DatetimeIndex):
        raise ValueError("Série vazia ou índice sem datas.")
    if retornos.index.has_duplicates or not retornos.index.is_monotonic_increasing:
        raise ValueError("Datas duplicadas ou fora de ordem.")
    valores = retornos.to_numpy(dtype=float)
    if not np.isfinite(valores).all() or (valores <= -1).any():
        raise ValueError("Retornos ausentes, não finitos ou menores/iguais a -100%.")


def patrimonio(retornos):
    """Patrimônio acumulado a partir de capital inicial igual a 1."""
    validar_retornos(retornos)
    return (1 + retornos).cumprod()


def drawdown(retornos):
    """Queda do patrimônio em relação ao maior valor anterior (TCC Equação 12)."""
    valores = patrimonio(retornos)
    # O capital antes da primeira compra é 1, inclusive quando há custo inicial.
    return valores / valores.cummax().clip(lower=1) - 1


def retorno_anualizado(retornos):
    """Retorno anual composto pelo tempo de calendário: dias corridos / 365,25 (Equação 9)."""
    anos = (retornos.index[-1] - retornos.index[0]).days / 365.25
    if anos <= 0:
        raise ValueError("Anualização exige um intervalo de datas positivo.")
    return np.expm1(np.log1p(retornos).sum() / anos)


def metricas(retornos, livre_risco):
    """As cinco medidas da Tabela 3 (TCC 4.5, Equações 8 a 12)."""
    validar_retornos(retornos)
    if not retornos.index.equals(livre_risco.index):
        raise ValueError("Retornos e taxa livre de risco precisam ter as mesmas datas.")
    validar_retornos(livre_risco)
    excesso = retornos - livre_risco
    desvio = excesso.std(ddof=1)
    return {
        "Retorno Total (%)": float(np.expm1(np.log1p(retornos).sum()) * 100),       # Eq. 8
        "Retorno Anual (%)": float(retorno_anualizado(retornos) * 100),             # Eq. 9
        "Volatilidade (%)": float(retornos.std(ddof=1) * np.sqrt(252) * 100),       # Eq. 10
        # Equação 11: excesso de retorno sobre a Selic diária.
        "Sharpe": float(excesso.mean() / desvio * np.sqrt(252)) if desvio > 0 else np.nan,
        "Max Drawdown (%)": float(drawdown(retornos).min() * 100),                  # Eq. 12
    }


def retornos_anuais(retornos):
    """Retorno de cada ano civil, em % (Tabela 4)."""
    validar_retornos(retornos)
    anual = ((1 + retornos).groupby(retornos.index.year).prod() - 1) * 100
    anual.index.name = "Ano"
    return anual


def distribuicao_setorial(composicao):
    """Peso médio de cada setor por carteira; setor ausente num ano conta como zero (Tabela 5)."""
    chaves = ["Universo", "Estrategia", "Ano", "Setor"]
    if not set(chaves + ["Peso"]).issubset(composicao):
        raise ValueError("Composição sem colunas de universo, estratégia, ano, setor e peso.")
    setores = sorted(composicao.Setor.unique())
    grupos = composicao[["Universo", "Estrategia", "Ano"]].drop_duplicates()
    grade = grupos.merge(pd.DataFrame({"Setor": setores}), how="cross")
    pesos = composicao.groupby(chaves, dropna=False).Peso.sum().reset_index()
    completa = grade.merge(pesos, on=chaves, how="left").fillna({"Peso": 0})
    return completa.groupby(["Universo", "Estrategia", "Setor"]).Peso.mean().reset_index()


def retorno_entre_fechamentos(retornos, inicio, fim):
    """Retorno acumulado do fechamento de `inicio` ao de `fim` (exclui o dia inicial)."""
    if inicio not in retornos.index or fim not in retornos.index or inicio >= fim:
        raise ValueError("Fronteiras inválidas para a janela de estresse.")
    janela = retornos.loc[(retornos.index > inicio) & (retornos.index <= fim)]
    validar_retornos(janela)
    return (1 + janela).prod() - 1


def episodios_estresse(diario):
    """Quedas de 15% ou mais do IBrX-100 e o retorno de cada série na queda e na recuperação
    (Tabela 9)."""
    p = patrimonio(diario.ret_ibrx)
    pico, data_pico = p.iloc[0], p.index[0]
    fundo, data_fundo = pico, data_pico
    episodios = []
    for data, valor in p.iloc[1:].items():
        if valor >= pico:
            if fundo / pico - 1 <= -0.15:
                episodios.append((data_pico, data_fundo, data, True))
            pico, data_pico, fundo, data_fundo = valor, data, valor, data
        elif valor < fundo:
            fundo, data_fundo = valor, data
    if fundo / pico - 1 <= -0.15:
        episodios.append((data_pico, data_fundo, p.index[-1], False))
    linhas = []
    for inicio, fundo, fim, recuperado in episodios:
        for fase, a, b in [("queda", inicio, fundo),
                           ("recuperacao" if recuperado else "apos_fundo_sem_recuperacao",
                            fundo, fim)]:
            if a >= b:
                continue
            retorno = retorno_entre_fechamentos(diario.drop(columns="selic_dia"), a, b) * 100
            for serie, valor in retorno.items():
                linhas.append({
                    "Pico": inicio, "Fundo": fundo, "Fim": fim, "Recuperado": recuperado,
                    "Fase": fase, "Inicio_janela": a, "Fim_janela": b,
                    "Pregoes": int(((diario.index > a) & (diario.index <= b)).sum()),
                    "Serie": serie, "Retorno_pct": valor})
    return pd.DataFrame(linhas)


def calcular_capturas(diario):
    """Retorno médio de cada série nos dias de alta e de baixa do IBrX-100 (Gráfico 3)."""
    linhas = []
    for serie in [c for c in diario if c not in ("selic_dia", "ret_ibrx")]:
        for fase, mascara in [("alta", diario.ret_ibrx > 0), ("baixa", diario.ret_ibrx < 0)]:
            linhas.append({"Serie": serie, "Fase": fase,
                           "Captura_pct": 100 * diario.loc[mascara, serie].mean()
                           / diario.loc[mascara, "ret_ibrx"].mean()})
    return pd.DataFrame(linhas)


def diferencial_indices(desempenho):
    """Diferença de retorno anual ISE B3 - IBrX-100 e a mesma diferença com os dois universos
    em pesos iguais: quanto dela é regra de ponderação (Tabela 10)."""
    cagr = desempenho.set_index("Serie")["Retorno Anual (%)"]
    oficial = cagr.ret_ise - cagr.ret_ibrx
    igual = cagr.ISE_Universo_EW - cagr.AMPLO_PROXY_Universo_EW
    return pd.DataFrame([{
        "Diferencial_oficial_pp": oficial,
        "Diferencial_universos_EW_pp": igual,
        "Reducao_magnitude_pct": (1 - abs(igual) / abs(oficial)) * 100 if oficial else np.nan}])


def eventos_por_carteira(ocorrencias):
    """Eventos documentados e liquidações aproximadas, com data, valor e peso (Apêndice B)."""
    eventos = (ocorrencias[ocorrencias.Tipo.isin(["evento_validado", "liquidacao_aproximada"])]
               .drop(columns="Detalhe").copy())
    eventos["Peso_fechamento_anterior_pct"] = eventos.Peso_fechamento_anterior * 100
    return eventos


# %% PARTE 6 — CONFERÊNCIAS
# ──────────────────────────────────────────────────────────────────────────────────────────
# Antes de gravar qualquer resultado, o programa confere que os índices e a Selic coincidem
# com as séries oficiais da B3 e do Banco Central, que as composições são válidas, que séries
# diárias, retornos anuais e métricas contam a mesma história e que o livro de posições e
# ordens bate com o patrimônio. Qualquer divergência interrompe a execução.
# No TCC: seções 4.2, 4.4 e 5.6 (Quadro 8).
# ──────────────────────────────────────────────────────────────────────────────────────────
def conferir_fontes_oficiais(bench):
    """Confere os níveis do ISE B3 e do IBrX-100 e a Selic com as séries oficiais.

    As séries oficiais estão em dados/fontes: fechamentos diários publicados pela B3
    (estatísticas históricas dos índices) e série 1178 do Banco Central (Selic anualizada).
    Todas as datas da base precisam existir na fonte oficial, com o mesmo valor.
    """
    b3 = pd.read_csv(FONTES / "indices_b3_estatisticas_historicas.csv", parse_dates=["data"])
    bcb = pd.read_csv(FONTES / "selic_bcb_sgs1178.csv", parse_dates=["data"])
    oficiais = {"ise_b3": (b3.set_index("data").ise_b3, "B3, estatísticas históricas do ISE B3"),
                "ibrx100": (b3.set_index("data").ibrx100, "B3, estatísticas históricas do IBrX-100"),
                "selic_aa": (bcb.set_index("data").selic_aa, "Banco Central do Brasil, série 1178")}
    linhas = []
    for serie, (oficial, fonte) in oficiais.items():
        comum = bench.index.intersection(oficial.index)
        diferenca = (bench.loc[comum, serie] - oficial.loc[comum]).abs()
        linhas.append({"Serie": serie, "Fonte_oficial": fonte, "Datas_na_base": len(bench),
                       "Datas_conferidas": len(comum),
                       "Valores_identicos": int((diferenca < 0.005).sum()),
                       "Maior_diferenca": float(diferenca.max())})
        if linhas[-1]["Valores_identicos"] != len(bench):
            raise ErroAuditoria(f"{serie}: a base diverge da fonte oficial ({fonte}).")
    return pd.DataFrame(linhas)


def conferir_composicoes(comp):
    """Nenhuma carteira repete ações, e os pesos são válidos e somam 1."""
    exigir_colunas(comp, ["Universo", "Estrategia", "Ano", "Ticker", "Peso"], "composição")
    chaves = ["Universo", "Estrategia", "Ano"]
    if comp.duplicated(chaves + ["Ticker"]).any():
        raise ErroAuditoria("Posição duplicada na composição.")
    if not np.isfinite(comp.Peso).all() or (comp.Peso < 0).any():
        raise ErroAuditoria("Peso inválido.")
    if not np.allclose(comp.groupby(chaves).Peso.sum(), 1, atol=1e-10, rtol=0):
        raise ErroAuditoria("Os pesos das composições não somam 1.")


def conferir_consistencia(diario, anual, desempenho, anos=None):
    """Confere, sem arredondar, que séries diárias, retornos anuais e métricas coincidem.

    Todas as séries, todos os anos e as cinco métricas; divergência acima de 1e-8 interrompe.
    """
    anos = range(ANO_INI, ANO_FIM + 1) if anos is None else anos
    exigir_colunas(diario, ["selic_dia"], "retornos diários")
    validar_retornos(diario)
    colunas = [c for c in diario if c != "selic_dia"]
    if not colunas:
        raise ErroAuditoria("Nenhuma carteira para verificar.")
    exigir_colunas(anual, colunas, "retornos anuais")
    exigir_colunas(desempenho, ["Serie", "Retorno Total (%)", "Retorno Anual (%)",
                                "Volatilidade (%)", "Sharpe", "Max Drawdown (%)"], "desempenho")
    if list(anual.index) != list(anos) or sorted(diario.index.year.unique()) != list(anos):
        raise ErroAuditoria("Os anos do experimento estão incompletos ou fora de ordem.")
    if desempenho.Serie.duplicated().any() or set(desempenho.Serie) != set(colunas):
        raise ErroAuditoria("Séries de desempenho ausentes, adicionais ou repetidas.")
    reconstruido = retornos_anuais(diario[colunas])
    try:
        np.testing.assert_allclose(anual[colunas], reconstruido[colunas], rtol=0, atol=1e-8)
        indexado = desempenho.set_index("Serie")
        for serie in colunas:
            esperado = metricas(diario[serie], diario.selic_dia)
            for campo, valor in esperado.items():
                np.testing.assert_allclose(indexado.loc[serie, campo], valor, rtol=0, atol=1e-8)
            np.testing.assert_allclose(((1 + anual[serie] / 100).prod() - 1) * 100,
                                       esperado["Retorno Total (%)"], rtol=0, atol=1e-8)
    except AssertionError as exc:
        raise ErroAuditoria("Divergência entre séries diárias, retornos anuais ou métricas.") from exc
    return {"series_conferidas": len(colunas), "anos_conferidos": len(list(anos)),
            "observacoes": len(diario), "status": "consistente"}


def conferir_livro(diario, posicoes, operacoes, rebalanceamentos, custo_por_lado):
    """Confere o livro de posições diárias e de ordens contra o patrimônio simulado.

    Valor e peso de cada posição em cada dia, e o custo de cada ordem e de cada
    rebalanceamento.
    """
    exigir_colunas(posicoes, ["Data", "Universo", "Estrategia", "Ticker", "Valor", "Peso"],
                   "posições")
    exigir_colunas(operacoes, ["Data", "Universo", "Estrategia", "Ticker", "Valor", "Custo"],
                   "operações")
    chaves = ["Universo", "Estrategia", "Data"]
    if posicoes[chaves + ["Ticker"]].isna().any().any():
        raise ErroAuditoria("Posições sem identificação de carteira, data ou ativo.")
    if posicoes.duplicated(chaves + ["Ticker"]).any():
        raise ErroAuditoria("Posições duplicadas no livro.")
    if (not np.isfinite(posicoes[["Valor", "Peso"]]).all().all()
            or (posicoes.Valor < -1e-12).any()):
        raise ErroAuditoria("Posições com valores inválidos.")
    if (posicoes.Peso < -1e-12).any():
        raise ErroAuditoria("Posições com pesos negativos.")
    esperadas = set(diario.columns) - {"ret_ibrx", "ret_ise", "selic_dia"}
    presentes = set(posicoes.Universo + "_" + posicoes.Estrategia)
    if not esperadas or presentes != esperadas:
        raise ErroAuditoria(
            f"Carteiras ausentes ou adicionais no livro: {sorted(esperadas ^ presentes)}")
    agregado = posicoes.groupby(chaves).agg(Valor=("Valor", "sum"), Peso=("Peso", "sum"))
    if not np.allclose(agregado.Peso, 1, rtol=0, atol=1e-10):
        raise ErroAuditoria("Pesos diários não somam 1.")
    for (universo, estrategia), grupo in agregado.groupby(level=[0, 1]):
        serie = f"{universo}_{estrategia}"
        valores = grupo.droplevel([0, 1]).Valor
        if not valores.index.equals(diario.index):
            raise ErroAuditoria(f"Livro incompleto para {serie}.")
        if not np.allclose(valores, (1 + diario[serie]).cumprod(), rtol=1e-10, atol=1e-10):
            raise ErroAuditoria(f"Patrimônio e posições divergem em {serie}.")
    totais = posicoes.groupby(chaves).Valor.transform("sum")
    if (totais <= 0).any() or not np.allclose(posicoes.Peso, posicoes.Valor / totais,
                                              rtol=0, atol=1e-10):
        raise ErroAuditoria("Peso individual diverge do valor relativo da posição.")
    if ((operacoes.Ticker == "CAIXA") | operacoes.Ticker.str.startswith("RECEBER_")).any():
        raise ErroAuditoria("Foi registrada negociação de caixa como ação.")
    if not np.allclose(operacoes.Custo, operacoes.Valor.abs() * custo_por_lado,
                       rtol=0, atol=1e-12):
        raise ErroAuditoria("Custos das ordens não correspondem ao volume negociado.")
    somas = operacoes.groupby(chaves).Custo.sum()
    esperado = rebalanceamentos.set_index(chaves).Custo
    if not np.allclose(somas.reindex(esperado.index, fill_value=0), esperado, rtol=0, atol=1e-12):
        raise ErroAuditoria("Custo do rebalanceamento difere da soma das ordens.")
    return {"dias_carteira_conferidos": len(agregado), "operacoes_conferidas": len(operacoes),
            "status": "consistente"}


# %% PARTE 7 — TESTES ESTATÍSTICOS E ALFAS
# ──────────────────────────────────────────────────────────────────────────────────────────
# Diferença entre índices de Sharpe (Ledoit e Wolf, bootstrap em blocos), diferença de
# médias, teste de interação, alfas contra os fatores do NEFIN e correção de Holm.
# No TCC: seção 4.5, Equação 13, e seção 5.3.
# ──────────────────────────────────────────────────────────────────────────────────────────
def defasagem_nw(n):
    """Defasagens do erro-padrão robusto pela regra de Newey e West (oito, neste estudo)."""
    return int(np.floor(4 * (n / 100) ** (2 / 9)))


def covariancia_hac(y, defasagem):
    """Covariância robusta à heterocedasticidade e à autocorrelação (pesos de Bartlett)."""
    n = len(y)
    yc = y - y.mean(axis=0)
    psi = yc.T @ yc / n
    for lag in range(1, min(defasagem, n - 1) + 1):
        gamma = yc[lag:].T @ yc[:-lag] / n
        psi += (1 - lag / (defasagem + 1)) * (gamma + gamma.T)
    return psi


def diferenca_sharpe_hac(a, b):
    """Diferença entre dois Sharpes diários e seu erro-padrão pelo método delta
    (Ledoit e Wolf, 2008)."""
    n = len(a)
    mu1, mu2 = a.mean(), b.mean()
    g1, g2 = np.mean(a * a), np.mean(b * b)
    s1, s2 = np.sqrt(max(g1 - mu1 * mu1, 0)), np.sqrt(max(g2 - mu2 * mu2, 0))
    if min(s1, s2) <= 1e-14:
        raise ValueError("Sharpe indefinido: volatilidade nula.")
    grad = np.array([g1 / s1**3, -g2 / s2**3, -mu1 / (2 * s1**3), mu2 / (2 * s2**3)])
    cov = covariancia_hac(np.column_stack([a, b, a * a, b * b]), defasagem_nw(n))
    correcao = np.sqrt((n - 1) / n)  # mesma correção ddof=1 das tabelas descritivas
    return correcao * (mu1 / s1 - mu2 / s2), correcao * np.sqrt(
        max(float(grad @ cov @ grad / n), 0))


def indices_blocos(rng, n, bloco):
    """Índices de uma reamostragem em blocos circulares de pregões consecutivos."""
    inicio = rng.integers(0, n, int(np.ceil(n / bloco)))
    return ((inicio[:, None] + np.arange(bloco)) % n).ravel()[:n]


def bootstrap_sharpe(a, b, replicacoes=N_BOOTSTRAP, bloco=5, semente=SEMENTE):
    """Teste da diferença entre índices de Sharpe por bootstrap studentizado (Tabela 6).

    Devolve a diferença anualizada, o intervalo de 95% e o p-valor bilateral.
    """
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    if len(a) != len(b) or len(a) < 30 or not np.isfinite(np.column_stack([a, b])).all():
        raise ValueError("Bootstrap exige séries pareadas completas e pelo menos 30 observações.")
    diferenca, se = diferenca_sharpe_hac(a, b)
    if se <= 1e-14:
        if abs(diferenca) > 1e-12:
            raise ValueError("Erro-padrão degenerado.")
        return {"Diferenca_Sharpe": 0.0, "IC95_inferior": 0.0, "IC95_superior": 0.0,
                "p_bootstrap": 1.0, "Replicacoes": replicacoes, "Bloco": bloco, "N": len(a)}
    rng = np.random.default_rng(semente)
    estatisticas = []
    for _ in range(replicacoes):
        idx = indices_blocos(rng, len(a), bloco)
        delta, erro = diferenca_sharpe_hac(a[idx], b[idx])
        if erro <= 1e-14:
            raise ValueError("Réplica bootstrap degenerada; revisar a amostra.")
        estatisticas.append((delta - diferenca) / erro)
    t = np.asarray(estatisticas)
    qlo, qhi = np.quantile(t, [0.025, 0.975])
    escala = np.sqrt(252)
    return {
        "Diferenca_Sharpe": diferenca * escala,
        "IC95_inferior": (diferenca - qhi * se) * escala,
        "IC95_superior": (diferenca - qlo * se) * escala,
        "p_bootstrap": (1 + np.sum(abs(t) >= abs(diferenca / se))) / (replicacoes + 1),
        "Replicacoes": replicacoes, "Bloco": bloco, "N": len(a),
    }


def teste_media_hac(serie):
    """Testa se a média das diferenças diárias é zero, com erro-padrão robusto (Tabela 7)."""
    y = np.asarray(serie)
    n = len(y)
    fit = sm.OLS(y, np.ones((n, 1))).fit(
        cov_type="HAC", cov_kwds={"maxlags": defasagem_nw(n), "use_correction": True})
    return {"Media_pp_ano": float(fit.params[0] * 252 * 100), "t": float(fit.tvalues[0]),
            "p_HAC": float(fit.pvalues[0]), "N": n}


def bootstrap_interacao(retornos, replicacoes, bloco, semente, fixar_inicio=False):
    """O ganho do fator é o mesmo nos dois universos? (Tabela 10)

    Contraste de quatro retornos anuais: (fator ISE - EW ISE) - (fator amplo - EW amplo). As
    quatro séries são reamostradas juntas; intervalo básico e teste bilateral. É uma
    comparação descritiva, e não uma estimativa causal nem uma carteira negociável.
    """
    if retornos.shape[1] != 4 or retornos.isna().any().any():
        raise ValueError("Interação exige quatro séries completas.")
    anos = (retornos.index[-1] - retornos.index[0]).days / 365.25
    log = np.log1p(retornos.to_numpy())
    contraste = np.array([1.0, -1.0, -1.0, 1.0])
    observado = float(np.expm1(log.sum(axis=0) / anos) @ contraste) * 100
    inicial = log[0].copy() if fixar_inicio else np.zeros(4)
    reamostravel = log[1:] if fixar_inicio else log
    rng = np.random.default_rng(semente)
    estimativas = np.empty(replicacoes)
    for i in range(replicacoes):
        idx = indices_blocos(rng, len(reamostravel), bloco)
        estimativas[i] = np.expm1((inicial + reamostravel[idx].sum(axis=0)) / anos) @ contraste * 100
    erros = estimativas - observado
    qlo, qhi = np.quantile(erros, [0.025, 0.975])
    return {
        "Diferenca_CAGR_pp": observado,
        "IC95_inferior_pp": observado - qhi,
        "IC95_superior_pp": observado - qlo,
        "p_bootstrap": float((1 + np.sum(abs(erros) >= abs(observado))) / (replicacoes + 1)),
        "Replicacoes": replicacoes, "Bloco": bloco, "N": len(retornos),
    }


def regressao_alfa(retorno, fatores, nomes):
    """Alfa contra os fatores do NEFIN (TCC 4.5, Equação 13, e Tabela 8).

    O excesso de retorno usa a taxa livre de risco do próprio NEFIN, e não a Selic do Sharpe.
    """
    dados = pd.concat([retorno.rename("carteira"), fatores[nomes + ["Risk_Free"]]],
                      axis=1, join="inner")
    if len(dados) != len(retorno) or dados.isna().any().any():
        raise ValueError("Fatores NEFIN não cobrem todas as datas da inferência.")
    y = dados.carteira - dados.Risk_Free
    X = sm.add_constant(dados[nomes])
    n = len(dados)
    fit = sm.OLS(y, X).fit(cov_type="HAC",
                           cov_kwds={"maxlags": defasagem_nw(n), "use_correction": True})
    return {
        "Alfa_diario": float(fit.params["const"]),
        "Alfa_linear_pp_ano": float(fit.params["const"] * 252 * 100),
        "Alfa_composto_pct_ano": float(np.expm1(np.log1p(fit.params["const"]) * 252) * 100),
        "t_alfa": float(fit.tvalues["const"]),
        "p_alfa": float(fit.pvalues["const"]),
        "R2": float(fit.rsquared),
        "N": n,
        **{f"beta_{c}": float(fit.params[c]) for c in nomes},
    }


def holm(pvalores):
    """Correção de Holm para comparações múltiplas (TCC 4.5)."""
    p = np.asarray(pvalores)
    ordem = np.argsort(p)
    ajustados = np.empty(len(p))
    ajustados[ordem] = np.minimum(1, np.maximum.accumulate((len(p) - np.arange(len(p))) * p[ordem]))
    return ajustados


def testes_estatisticos(diario, nefin):
    """Sharpe e médias nos 13 pares, interação nas seis estratégias e alfas (TCC 4.5 e 5.3).

    O primeiro pregão é a montagem, e não um intervalo diário: o custo inicial entra no
    patrimônio e no retorno anual, e os testes diários começam no pregão seguinte.
    """
    df = diario.iloc[1:]
    selic = df.selic_dia
    # Os treze pares da Tabela 6; a correção de Holm considera os treze em cada bloco.
    pares = [
        ("ISE_Uniao_TCC", "ret_ibrx", "União ISE × IBrX-100 oficial"),
        ("ISE_Multifator", "ret_ibrx", "Multifator ISE × IBrX-100 oficial"),
        ("ISE_Baixa_Vol", "ret_ibrx", "Baixa vol ISE × IBrX-100 oficial"),
        ("ISE_Uniao_TCC", "ret_ise", "União ISE × ISE oficial"),
        ("ISE_Multifator", "ret_ise", "Multifator ISE × ISE oficial"),
        ("ISE_Universo_EW", "AMPLO_PROXY_Universo_EW", "Universos elegíveis em pesos iguais"),
        ("ret_ise", "ret_ibrx", "Índices oficiais"),
    ] + [(f"ISE_{e}", f"AMPLO_PROXY_{e}", f"{e}: ISE × amplo aproximado") for e in ESTRATEGIAS]
    sharpe, medias = [], []
    for a, b, nome in pares:
        print(f"  Teste de Sharpe: {nome}", flush=True)
        for bloco in BLOCOS_BOOTSTRAP:
            sharpe.append({"Comparacao": nome, "A": a, "B": b,
                           **bootstrap_sharpe(df[a] - selic, df[b] - selic, N_BOOTSTRAP, bloco,
                                              SEMENTE)})
        medias.append({"Comparacao": nome, **teste_media_hac(df[a] - df[b])})
    sharpe = pd.DataFrame(sharpe)
    for _, sub in sharpe.groupby("Bloco"):
        sharpe.loc[sub.index, "p_Holm"] = holm(sub.p_bootstrap)

    # Interação: mantém fixo o custo da montagem e reamostra só os intervalos diários.
    interacao = []
    for estrategia in ESTRATEGIAS:
        colunas = [f"ISE_{estrategia}", "ISE_Universo_EW",
                   f"AMPLO_PROXY_{estrategia}", "AMPLO_PROXY_Universo_EW"]
        for bloco in BLOCOS_BOOTSTRAP:
            interacao.append({"Estrategia": estrategia,
                              **bootstrap_interacao(diario[colunas], N_BOOTSTRAP, bloco,
                                                    SEMENTE, fixar_inicio=True)})
    interacao = pd.DataFrame(interacao)
    for _, sub in interacao.groupby("Bloco"):
        interacao.loc[sub.index, "p_Holm"] = holm(sub.p_bootstrap)

    # Três modelos de alfa: CAPM, Carhart e Carhart com o fator de liquidez.
    modelos = {"CAPM": ["Rm_minus_Rf"],
               "Carhart": ["Rm_minus_Rf", "SMB", "HML", "WML"],
               "Carhart_IML": ["Rm_minus_Rf", "SMB", "HML", "WML", "IML"]}
    alfas = pd.DataFrame([{"Serie": carteira, "Modelo": modelo,
                           **regressao_alfa(df[carteira], nefin, colunas)}
                          for carteira in [c for c in df if c != "selic_dia"]
                          for modelo, colunas in modelos.items()])
    return sharpe, pd.DataFrame(medias), interacao, alfas


# %% PARTE 8 — ROBUSTEZ
# ──────────────────────────────────────────────────────────────────────────────────────────
# As análises de sensibilidade da seção 4.6: custos de negociação, listas do ISE B3 e eventos
# societários. No TCC: seções 4.6 e 5.6.
# ──────────────────────────────────────────────────────────────────────────────────────────
def sensibilidade_custos(precos, selic, agendas, eventos, diario):
    """Carteiras do ISE refeitas com custo de 0, 10, 20 e 50 pontos-base por lado (Tabela 11)."""
    linhas = []
    for (universo, estrategia), agenda in agendas.items():
        if universo != "ISE":
            continue
        nome = f"ISE_{estrategia}"
        for custo in CUSTOS_SENSIBILIDADE:
            retornos = (diario[nome] if custo == CUSTO_POR_LADO else
                        simular(precos, selic, agenda, custo_por_lado=custo, eventos=eventos).retornos)
            linhas.append({"Serie": nome, "Custo_bps_lado": custo * 10000,
                           **metricas(retornos, selic)})
    return pd.DataFrame(linhas)


def sensibilidade_listas_e_eventos(px, bench, agendas, eventos, diario, selic):
    """Tabela 12 do TCC, para União, Multifator e baixa volatilidade no ISE.

    Listas: as carteiras são refeitas com as listas do ISE B3 usadas antes da conferência com
    os boletins da B3 (dados/entrada/universos_anteriores.csv), pelo mesmo motor; as das
    listas conferidas são as da execução principal.
    Eventos: as carteiras da execução principal são simuladas de novo sem os tratamentos
    documentados de eventos societários, de modo que toda saída segue a regra aproximada.
    """
    precos = px.reindex(diario.index)
    antigas = ler_universos(ENTRADA / "universos_anteriores.csv")
    agendas_antigas, _, _, _ = formar_carteiras(
        px, bench, antigas[antigas.Universo == "ISE"], RENOMEADOS, exigir_lista_anunciada=False)
    listas = [{"Listas": "listas_anteriores", "Serie": f"ISE_{e}",
               **metricas(simular(precos, selic, agendas_antigas[("ISE", e)],
                                  eventos=eventos).retornos, selic)} for e in PRINCIPAIS]
    listas += [{"Listas": "listas_documentadas", "Serie": f"ISE_{e}",
                **metricas(diario[f"ISE_{e}"], selic)} for e in PRINCIPAIS]
    efeito = []
    for e in PRINCIPAIS:
        sem = metricas(simular(precos, selic, agendas[("ISE", e)]).retornos, selic)
        com = metricas(diario[f"ISE_{e}"], selic)
        efeito.append({"Estrategia": e, "CAGR_sem_eventos_pct": sem["Retorno Anual (%)"],
                       "CAGR_com_eventos_pct": com["Retorno Anual (%)"],
                       "Delta_pp": com["Retorno Anual (%)"] - sem["Retorno Anual (%)"]})
    return pd.DataFrame(listas), pd.DataFrame(efeito)


# %% PARTE 9 — GRÁFICOS
# ──────────────────────────────────────────────────────────────────────────────────────────
# Os quatro gráficos do TCC. Cores da paleta de Okabe e Ito, legível para daltônicos, e um
# traço próprio para cada série, para a impressão em preto e branco. Sem título na figura:
# a legenda ABNT fica no documento.
# ──────────────────────────────────────────────────────────────────────────────────────────
CM = 1 / 2.54
LARGURA = 16 * CM
ESTILOS = {
    "ISE_Uniao_TCC": dict(cor="#0072B2", traco="-", rotulo="União (ISE B3)"),
    "ISE_Multifator": dict(cor="#009E73", traco="--", rotulo="Multifator (ISE B3)"),
    "ISE_Baixa_Vol": dict(cor="#CC79A7", traco=(0, (1, 1.2)),
                          rotulo="Baixa volatilidade (ISE B3)"),
    "ISE_Valor": dict(cor="#E69F00", traco="--", rotulo="Valor (ISE B3)"),
    "ISE_Momentum": dict(cor="#56B4E9", traco="-", rotulo="Momentum (ISE B3)"),
    "ISE_Qualidade": dict(cor="#8C6D31", traco=(0, (3, 1, 1, 1)), rotulo="Qualidade (ISE B3)"),
    "ret_ibrx": dict(cor="#3A3A3A", traco="-", rotulo="IBrX-100"),
    "ret_ise": dict(cor="#D55E00", traco=(0, (5, 1.5)), rotulo="ISE B3"),
}
MESES = ["jan.", "fev.", "mar.", "abr.", "maio", "jun.",
         "jul.", "ago.", "set.", "out.", "nov.", "dez."]


def _numero_br(valor, casas=0):
    return f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _linhas(ax, dados, series, rotular_fim=True):
    """Desenha as séries e, se pedido, escreve o valor final de cada uma na ponta da linha."""
    for nome in series:
        estilo = ESTILOS[nome]
        ax.plot(dados.index, dados[nome], color=estilo["cor"], linestyle=estilo["traco"],
                linewidth=1.4, label=estilo["rotulo"], solid_capstyle="round")
    ax.grid(axis="y")
    ax.set_axisbelow(True)
    if not rotular_fim:
        return
    # Rótulos afastados uns dos outros para não se sobreporem.
    inferior, superior = ax.get_ylim()
    folga = (superior - inferior) * 0.055
    anterior = None
    for valor, nome in sorted(((dados[nome].iloc[-1], nome) for nome in series), reverse=True):
        alvo = valor if anterior is None else min(valor, anterior - folga)
        anterior = alvo
        ax.annotate(_numero_br(valor), xy=(dados.index[-1], alvo), xytext=(5, 0),
                    textcoords="offset points", va="center", fontsize=8,
                    color=ESTILOS[nome]["cor"], annotation_clip=False)


def gerar_graficos(diario, captura, pasta):
    """Gráficos 1 (patrimônio), 2 (drawdown), 3 (captura) e 4 (crise de 2020) do TCC."""
    pasta.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({
        "font.family": "serif", "font.serif": ["Times New Roman", "DejaVu Serif"],
        "font.size": 9, "axes.titlesize": 9, "axes.labelsize": 9, "legend.fontsize": 8.5,
        "xtick.labelsize": 8.5, "ytick.labelsize": 8.5,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.edgecolor": "#5A5A5A", "axes.linewidth": 0.6,
        "grid.color": "#B7B7B7", "grid.linewidth": 0.4, "grid.alpha": 0.6,
        "figure.dpi": 300, "savefig.dpi": 300, "savefig.bbox": "tight",
        "savefig.pad_inches": 0.02,
    })
    formato = FuncFormatter(lambda valor, _: _numero_br(valor))
    principais = ["ISE_Uniao_TCC", "ISE_Multifator", "ret_ibrx", "ret_ise"]

    # Gráfico 1: patrimônio acumulado.
    dados = patrimonio(diario[principais]) * 100
    fig, ax = plt.subplots(figsize=(LARGURA, 8.4 * CM))
    _linhas(ax, dados, principais)
    ax.set_ylabel("Capital inicial = 100")
    ax.yaxis.set_major_formatter(formato)
    ax.set_xlim(dados.index[0], dados.index[-1] + pd.Timedelta(days=210))
    ax.legend(loc="upper left", frameon=False, ncol=2)
    fig.savefig(pasta / "grafico1_patrimonio.png")
    plt.close(fig)

    # Gráfico 2: drawdown.
    dados = drawdown(diario[principais]) * 100
    fig, ax = plt.subplots(figsize=(LARGURA, 7.6 * CM))
    _linhas(ax, dados, principais, rotular_fim=False)
    ax.set_ylabel("Drawdown (%)")
    ax.yaxis.set_major_formatter(formato)
    ax.set_xlim(dados.index[0], dados.index[-1])
    ax.legend(loc="lower left", frameon=False, ncol=2)
    fig.savefig(pasta / "grafico2_drawdown.png")
    plt.close(fig)

    # Gráfico 3: captura de alta e de baixa em relação ao IBrX-100.
    ordem = ["ISE_Multifator", "ISE_Baixa_Vol", "ISE_Uniao_TCC", "ISE_Valor",
             "ISE_Momentum", "ISE_Qualidade", "ret_ise"]
    tabela = captura.pivot(index="Serie", columns="Fase", values="Captura_pct").reindex(ordem)
    posicoes = range(len(tabela))
    fig, ax = plt.subplots(figsize=(LARGURA, 8.6 * CM))
    altura = 0.36
    for deslocamento, fase, cor, rotulo in (
            (altura / 2, "alta", "#0072B2", "Pregões de alta do IBrX-100"),
            (-altura / 2, "baixa", "#D55E00", "Pregões de baixa do IBrX-100")):
        barras = ax.barh([p + deslocamento for p in posicoes], tabela[fase], height=altura,
                         color=cor, edgecolor="white", linewidth=0.8, label=rotulo)
        for barra, valor in zip(barras, tabela[fase]):
            ax.annotate(f"{valor:,.0f}".replace(",", "."),
                        xy=(valor, barra.get_y() + barra.get_height() / 2), xytext=(3, 0),
                        textcoords="offset points", va="center", fontsize=8, color="#3A3A3A")
    ax.set_yticks(list(posicoes))
    ax.set_yticklabels([ESTILOS[s]["rotulo"] for s in tabela.index])
    ax.invert_yaxis()
    ax.axvline(100, color="#5A5A5A", linewidth=0.8, linestyle=(0, (3, 2)),
               label="100 = mesmo movimento do IBrX-100")
    ax.set_xlabel("Retorno médio diário da carteira em relação ao do IBrX-100 (%)")
    ax.set_xlim(0, 122)
    ax.xaxis.set_major_formatter(formato)
    ax.grid(axis="x")
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.01), ncol=2, frameon=False,
              borderaxespad=0)
    fig.savefig(pasta / "grafico3_captura.png")
    plt.close(fig)

    # Gráfico 4: crise de 2020, a partir do pico de 23/01/2020 (Apêndice B).
    series = ["ISE_Multifator", "ISE_Baixa_Vol", "ISE_Uniao_TCC", "ret_ibrx", "ret_ise"]
    dados = patrimonio(diario.loc["2020-01-23":"2020-12-29", series])
    dados = dados / dados.iloc[0] * 100
    fig, ax = plt.subplots(figsize=(LARGURA, 8.0 * CM))
    _linhas(ax, dados, series)
    ax.set_ylabel("Pico de 23/01/2020 = 100")
    ax.yaxis.set_major_formatter(formato)
    ax.axhline(100, color="#8A8A8A", linewidth=0.6, linestyle=(0, (2, 2)))
    ax.set_xlim(dados.index[0], dados.index[-1] + pd.Timedelta(days=22))
    ax.legend(loc="lower right", frameon=False, ncol=2)
    ax.xaxis.set_major_locator(MonthLocator())
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _: MESES[num2date(x).month - 1]))
    fig.savefig(pasta / "grafico4_crise_2020.png")
    plt.close(fig)


# %% PARTE 10 — EXECUÇÃO
# ──────────────────────────────────────────────────────────────────────────────────────────
# Roda as Partes 2 a 9 na ordem, grava cada tabela em resultados/ (ao lado, a tabela do TCC
# que sai dela) e registra a execução. No TCC: seção 4.6.
# ──────────────────────────────────────────────────────────────────────────────────────────
def executar():
    """Roda o estudo completo."""
    inicio = datetime.now(timezone.utc)

    print("Parte 2 — Dados: as ações de cada ano, preços, índices, Selic e fundamentos",
          flush=True)
    universos = montar_universos()
    px, bench = carregar_mercado()
    obter_fundamentos(bench, ATUALIZAR_FUNDAMENTOS)

    print("Parte 3 — Formação das carteiras, ano a ano (universo do ISE)", flush=True)
    agendas, comp, fatores, exclusoes = formar_carteiras(px, bench, universos, RENOMEADOS)
    mostrar_carteiras(comp, fatores)

    print("Parte 4 — Simulação diária das 14 carteiras", flush=True)
    datas, selic = periodo_simulacao(bench)
    precos = px.reindex(datas)
    eventos = json.loads((ENTRADA / "eventos.json").read_text(encoding="utf-8"))
    diario, registros = simular_todas(precos, selic, agendas, eventos)
    for nome, serie in retornos_benchmarks(bench, datas).items():
        diario[nome] = serie
    diario["selic_dia"] = selic
    diario.index.name = "data"

    print("Parte 5 — Desempenho", flush=True)
    anual = retornos_anuais(diario.drop(columns="selic_dia"))
    desempenho = pd.DataFrame([{"Serie": c, **metricas(diario[c], selic)}
                               for c in diario if c != "selic_dia"])
    captura = calcular_capturas(diario)

    print("Parte 6 — Conferências", flush=True)
    fontes_oficiais = conferir_fontes_oficiais(bench)
    conferir_composicoes(comp)
    auditoria = conferir_consistencia(diario, anual, desempenho)
    livro = conferir_livro(diario, registros["posicoes"], registros["operacoes"],
                           registros["rebalanceamentos"], CUSTO_POR_LADO)

    print("Parte 7 — Testes estatísticos e alfas", flush=True)
    nefin = pd.read_csv(ENTRADA / "nefin_fatores.csv", parse_dates=["Date"]).set_index("Date")
    sharpe, medias, interacao, alfas = testes_estatisticos(diario, nefin)

    print("Parte 8 — Robustez", flush=True)
    custos = sensibilidade_custos(precos, selic, agendas, eventos, diario)
    listas, efeito_eventos = sensibilidade_listas_e_eventos(px, bench, agendas, eventos,
                                                            diario, selic)

    print("Parte 9 — Gráficos e gravação dos resultados", flush=True)
    pasta = RESULTADOS
    pasta.mkdir(exist_ok=True)

    def salvar(tabela, nome, **opcoes):
        tabela.to_csv(pasta / f"{nome}.csv", **opcoes)

    gerar_graficos(diario, captura, pasta / "figuras")                   # Gráficos 1 a 4
    # Formação
    salvar(fatores, "fatores_formacao", index=False)                     # Tabela 1
    salvar(comp, "composicoes_alvo", index=False)                        # Tabela 1, Quadros 4-6
    salvar(exclusoes, "exclusoes", index=False)                          # seção 4.2
    # Simulação e desempenho
    salvar(diario, "retornos_diarios", encoding="utf-8-sig")             # Tabela 2
    salvar(desempenho, "desempenho", index=False, encoding="utf-8-sig")  # Tabelas 3 e 10
    salvar(anual, "retornos_anuais", encoding="utf-8-sig")               # Tabela 4
    salvar(distribuicao_setorial(comp), "setores_media", index=False)    # Tabela 5
    salvar(episodios_estresse(diario), "periodos_estresse", index=False)  # Tabela 9
    salvar(captura, "captura_alta_baixa", index=False)                   # Gráfico 3
    salvar(diferencial_indices(desempenho), "decomposicao_descritiva_indices",
           index=False)                                                  # Tabela 10
    salvar(registros["rebalanceamentos"], "rebalanceamentos", index=False,
           encoding="utf-8-sig")                                         # Tabela 11 (giro)
    salvar(registros["operacoes"], "operacoes", index=False, encoding="utf-8-sig")  # ordens
    salvar(eventos_por_carteira(registros["ocorrencias"]), "eventos_por_carteira",
           index=False)                                                  # Quadro 8, Apêndice B
    # Testes estatísticos
    salvar(sharpe, "testes_sharpe", index=False)                         # Tabelas 6 e 10
    salvar(medias, "testes_medias", index=False)                         # Tabela 7
    salvar(alfas, "testes_alfas", index=False)                           # Tabela 8
    salvar(interacao, "testes_interacao_cagr", index=False)              # Tabela 10
    # Robustez
    salvar(custos, "sensibilidade_custos", index=False, encoding="utf-8-sig")  # Tabela 11
    salvar(listas, "sensibilidade_listas_ise", index=False)              # Tabela 12
    salvar(efeito_eventos, "sensibilidade_eventos", index=False)         # Tabela 12
    # Conferência dos dados
    salvar(fontes_oficiais, "conferencia_fontes_oficiais", index=False)  # Quadro 8

    registrar_execucao(inicio, auditoria, livro)
    mostrar_resumo(desempenho, sharpe)


def registrar_execucao(inicio, auditoria, livro):
    """Grava resultados/execucao.json: configuração, versões, conferências, pendências
    declaradas e o SHA-256 deste arquivo, de cada entrada e de cada saída (TCC 4.6)."""
    def sha256(caminho):
        return hashlib.sha256(caminho.read_bytes()).hexdigest()

    registro = {
        "inicio_utc": inicio.isoformat(),
        "fim_utc": datetime.now(timezone.utc).isoformat(),
        "configuracao": {
            "ano_inicial": ANO_INI, "ano_final": ANO_FIM, "top_n": TOP_N,
            "minimo_pregoes": MIN_PREGOES, "custo_por_lado": CUSTO_POR_LADO,
            "bootstrap_replicacoes": N_BOOTSTRAP, "bootstrap_semente": SEMENTE,
            "bootstrap_blocos": list(BLOCOS_BOOTSTRAP)},
        "python": platform.python_version(),
        "bibliotecas": {nome: version(nome)
                        for nome in ("numpy", "pandas", "statsmodels", "matplotlib")},
        "auditoria_numerica": auditoria,
        "auditoria_livro": livro,
        "pendencias": json.loads((ENTRADA / "pendencias.json").read_text(encoding="utf-8")),
        "sha256_codigo": sha256(ARQUIVO_CODIGO),
        "sha256_entradas": {p.relative_to(RAIZ).as_posix(): sha256(p)
                            for p in sorted((RAIZ / "dados").rglob("*")) if p.is_file()},
        "sha256_resultados": {p.relative_to(RESULTADOS).as_posix(): sha256(p)
                              for p in sorted(RESULTADOS.rglob("*"))
                              if p.is_file() and p.name != "execucao.json"},
    }
    (RESULTADOS / "execucao.json").write_text(
        json.dumps(registro, ensure_ascii=False, indent=2), encoding="utf-8")


def mostrar_resumo(desempenho, sharpe):
    """Mostra no terminal a Tabela 3 e a Tabela 6 (bloco de 5 pregões)."""
    nomes = {"ISE_Multifator": "Multifator (ISE)", "ISE_Uniao_TCC": "União (ISE)",
             "ISE_Baixa_Vol": "Baixa vol. (ISE)", "ret_ibrx": "IBrX-100", "ret_ise": "ISE B3"}
    tabela = desempenho.set_index("Serie").loc[list(nomes)].rename(index=nomes)
    with pd.option_context("display.width", 140, "display.max_columns", None):
        print("\n" + "=" * 90)
        custo = f"{CUSTO_POR_LADO * 100:.2f}".replace(".", ",")
        print(f"DESEMPENHO {ANO_INI}–{ANO_FIM} | custo de {custo}% por lado")
        print("=" * 90)
        print(tabela.round(2).to_string())
        print("\nTESTES DE SHARPE (bloco de 5 pregões; p de Holm sobre as 13 comparações)")
        colunas = ["Comparacao", "Diferenca_Sharpe", "IC95_inferior", "IC95_superior",
                   "p_bootstrap", "p_Holm"]
        print(sharpe[sharpe.Bloco == 5][colunas].round(3).to_string(index=False))
    print(f"\nResultados em {RESULTADOS}")


# %% PARTE 11 — TESTES INTERNOS (só com --testar)
# ──────────────────────────────────────────────────────────────────────────────────────────
# Situações-limite com dados sintéticos, sem tocar nos resultados do TCC:
#   séries e métricas ........ 4 testes     livro de posições e ordens ... 6 testes
#   estresse e setores ....... 2 testes     caixa, custos e compras ...... 5 testes
#   testes estatísticos ...... 3 testes     eventos societários .......... 5 testes
# ──────────────────────────────────────────────────────────────────────────────────────────
def _perto(a, b, tolerancia=1e-6):
    return np.allclose(a, b, rtol=tolerancia, atol=1e-12)


def _erro_esperado(tipo, trecho, funcao, *args, **kwargs):
    """Confere que funcao(*args) recusa os dados com o erro e a mensagem esperados."""
    try:
        funcao(*args, **kwargs)
    except tipo as erro:
        assert re.search(trecho, str(erro)), f"mensagem inesperada: {erro}"
    else:
        raise AssertionError(f"{funcao.__name__} deveria ter recusado os dados.")


def _serie_teste():
    """Dois anos sintéticos de retornos, com as tabelas que a execução gravaria."""
    idx = pd.bdate_range("2020-01-01", "2021-12-31")
    r = pd.DataFrame({"A": np.sin(np.arange(len(idx))) / 100, "selic_dia": 0.0001}, index=idx)
    return r, retornos_anuais(r[["A"]]), pd.DataFrame([{"Serie": "A",
                                                         **metricas(r.A, r.selic_dia)}])


def _livro_teste():
    """Uma ação por seis pregões, para os testes do livro de posições e ordens."""
    datas = pd.bdate_range("2020-12-29", periods=6)
    precos = pd.DataFrame({"A": [10, 11, 12, 13, 12, 11]}, index=datas)
    r = simular(precos, pd.Series(0.0, index=datas), {datas[0]: {"A": 1.0}}, custo_por_lado=0.002)
    diario = pd.DataFrame({"ISE_M": r.retornos}, index=datas)
    return diario, *(d.assign(Universo="ISE", Estrategia="M")
                     for d in (r.posicoes, r.operacoes, r.rebalanceamentos))


def _livro_com_duas_posicoes():
    """Livro sintético com duas posições de mesmo peso."""
    diario, posicoes, operacoes, rebals = _livro_teste()
    metade = pd.DataFrame({"Data": diario.index,
                           "Valor": (1 + diario.ISE_M).cumprod().to_numpy() / 2,
                           "Peso": 0.5, "Universo": "ISE", "Estrategia": "M"})
    posicoes = pd.concat([metade.assign(Ticker=t) for t in ("A", "B")], ignore_index=True)
    conferir_livro(diario, posicoes, operacoes, rebals, 0.002)
    return diario, posicoes, operacoes, rebals


# Séries e métricas
def test_todas_as_series_sao_conferidas():
    assert conferir_consistencia(*_serie_teste(), anos=[2020, 2021])["series_conferidas"] == 1


def test_999_porcento_nao_passa():
    r, a, p = _serie_teste()
    a.loc[:, "A"] = 999
    _erro_esperado(ErroAuditoria, "", conferir_consistencia, r, a, p, anos=[2020, 2021])


def test_coluna_ausente_nao_e_ignorada():
    r, a, p = _serie_teste()
    _erro_esperado(ErroAuditoria, "ausentes", conferir_consistencia, r,
                   a.rename(columns={"A": "nome errado"}), p, anos=[2020, 2021])


def test_nan_nao_e_zerado():
    r, a, p = _serie_teste()
    r.iloc[3, 0] = np.nan
    _erro_esperado(ValueError, "", conferir_consistencia, r, a, p, anos=[2020, 2021])


# Estresse e setores
def test_estresse_exclui_retorno_do_pico():
    r = pd.Series([0.5, -0.2, -0.25], index=pd.date_range("2020-01-01", periods=3))
    assert _perto(retorno_entre_fechamentos(r, r.index[0], r.index[-1]), -0.4)


def test_setor_ausente_conta_como_zero():
    linhas = [{"Universo": "ISE", "Estrategia": "M", "Ano": ano, "Ticker": "A",
               "Setor": "Saneamento" if ano < 2019 else "Outro", "Peso": 0.2}
              for ano in range(2016, 2026)]
    media = distribuicao_setorial(pd.DataFrame(linhas)).set_index("Setor")
    assert _perto(media.loc["Saneamento", "Peso"], 0.06)


# Testes estatísticos
def test_series_identicas_nao_produzem_diferenca():
    r = np.random.default_rng(11).normal(0, 0.01, 100)
    t = bootstrap_sharpe(r, r, 99)
    assert t["p_bootstrap"] == 1 and t["Diferenca_Sharpe"] == 0


def test_interacao_preserva_dependencia_das_quatro_series():
    rng = np.random.default_rng(31)
    a, b = rng.normal(0.001, 0.01, 100), rng.normal(0.0005, 0.01, 100)
    df = pd.DataFrame(np.column_stack([a, b, a, b]),
                      index=pd.bdate_range("2020-01-01", periods=100))
    t = bootstrap_interacao(df, 99, 5, 4)
    assert abs(t["Diferenca_CAGR_pp"]) < 1e-10 and abs(t["IC95_inferior_pp"]) < 1e-10


def test_holm_nao_reduz_p_valores():
    p = np.array([0.01, 0.04, 0.2])
    ajustados = holm(p)
    assert np.all(ajustados >= p) and _perto(ajustados, [0.03, 0.08, 0.2])


# Livro de posições e ordens
def test_livro_bate_com_patrimonio_e_custos():
    assert conferir_livro(*_livro_teste(), 0.002)["operacoes_conferidas"] == 1


def test_alteracao_de_valor_no_livro_e_detectada():
    diario, posicoes, operacoes, rebals = _livro_teste()
    posicoes.loc[0, "Valor"] += 0.1
    _erro_esperado(ErroAuditoria, "Patrimônio", conferir_livro,
                   diario, posicoes, operacoes, rebals, 0.002)


def test_venda_de_caixa_e_detectada():
    diario, posicoes, operacoes, rebals = _livro_teste()
    operacoes.loc[0, "Ticker"] = "CAIXA"
    _erro_esperado(ErroAuditoria, "caixa", conferir_livro,
                   diario, posicoes, operacoes, rebals, 0.002)


def test_livro_rejeita_carteira_inteira_ausente():
    diario, posicoes, operacoes, rebals = _livro_teste()
    diario["ISE_Outra"] = diario.ISE_M
    _erro_esperado(ErroAuditoria, "Carteiras ausentes", conferir_livro,
                   diario, posicoes, operacoes, rebals, 0.002)


def test_livro_rejeita_pesos_individuais_incorretos():
    diario, posicoes, operacoes, rebals = _livro_com_duas_posicoes()
    primeiro_dia = posicoes.index[posicoes.Data == posicoes.Data.iloc[0]]
    posicoes.loc[primeiro_dia, "Peso"] += [0.1, -0.1]
    _erro_esperado(ErroAuditoria, "Peso individual", conferir_livro,
                   diario, posicoes, operacoes, rebals, 0.002)


def test_livro_rejeita_pesos_negativos():
    diario, posicoes, operacoes, rebals = _livro_com_duas_posicoes()
    primeiro_dia = posicoes.index[posicoes.Data == posicoes.Data.iloc[0]]
    posicoes.loc[primeiro_dia, "Peso"] = [-0.1, 1.1]
    _erro_esperado(ErroAuditoria, "pesos negativos", conferir_livro,
                   diario, posicoes, operacoes, rebals, 0.002)


# Caixa, custos e compras
def test_caixa_nao_paga_venda():
    novos, caixa, ordens, custo = executar_rebalanceamento({"B": 0.8}, 0.2, {"B": 1.0}, 0.002)
    assert _perto(ordens["B"], 0.2 / 1.002) and _perto(custo, 0.002 * 0.2 / 1.002)
    assert _perto(novos["B"] + caixa + custo, 1)


def test_primeira_compra_autofinanciada():
    novos, caixa, _, _ = executar_rebalanceamento({}, 1, {"A": 0.5, "B": 0.5}, 0.002)
    assert _perto(sum(novos.values()), 1 / 1.002) and abs(caixa) <= 1e-12


def test_virada_nao_apaga_retorno_posicao_antiga():
    idx = pd.to_datetime(["2020-12-30", "2021-01-04", "2021-01-05"])
    px = pd.DataFrame({"A": [100, 110, 110], "B": [10, 10, 11]}, index=idx)
    r = simular(px, pd.Series(0, index=idx), {idx[0]: {"A": 1}, idx[1]: {"B": 1}},
                custo_por_lado=0)
    assert _perto(r.retornos.iloc[1], 0.1) and _perto(r.patrimonio.iloc[-1], 1.21)


def test_pesos_flutuam_sem_rebalancear_diariamente():
    idx = pd.date_range("2020-01-01", periods=3)
    px = pd.DataFrame({"A": [10, 20, 10], "B": [10, 10, 10]}, index=idx)
    r = simular(px, pd.Series(0, index=idx), {idx[0]: {"A": 0.5, "B": 0.5}}, custo_por_lado=0)
    assert _perto(r.patrimonio.iloc[-1], 1) and len(r.rebalanceamentos) == 1


def test_sem_preco_na_compra_fica_caixa():
    idx = pd.date_range("2020-01-01", periods=3)
    px = pd.DataFrame({"A": [np.nan, 10, 20]}, index=idx)
    r = simular(px, pd.Series(0, index=idx), {idx[0]: {"A": 1}}, custo_por_lado=0)
    assert r.patrimonio.iloc[-1] == 1 and "compra_cancelada" in r.ocorrencias.Tipo.values


# Eventos societários
def _evento(**campos):
    return {"fonte": "evento sintético", "base": "mesma_dos_precos", "validado": True, **campos}


def test_conversao_mista_nao_vende_caixa():
    idx = pd.date_range("2020-01-01", periods=3)
    px = pd.DataFrame({"A": [10, np.nan, np.nan], "B": [4, 4, 6]}, index=idx)
    ev = [_evento(data=idx[1], ticker="A", destino="B", fator_cotas=2, caixa_por_cota=2)]
    r = simular(px, pd.Series(0, index=idx), {idx[0]: {"A": 1}}, custo_por_lado=0, eventos=ev)
    assert _perto(r.patrimonio.iloc[1], 1) and _perto(r.patrimonio.iloc[-1], 1.4)
    assert len(r.operacoes) == 1


def test_serie_encerrada_vira_caixa_no_terceiro_pregao():
    idx = pd.bdate_range("2020-01-01", periods=6)
    px = pd.DataFrame({"A": [10, 11, np.nan, np.nan, np.nan, np.nan]}, index=idx)
    r = simular(px, pd.Series(0.001, index=idx), {idx[0]: {"A": 1}}, custo_por_lado=0)
    liquidacoes = r.ocorrencias[r.ocorrencias.Tipo == "liquidacao_aproximada"]
    assert liquidacoes.Data.tolist() == [idx[4]]
    np.testing.assert_allclose(r.patrimonio, [1, 1.1, 1.1, 1.1, 1.1, 1.1 * 1.001], atol=1e-12)


def test_recebivel_nao_rende_selic_antes_do_pagamento():
    datas = pd.bdate_range("2025-12-19", periods=5)
    px = pd.DataFrame({"PN": [10, np.nan, np.nan, np.nan, np.nan],
                       "ON": [np.nan, 8, 8, 8, 8]}, index=datas)
    ev = [_evento(data=str(datas[1].date()), ticker="PN", destino="ON", fator_cotas=1,
                  caixa_por_cota=2, data_pagamento=str(datas[3].date()))]
    r = simular(px, pd.Series(0.01, index=datas), {datas[0]: {"PN": 1}}, custo_por_lado=0,
                eventos=ev)
    np.testing.assert_allclose(r.patrimonio, [1, 1, 1, 1, 1.002], atol=1e-12)
    assert r.operacoes.Ticker.tolist() == ["PN"]


def test_cadeia_cple_e_base_ajustada():
    datas = pd.bdate_range("2025-11-07", periods=4)
    px = pd.DataFrame({"CPLE6": [10, np.nan, np.nan, np.nan],
                       "CPLE5": [np.nan, 10, np.nan, np.nan],
                       "CPLE3": [np.nan, np.nan, 4, 4.5]}, index=datas)
    # A ON ajustada vale metade da cotação nominal: uma ON nominal equivale a duas cotas.
    ev = [_evento(data=str(datas[1].date()), ticker="CPLE6", destino="CPLE5", fator_cotas=1),
          _evento(data=str(datas[2].date()), ticker="CPLE5", destino="CPLE3", fator_cotas=2,
                  caixa_por_cota=2)]
    r = simular(px, pd.Series(0.0, index=datas), {datas[0]: {"CPLE6": 1}}, custo_por_lado=0,
                eventos=ev)
    np.testing.assert_allclose(r.patrimonio, [1, 1, 1, 1.1], atol=1e-12)
    assert len(r.ocorrencias.query("Tipo == 'evento_validado'")) == 2


def test_evento_fora_do_calendario_nao_e_ignorado():
    datas = pd.bdate_range("2025-01-03", periods=3)
    px = pd.DataFrame({"A": [10, 10, 10]}, index=datas)
    ev = [_evento(data="2025-01-04", ticker="A", caixa_por_cota=10)]
    _erro_esperado(ValueError, "fora do calendário", simular,
                   px, pd.Series(0.0, index=datas), {datas[0]: {"A": 1}}, eventos=ev)


def testar():
    """Roda os testes desta parte, na ordem em que aparecem, e mostra o resultado de cada um."""
    testes = [(nome, f) for nome, f in globals().items() if nome.startswith("test_")]
    falhas = 0
    for nome, teste in testes:
        try:
            teste()
            print("OK     ", nome)
        except Exception as erro:
            falhas += 1
            print("FALHOU ", nome, "—", erro)
    print(f"\n{len(testes) - falhas} de {len(testes)} testes aprovados.")
    if falhas:
        raise SystemExit(1)


if __name__ == "__main__":
    if "--testar" in sys.argv:
        testar()
    else:
        executar()
