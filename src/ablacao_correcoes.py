# Ablacao das correcoes do plano de trabalho (secao 1).
# Roda o backtest sempre com a REGRA DE CARTEIRA ORIGINAL (uniao dos
# top-10) e liga uma correcao por vez, para medir o efeito de cada uma.
# Uso:  python src/ablacao_correcoes.py
# de carteira original (união dos top-10) para isolar as mudanças.
import sys, pathlib, requests, numpy as np, pandas as pd

REPO = pathlib.Path(r"C:\Users\rafin\OneDrive\Documentos\TCC GITHUB")
SP   = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "src"))

TOKEN = ""
for l in (REPO / ".env").read_text(encoding="utf-8-sig").splitlines():
    if l.strip().startswith("LAB_FINANCAS_TOKEN="):
        TOKEN = l.split("=", 1)[1].strip()
H = {"Authorization": f"Bearer {TOKEN}"}
BASE = "https://laboratoriodefinancas.com/api/v2"

# universo original (importado do módulo corrigido, sem executar o backtest)
import ast, re
src = (REPO / "src" / "carteira_factor_investing.py").read_text(encoding="utf-8")
UNI = ast.literal_eval(re.search(r"universo_ise = (\{.*?\n\})", src, re.S).group(1))
_i = src.index("RENOMEADOS = {")
_j = src.index(chr(10) + "}", _i) + 2
REN = ast.literal_eval(src[_i + len("RENOMEADOS = "):_j])
# o universo corrigido tirou TIET11 de 2021; para o cenário "antes" repõe-se
UNI_ORIG = {k: list(v) for k, v in UNI.items()}
UNI_ORIG[2021] = UNI_ORIG[2021] + ["TIET11"]

CACHE_NOVO  = pd.read_csv(REPO / "precos_historicos_cache.csv", index_col=0, parse_dates=True)
CACHE_VELHO = pd.read_csv(REPO / "data" / "precos_cache_ANTES_correcao.csv", index_col=0, parse_dates=True)

BENCH = (pd.read_csv(REPO / "data" / "base_ise_ibrx_selic.csv", parse_dates=["data"])
           .sort_values("data").set_index("data"))
SELIC = (1 + BENCH["selic_aa"] / 100) ** (1 / 252) - 1

_hit, _miss = {}, set()
def planilhao(data):
    if data in _hit:  return _hit[data]
    if data in _miss: return None
    try:
        r = requests.get(f"{BASE}/bolsa/planilhao", headers=H,
                         params={"data_base": data}, timeout=60)
        d = r.json() if r.status_code == 200 else []
    except Exception:
        d = []
    if isinstance(d, dict): d = d.get("results", d.get("data", []))
    if not d:
        _miss.add(data); return None
    df = pd.DataFrame(d)
    df.columns = [str(c).lower() for c in df.columns]
    df["Ticker"] = df["ticker"].astype(str).str.upper()
    for c in ("p_vp", "roic"): df[c] = pd.to_numeric(df[c], errors="coerce")
    _hit[data] = df[["Ticker", "p_vp", "roic"]]
    return _hit[data]

def plan_original(ano):
    for d in [f"{ano}-01-15", f"{ano}-01-20", f"{ano}-01-31",
              f"{ano}-02-15", f"{ano}-03-01", f"{ano}-03-15"]:
        p = planilhao(d)
        if p is not None: return p, d
    return None, None

def plan_pit(d_sinal):
    for k in range(150):
        d = (d_sinal - pd.Timedelta(days=k)).strftime("%Y-%m-%d")
        p = planilhao(d)
        if p is not None: return p, d
    return None, None


def backtest(dados_novos, pit, exec_lag, buy_hold, custo_lado, universo,
             canonico=False, calendario_b3=False):
    px  = CACHE_NOVO if dados_novos else CACHE_VELHO
    # [C11] restringe ao calendário oficial da B3: sem isso, os
    # feriados nacionais com preço repetido entram como retorno zero
    # e subestimam a volatilidade das ações que os têm.
    if calendario_b3:
        px = px.loc[px.index.isin(BENCH.index)]
    rt  = px.pct_change(fill_method=None)
    pr  = px.index
    series, pesos_ant, giros = [], pd.Series(dtype=float), []

    for ano in range(2016, 2026):
        ant = pr[(pr >= f"{ano-1}-01-01") & (pr <= f"{ano-1}-12-31")]
        cur = pr[(pr >= f"{ano}-01-01")   & (pr <= f"{ano}-12-31")]
        if len(ant) < 150 or len(cur) < 2: continue
        d_sinal, d_compra, d_fim = ant[-1], cur[0], cur[-1]

        linhas = []
        vistos = set()
        for t0 in universo[ano]:
            # [C9] traduz para o codigo canonico antes de qualquer juncao
            t = REN.get(t0, t0) if canonico else t0
            if t in vistos: continue
            vistos.add(t)
            if t not in px.columns: continue
            p = px.loc[ant[0]:d_sinal, t].dropna()
            r = rt.loc[ant[0]:d_sinal, t].dropna()
            if len(p) < 150: continue
            linhas.append({"Ticker": t, "momentum": p.iloc[-1]/p.iloc[0]-1,
                           "baixa_vol": r.std()*np.sqrt(252)})
        f = pd.DataFrame(linhas)
        if f.empty: continue

        pl, _ = (plan_pit(d_sinal) if pit else plan_original(ano))
        if pl is None: continue
        f = f.merge(pl, on="Ticker", how="inner")
        if f.empty: continue

        g = f.set_index("Ticker")
        cart = sorted(set(
            g["momentum"].dropna().sort_values(ascending=False).head(10).index.tolist() +
            g["baixa_vol"].dropna().sort_values(ascending=True ).head(10).index.tolist() +
            g.loc[g["p_vp"] > 0, "p_vp"].sort_values(ascending=True).head(10).index.tolist() +
            g["roic"].dropna().sort_values(ascending=False).head(10).index.tolist()))
        cart = [t for t in cart if t in px.columns]
        if not cart: continue

        alvo = pd.Series(1/len(cart), index=cart)
        idx  = pesos_ant.index.union(alvo.index)
        giro = float(0.5*(alvo.reindex(idx).fillna(0)-pesos_ant.reindex(idx).fillna(0)).abs().sum())
        giros.append(giro)

        ini = d_compra if exec_lag else f"{ano}-01-01"
        if buy_hold:
            jan = px.loc[d_compra:d_fim, cart]
            val = pd.DataFrame(index=jan.index, columns=cart, dtype=float)
            sel = SELIC.reindex(jan.index).fillna(0)
            ok  = []
            for t in cart:
                h = px.loc[:d_compra, t].dropna()
                if h.empty or not jan[t].notna().any(): continue
                ok.append(t)
            if not ok: continue
            w = 1/len(ok)
            for t in ok:
                p0 = float(px.loc[:d_compra, t].dropna().iloc[-1])
                q  = w/p0
                b  = jan[t]
                v  = q*b.ffill().fillna(p0)
                u  = b.last_valid_index()
                if u is not None and u < jan.index[-1]:
                    dep = jan.index > u
                    v.loc[dep] = q*float(b.loc[u])*(1+sel[dep]).cumprod()
                val[t] = v
            tot = val[ok].sum(axis=1)
            s   = tot.pct_change(fill_method=None); s.iloc[0] = 0.0
            pesos_ant = val[ok].iloc[-1]/tot.iloc[-1]
            if not exec_lag:   # cenário antigo: embolsa o retorno 31/12 -> 02/01
                extra = rt.loc[d_compra, cart].mean()
                s.iloc[0] = extra
        else:
            s = rt.loc[ini:f"{ano}-12-31", cart].mean(axis=1)
            if exec_lag: s = s.loc[d_compra:]; s.iloc[0] = 0.0
            pesos_ant = alvo
        s = s.dropna()
        if s.empty: continue
        s.iloc[0] -= 2*giro*custo_lado
        series.append(s)

    r = pd.concat(series)
    tot = (1+r).prod()-1
    an  = (1+tot)**(1/((r.index[-1]-r.index[0]).days/365.25))-1   # [C12]
    vol = r.std()*np.sqrt(252)
    exc = r - SELIC.reindex(r.index).fillna(0)
    pat = (1+r).cumprod()
    return dict(total=tot*100, anual=an*100, vol=vol*100,
                sharpe=float(exc.mean()/exc.std()*np.sqrt(252)),
                dd=float((pat/pat.cummax()-1).min()*100),
                giro=float(np.mean(giros)), n=len(r))


CENARIOS = [
 ("A. Codigo original (como estava)",              dict(dados_novos=False, pit=False, exec_lag=False, buy_hold=False, custo_lado=0.0,    universo=UNI_ORIG, canonico=False)),
 ("B. + [C6/C7] series de preco reparadas",        dict(dados_novos=True,  pit=False, exec_lag=False, buy_hold=False, custo_lado=0.0,    universo=UNI,      canonico=False)),
 ("C. + [C9] codigos canonicos no merge",          dict(dados_novos=True,  pit=False, exec_lag=False, buy_hold=False, custo_lado=0.0,    universo=UNI,      canonico=True)),
 ("D. + [C11] calendario oficial de pregoes",     dict(dados_novos=True,  pit=False, exec_lag=False, buy_hold=False, custo_lado=0.0,    universo=UNI,      canonico=True, calendario_b3=True)),
 ("E. + [C2] planilhao point-in-time",             dict(dados_novos=True,  pit=True,  exec_lag=False, buy_hold=False, custo_lado=0.0,    universo=UNI,      canonico=True, calendario_b3=True)),
 ("F. + [C3] compra no pregao seguinte",           dict(dados_novos=True,  pit=True,  exec_lag=True,  buy_hold=False, custo_lado=0.0,    universo=UNI,      canonico=True, calendario_b3=True)),
 ("G. + [C1] rebalanceamento anual (buy&hold)",    dict(dados_novos=True,  pit=True,  exec_lag=True,  buy_hold=True,  custo_lado=0.0,    universo=UNI,      canonico=True, calendario_b3=True)),
 ("H. + [C5] custos de negociacao (20 bps/lado)",  dict(dados_novos=True,  pit=True,  exec_lag=True,  buy_hold=True,  custo_lado=0.0020, universo=UNI,      canonico=True, calendario_b3=True)),
]

print("ABLACAO - regra de carteira sempre a ORIGINAL (uniao dos top-10)\n")
print(f"{'Cenario':<46}{'Total%':>9}{'Anual%':>9}{'Vol%':>8}{'Sharpe':>8}{'MaxDD%':>9}{'Giro':>7}")
print("-"*96)
linhas = []
for nome, kw in CENARIOS:
    m = backtest(**kw)
    linhas.append({"Cenario": nome, **{k: round(v,2) for k,v in m.items() if k!="n"}})
    print(f"{nome:<46}{m['total']:9.2f}{m['anual']:9.2f}{m['vol']:8.2f}"
          f"{m['sharpe']:8.2f}{m['dd']:9.2f}{m['giro']:7.3f}")
pd.DataFrame(linhas).to_csv(REPO/"data"/"ablacao_correcoes.csv", index=False, encoding="utf-8-sig")
print("\nsalvo em data/ablacao_correcoes.csv")
