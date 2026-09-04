# ==============================================================
# TCC — Testes estatísticos das hipóteses
# Plano de trabalho, seção 3 ("Rever os testes e as hipóteses")
#
# O plano dá uma alternativa em cada ponto: ou se retira a
# afirmação, ou se faz o teste. Este script faz os testes, para
# que as afirmações possam ficar no texto — com o resultado que
# elas de fato tiverem.
#
# [3.1] "estatisticamente significativa"
#       -> teste de diferença de índice de Sharpe, em duas versões:
#          Memmel (2003), correção analítica do Jobson-Korkie, e
#          Ledoit & Wolf (2008), com erro-padrão HAC pelo método
#          delta e bootstrap de blocos circulares estudentizado.
#          São exatamente os dois testes que a seção de limitações
#          do TCC já cita pelo nome.
#
# [3.2] "não inferioridade"
#       -> um teste de não inferioridade é unilateral e exige uma
#          margem delta declarada. Reporta-se o intervalo de
#          confiança da diferença de Sharpe e a maior margem que os
#          dados sustentam, para que a afirmação seja feita (ou
#          abandonada) com base em número, não em comparação de
#          ponto.
#
# [3.3] "prêmio ESG residual"
#       -> alfa por regressão, com os fatores brasileiros do NEFIN
#          (Rm-Rf, SMB, HML, WML, IML), erros-padrão de
#          Newey-West. Se o alfa não for distinguível de zero, o
#          termo "prêmio" não se sustenta e deve virar "retorno
#          relativo da carteira".
#
# Taxa livre de risco: a Selic do próprio trabalho nos testes de
# Sharpe (para bater com o resto do TCC) e a Risk_Free do NEFIN nas
# regressões de fator (para bater com a construção dos fatores).
# ==============================================================

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import statsmodels.api as sm
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))

RAIZ      = Path(__file__).resolve().parents[1]
DIR_DADOS = RAIZ / "data"

URL_NEFIN  = "https://nefin.com.br/resources/risk_factors/nefin_factors.csv"
ARQ_NEFIN  = DIR_DADOS / "nefin_fatores.csv"

N_BOOT   = 4999    # replicações do bootstrap
BLOCO    = 5       # tamanho do bloco circular (uma semana de pregões)
SEMENTE  = 20260902


def defasagem_nw(n: int) -> int:
    """Regra usual de Newey-West: floor(4 * (T/100)^(2/9))."""
    return int(np.floor(4 * (n / 100) ** (2 / 9)))


# ──────────────────────────────────────────────────────────────
# [3.1] DIFERENÇA DE ÍNDICE DE SHARPE
# ──────────────────────────────────────────────────────────────
def sharpe(r: np.ndarray) -> float:
    return float(r.mean() / r.std(ddof=1))


def teste_memmel(r1: np.ndarray, r2: np.ndarray) -> dict:
    """Jobson-Korkie com a correção de Memmel (2003).

    Analítico e fechado, mas supõe retornos i.i.d. — o que retornos
    diários de ações não são. Serve como referência; o resultado
    que vale é o de Ledoit-Wolf.
    """
    n = len(r1)
    s1, s2 = sharpe(r1), sharpe(r2)
    rho = float(np.corrcoef(r1, r2)[0, 1])
    theta = (1 / n) * (2 * (1 - rho)
                       + 0.5 * (s1 ** 2 + s2 ** 2 - 2 * s1 * s2 * rho ** 2))
    dif = s1 - s2
    z = dif / np.sqrt(theta)
    return {"dif_sharpe_diario": dif,
            "erro_padrao": float(np.sqrt(theta)),
            "z": float(z),
            "p_valor": float(2 * (1 - stats.norm.cdf(abs(z))))}


def _hac(y: np.ndarray, defas: int) -> np.ndarray:
    """Covariância HAC (Newey-West, kernel de Bartlett) de y."""
    n, k = y.shape
    yc = y - y.mean(axis=0)
    psi = yc.T @ yc / n
    for j in range(1, defas + 1):
        g = yc[j:].T @ yc[:-j] / n
        peso = 1 - j / (defas + 1)
        psi += peso * (g + g.T)
    return psi


def _se_ledoit_wolf(r1: np.ndarray, r2: np.ndarray, defas: int) -> tuple[float, float]:
    """Erro-padrão HAC da diferença de Sharpe, pelo método delta.

    Ledoit & Wolf (2008). Com v = (mu1, mu2, gama1, gama2) e
    SR_i = mu_i / sqrt(gama_i - mu_i^2), o gradiente da diferença é
    calculado analiticamente e combinado com a covariância HAC de
    (r1, r2, r1^2, r2^2).
    """
    n = len(r1)
    mu1, mu2 = r1.mean(), r2.mean()
    g1, g2 = (r1 ** 2).mean(), (r2 ** 2).mean()
    s1, s2 = np.sqrt(g1 - mu1 ** 2), np.sqrt(g2 - mu2 ** 2)
    grad = np.array([g1 / s1 ** 3,
                     -g2 / s2 ** 3,
                     -mu1 / (2 * s1 ** 3),
                     mu2 / (2 * s2 ** 3)])
    y = np.column_stack([r1, r2, r1 ** 2, r2 ** 2])
    psi = _hac(y, defas)
    var = float(grad @ psi @ grad / n)
    dif = mu1 / s1 - mu2 / s2
    return dif, float(np.sqrt(max(var, 1e-300)))


def teste_ledoit_wolf(r1: np.ndarray, r2: np.ndarray,
                      n_boot: int = N_BOOT, bloco: int = BLOCO) -> dict:
    """Ledoit & Wolf (2008): HAC + bootstrap de blocos estudentizado.

    O bootstrap circular preserva a dependência temporal, e a
    estudentização corrige o viés de amostra finita do erro-padrão.
    Devolve também o IC de 95% da diferença de Sharpe, que é o que
    o teste de não inferioridade [3.2] consome.
    """
    n = len(r1)
    defas = defasagem_nw(n)
    dif, se = _se_ledoit_wolf(r1, r2, defas)
    z = dif / se

    rng = np.random.default_rng(SEMENTE)
    n_blocos = int(np.ceil(n / bloco))
    estat, difs = np.empty(n_boot), np.empty(n_boot)
    for b in range(n_boot):
        inicio = rng.integers(0, n, n_blocos)
        idx = ((inicio[:, None] + np.arange(bloco)[None, :]) % n).ravel()[:n]
        d_b, se_b = _se_ledoit_wolf(r1[idx], r2[idx], defas)
        difs[b] = d_b
        estat[b] = (d_b - dif) / se_b
    p_boot = float((np.abs(estat) >= abs(z)).mean())

    # IC estudentizado (percentis invertidos)
    q_lo, q_hi = np.percentile(estat, [2.5, 97.5])
    ic = (dif - q_hi * se, dif - q_lo * se)

    an = np.sqrt(252)
    return {"dif_sharpe_diario": dif,
            "dif_sharpe_anual": dif * an,
            "erro_padrao": se,
            "z": float(z),
            "p_valor_hac": float(2 * (1 - stats.norm.cdf(abs(z)))),
            "p_valor_boot": p_boot,
            "ic95_inf_anual": ic[0] * an,
            "ic95_sup_anual": ic[1] * an,
            "defasagem_nw": defas}


# ──────────────────────────────────────────────────────────────
# [3.3] ALFA POR REGRESSÃO — fatores brasileiros do NEFIN
# ──────────────────────────────────────────────────────────────
def carregar_nefin() -> pd.DataFrame:
    if not ARQ_NEFIN.exists():
        print("Baixando fatores do NEFIN...")
        resp = requests.get(URL_NEFIN, timeout=120)
        resp.raise_for_status()
        ARQ_NEFIN.write_bytes(resp.content)
    df = pd.read_csv(ARQ_NEFIN)
    df = df.rename(columns={"Date": "data"})
    df["data"] = pd.to_datetime(df["data"])
    cols = ["Rm_minus_Rf", "SMB", "HML", "WML", "IML", "Risk_Free"]
    return df.set_index("data")[cols].sort_index()


def regressao_alfa(ret: pd.Series, fat: pd.DataFrame,
                   fatores: list[str]) -> dict:
    """r_p - r_f = alfa + betas * fatores + erro, com EP de Newey-West."""
    d = pd.concat([ret.rename("r"), fat], axis=1, sort=False).dropna()
    y = d["r"] - d["Risk_Free"]
    X = sm.add_constant(d[fatores])
    n = len(d)
    mod = sm.OLS(y, X).fit(cov_type="HAC",
                           cov_kwds={"maxlags": defasagem_nw(n), "use_correction": True})
    saida = {"n": n,
             "alfa_diario": float(mod.params["const"]),
             "alfa_anual_%": float(((1 + mod.params["const"]) ** 252 - 1) * 100),
             "t_alfa": float(mod.tvalues["const"]),
             "p_alfa": float(mod.pvalues["const"]),
             "R2": float(mod.rsquared)}
    for f in fatores:
        saida[f"beta_{f}"] = round(float(mod.params[f]), 3)
    return saida


# ──────────────────────────────────────────────────────────────
# TESTE DE MÉDIA COM ERRO-PADRÃO DE NEWEY-WEST
# ──────────────────────────────────────────────────────────────
def teste_media_nw(d: pd.Series) -> dict:
    """H0: E[d] = 0, com erro-padrão robusto a autocorrelação."""
    x = d.dropna()
    n = len(x)
    mod = sm.OLS(x.values, np.ones(n)).fit(
        cov_type="HAC", cov_kwds={"maxlags": defasagem_nw(n), "use_correction": True})
    media = float(mod.params[0])
    return {"n": n,
            "media_diaria": media,
            "media_anual_pp": float(((1 + media) ** 252 - 1) * 100),
            "t": float(mod.tvalues[0]),
            "p_valor": float(mod.pvalues[0])}


def estrela(p: float) -> str:
    return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else ""


# ──────────────────────────────────────────────────────────────
def main() -> None:
    fat = carregar_nefin()

    car = pd.read_csv(DIR_DADOS / "retornos_diarios_factor.csv",
                      index_col=0, parse_dates=True)
    uni = pd.read_csv(DIR_DADOS / "retornos_diarios_universos.csv",
                      index_col=0, parse_dates=True)
    df = car.join(uni[[c for c in uni.columns if c not in car.columns]], how="inner")
    selic = df["selic_dia"]

    ROT = {"Multifator": "Multifator (score)", "Baixa_Vol": "Fator Baixa Vol",
           "Valor": "Fator Valor", "Qualidade": "Fator Qualidade",
           "Momentum": "Fator Momentum", "Uniao_TCC": "Carteira do TCC (união)",
           "ISE_Universo_EW": "Universo ISE, peso igual",
           "IBRX_Universo_EW": "Universo IBrX-100, peso igual",
           "ret_ise": "ISE B3 (índice)", "ret_ibrx": "IBrX-100 (índice)"}

    print("=" * 96)
    print("  [3.1] Diferença de índice de Sharpe — Memmel (2003) e Ledoit-Wolf (2008)")
    print("=" * 96)
    print(f"  amostra: {len(df)} pregões, {df.index[0].date()} a {df.index[-1].date()}")
    print(f"  bootstrap: {N_BOOT} replicações, blocos circulares de {BLOCO} pregões\n")

    pares = [("Uniao_TCC", "ret_ibrx", "H1 — carteira do TCC vs IBrX-100"),
             ("Multifator", "ret_ibrx", "Multifator vs IBrX-100"),
             ("Baixa_Vol",  "ret_ibrx", "Baixa Vol vs IBrX-100"),
             ("Uniao_TCC",  "ret_ise",  "Carteira do TCC vs ISE B3"),
             ("ISE_Universo_EW", "IBRX_Universo_EW", "ESG: universos em peso igual"),
             ("ret_ise", "ret_ibrx", "ESG: índices oficiais")]

    linhas = []
    for a, b, rotulo in pares:
        if a not in df or b not in df:
            continue
        d = df[[a, b]].dropna()
        r1 = (d[a] - selic.reindex(d.index)).values
        r2 = (d[b] - selic.reindex(d.index)).values
        mm = teste_memmel(r1, r2)
        lw = teste_ledoit_wolf(r1, r2)
        an = np.sqrt(252)
        linhas.append({
            "Comparação": rotulo,
            "Sharpe A": round(sharpe(r1) * an, 3),
            "Sharpe B": round(sharpe(r2) * an, 3),
            "Diferença": round(lw["dif_sharpe_anual"], 3),
            "IC95 inf": round(lw["ic95_inf_anual"], 3),
            "IC95 sup": round(lw["ic95_sup_anual"], 3),
            "p Memmel": round(mm["p_valor"], 4),
            "p Ledoit-Wolf": round(lw["p_valor_boot"], 4),
            "sig.": estrela(lw["p_valor_boot"]),
        })
    tab_sharpe = pd.DataFrame(linhas)
    print(tab_sharpe.to_string(index=False))
    print("\n  Sharpe anualizado. IC95 é o do bootstrap estudentizado de Ledoit-Wolf.")
    print("  *** p<0,01   ** p<0,05   * p<0,10")

    # ── [3.2] não inferioridade ───────────────────────────────
    print("\n" + "=" * 96)
    print("  [3.2] Não inferioridade — o que os dados sustentam")
    print("=" * 96)
    print("  Um teste de não inferioridade é unilateral e precisa de uma margem")
    print("  delta declarada de antemão. Sem delta não existe conclusão de")
    print("  'não inferioridade' — só a comparação de pontos, que é o que o")
    print("  plano de trabalho proíbe. Abaixo, a margem que cada comparação")
    print("  sustenta: é o limite inferior do IC95 da diferença de Sharpe.\n")
    for _, r in tab_sharpe.iterrows():
        inf = r["IC95 inf"]
        if inf >= 0:
            veredito = "diferença POSITIVA e distinguível de zero"
        elif r["IC95 sup"] <= 0:
            veredito = "diferença NEGATIVA e distinguível de zero"
        else:
            veredito = (f"não distinguível de zero; só sustenta não inferioridade "
                        f"com margem delta >= {abs(inf):.3f} de Sharpe")
        print(f"  {r['Comparação']:38} {veredito}")

    # ── [3.3] alfa por regressão ──────────────────────────────
    print("\n" + "=" * 96)
    print("  [3.3] Alfa por regressão — fatores brasileiros do NEFIN, EP de Newey-West")
    print("=" * 96)
    F4 = ["Rm_minus_Rf", "SMB", "HML", "WML"]
    F5 = F4 + ["IML"]

    linhas = []
    for col in ["Uniao_TCC", "Multifator", "Baixa_Vol", "Valor", "Qualidade",
                "Momentum", "ISE_Universo_EW", "IBRX_Universo_EW",
                "ret_ise", "ret_ibrx"]:
        if col not in df:
            continue
        capm = regressao_alfa(df[col], fat, ["Rm_minus_Rf"])
        c4   = regressao_alfa(df[col], fat, F4)
        c5   = regressao_alfa(df[col], fat, F5)
        linhas.append({
            "Carteira": ROT.get(col, col),
            "alfa CAPM %aa": round(capm["alfa_anual_%"], 2),
            "t": round(capm["t_alfa"], 2),
            "alfa Carhart %aa": round(c4["alfa_anual_%"], 2),
            "t ": round(c4["t_alfa"], 2),
            "sig.": estrela(c4["p_alfa"]),
            "alfa +IML %aa": round(c5["alfa_anual_%"], 2),
            "t  ": round(c5["t_alfa"], 2),
            "beta mkt": c4["beta_Rm_minus_Rf"],
            "SMB": c4["beta_SMB"], "HML": c4["beta_HML"], "WML": c4["beta_WML"],
            "R2": round(c4["R2"], 3),
        })
    tab_alfa = pd.DataFrame(linhas)
    print(tab_alfa.to_string(index=False))
    print("\n  Carhart = mercado + SMB + HML + WML. A coluna sig. refere-se ao alfa de Carhart.")

    # ── diferenciais de retorno ───────────────────────────────
    print("\n" + "=" * 96)
    print("  Diferenciais de retorno médio — H0: diferença = 0 (Newey-West)")
    print("=" * 96)
    linhas = []
    for a, b, rotulo in pares:
        if a not in df or b not in df:
            continue
        d = (df[a] - df[b]).dropna()
        t = teste_media_nw(d)
        linhas.append({"Diferença": rotulo,
                       "Média (p.p. aa)": round(t["media_anual_pp"], 2),
                       "t": round(t["t"], 2),
                       "p": round(t["p_valor"], 4),
                       "sig.": estrela(t["p_valor"])})
    tab_dif = pd.DataFrame(linhas)
    print(tab_dif.to_string(index=False))

    tab_sharpe.to_csv(DIR_DADOS / "teste_sharpe.csv", index=False, encoding="utf-8-sig")
    tab_alfa.to_csv(DIR_DADOS / "teste_alfa.csv", index=False, encoding="utf-8-sig")
    tab_dif.to_csv(DIR_DADOS / "teste_diferencas.csv", index=False, encoding="utf-8-sig")
    print(f"\nTabelas salvas em {DIR_DADOS}")


if __name__ == "__main__":
    main()
