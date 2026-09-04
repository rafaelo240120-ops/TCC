# ==============================================================
# TCC — Auditoria de código e dados
# Plano de trabalho, seção 5
#
# [5.1] Reproduzir a Tabela 1 diretamente pelo código
#       -> gera data/tabela1.csv e tex/tabelas/tabela1.tex, prontos
#          para \input no LaTeX. A tabela deixa de ser digitada à
#          mão e passa a sair do backtest.
#
# [5.2] Conferir dados ausentes, empresas deslistadas e mudanças
#       de ticker
#       -> varre ticker por ticker e ano por ano: quantos pregões
#          existem, se a série morre durante o período de posse, se
#          o código foi traduzido, e o que foi descartado por falta
#          de dado.
#
# [5.3] Validar as composições históricas dos índices e carteiras
#       -> confere tamanho das carteiras, soma dos pesos, duplicidade
#          de empresa dentro do mesmo ano, e valida as séries de
#          índice contra uma fonte independente (ETFs).
#
# [5.4] Recalcular todas as métricas após as correções
#       -> `python src/auditoria_dados.py --tudo` roda os quatro
#          scripts na ordem e depois confere se as tabelas
#          resultantes são mutuamente consistentes.
# ==============================================================

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

RAIZ       = Path(__file__).resolve().parents[1]
DIR_DADOS  = RAIZ / "data"
DIR_TAB    = RAIZ / "tex" / "tabelas"
DIR_TAB.mkdir(parents=True, exist_ok=True)

# valores que estão hoje na Tabela 1 do texto, para o confronto
TABELA1_TEXTO = {
    "Retorno acumulado":       {"Factor ESG": 227.15, "IBrX-100": 302.23, "ISE B3": 108.17},
    "Retorno anualizado":      {"Factor ESG": 12.83,  "IBrX-100": 15.23,  "ISE B3": 7.75},
    "Volatilidade anualizada": {"Factor ESG": 23.81,  "IBrX-100": 22.98,  "ISE B3": 22.79},
    "Índice de Sharpe":        {"Factor ESG": 0.25,   "IBrX-100": 0.34,   "ISE B3": 0.05},
    "Drawdown máximo":         {"Factor ESG": -47.17, "IBrX-100": -46.73, "ISE B3": -43.86},
}

SCRIPTS = ["carteira_factor_investing.py", "comparacao_universos.py",
           "testes_hipoteses.py", "apresentacao_resultados.py"]


def br(v: float, casas: int = 2, pct: bool = False) -> str:
    s = f"{v:.{casas}f}".replace(".", ",")
    return s + "\\%" if pct else s


# ──────────────────────────────────────────────────────────────
# [5.1] TABELA 1 REPRODUZIDA PELO CÓDIGO
# ──────────────────────────────────────────────────────────────
def tabela1() -> pd.DataFrame:
    perf = pd.read_csv(DIR_DADOS / "performance_comparativa.csv").set_index("Estrategia")
    mapa = {"Factor ESG": "Uniao top-10 (TCC)", "IBrX-100": "IBrX-100", "ISE B3": "ISE B3"}
    campos = [("Retorno acumulado", "Retorno Total (%)"),
              ("Retorno anualizado", "Retorno Anual (%)"),
              ("Volatilidade anualizada", "Volatilidade (%)"),
              ("Índice de Sharpe", "Sharpe"),
              ("Drawdown máximo", "Max Drawdown (%)")]
    linhas = []
    for rotulo, col in campos:
        linha = {"Indicador": rotulo}
        for nome, chave in mapa.items():
            linha[nome] = float(perf.loc[chave, col])
        linhas.append(linha)
    return pd.DataFrame(linhas).set_index("Indicador")


def tabela1_latex(tab: pd.DataFrame) -> str:
    """Tabela 1 em LaTeX (booktabs), para \\input no capítulo."""
    L = []
    L.append("% Gerado por src/auditoria_dados.py -- nao editar a mao.")
    L.append("\\begin{table}[htbp]")
    L.append("\\centering")
    L.append("\\caption{Desempenho comparativo da carteira Factor ESG e dos "
             "índices de referência (2016--2025)}")
    L.append("\\label{tab:desempenho}")
    L.append("\\begin{tabular}{lrrr}")
    L.append("\\toprule")
    L.append("Indicador & Factor ESG & IBrX-100 & ISE B3 \\\\")
    L.append("\\midrule")
    for ind, r in tab.iterrows():
        pct = ind != "Índice de Sharpe"
        vals = " & ".join(br(r[c], 2, pct) for c in tab.columns)
        L.append(f"{ind} & {vals} \\\\")
    L.append("\\bottomrule")
    L.append("\\end{tabular}")
    L.append("\\begin{tablenotes}\\small")
    L.append("\\item Rebalanceamento anual, custo de negociação de 20 pontos-base "
             "por lado. Taxa livre de risco: Selic. Elaborado pelo autor.")
    L.append("\\end{tablenotes}")
    L.append("\\end{table}")
    return "\n".join(L) + "\n"


def confronto_tabela1(tab: pd.DataFrame) -> pd.DataFrame:
    linhas = []
    for ind, r in tab.iterrows():
        for col in tab.columns:
            antigo = TABELA1_TEXTO[ind][col]
            novo = float(r[col])
            linhas.append({"Indicador": ind, "Série": col,
                           "No texto": antigo, "Recalculado": round(novo, 2),
                           "Diferença": round(novo - antigo, 2)})
    return pd.DataFrame(linhas)


# ──────────────────────────────────────────────────────────────
# [5.2] DADOS AUSENTES, DESLISTAGENS E MUDANÇAS DE TICKER
# ──────────────────────────────────────────────────────────────
def auditoria_cobertura():
    import carteira_factor_investing as cfi

    px = cfi.df_precos
    pregoes = px.index
    linhas = []
    for ano in range(cfi.ANO_INI, cfi.ANO_FIM + 1):
        cal = cfi.calendario(ano)
        if cal is None:
            continue
        for original in cfi.universo_ise[ano]:
            canon = cfi.RENOMEADOS.get(original, original)
            tem_col = canon in px.columns
            serie = px[canon].dropna() if tem_col else pd.Series(dtype=float)
            obs = px.loc[cal["d_ini_obs"]:cal["d_sinal"], canon].dropna() if tem_col else pd.Series(dtype=float)
            pos = px.loc[cal["d_compra"]:cal["d_fim"], canon].dropna() if tem_col else pd.Series(dtype=float)
            ult = pos.last_valid_index()
            # mesma tolerância do backtest: buraco final de 3+ pregões
            resto = px.loc[cal["d_compra"]:cal["d_fim"]].index
            falta = int((resto > ult).sum()) if ult is not None else 0
            deslistou = bool(len(pos) and ult is not None and falta >= 3)
            if len(obs) < cfi.MIN_PREGOES:
                situacao = "sem preço" if not tem_col or serie.empty else "poucos pregões"
            elif deslistou:
                situacao = "deslistou no período"
            else:
                situacao = "ok"
            linhas.append({
                "Ano": ano, "Ticker_universo": original, "Ticker_serie": canon,
                "Renomeado": original != canon,
                "Pregoes_observacao": len(obs), "Pregoes_posse": len(pos),
                "Elegivel": len(obs) >= cfi.MIN_PREGOES,
                "Ultimo_pregao": ult.date() if ult is not None else None,
                "Situacao": situacao,
            })
    return pd.DataFrame(linhas)


# ──────────────────────────────────────────────────────────────
# [5.3] VALIDAÇÃO DE COMPOSIÇÕES
# ──────────────────────────────────────────────────────────────
def validar_carteiras() -> tuple[pd.DataFrame, list[str]]:
    comp = pd.read_csv(DIR_DADOS / "composicao_carteiras.csv")
    import carteira_factor_investing as cfi

    problemas = []
    g = comp.groupby(["Estrategia", "Ano"])
    resumo = g.agg(N_acoes=("Ticker", "size"),
                   Soma_pesos=("Peso", "sum"),
                   N_unicos=("Ticker", "nunique")).reset_index()

    for _, r in resumo.iterrows():
        if r["N_acoes"] != r["N_unicos"]:
            problemas.append(f"{r['Estrategia']} {int(r['Ano'])}: ticker repetido "
                             f"({int(r['N_acoes'])} linhas, {int(r['N_unicos'])} únicos)")
        if abs(r["Soma_pesos"] - 1.0) > 0.005:
            problemas.append(f"{r['Estrategia']} {int(r['Ano'])}: pesos somam "
                             f"{r['Soma_pesos']:.4f}, não 1")
        if r["Estrategia"] != "Uniao_TCC" and r["N_acoes"] != cfi.TOP_N:
            problemas.append(f"{r['Estrategia']} {int(r['Ano'])}: {int(r['N_acoes'])} "
                             f"ações, esperado {cfi.TOP_N}")

    # empresa entrando duas vezes sob códigos diferentes
    for (est, ano), sub in comp.groupby(["Estrategia", "Ano"]):
        canon = [cfi.RENOMEADOS.get(t, t) for t in sub["Ticker"]]
        if len(canon) != len(set(canon)):
            problemas.append(f"{est} {int(ano)}: mesma empresa sob dois códigos")
    return resumo, problemas


def validar_universo() -> tuple[pd.DataFrame, list[str]]:
    import carteira_factor_investing as cfi

    problemas, linhas = [], []
    for ano, lista in sorted(cfi.universo_ise.items()):
        canon = [cfi.RENOMEADOS.get(t, t) for t in lista]
        dups = {c for c in canon if canon.count(c) > 1}
        if dups:
            problemas.append(f"universo {ano}: código duplicado após tradução -> "
                             f"{sorted(dups)}")
        sem_preco = [t for t, c in zip(lista, canon)
                     if c not in cfi.df_precos.columns
                     or cfi.df_precos[c].dropna().empty]
        if sem_preco:
            problemas.append(f"universo {ano}: sem série de preço -> {sem_preco}")
        linhas.append({"Ano": ano, "N_listado": len(lista),
                       "N_unico_apos_traducao": len(set(canon)),
                       "N_com_preco": len(canon) - len(sem_preco),
                       "N_elegivel": len(cfi.universo_efetivo(ano))
                       if ano >= cfi.ANO_INI else np.nan})
    return pd.DataFrame(linhas), problemas


def validar_indices() -> pd.DataFrame:
    """Confere as séries de índice contra uma fonte independente (ETFs).

    ISUS11 replica o ISE B3 e BRAX11 replica o IBrX-100. A diferença
    esperada é pequena e negativa (taxa de administração e tracking
    error), nunca estrutural.
    """
    import yfinance as yf

    b = pd.read_csv(DIR_DADOS / "base_ise_ibrx_selic.csv",
                    parse_dates=["data"]).set_index("data")
    ini, fim = "2016-01-04", "2025-12-30"

    def cagr(s):
        s = s.dropna().loc[ini:fim]
        anos = (s.index[-1] - s.index[0]).days / 365.25
        return (s.iloc[-1] / s.iloc[0]) ** (1 / anos) - 1

    linhas = []
    for col, etf, rot in [("ise_b3", "ISUS11.SA", "ISE B3"),
                          ("ibrx100", "BRAX11.SA", "IBrX-100")]:
        try:
            h = yf.Ticker(etf).history(start="2015-12-20", end="2026-01-05",
                                       auto_adjust=True)["Close"]
            h.index = pd.to_datetime(h.index).tz_localize(None)
            ref = cagr(h) * 100
        except Exception:
            ref = np.nan
        base = cagr(b[col]) * 100
        linhas.append({"Índice": rot, "Base do TCC (%aa)": round(base, 2),
                       "ETF de referência": etf,
                       "ETF (%aa)": round(ref, 2) if ref == ref else None,
                       "Diferença (p.p.)": round(base - ref, 2) if ref == ref else None})
    return pd.DataFrame(linhas)


# ──────────────────────────────────────────────────────────────
# [5.4] RECÁLCULO E CONSISTÊNCIA
# ──────────────────────────────────────────────────────────────
def rodar_tudo() -> None:
    for nome in SCRIPTS:
        print(f"\n>>> {nome}")
        r = subprocess.run([sys.executable, "-X", "utf8", str(RAIZ / "src" / nome)],
                           cwd=RAIZ, capture_output=True, text=True)
        if r.returncode != 0:
            print(r.stdout[-2000:])
            print(r.stderr[-2000:])
            raise SystemExit(f"{nome} falhou com código {r.returncode}")
        print(f"    ok ({len(r.stdout.splitlines())} linhas de saída)")


def consistencia() -> list[str]:
    """As tabelas independentes precisam concordar entre si."""
    avisos = []
    perf = pd.read_csv(DIR_DADOS / "performance_comparativa.csv").set_index("Estrategia")
    uni  = pd.read_csv(DIR_DADOS / "comparacao_universos.csv")
    ret  = pd.read_csv(DIR_DADOS / "retornos_diarios_factor.csv",
                       index_col=0, parse_dates=True)
    anual = pd.read_csv(DIR_DADOS / "retornos_anuais.csv", index_col=0)

    # o IBrX-100 aparece nas duas tabelas de desempenho
    a = float(perf.loc["IBrX-100", "Retorno Anual (%)"])
    b = float(uni.loc[uni.Carteira == "IBrX-100 (índice oficial)",
                      "Retorno Anual (%)"].iloc[0])
    if abs(a - b) > 0.01:
        avisos.append(f"IBrX-100 diverge entre performance_comparativa ({a}) "
                      f"e comparacao_universos ({b})")

    # o retorno total tem de bater com o composto dos retornos anuais
    for col, rot in [("Multifator", "Multifator (score)"),
                     ("Uniao_TCC", "Uniao top-10 (TCC)")]:
        nome = {"Multifator": "Multifator (score)",
                "Uniao_TCC": "Uniao top-10 (TCC)"}[col]
        rot_anual = {"Multifator": "Multifator (score)",
                     "Uniao_TCC": "Uniao top-10 (TCC)"}[col]
        if rot_anual not in anual.columns:
            continue
        comp_anos = float(((anual[rot_anual] / 100 + 1).prod() - 1) * 100)
        total = float(perf.loc[nome, "Retorno Total (%)"])
        if abs(comp_anos - total) > 0.5:
            avisos.append(f"{nome}: retorno total {total:.2f}% não bate com o "
                          f"composto dos anos {comp_anos:.2f}%")

    # a série diária tem de cobrir exatamente os dez anos
    anos = sorted(ret.index.year.unique())
    if anos != list(range(2016, 2026)):
        avisos.append(f"retornos diários cobrem {anos}, esperado 2016..2025")
    return avisos


# ──────────────────────────────────────────────────────────────
def main() -> None:
    if "--tudo" in sys.argv:
        print("=" * 92)
        print("  [5.4] Recalculando tudo, na ordem")
        print("=" * 92)
        rodar_tudo()

    print("\n" + "=" * 92)
    print("  [5.1] Tabela 1 reproduzida pelo código")
    print("=" * 92)
    t1 = tabela1()
    print(t1.round(2).to_string())
    t1.round(2).to_csv(DIR_DADOS / "tabela1.csv", encoding="utf-8-sig")
    (DIR_TAB / "tabela1.tex").write_text(tabela1_latex(t1), encoding="utf-8")
    print(f"\n  -> data/tabela1.csv e tex/tabelas/tabela1.tex")

    conf = confronto_tabela1(t1)
    print("\n--- Confronto com os números que estão hoje no texto ---")
    print(conf.to_string(index=False))
    conf.to_csv(DIR_DADOS / "tabela1_confronto.csv", index=False, encoding="utf-8-sig")

    print("\n" + "=" * 92)
    print("  [5.2] Cobertura de dados, deslistagens e mudanças de ticker")
    print("=" * 92)
    cob = auditoria_cobertura()
    cob.to_csv(DIR_DADOS / "auditoria_cobertura.csv", index=False, encoding="utf-8-sig")
    print(cob.groupby("Situacao").size().rename("Casos").to_string())
    print(f"\n  {int(cob.Renomeado.sum())} de {len(cob)} pares ticker-ano usam "
          f"código traduzido")
    print("\n  Deslistagens durante o período de posse:")
    desl = cob[cob.Situacao == "deslistou no período"]
    for _, r in desl.iterrows():
        print(f"    {r['Ano']}  {r['Ticker_universo']:7} último pregão em "
              f"{r['Ultimo_pregao']}")
    print("\n  Descartados por falta de dado:")
    ruins = cob[~cob.Elegivel]
    if ruins.empty:
        print("    nenhum")
    else:
        for _, r in ruins.iterrows():
            print(f"    {r['Ano']}  {r['Ticker_universo']:7} "
                  f"{r['Pregoes_observacao']:3} pregões — {r['Situacao']}")

    print("\n" + "=" * 92)
    print("  [5.3] Validação das composições")
    print("=" * 92)
    uni, prob_uni = validar_universo()
    print(uni.to_string(index=False))
    uni.to_csv(DIR_DADOS / "validacao_universo.csv", index=False, encoding="utf-8-sig")

    resumo, prob_cart = validar_carteiras()
    resumo.to_csv(DIR_DADOS / "validacao_carteiras.csv", index=False, encoding="utf-8-sig")

    print("\n--- Séries de índice contra fonte independente ---")
    idx = validar_indices()
    print(idx.to_string(index=False))
    idx.to_csv(DIR_DADOS / "validacao_indices.csv", index=False, encoding="utf-8-sig")

    print("\n--- Problemas encontrados ---")
    todos = prob_uni + prob_cart + consistencia()
    if not todos:
        print("  nenhum: composições, pesos, códigos e tabelas estão consistentes.")
    else:
        for p in todos:
            print(f"  ATENÇÃO: {p}")

    print(f"\nTabelas salvas em {DIR_DADOS} e {DIR_TAB}")


if __name__ == "__main__":
    main()
