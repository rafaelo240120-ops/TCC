# ==========================================================================================
# TCC: ESTRATÉGIAS DE FACTOR INVESTING NO UNIVERSO DO ISE B3 (2016 A 2025)
# Rafael Diniz Oliveira, Ciências Econômicas, Faculdade Ibmec de Brasília
# Orientador: Prof. Laerte Jun Takeuti
#
# O QUE ESTE CÓDIGO FAZ (seção 3 do TCC)
#   Simulação histórica (backtest) com rebalanceamento ANUAL. No último pregão de cada ano
#   (data do sinal), as ações do ISE B3 são ordenadas por quatro fatores. A carteira é comprada
#   no fechamento do primeiro pregão do ano seguinte e mantida, sem trocas, até o último pregão
#   desse ano. O desempenho é comparado com o IBrX-100 e com o índice ISE B3.
#
#   Fatores (Quadro 2 do TCC):
#     Momentum ............ retorno da ação no ano de formação (maior é melhor)
#     Baixa volatilidade .. oscilação dos retornos diários no ano de formação (menor é melhor)
#     Valor ............... P/VP positivo (menor é melhor)
#     Qualidade ........... ROIC (maior é melhor)
#
#   Carteiras (Quadro 3 do TCC), todas com o mesmo peso para cada ação na compra:
#     Momentum, Baixa_Vol, Valor, Qualidade .. as 10 ações mais bem colocadas em cada fator
#     Uniao .................................. junta as quatro listas de 10 (de 23 a 38 ações)
#     Multifator ............................. as 10 de maior nota média nos quatro fatores
#     Pesos_iguais_ISE ....................... todas as ações do ISE B3 que podiam ser escolhidas
#                                              (a "carteira ISE B3 em pesos iguais")
#
# COMO EXECUTAR
#   1. Instale as bibliotecas:  python -m pip install -r requirements.txt
#   2. Nesta pasta, rode:       python carteira_factor_investing.py
#   O estudo roda sem internet e sem token, porque todos os dados usados estão em dados/.
#   A tela mostra as Tabelas 1 a 9 do TCC; as tabelas, o Apêndice A, os números citados no
#   texto e os Gráficos 1 a 3 são gravados em resultados/.
#
# ONDE ESTÁ CADA PARTE DO TCC NESTE ARQUIVO
#   Parte 1   Configuração ............................... período, custo, token (3.2 e 3.5)
#   Parte 2   Dados ...................................... ações do ISE B3, preços, índices,
#                                                          Selic e P/VP e ROIC (3.1 e 3.2)
#   Parte 3   Fatores e carteiras ........................ Equações 1 a 7 (3.3 e 3.4)
#   Parte 4   Simulação .................................. compra, custos, eventos, caixa (3.5)
#   Parte 5   Medidas de desempenho ...................... Equações 8 a 10 (3.6)
#   Parte 6   Resultados ................................. Tabelas 1 a 6 (seção 4)
#   Parte 7   Discussão .................................. Tabelas 7 a 9 e Equação 11 (seção 5)
#   Parte 8   Gráficos ................................... Gráficos 1 a 3
#   Parte 9   Execução ................................... roda tudo e grava em resultados/
# ==========================================================================================

from __future__ import annotations

import hashlib
import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402


# %% PARTE 1 — CONFIGURAÇÃO
# ──────────────────────────────────────────────────────────────────────────────────────────
# Os parâmetros do estudo. No TCC: seções 3.2, 3.4 e 3.5.
# ──────────────────────────────────────────────────────────────────────────────────────────
ANO_INI, ANO_FIM = 2016, 2025              # período analisado (3.2)
TOP_N = 10                                 # ações por fator e na Multifator (3.4)
MIN_PREGOES = 150                          # pregões mínimos com preço no ano de formação (3.2)
CUSTO_POR_LADO = 0.002                     # 0,20% sobre cada compra e cada venda (3.5)
CUSTOS_SENSIBILIDADE = (0.0, 0.001, 0.002, 0.005)   # 0%, 0,10%, 0,20% e 0,50% (Tabela 6)

# ──────────────────────────────────────────────────────────────────────────────────────────
# TOKEN DO LABORATÓRIO DE FINANÇAS
# Cole o seu token entre as aspas abaixo. Ele NÃO é necessário para rodar o estudo: as
# consultas de P/VP, ROIC e setor feitas na API estão guardadas em dados/fundamentos, cada uma
# com a data da consulta e um código de verificação (SHA-256). O token só é usado para baixar
# essas consultas de novo, com ATUALIZAR_FUNDAMENTOS = True. Não divulgue o código com o token.
# ──────────────────────────────────────────────────────────────────────────────────────────
TOKEN_LAB_FINANCAS = ""
ATUALIZAR_FUNDAMENTOS = False              # True: baixa de novo as consultas da API

# Pastas: os dados ficam em dados/, ao lado deste arquivo; as saídas vão para resultados/.
RAIZ = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
DADOS = RAIZ / "dados"
FUNDAMENTOS = DADOS / "fundamentos"
RESULTADOS = RAIZ / "resultados"

# Nomes das carteiras e dos índices, como aparecem no TCC.
CARTEIRAS = ("Momentum", "Baixa_Vol", "Valor", "Qualidade", "Multifator", "Uniao", "Pesos_iguais_ISE")
NOMES = {
    "Multifator": "Multifator", "Valor": "Valor", "Baixa_Vol": "Baixa volatilidade",
    "Uniao": "União", "Momentum": "Momentum", "Qualidade": "Qualidade",
    "Pesos_iguais_ISE": "Carteira ISE B3 em pesos iguais",
    "IBrX_100": "IBrX-100", "Indice_ISE_B3": "Índice ISE B3",
}


class ErroDados(ValueError):
    """Inconsistência nos dados: a execução para antes de gravar qualquer resultado."""


# %% PARTE 2 — DADOS: AÇÕES DO ISE B3, PREÇOS, ÍNDICES, SELIC E FUNDAMENTOS
# ──────────────────────────────────────────────────────────────────────────────────────────
# Ações que podem ser escolhidas em cada ano: a última carteira do ISE B3 anunciada pela B3
# antes da montagem, sem as empresas que já tinham sido excluídas dela (TCC 3.2). A data ao
# lado de cada ano é quando a lista passou a ser conhecida; o código recusa usar uma lista
# anunciada depois da data do sinal. Fontes: portal histórico do ISE B3 e boletins diários
# da B3.
# ──────────────────────────────────────────────────────────────────────────────────────────
LISTAS_ISE = {
    # ano da carteira: (lista conhecida desde, ações)
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
    2021: ("2020-12-01", [  # 40 ações; ASAI3 fica de fora: só entrou no índice em 01/03/2021
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
# Compras de uma empresa por outra (SulAmérica, AES Brasil, BRF, Copel) não entram aqui: são
# eventos societários, tratados na simulação (Parte 4) com os documentos de dados/eventos.json.
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


def carregar_mercado():
    """Preços das ações, níveis do ISE B3 e do IBrX-100 e Selic anual (TCC 3.2).

    Preços: fechamento ajustado por proventos e desdobramentos, da API "preço corrigido" do
    Laboratório de Finanças, com o Yahoo Finance como fonte alternativa (dados/precos.csv).
    Índices: valores diários publicados pela B3
    (índices de retorno total). Selic: série 1178 do Banco Central (dados/indices_e_selic.csv).
    """
    bench = (pd.read_csv(DADOS / "indices_e_selic.csv", parse_dates=["data"])
             .set_index("data").sort_index())
    if bench.index.has_duplicates or bench.isna().any().any():
        raise ErroDados("Índices ou Selic com datas repetidas ou valores ausentes.")
    px = pd.read_csv(DADOS / "precos.csv", index_col=0, parse_dates=True).sort_index()
    if px.index.has_duplicates or px.columns.has_duplicates:
        raise ErroDados("Preços duplicados.")
    px = px.reindex(bench.index)
    if (px <= 0).any().any() or np.isinf(px.to_numpy()).any():
        raise ErroDados("Preços não positivos ou infinitos.")
    return px, bench


def carregar_token():
    """Token do Laboratório de Finanças (Parte 1) ou da variável de ambiente LAB_FINANCAS_TOKEN."""
    token = TOKEN_LAB_FINANCAS.strip() or os.environ.get("LAB_FINANCAS_TOKEN", "").strip()
    if not token:
        raise ValueError("Cole o token do Laboratório de Finanças em TOKEN_LAB_FINANCAS (Parte 1).")
    return token


def obter_fundamentos(bench, atualizar=False):
    """Garante uma consulta de P/VP, ROIC e setor (o "planilhão" da API) para cada data de sinal.

    A execução normal só lê as consultas guardadas em dados/fundamentos. Com atualizar=True,
    baixa de novo da API (exige o token) e grava a data da consulta e o SHA-256 da resposta.
    """
    for ano in range(ANO_INI, ANO_FIM + 1):
        sinal = f"{bench.index[bench.index.year == ano - 1].max():%Y-%m-%d}"
        caminho = FUNDAMENTOS / f"planilhao_{sinal}.json"
        if caminho.exists() and not atualizar:
            continue
        url = ("https://laboratoriodefinancas.com/api/v2/bolsa/planilhao?"
               + urllib.parse.urlencode({"data_base": sinal}))
        pedido = urllib.request.Request(url, headers={
            "Authorization": "Bearer " + carregar_token(), "User-Agent": "TCC-factor-investing/1.0"})
        with urllib.request.urlopen(pedido, timeout=60) as resposta:
            bruto = resposta.read()
        obj = json.loads(bruto)
        linhas = obj.get("results", obj.get("data", [])) if isinstance(obj, dict) else obj
        if not linhas:
            raise ValueError(f"Fundamentos vazios em {sinal}.")
        FUNDAMENTOS.mkdir(parents=True, exist_ok=True)
        caminho.write_bytes(bruto)
        caminho.with_suffix(".meta.json").write_text(json.dumps({
            "url": url, "data_base": sinal, "obtido_em": datetime.now(timezone.utc).isoformat(),
            "sha256": hashlib.sha256(bruto).hexdigest(), "linhas": len(linhas)}, indent=2),
            encoding="utf-8")
        print(f"Fundamentos de {sinal}: {len(linhas)} registros salvos.", flush=True)


def fundamentos(sinal):
    """P/VP, ROIC e setor da consulta de uma data de sinal (TCC 3.2 e 3.3).

    Confere o SHA-256 do arquivo e recusa qualquer indicador com data posterior ao sinal: nenhuma
    informação do futuro entra na escolha das ações.
    """
    caminho = FUNDAMENTOS / f"planilhao_{sinal:%Y-%m-%d}.json"
    if not caminho.exists():
        raise ErroDados(f"Falta a consulta {caminho.name}; use ATUALIZAR_FUNDAMENTOS = True.")
    meta = json.loads(caminho.with_suffix(".meta.json").read_text(encoding="utf-8"))
    if hashlib.sha256(caminho.read_bytes()).hexdigest() != meta.get("sha256"):
        raise ErroDados(f"A consulta {caminho.name} foi modificada depois de baixada.")
    obj = json.loads(caminho.read_bytes())
    linhas = obj.get("results", obj.get("data", [])) if isinstance(obj, dict) else obj
    df = pd.DataFrame(linhas).rename(columns={"ticker": "Ticker", "setor": "Setor"})
    if df.Ticker.duplicated().any():
        raise ErroDados("Fundamentos com códigos repetidos.")
    if (pd.to_datetime(df.data_base) > sinal).any():
        raise ErroDados("Fundamento com data posterior ao sinal.")
    for campo in ("p_vp", "roic"):
        df[campo] = pd.to_numeric(df[campo], errors="coerce")
    return df.set_index("Ticker")


# %% PARTE 3 — FATORES E CARTEIRAS, ANO A ANO
# ──────────────────────────────────────────────────────────────────────────────────────────
# Para cada ano: as três condições de entrada, os quatro fatores medidos na data do sinal e a
# escolha das ações de cada carteira. No TCC: seções 3.2 a 3.4, Equações 1 a 7.
# ──────────────────────────────────────────────────────────────────────────────────────────
def calendario(indice, ano):
    """Datas de um ano (TCC 3.5): o ano de formação vai de inicio_observacao a sinal (último
    pregão do ano anterior); a compra é no fechamento de execucao (primeiro pregão do ano)."""
    anterior = indice[indice.year == ano - 1]
    atual = indice[indice.year == ano]
    if len(anterior) < MIN_PREGOES or len(atual) < 2:
        raise ErroDados(f"Calendário incompleto para {ano}.")
    return {"sinal": anterior[-1], "execucao": atual[0],
            "inicio_observacao": anterior[0], "fim": atual[-1]}


def escolher_acoes(fatores):
    """Ações escolhidas por carteira (TCC 3.4). Empates são desfeitos pela ordem do código."""
    f = fatores.sort_values("Ticker").set_index("Ticker")

    def escolher(s, menor):
        return s.dropna().sort_values(ascending=menor, kind="stable").head(TOP_N).index.tolist()

    # Equação 6: nota de cada ação em cada fator pela sua posição, de 0 a 1 (o TCC mostra a
    # mesma nota multiplicada por 100), orientada para que a maior nota seja a melhor. Ações
    # empatadas recebem a posição média. No valor, só entram as ações com P/VP positivo.
    notas = pd.DataFrame({
        "Momentum": f.momentum.rank(pct=True),
        "Baixa_Vol": f.baixa_vol.rank(pct=True, ascending=False),
        "Valor": f.p_vp.where(f.p_vp > 0).rank(pct=True, ascending=False),
        "Qualidade": f.roic.rank(pct=True),
    })
    escolhidas = {
        "Momentum": escolher(f.momentum, False),
        "Baixa_Vol": escolher(f.baixa_vol, True),
        "Valor": escolher(f.p_vp.where(f.p_vp > 0), True),
        "Qualidade": escolher(f.roic, False),
        # Equação 7: nota final = média das quatro notas; só entram ações com os quatro fatores.
        "Multifator": escolher(notas.mean(axis=1, skipna=False), False),
    }
    # União: as quatro listas de 10 juntas; uma ação que está em mais de uma lista entra uma vez.
    escolhidas["Uniao"] = sorted(
        set().union(*(escolhidas[n] for n in ("Momentum", "Baixa_Vol", "Valor", "Qualidade"))))
    # Carteira ISE B3 em pesos iguais: todas as ações que podiam ser escolhidas no ano.
    escolhidas["Pesos_iguais_ISE"] = f.index.tolist()
    return escolhidas


def formar_carteiras(px, bench):
    """Forma as carteiras de todos os anos (TCC 3.2 a 3.4).

    Para cada ano: aplica as condições de entrada, registrando o motivo de cada exclusão; calcula
    os fatores na data do sinal; escolhe as ações e marca a compra, com pesos iguais, para a data
    de execução.
    """
    agendas, composicoes, fatores_salvos, exclusoes = {}, [], [], []
    for ano in range(ANO_INI, ANO_FIM + 1):
        cal = calendario(bench.index, ano)
        anunciada, lista = LISTAS_ISE[ano]
        if pd.Timestamp(anunciada) > cal["sinal"]:
            raise ErroDados(f"A lista do ISE B3 de {ano} foi anunciada depois do sinal.")
        fund = fundamentos(cal["sinal"])
        vistos, linhas = set(), []
        for t in lista:
            serie = RENOMEADOS.get(t, t)  # código sob o qual o histórico de preços está guardado
            # P/VP e ROIC da própria classe da ação, quando existem (nunca trocar CPLE6 por CPLE3).
            chave = t if t in fund.index else serie
            razao = None
            if serie in vistos:
                razao = "código repetido na lista"
            elif serie not in px:
                razao = "sem série de preços"
            elif chave not in fund.index:
                razao = "sem P/VP e ROIC na base"
            else:
                vistos.add(serie)
                p = px.loc[cal["inicio_observacao"]:cal["sinal"], serie]
                validos = p.dropna()
                if len(validos) < MIN_PREGOES:
                    razao = f"menos de {MIN_PREGOES} pregões com preço no ano de formação"
                elif pd.isna(p.iloc[-1]):  # não medir o sinal com um preço antigo
                    razao = "sem preço no último pregão do ano de formação"
            if razao:
                exclusoes.append({"Ano": ano, "Ticker": t, "Motivo": razao})
                continue
            dados = fund.loc[chave]
            linhas.append({
                "Ticker": serie, "Ticker_original": t, "Ticker_fundamento": chave,
                "Setor": dados.Setor,
                # Equação 2: momentum = retorno da ação no ano de formação.
                "momentum": validos.iloc[-1] / validos.iloc[0] - 1,
                # Equações 1 e 3: desvio-padrão dos retornos diários vezes a raiz de 252.
                "baixa_vol": p.pct_change(fill_method=None).std() * np.sqrt(252),
                # Equações 4 e 5: P/VP e ROIC calculados pela base do Laboratório de Finanças.
                "p_vp": dados.p_vp, "roic": dados.roic, "Observacoes": len(validos),
                "Data_sinal": cal["sinal"], "Data_execucao": cal["execucao"],
            })
        if not linhas:
            raise ErroDados(f"Nenhuma ação pôde ser escolhida em {ano}.")
        fatores = pd.DataFrame(linhas)
        setores = fatores.set_index("Ticker").Setor
        for carteira, tickers in escolher_acoes(fatores).items():
            if not tickers:
                raise ErroDados(f"Carteira vazia: {carteira} em {ano}.")
            # Pesos iguais, marcados para a data da compra (execução), e não para a do sinal.
            agendas.setdefault(carteira, {})[cal["execucao"]] = {t: 1 / len(tickers) for t in tickers}
            for ticker in tickers:
                composicoes.append({
                    "Carteira": carteira, "Ano": ano, "Ticker": ticker,
                    "Setor": setores[ticker] if pd.notna(setores[ticker]) else "Não informado",
                    "Peso": 1 / len(tickers),
                    "Data_sinal": cal["sinal"], "Data_execucao": cal["execucao"],
                })
        fatores_salvos.append(fatores.assign(Ano=ano))
    composicoes = pd.DataFrame(composicoes)
    if not np.allclose(composicoes.groupby(["Carteira", "Ano"]).Peso.sum(), 1, rtol=0, atol=1e-10):
        raise ErroDados("Os pesos de alguma carteira não somam 100%.")
    return agendas, composicoes, pd.concat(fatores_salvos, ignore_index=True), pd.DataFrame(exclusoes)


# %% PARTE 4 — SIMULAÇÃO: COMPRA, CUSTOS, EVENTOS SOCIETÁRIOS E CAIXA
# ──────────────────────────────────────────────────────────────────────────────────────────
# Compra no fechamento do primeiro pregão do ano, posição mantida até dezembro sem trocas, custo
# de 0,20% pago pela própria carteira em cada compra e cada venda, eventos societários
# documentados (dados/eventos.json) e caixa rendendo a Selic. No TCC: seção 3.5.
# ──────────────────────────────────────────────────────────────────────────────────────────
def periodo_simulacao(bench):
    """Pregões do estudo e Selic diária: (1 + taxa anual)^(1/252) − 1 (TCC 3.6)."""
    datas = bench.index[(bench.index.year >= ANO_INI) & (bench.index.year <= ANO_FIM)]
    selic = (1 + bench.loc[datas, "selic_aa"] / 100) ** (1 / 252) - 1
    selic.iloc[0] = 0  # o caixa só começa a render depois da primeira compra
    return datas, selic


def retornos_indices(bench, datas):
    """Retornos diários do IBrX-100 e do índice ISE B3 (Equação 1); zero no dia da primeira compra."""
    retornos = bench.loc[datas, ["ibrx100", "ise_b3"]].pct_change(fill_method=None)
    retornos.iloc[0] = 0
    return retornos.rename(columns={"ibrx100": "IBrX_100", "ise_b3": "Indice_ISE_B3"})


@dataclass
class ResultadoSimulacao:
    retornos: pd.Series
    patrimonio: pd.Series
    operacoes: pd.DataFrame
    rebalanceamentos: pd.DataFrame
    ocorrencias: pd.DataFrame


def executar_rebalanceamento(valores, caixa, pesos_alvo, custo_por_lado):
    """Refaz a carteira pagando o custo com o próprio patrimônio (TCC 3.5).

    Encontra o patrimônio final V que satisfaz V + custo × soma(|peso_alvo × V − valor_antes|) =
    patrimônio antes. O caixa não paga custo; se os pesos-alvo somam menos de 1, a diferença fica
    em caixa.
    """
    if not 0 <= custo_por_lado < 1:
        raise ValueError("Custo por lado inválido.")
    if caixa < -1e-10 or any(v < 0 for v in valores.values()):
        raise ValueError("A simulação só aceita posições compradas, sem alavancagem.")
    if any(w < 0 for w in pesos_alvo.values()) or sum(pesos_alvo.values()) > 1 + 1e-12:
        raise ValueError("Pesos-alvo inválidos.")
    tickers = sorted(set(valores) | set(pesos_alvo))
    antigo = np.array([valores.get(t, 0.0) for t in tickers])
    alvo = np.array([pesos_alvo.get(t, 0.0) for t in tickers])
    inicial = float(antigo.sum() + caixa)
    if inicial <= 0:
        raise ValueError("Patrimônio não positivo.")
    inferior, superior = 0.0, inicial   # resolvido por bisseção
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
    """Simula uma carteira dia a dia, do primeiro ao último pregão (TCC 3.5).

    agenda = {data_da_compra: {ticker: peso}}. Em cada pregão: o caixa rende a Selic, valores a
    receber de eventos são pagos, os eventos societários documentados são aplicados, as posições
    são valoradas e, nas datas da agenda, a carteira é refeita com custo. Uma ação que fica três
    pregões seguidos sem negócios depois do último preço, sem evento documentado, é vendida pelo
    último preço negociado, e o dinheiro fica em caixa.
    """
    if not precos.index.equals(selic.index) or precos.index.has_duplicates:
        raise ValueError("Calendários de preços e Selic incompatíveis.")
    if not precos.index.is_monotonic_increasing or selic.isna().any():
        raise ValueError("Calendário fora de ordem ou Selic ausente.")
    if not agenda or min(agenda) != precos.index[0] or not set(agenda).issubset(precos.index):
        raise ValueError("A agenda deve começar na primeira data da simulação.")
    por_data = {}
    for evento in eventos or []:
        if (not evento.get("validado") or not evento.get("fonte")
                or evento.get("base") != "mesma_dos_precos"):
            raise ValueError("Evento sem documento ou sem a mesma base de preços da simulação.")
        data_evento = pd.Timestamp(evento["data"])
        fatores_evento = [float(evento.get("fator_cotas", 0)), float(evento.get("caixa_por_cota", 0))]
        if pd.isna(data_evento) or not np.isfinite(fatores_evento).all() or min(fatores_evento) < 0:
            raise ValueError("Data ou valores inválidos no evento.")
        if precos.index[0] <= data_evento <= precos.index[-1] and data_evento not in precos.index:
            raise ValueError("Evento dentro do período, mas fora dos dias de negociação.")
        if any(e["ticker"] == evento["ticker"] for e in por_data.get(data_evento, [])):
            raise ValueError("Dois eventos para a mesma ação no mesmo dia.")
        por_data.setdefault(data_evento, []).append(evento)

    ultimos = {t: precos[t].last_valid_index() for t in precos}
    cotas, ultimos_precos = {}, {}
    recebiveis = {}  # dinheiro de eventos: entra no patrimônio, mas só rende depois do pagamento
    caixa = anterior = 1.0
    diarios, operacoes, rebals, ocorrencias = [], [], [], []
    for i, (data, linha) in enumerate(precos.iterrows()):
        if i:
            caixa *= 1 + float(selic.loc[data])  # o caixa rende a Selic do dia
        for chave, (pagamento, valor) in list(recebiveis.items()):
            if data >= pagamento:
                caixa += valor
                del recebiveis[chave]

        # Eventos societários documentados: a posição é trocada como a do acionista, sem venda.
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
                raise ValueError("Pagamento anterior à data do evento.")
            if dinheiro and pagamento > data:
                recebiveis[f"RECEBER_{ticker}_{data:%Y%m%d}"] = (pagamento, dinheiro)
            else:
                caixa += dinheiro
            if destino:
                cotas[destino] = cotas.get(destino, 0.0) + quantidade * float(ev["fator_cotas"])
                if pd.isna(linha.get(destino, np.nan)):
                    raise ValueError(f"{data.date()}: falta o preço da ação recebida {destino}.")
            ocorrencias.append({
                "Data": data, "Ticker": ticker, "Tipo": "evento_documentado", "Detalhe": ev["fonte"],
                "Valor_antes": valor_anterior, "Peso_fechamento_anterior": valor_anterior / anterior})

        # Valoração. Sem preço no dia, vale o último; no terceiro pregão sem negócio, vira caixa.
        for t in list(cotas):
            valor = linha.get(t, np.nan)
            if pd.notna(valor) and float(valor) > 0:
                ultimos_precos[t] = float(valor)
                continue
            if t not in ultimos_precos:
                raise ValueError(f"Não há preço para valorar {t} em {data.date()}.")
            ultimo = ultimos.get(t)
            if ultimo is not None and data > ultimo:
                atraso = int(((precos.index > ultimo) & (precos.index <= data)).sum())
                if atraso >= 3:
                    valor_vendido = cotas.pop(t) * ultimos_precos[t]
                    caixa += valor_vendido
                    ocorrencias.append({
                        "Data": data, "Ticker": t, "Tipo": "venda_pelo_ultimo_preco",
                        "Detalhe": "Três pregões sem negócios depois do último preço.",
                        "Valor_antes": valor_vendido,
                        "Peso_fechamento_anterior": valor_vendido / anterior})

        valores = {t: q * ultimos_precos[t] for t, q in cotas.items()}
        direitos = {t: v for t, (_, v) in recebiveis.items()}
        antes = sum(valores.values()) + caixa + sum(direitos.values())

        # Remontagem anual, nas datas da agenda.
        if data in agenda:
            if direitos:
                raise ValueError("Há valores a receber pendentes na data da remontagem.")
            alvos = dict(agenda[data])
            cancelados = []
            # Compra sem preço é cancelada e o dinheiro fica em caixa; não se escolhe outra ação
            # olhando dados do dia da compra.
            for t in list(alvos):
                if pd.isna(linha.get(t, np.nan)) or float(linha[t]) <= 0:
                    if t in cotas:
                        raise ValueError(f"{data.date()}: remontagem de {t} sem preço.")
                    cancelados.append(t)
                    alvos.pop(t)
            for t in cotas:
                if pd.isna(linha.get(t, np.nan)):
                    raise ValueError(f"{data.date()}: venda de {t} sem preço.")
            novos, caixa, ordens, custo = executar_rebalanceamento(valores, caixa, alvos, custo_por_lado)
            cotas = {t: v / float(linha[t]) for t, v in novos.items() if v > 1e-14}
            for t in cotas:
                ultimos_precos[t] = float(linha[t])
            compras = sum(max(v, 0) for v in ordens.values())
            vendas = sum(max(-v, 0) for v in ordens.values())
            rebals.append({
                "Data": data, "Ano": data.year, "Patrimonio_antes": antes,
                "Compras": compras, "Vendas": vendas,
                # Parte da carteira trocada = metade de compras mais vendas, sobre o patrimônio.
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
        anterior = total

    diario = pd.DataFrame(diarios).set_index("Data")
    colunas = ["Data", "Ticker", "Tipo", "Detalhe", "Valor_antes", "Peso_fechamento_anterior"]
    return ResultadoSimulacao(diario.Retorno, diario.Patrimonio, pd.DataFrame(operacoes),
                              pd.DataFrame(rebals), pd.DataFrame(ocorrencias, columns=colunas))


def simular_todas(precos, selic, agendas, eventos):
    """Simula as sete carteiras e junta os registros de remontagens e eventos."""
    retornos, rebals, ocorrencias = {}, [], []
    for carteira in CARTEIRAS:
        print(f"  {NOMES[carteira]}", flush=True)
        resultado = simular(precos, selic, agendas[carteira], eventos=eventos)
        retornos[carteira] = resultado.retornos
        rebals.append(resultado.rebalanceamentos.assign(Carteira=carteira))
        ocorrencias.append(resultado.ocorrencias.assign(Carteira=carteira))
    return (pd.DataFrame(retornos, index=precos.index), pd.concat(rebals, ignore_index=True),
            pd.concat(ocorrencias, ignore_index=True))


# %% PARTE 5 — MEDIDAS DE DESEMPENHO
# ──────────────────────────────────────────────────────────────────────────────────────────
# Retorno total, retorno anual (Equação 8), volatilidade (Equação 3), índice de Sharpe com a
# Selic (Equação 9) e maior queda acumulada (Equação 10). No TCC: seção 3.6.
# ──────────────────────────────────────────────────────────────────────────────────────────
def validar_retornos(retornos):
    """Recusa séries vazias, fora de ordem, com valores não finitos ou perdas de 100%."""
    if retornos.empty or not isinstance(retornos.index, pd.DatetimeIndex):
        raise ValueError("Série vazia ou sem datas.")
    if retornos.index.has_duplicates or not retornos.index.is_monotonic_increasing:
        raise ValueError("Datas repetidas ou fora de ordem.")
    valores = retornos.to_numpy(dtype=float)
    if not np.isfinite(valores).all() or (valores <= -1).any():
        raise ValueError("Retornos ausentes, não finitos ou menores ou iguais a −100%.")


def patrimonio(retornos):
    """Patrimônio acumulado a partir de um capital inicial igual a 1."""
    validar_retornos(retornos)
    return (1 + retornos).cumprod()


def queda_acumulada(retornos):
    """Equação 10: queda do patrimônio em relação ao maior valor anterior."""
    valores = patrimonio(retornos)
    # O capital antes da primeira compra é 1, inclusive quando há custo na primeira compra.
    return valores / valores.cummax().clip(lower=1) - 1


def retorno_anual(retornos):
    """Equação 8: retorno anual composto; A = dias corridos do período / 365,25."""
    anos = (retornos.index[-1] - retornos.index[0]).days / 365.25
    if anos <= 0:
        raise ValueError("O período precisa ter duração positiva.")
    return np.expm1(np.log1p(retornos).sum() / anos)


def metricas(retornos, selic):
    """As cinco medidas da Tabela 2 (TCC 3.6)."""
    validar_retornos(retornos)
    if not retornos.index.equals(selic.index):
        raise ValueError("Retornos e Selic precisam ter as mesmas datas.")
    validar_retornos(selic)
    excesso = retornos - selic
    desvio = excesso.std(ddof=1)
    return {
        "Retorno Total (%)": float(np.expm1(np.log1p(retornos).sum()) * 100),
        "Retorno Anual (%)": float(retorno_anual(retornos) * 100),                     # Eq. 8
        "Volatilidade (%)": float(retornos.std(ddof=1) * np.sqrt(252) * 100),          # Eq. 3
        "Sharpe": float(excesso.mean() / desvio * np.sqrt(252)) if desvio > 0 else np.nan,  # Eq. 9
        "Max Drawdown (%)": float(queda_acumulada(retornos).min() * 100),             # Eq. 10
    }


def retornos_anuais(retornos):
    """Retorno de cada ano civil, em % (Tabela 3)."""
    validar_retornos(retornos)
    anual = ((1 + retornos).groupby(retornos.index.year).prod() - 1) * 100
    anual.index.name = "Ano"
    return anual


def retorno_entre_fechamentos(retornos, inicio, fim):
    """Retorno acumulado do fechamento de `inicio` ao fechamento de `fim`."""
    if inicio not in retornos.index or fim not in retornos.index or inicio >= fim:
        raise ValueError("Datas inválidas para a janela de queda ou de recuperação.")
    janela = retornos.loc[(retornos.index > inicio) & (retornos.index <= fim)]
    validar_retornos(janela)
    return (1 + janela).prod() - 1


# %% PARTE 6 — RESULTADOS (SEÇÃO 4 DO TCC): TABELAS 1 A 6
# ──────────────────────────────────────────────────────────────────────────────────────────
def tabela_1_acoes_por_ano(composicoes):
    """Tabela 1: número de ações em cada ano."""
    contagem = composicoes.groupby(["Ano", "Carteira"]).Ticker.nunique().unstack()
    return pd.DataFrame({
        "Ações do ISE B3 que podiam ser escolhidas": contagem["Pesos_iguais_ISE"],
        "União": contagem["Uniao"],
        "Multifator": contagem["Multifator"],
        "Cada carteira de fator único": contagem[["Momentum", "Baixa_Vol", "Valor", "Qualidade"]].max(axis=1),
    })


def tabela_2_desempenho(diario):
    """Tabela 2: desempenho de 2016 a 2025, com a linha da Selic (risk-free)."""
    ordem = ["Multifator", "Valor", "Baixa_Vol", "Uniao", "Momentum", "Qualidade",
             "Pesos_iguais_ISE", "IBrX_100", "Indice_ISE_B3"]
    tabela = pd.DataFrame({NOMES[s]: metricas(diario[s], diario.Selic_dia) for s in ordem}).T
    # A Selic é medida com as mesmas fórmulas; volatilidade e Sharpe não se aplicam a ela.
    selic = diario.Selic_dia
    tabela.loc["Selic (risk-free)"] = [float(np.expm1(np.log1p(selic).sum()) * 100),
                                       float(retorno_anual(selic) * 100), np.nan, np.nan,
                                       float(queda_acumulada(selic).min() * 100)]
    tabela.columns = ["Retorno total (%)", "Retorno anual (%)", "Volatilidade (%)",
                      "Índice de Sharpe", "Maior queda acumulada (%)"]
    return tabela


def tabela_3_anuais(anual):
    """Tabela 3: retorno de cada ano e quantos anos cada série ficou acima do IBrX-100."""
    ordem = ["Multifator", "Uniao", "Baixa_Vol", "Pesos_iguais_ISE", "IBrX_100", "Indice_ISE_B3"]
    tabela = anual[ordem].rename(columns=NOMES).astype(object)
    acima = {NOMES[s]: int((anual[s] > anual.IBrX_100).sum()) for s in ordem if s != "IBrX_100"}
    tabela.loc["Anos acima do IBrX-100"] = [acima.get(NOMES[s], "–") for s in ordem]
    return tabela


def periodos_de_queda(diario):
    """Quedas de 15% ou mais do IBrX-100, do pico ao fundo seguinte, e as recuperações até a volta
    ao pico anterior (TCC 3.6). Todas as séries são medidas nas datas do IBrX-100."""
    p = patrimonio(diario.IBrX_100)
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
                           ("recuperacao" if recuperado else "apos_fundo_sem_recuperacao", fundo, fim)]:
            if a >= b:
                continue
            retorno = retorno_entre_fechamentos(diario.drop(columns="Selic_dia"), a, b) * 100
            for serie, valor in retorno.items():
                linhas.append({"Pico": inicio, "Fundo": fundo, "Fim": fim, "Recuperado": recuperado,
                               "Fase": fase, "Pregoes": int(((diario.index > a) & (diario.index <= b)).sum()),
                               "Serie": serie, "Retorno_pct": valor})
    return pd.DataFrame(linhas)


def tabela_4_quedas(quedas):
    """Tabela 4: ganho ou perda nas três grandes quedas do IBrX-100 e nas recuperações seguintes."""
    ordem = ["Multifator", "Uniao", "Baixa_Vol", "Pesos_iguais_ISE", "IBrX_100", "Indice_ISE_B3"]

    def periodo(inicio, fim):
        return str(inicio.year) if inicio.year == fim.year else f"{inicio.year} a {fim.year}"

    tabela, colunas = {}, []
    for pico, grupo in quedas.groupby("Pico"):
        fundo, fim = grupo.Fundo.iloc[0], grupo.Fim.iloc[0]
        for fase, rotulo in (("queda", f"Queda {periodo(pico, fundo)}"),
                             ("recuperacao", f"Recuperação {periodo(fundo, fim)}")):
            colunas.append(rotulo)
            tabela[rotulo] = grupo[grupo.Fase == fase].set_index("Serie").Retorno_pct
    return pd.DataFrame(tabela).loc[ordem, colunas].rename(index=NOMES)


def setores_medios(composicoes):
    """Peso médio de cada setor por carteira; setor ausente num ano conta como zero (Tabela 5)."""
    chaves = ["Carteira", "Ano", "Setor"]
    setores = sorted(composicoes.Setor.unique())
    grupos = composicoes[["Carteira", "Ano"]].drop_duplicates()
    grade = grupos.merge(pd.DataFrame({"Setor": setores}), how="cross")
    pesos = composicoes.groupby(chaves, dropna=False).Peso.sum().reset_index()
    completa = grade.merge(pesos, on=chaves, how="left").fillna({"Peso": 0})
    return completa.groupby(["Carteira", "Setor"]).Peso.mean().reset_index()


def tabela_5_setores(setores):
    """Tabela 5: participação média dos três maiores setores da Multifator nas carteiras."""
    tabela = (setores.pivot(index="Setor", columns="Carteira", values="Peso").fillna(0) * 100)
    tabela = tabela[["Multifator", "Uniao", "Pesos_iguais_ISE"]].sort_values("Multifator", ascending=False)
    tres = tabela.head(3).rename(index=str.capitalize)
    tres.loc["Total dos três setores"] = tres.sum()
    tres.loc["Demais setores"] = 100 - tres.loc["Total dos três setores"]
    return tres.rename(columns=NOMES)


def tabela_6_custos(precos, selic, agendas, eventos, diario):
    """Tabela 6: retorno anual com custos de 0%, 0,10%, 0,20% e 0,50% por compra e por venda."""
    ordem = ["Multifator", "Valor", "Baixa_Vol", "Uniao", "Momentum", "Qualidade", "Pesos_iguais_ISE"]
    tabela = {}
    for carteira in ordem:
        linha = {}
        for custo in CUSTOS_SENSIBILIDADE:
            retornos = (diario[carteira] if custo == CUSTO_POR_LADO else
                        simular(precos, selic, agendas[carteira], custo_por_lado=custo,
                                eventos=eventos).retornos)
            rotulo = "Sem custo" if custo == 0 else f"Custo de {custo * 100:.2f}%".replace(".", ",")
            linha[rotulo] = metricas(retornos, selic)["Retorno Anual (%)"]
        tabela[NOMES[carteira]] = linha
    return pd.DataFrame(tabela).T


# %% PARTE 7 — DISCUSSÃO (SEÇÃO 5 DO TCC): TABELAS 7 A 9 E EQUAÇÃO 11
# ──────────────────────────────────────────────────────────────────────────────────────────
# As Tabelas 7 a 9 são feitas com os valores das Tabelas 2 e 4 já arredondados, como aparecem no
# TCC, para que o leitor chegue ao mesmo número fazendo a conta pela tabela.
# ──────────────────────────────────────────────────────────────────────────────────────────
def tabela_7_passos(tab2):
    """Tabela 7: vantagem da Multifator sobre o IBrX-100 em dois passos (retorno anual)."""
    r = tab2["Retorno anual (%)"].round(2)
    ibrx, ew, multi = r["IBrX-100"], r["Carteira ISE B3 em pesos iguais"], r["Multifator"]
    return pd.DataFrame({
        "Carteira": ["IBrX-100", "Carteira ISE B3 em pesos iguais", "Multifator", ""],
        "Retorno anual (%)": [ibrx, ew, multi, np.nan],
        "Ganho no passo (p.p.)": [np.nan, ew - ibrx, multi - ew, multi - ibrx],
    }, index=["Ponto de partida", "1. Ficar só com empresas sustentáveis", "2. Escolher pelos fatores",
              "Vantagem total da Multifator"])


def tabela_8_quedas_passos(tab2):
    """Tabela 8: maior queda acumulada em dois passos, do IBrX-100 à Multifator."""
    q = tab2["Maior queda acumulada (%)"].round(2)
    ibrx, ew, multi = q["IBrX-100"], q["Carteira ISE B3 em pesos iguais"], q["Multifator"]
    return pd.DataFrame({
        "Carteira": ["IBrX-100", "Carteira ISE B3 em pesos iguais", "Multifator", ""],
        "Maior queda acumulada (%)": [ibrx, ew, multi, np.nan],
        "Redução no passo (p.p.)": [np.nan, ew - ibrx, multi - ew, multi - ibrx],
    }, index=["Ponto de partida", "1. Ficar só com empresas sustentáveis", "2. Escolher pelos fatores",
              "Redução total da Multifator"])


def ciclos_completos(quedas):
    """Equação 11: resultado do ciclo completo de cada queda, (1 + queda) × (1 + recuperação) − 1,
    com os valores da Tabela 4 arredondados a duas casas. Inclui todas as carteiras."""
    linhas = {}
    for pico, grupo in quedas.groupby("Pico"):
        fim = grupo.Fim.iloc[0]
        rotulo = f"Ciclo de {pico.year}" if fim.year == pico.year else f"Ciclo de {pico.year} a {fim.year}"
        for serie, fases in grupo.groupby("Serie"):
            taxa = fases.set_index("Fase").Retorno_pct.round(2) / 100
            linhas.setdefault(serie, {})[rotulo] = ((1 + taxa["queda"]) * (1 + taxa.drop("queda").iloc[0]) - 1) * 100
    return pd.DataFrame(linhas).T


def tabela_9_ciclos(ciclos):
    """Tabela 9: ganho ou perda no ciclo completo de cada grande queda do IBrX-100."""
    ordem = ["Multifator", "Uniao", "Baixa_Vol", "Pesos_iguais_ISE", "IBrX_100", "Indice_ISE_B3"]
    return ciclos.loc[ordem].rename(index=NOMES)


def notas_por_setor(fatores, composicoes):
    """Notas das Equações 6 e 7 (de 0 a 100) de todas as ações com os quatro fatores, para comparar
    as empresas de energia com as demais (TCC 5.5). As dez maiores notas de cada ano precisam ser
    exatamente as ações da Multifator."""
    notas = []
    validas = fatores[fatores.p_vp > 0].dropna(subset=["momentum", "baixa_vol", "p_vp", "roic"])
    for ano, grupo in validas.groupby("Ano"):
        grupo = grupo.copy()
        grupo["mom"] = grupo.momentum.rank(pct=True) * 100
        grupo["vol"] = (-grupo.baixa_vol).rank(pct=True) * 100
        grupo["val"] = (-grupo.p_vp).rank(pct=True) * 100
        grupo["qual"] = grupo.roic.rank(pct=True) * 100
        grupo["final"] = grupo[["mom", "vol", "val", "qual"]].mean(axis=1)
        multifator = set(composicoes[(composicoes.Carteira == "Multifator") & (composicoes.Ano == ano)].Ticker)
        if set(grupo.nlargest(TOP_N, "final").Ticker) != multifator:
            raise ErroDados(f"As notas refeitas não reproduzem a Multifator de {ano}.")
        notas.append(grupo)
    notas = pd.concat(notas)
    energia = notas.Setor.str.startswith("energia")
    return pd.DataFrame({"Energia": notas.loc[energia, ["mom", "vol", "val", "qual", "final"]].mean(),
                         "Demais setores": notas.loc[~energia, ["mom", "vol", "val", "qual", "final"]].mean()})


# ──────────────────────────────────────────────────────────────────────────────────────────
# NÚMEROS CITADOS NO TEXTO QUE NÃO ESTÃO NAS TABELAS, na formatação do TCC
# ──────────────────────────────────────────────────────────────────────────────────────────
def num(valor, casas=2):
    """Número no formato do TCC: vírgula decimal e sinal de menos tipográfico."""
    texto = f"{abs(valor):,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("−" + texto) if round(valor, casas) < 0 else texto


def pct(valor, casas=2):
    return num(valor, casas) + "%"


def numeros_do_texto(diario, anual, tab2, quedas, ciclos, composicoes, fatores, exclusoes, rebals, setores):
    """Os números citados no texto do TCC que não aparecem nas tabelas, com a seção onde estão."""
    N = []

    def anotar(secao, descricao, valor):
        N.append({"Secao": secao, "Descricao": descricao, "Valor": valor})

    ise = composicoes[composicoes.Carteira == "Pesos_iguais_ISE"].groupby("Ano").Ticker.nunique()
    uniao = composicoes[composicoes.Carteira == "Uniao"].groupby("Ano").Ticker.nunique()
    anotar("3.2", "Primeiro e último pregão do período", f"{diario.index[0]:%d/%m/%Y} a {diario.index[-1]:%d/%m/%Y}")
    anotar("3.2", "Número de pregões", num(len(diario), 0))
    anotar("3.2", "Exclusões pelas três condições de entrada (casos)", str(len(exclusoes)))
    anotar("3.2", "Ações diferentes excluídas", str(exclusoes.Ticker.nunique()))
    anotar("3.4", "Ações da carteira ISE B3 em pesos iguais (mínimo e máximo)", f"{ise.min()} e {ise.max()}")
    anotar("3.4", "Ações da União (mínimo e máximo)", f"{uniao.min()} e {uniao.max()}")

    total = tab2["Retorno total (%)"]
    for nome in ("Multifator", "IBrX-100", "Índice ISE B3"):
        anotar("4.2 e 6", f"R$ 100 aplicados em 2016 viraram (R$): {nome}", str(int(round(100 + total[nome]))))
    anotar("4.3", "Anos em que a Multifator rendeu menos que o IBrX-100",
           " e ".join(str(a) for a in anual.index[anual.Multifator <= anual.IBrX_100]))
    anotar("4.3", "Anos em que o índice ISE B3 rendeu mais que o IBrX-100",
           " e ".join(str(a) for a in anual.index[anual.Indice_ISE_B3 > anual.IBrX_100]))
    diferenca = anual.Pesos_iguais_ISE.round(1) - anual.Indice_ISE_B3.round(1)  # como na Tabela 3
    anotar("4.6", "Anos em que a carteira ISE B3 em pesos iguais rendeu mais que o índice ISE B3",
           str(int((diferenca > 0).sum())))
    anotar("4.6", "Diferença média por ano, pesos iguais menos índice, 2016 a 2021 (p.p.)",
           num(diferenca.loc[2016:2021].mean(), 1))
    anotar("4.6", "Diferença média por ano, pesos iguais menos índice, 2022 a 2025 (p.p.)",
           num(diferenca.loc[2022:2025].mean(), 1))
    anotar("5.2", "Diferença em 2016 (p.p.)", num(diferenca.loc[2016], 1))
    anotar("5.2", "Diferença média de 2017 a 2021 (p.p.)", num(diferenca.loc[2017:2021].mean(), 1))

    # Exemplo da crise de 2020 (4.4): R$ 100 aplicados em 2016, nas datas do pico e do fundo.
    meses = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
             "setembro", "outubro", "novembro", "dezembro"]
    p100 = np.exp(np.log1p(diario[["IBrX_100", "Multifator"]]).cumsum()) * 100
    crise = quedas[quedas.Pico.dt.year == 2020].iloc[0]
    for campo in ("Pico", "Fundo"):
        data = crise[campo]
        anotar("4.4", f"Crise de 2020, {campo.lower()} do IBrX-100", f"{data.day} de {meses[data.month - 1]}")
        for serie in ("IBrX_100", "Multifator"):
            anotar("4.4", f"Crise de 2020, valor no {campo.lower()} (R$): {NOMES[serie]}",
                   num(p100.loc[data, serie], 2))

    neg = anual.index[anual.IBrX_100 < 0].tolist()
    anotar("5.3", "Anos em que o IBrX-100 fechou no negativo", " e ".join(str(a) for a in neg))
    acima = [NOMES.get(s, s) for s in ciclos.index if s != "IBrX_100"
             and all(ciclos.loc[s, a] > ciclos.loc["IBrX_100", a] for a in ciclos.columns)]
    anotar("5.3 e 6", "Únicas séries à frente do IBrX-100 nos três ciclos (entre todas as carteiras e o índice ISE B3)",
           ", ".join(acima))
    mom = anual.Momentum > anual.IBrX_100
    anotar("5.4", "Anos em que o momentum rendeu mais que o IBrX-100, 2016 a 2021", str(int(mom.loc[2016:2021].sum())))
    anotar("5.4", "Anos em que o momentum rendeu mais que o IBrX-100, 2022 a 2025", str(int(mom.loc[2022:2025].sum())))

    escolhidas = composicoes.merge(fatores[["Ano", "Ticker", "baixa_vol"]], on=["Ano", "Ticker"], how="left")
    for carteira in ("Multifator", "Uniao"):
        anotar("5.4", f"Volatilidade média, no ano de formação, das ações escolhidas: {NOMES[carteira]}",
               pct(escolhidas[escolhidas.Carteira == carteira].baixa_vol.mean() * 100, 1))
    remontagens = rebals[rebals.Ano > rebals.Ano.min()]  # a compra de 2016 não é troca de ações
    for carteira in ("Multifator", "Momentum"):
        r = remontagens[remontagens.Carteira == carteira]
        anotar("5.4", f"Parte da carteira trocada por remontagem: {NOMES[carteira]}", pct(r.Turnover.mean() * 100, 1))
        anotar("5.4", f"Custo pago por ano, em % do patrimônio: {NOMES[carteira]}", pct(r.Custo_bps.mean() / 100))

    energia = setores[setores.Setor.str.startswith("energia")].groupby("Carteira").Peso.sum() * 100
    for carteira in ("Valor", "Baixa_Vol", "Momentum", "Qualidade", "Pesos_iguais_ISE"):
        anotar("5.5", f"Peso médio do setor de energia: {NOMES[carteira]}", pct(energia[carteira], 1))
    notas = notas_por_setor(fatores, composicoes)
    for nota, rotulo in (("final", "nota final"), ("val", "nota de valor"), ("vol", "nota de volatilidade")):
        for grupo in ("Energia", "Demais setores"):
            anotar("5.5", f"Média da {rotulo}, de 0 a 100: {grupo}", num(notas.loc[nota, grupo], 1))
    return pd.DataFrame(N)


def apendice_a(composicoes, fatores):
    """Apêndice A: ações de cada carteira de fatores, ano a ano, com o código da época."""
    codigo_da_epoca = fatores.set_index(["Ano", "Ticker"]).Ticker_original
    linhas = []
    for carteira in ("Multifator", "Uniao", "Valor", "Baixa_Vol", "Momentum", "Qualidade"):
        for ano, grupo in composicoes[composicoes.Carteira == carteira].groupby("Ano"):
            codigos = sorted(codigo_da_epoca[ano, t] for t in grupo.Ticker)
            linhas.append({"Carteira": NOMES[carteira], "Ano": ano, "Ações": len(codigos),
                           "Códigos de negociação": ", ".join(codigos)})
    return pd.DataFrame(linhas)


# %% PARTE 8 — GRÁFICOS 1 A 3
# ──────────────────────────────────────────────────────────────────────────────────────────
# Cores da paleta de Okabe e Ito, legível para daltônicos, e um traço próprio para cada série.
# Sem título na figura: a legenda fica no documento.
# ──────────────────────────────────────────────────────────────────────────────────────────
CM = 1 / 2.54
LARGURA = 16 * CM
CORES = {"Uniao": ("#0072B2", "-"), "Multifator": ("#009E73", "--"),
         "Pesos_iguais_ISE": ("#CC79A7", "-"), "IBrX_100": ("#3A3A3A", "-"),
         "Indice_ISE_B3": ("#D55E00", (0, (5, 1.5)))}


def numero_br(valor, casas=0):
    return f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def desenhar(ax, dados, rotulos):
    for nome, rotulo in rotulos.items():
        cor, traco = CORES[nome]
        ax.plot(dados.index, dados[nome], color=cor, linestyle=traco, linewidth=1.4, label=rotulo,
                solid_capstyle="round")
    ax.grid(axis="y")
    ax.set_axisbelow(True)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda valor, _: numero_br(valor)))


def rotular_fim(ax, dados, series):
    """Escreve o valor final de cada série na ponta da linha, sem sobrepor os números."""
    inferior, superior = ax.get_ylim()
    folga, anterior = (superior - inferior) * 0.055, None
    for valor, nome in sorted(((dados[n].iloc[-1], n) for n in series), reverse=True):
        alvo = valor if anterior is None else min(valor, anterior - folga)
        anterior = alvo
        ax.annotate(numero_br(valor), xy=(dados.index[-1], alvo), xytext=(5, 0), textcoords="offset points",
                    va="center", fontsize=8, color=CORES[nome][0], annotation_clip=False)


def gerar_graficos(diario, pasta):
    pasta.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({
        "font.family": "serif", "font.serif": ["Times New Roman", "DejaVu Serif"],
        "font.size": 9, "axes.titlesize": 9, "axes.labelsize": 9, "legend.fontsize": 8.5,
        "xtick.labelsize": 8.5, "ytick.labelsize": 8.5,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.edgecolor": "#5A5A5A", "axes.linewidth": 0.6,
        "grid.color": "#B7B7B7", "grid.linewidth": 0.4, "grid.alpha": 0.6,
        "figure.dpi": 300, "savefig.dpi": 300, "savefig.bbox": "tight", "savefig.pad_inches": 0.02,
    })

    # Gráfico 1: evolução de R$ 100 investidos no início de 2016.
    rotulos = {"Uniao": "União (ISE B3)", "Multifator": "Multifator (ISE B3)",
               "IBrX_100": "IBrX-100", "Indice_ISE_B3": "ISE B3"}
    dados = patrimonio(diario[list(rotulos)]) * 100
    fig, ax = plt.subplots(figsize=(LARGURA, 8.4 * CM))
    desenhar(ax, dados, rotulos)
    rotular_fim(ax, dados, list(rotulos))
    ax.set_ylabel("Capital inicial = 100")
    ax.set_xlim(dados.index[0], dados.index[-1] + pd.Timedelta(days=210))
    ax.legend(loc="upper left", frameon=False, ncol=2)
    fig.savefig(pasta / "grafico_1_patrimonio.png")
    plt.close(fig)

    # Gráfico 2: queda acumulada em relação ao maior valor anterior (Equação 10).
    rotulos = {"Uniao": "União (ISE B3)", "Multifator": "Multifator (ISE B3)",
               "IBrX_100": "IBrX-100", "Indice_ISE_B3": "Índice ISE B3"}
    valores = np.exp(np.log1p(diario[list(rotulos)]).cumsum())
    dados = (valores / valores.cummax().clip(lower=1) - 1) * 100
    fig, ax = plt.subplots(figsize=(LARGURA, 7.6 * CM))
    desenhar(ax, dados, rotulos)
    ax.set_ylabel("Queda acumulada (%)")
    ax.set_xlim(dados.index[0], dados.index[-1])
    ax.legend(loc="lower right", frameon=False, ncol=2)
    fig.savefig(pasta / "grafico_2_quedas.png")
    plt.close(fig)

    # Gráfico 3: índice ISE B3, carteira ISE B3 em pesos iguais e IBrX-100 (R$ 100 em 2016).
    rotulos = {"Pesos_iguais_ISE": "Carteira ISE B3 em pesos iguais", "IBrX_100": "IBrX-100",
               "Indice_ISE_B3": "Índice ISE B3"}
    dados = np.exp(np.log1p(diario[list(rotulos)]).cumsum()) * 100
    fig, ax = plt.subplots(figsize=(LARGURA, 8.4 * CM))
    desenhar(ax, dados, rotulos)
    rotular_fim(ax, dados, list(rotulos))
    ax.set_ylabel("Capital inicial = 100")
    ax.set_xlim(dados.index[0], dados.index[-1] + pd.Timedelta(days=210))
    ax.legend(loc="upper left", frameon=False)
    fig.savefig(pasta / "grafico_3_pesos_iguais.png")
    plt.close(fig)


# %% PARTE 9 — EXECUÇÃO
# ──────────────────────────────────────────────────────────────────────────────────────────
# Roda as Partes 2 a 8 na ordem, mostra as tabelas do TCC na tela e grava tudo em resultados/.
# ──────────────────────────────────────────────────────────────────────────────────────────
def mostrar(titulo, tabela, casas=2):
    with pd.option_context("display.width", 160, "display.max_columns", None,
                           "display.float_format", lambda v: f"{v:,.{casas}f}"):
        print(f"\n{titulo}\n{tabela.to_string()}")


def salvar_tabela(tabela, nome, casas=2, **opcoes):
    """Grava no formato do Excel em português (ponto e vírgula entre colunas e vírgula decimal),
    com as casas decimais do TCC."""
    def formatar(v):
        if isinstance(v, float):
            return "" if np.isnan(v) else f"{v:.{casas}f}".replace(".", ",")
        return v
    tabela.map(formatar).to_csv(RESULTADOS / f"{nome}.csv", sep=";", encoding="utf-8-sig", **opcoes)


def executar():
    print("Parte 2 — Dados", flush=True)
    px, bench = carregar_mercado()
    obter_fundamentos(bench, ATUALIZAR_FUNDAMENTOS)
    eventos = json.loads((DADOS / "eventos.json").read_text(encoding="utf-8"))

    print("Parte 3 — Fatores e carteiras", flush=True)
    agendas, composicoes, fatores, exclusoes = formar_carteiras(px, bench)

    print("Parte 4 — Simulação diária das sete carteiras", flush=True)
    datas, selic = periodo_simulacao(bench)
    precos = px.reindex(datas)
    diario, rebals, ocorrencias = simular_todas(precos, selic, agendas, eventos)
    diario = diario.join(retornos_indices(bench, datas))
    diario["Selic_dia"] = selic
    diario.index.name = "data"

    print("Partes 5 a 7 — Desempenho, Resultados e Discussão", flush=True)
    anual = retornos_anuais(diario.drop(columns="Selic_dia"))
    quedas = periodos_de_queda(diario)
    setores = setores_medios(composicoes)
    ciclos = ciclos_completos(quedas)
    tabelas = {
        "tabela_1_acoes_por_ano": tabela_1_acoes_por_ano(composicoes),
        "tabela_2_desempenho": tabela_2_desempenho(diario),
        "tabela_3_retorno_de_cada_ano": tabela_3_anuais(anual),
        "tabela_4_quedas_e_recuperacoes": tabela_4_quedas(quedas),
        "tabela_5_setores": tabela_5_setores(setores),
        "tabela_6_custos": tabela_6_custos(precos, selic, agendas, eventos, diario),
    }
    tabelas["tabela_7_vantagem_em_dois_passos"] = tabela_7_passos(tabelas["tabela_2_desempenho"])
    tabelas["tabela_8_queda_em_dois_passos"] = tabela_8_quedas_passos(tabelas["tabela_2_desempenho"])
    tabelas["tabela_9_ciclos_completos"] = tabela_9_ciclos(ciclos)
    numeros = numeros_do_texto(diario, anual, tabelas["tabela_2_desempenho"], quedas, ciclos,
                               composicoes, fatores, exclusoes, rebals, setores)

    print("Parte 8 — Gráficos e gravação", flush=True)
    RESULTADOS.mkdir(exist_ok=True)
    gerar_graficos(diario, RESULTADOS / "figuras")
    casas = {"tabela_3_retorno_de_cada_ano": 1, "tabela_5_setores": 1, "tabela_9_ciclos_completos": 1}
    for nome, tabela in tabelas.items():
        salvar_tabela(tabela, nome, casas.get(nome, 2))
    salvar_tabela(apendice_a(composicoes, fatores), "apendice_A_acoes_de_cada_carteira", index=False)
    salvar_tabela(numeros, "numeros_citados_no_texto", index=False)

    # Dados completos, sem arredondamento, para quem quiser refazer qualquer conta.
    detalhes = RESULTADOS / "detalhes"
    detalhes.mkdir(exist_ok=True)
    diario.to_csv(detalhes / "retornos_diarios.csv")
    pd.DataFrame([{"Serie": s, **metricas(diario[s], diario.Selic_dia)}
                  for s in diario if s != "Selic_dia"]).to_csv(detalhes / "desempenho.csv", index=False)
    anual.to_csv(detalhes / "retornos_anuais.csv")
    fatores.to_csv(detalhes / "fatores_no_ano_de_formacao.csv", index=False)
    composicoes.to_csv(detalhes / "composicoes.csv", index=False)
    exclusoes.to_csv(detalhes / "exclusoes.csv", index=False)
    rebals.to_csv(detalhes / "remontagens_e_custos.csv", index=False)
    ocorrencias[ocorrencias.Tipo != "preco_ausente"].drop(columns="Detalhe").to_csv(
        detalhes / "eventos_e_vendas_pelo_ultimo_preco.csv", index=False)
    quedas.to_csv(detalhes / "quedas_e_recuperacoes.csv", index=False)
    setores.to_csv(detalhes / "setores_medios.csv", index=False)

    # Tabelas do TCC na tela.
    for nome, tabela in tabelas.items():
        mostrar(nome.replace("_", " ").upper(), tabela, casas.get(nome, 2))
    with pd.option_context("display.width", 200, "display.max_colwidth", 120):
        print("\nNÚMEROS CITADOS NO TEXTO\n" + numeros.to_string(index=False))
    print(f"\nResultados gravados em {RESULTADOS}")


if __name__ == "__main__":
    executar()
