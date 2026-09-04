# ==============================================================
# TCC — Apresentação dos resultados
# Plano de trabalho, seção 4
#
# [4.1] gráficos de patrimônio e drawdown
# [4.2] retornos de cada ano
# [4.3] composição das carteiras
# [4.4] distribuição por setor
# [4.5] crise de 2020 e outros períodos de estresse
#
# Consome os CSVs gerados por carteira_factor_investing.py e
# comparacao_universos.py. Não recalcula nenhum retorno — se um
# número aparece aqui, ele veio do backtest, não de uma segunda
# implementação.
# ==============================================================

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm

RAIZ      = Path(__file__).resolve().parents[1]
DIR_DADOS = RAIZ / "data"
DIR_FIG   = RAIZ / "fig"
DIR_FIG.mkdir(exist_ok=True)

ROT = {"Momentum": "Momentum", "Baixa_Vol": "Baixa Vol", "Valor": "Valor",
       "Qualidade": "Qualidade", "Multifator": "Multifator",
       "Uniao_TCC": "Uniao top-10 (TCC)", "ret_ibrx": "IBrX-100", "ret_ise": "ISE B3"}
COR = {"Multifator": "#2B4C63", "Baixa_Vol": "#1E5945", "Uniao_TCC": "#C77B36",
       "Momentum": "#7A6A9B", "Valor": "#9E2B25", "Qualidade": "#4E7A8C",
       "ret_ibrx": "#5B6570", "ret_ise": "#B03A2E"}
LINHA = {"ret_ibrx": "--", "ret_ise": ":"}

# escalas de cor: divergente para retornos (vermelho-neutro-verde) e
# sequencial para pesos. Derivadas da mesma paleta das linhas.
DIVERGENTE = matplotlib.colors.LinearSegmentedColormap.from_list(
    "tcc_div", ["#8C2018", "#C9705F", "#F2EFE9", "#5E9B82", "#14503D"])
SEQUENCIAL = matplotlib.colors.LinearSegmentedColormap.from_list(
    "tcc_seq", ["#F4F5F2", "#A9C0CE", "#5E8299", "#2B4C63", "#16303F"])

plt.rcParams.update({"figure.dpi": 150, "font.size": 9.5,
                     "axes.grid": True, "grid.linestyle": ":", "grid.alpha": 0.55,
                     "axes.spines.top": False, "axes.spines.right": False})


def carregar() -> pd.DataFrame:
    return pd.read_csv(DIR_DADOS / "retornos_diarios_factor.csv",
                       index_col=0, parse_dates=True)


def patrimonio(ret: pd.Series) -> pd.Series:
    return (1 + ret.fillna(0)).cumprod() * 100


def drawdown(pat: pd.Series) -> pd.Series:
    return pat / pat.cummax() - 1


def rotula_fim(ax, serie, texto, cor, dx=6, dy=0):
    """Rótulo no fim da linha, no lugar de legenda."""
    ax.annotate(texto, xy=(serie.index[-1], serie.iloc[-1]),
                xytext=(dx, dy), textcoords="offset points",
                va="center", fontsize=9, color=cor, fontweight="600")


def rotula_fim_varios(ax, itens, folga=0.032):
    """Rótulos no fim das linhas, afastados quando ficam colados.

    `itens` é uma lista de (serie, texto, cor). Séries que terminam
    perto demais uma da outra recebem um deslocamento vertical, para
    que os rótulos não se sobreponham.
    """
    lim = ax.get_ylim()
    minimo = (lim[1] - lim[0]) * folga
    ordenados = sorted(itens, key=lambda t: t[0].iloc[-1])
    alvos, ultimo = [], None
    for serie, _, _ in ordenados:
        v = float(serie.iloc[-1])
        if ultimo is not None and v - ultimo < minimo:
            v = ultimo + minimo
        alvos.append(v)
        ultimo = v
    for (serie, texto, cor), alvo in zip(ordenados, alvos):
        y = float(serie.iloc[-1])
        desloc = (alvo - y) / (lim[1] - lim[0]) * ax.bbox.height
        rotula_fim(ax, serie, texto, cor, dy=desloc)


def marca_covid(ax, cor="#9E2B25"):
    ax.axvspan(pd.Timestamp("2020-01-23"), pd.Timestamp("2020-03-23"),
               color=cor, alpha=0.09, zorder=0, linewidth=0)


def mapa_calor(ax, dados, fmt="{:.0f}", centro_zero=True, cmap=None,
               vmin=None, vmax=None):
    """Heatmap com o valor escrito em cada célula."""
    m = dados.values.astype(float)
    if centro_zero:
        lim = np.nanmax(np.abs(m))
        norm = matplotlib.colors.TwoSlopeNorm(vmin=-lim, vcenter=0, vmax=lim)
        cmap = cmap or DIVERGENTE
        escuro = lambda v: abs(norm(v) - 0.5) > 0.34   # noqa: E731
    else:
        norm = matplotlib.colors.Normalize(vmin=vmin if vmin is not None else 0,
                                           vmax=vmax if vmax is not None else np.nanmax(m))
        cmap = cmap or SEQUENCIAL
        # numa escala sequencial só a ponta alta é escura; usar a regra
        # da divergente pintava os zeros de branco sobre fundo claro
        escuro = lambda v: norm(v) > 0.58                # noqa: E731
    ax.imshow(m, cmap=cmap, norm=norm, aspect="auto")
    ax.set_xticks(range(dados.shape[1]))
    ax.set_xticklabels(dados.columns)
    ax.set_yticks(range(dados.shape[0]))
    ax.set_yticklabels(dados.index)
    ax.grid(False)
    for i in range(m.shape[0]):
        for j in range(m.shape[1]):
            v = m[i, j]
            if np.isnan(v):
                continue
            esc = escuro(v)
            ax.text(j, i, fmt.format(v), ha="center", va="center", fontsize=8.4,
                    color="white" if esc else "#3A4045",
                    fontweight="600" if esc else "400")
    for lado in ("top", "right", "bottom", "left"):
        ax.spines[lado].set_visible(False)
    ax.tick_params(length=0)


# ──────────────────────────────────────────────────────────────
# [4.1] PATRIMÔNIO E DRAWDOWN
#
# Antes: escala log com cinco linhas de mesmo peso nos dois painéis.
# A log achatava a queda de 2020 e o painel de drawdown virava um
# emaranhado em que não se distinguia uma série da outra.
#
# Agora: escala linear, hierarquia visual (carteiras em cor e traço
# grosso, índices em cinza), rótulo no fim de cada linha em vez de
# legenda sobre os dados, e o drawdown do IBrX-100 como área
# preenchida ao fundo, servindo de régua para as duas linhas.
# ──────────────────────────────────────────────────────────────
def fig_patrimonio_drawdown(df: pd.DataFrame, carteira: str,
                            arquivo: str) -> None:
    """Patrimônio e drawdown de UMA carteira contra o IBrX-100.

    Uma carteira por figura: cada gráfico responde a uma pergunta só
    ("como foi esta carteira contra o mercado?") e não exige que o
    leitor siga várias linhas ao mesmo tempo. O índice aparece como
    área cinza de fundo, servindo de régua.
    """
    pat = patrimonio(df[carteira])
    ben = patrimonio(df["ret_ibrx"])
    dd_p, dd_b = drawdown(pat) * 100, drawdown(ben) * 100

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11.5, 7.6), sharex=True,
                                   gridspec_kw={"height_ratios": [2.2, 1]})
    ax1.fill_between(ben.index, ben, 100, color="#5B6570", alpha=0.13,
                     linewidth=0, zorder=1)
    ax1.plot(ben, color=COR["ret_ibrx"], linestyle="--", linewidth=1.6, zorder=2)
    ax1.plot(pat, color=COR[carteira], linewidth=2.4, zorder=3)
    marca_covid(ax1)
    ax1.axhline(100, color="#555", linewidth=0.8)
    ax1.set_ylabel("Patrimônio (base 100)")
    ax1.set_title(f"{ROT[carteira]}: quanto rendeu cada R$ 100 investidos "
                  f"no início de 2016", loc="left", fontsize=13, pad=12)
    ax1.set_ylim(60, 660)
    ax1.margins(x=0.14)
    rotula_fim_varios(ax1, [
        (pat, f"{ROT[carteira]}  {pat.iloc[-1]:.0f}", COR[carteira]),
        (ben, f"IBrX-100  {ben.iloc[-1]:.0f}", COR["ret_ibrx"])])

    ax2.fill_between(dd_b.index, dd_b, 0, color="#5B6570", alpha=0.22,
                     linewidth=0)
    ax2.plot(dd_p, color=COR[carteira], linewidth=1.7)
    marca_covid(ax2)
    ax2.axhline(0, color="#555", linewidth=0.8)
    ax2.set_ylabel("Drawdown (%)")
    ax2.set_ylim(min(dd_b.min(), dd_p.min()) * 1.22, 4)
    ax2.set_title("Queda acumulada desde o topo anterior — área cinza é o "
                  "IBrX-100", loc="left", fontsize=10.5, pad=8)
    ax2.margins(x=0.14)
    ax2.annotate(f"pior queda {dd_p.min():.0f}%",
                 xy=(dd_p.idxmin(), dd_p.min()), xytext=(10, 4),
                 textcoords="offset points", fontsize=9,
                 color=COR[carteira], fontweight="600")
    ax2.annotate(f"IBrX-100 {dd_b.min():.0f}%",
                 xy=(dd_b.idxmin(), dd_b.min()), xytext=(10, -14),
                 textcoords="offset points", fontsize=9, color="#5B6570",
                 annotation_clip=False)

    fig.text(0.012, 0.012,
             "Faixa vermelha: crise da COVID-19 (23/01 a 23/03/2020). "
             "Tracejado e área cinza: IBrX-100.",
             fontsize=8.5, color="#61686D")
    fig.tight_layout(rect=[0, 0.03, 1, 1])
    fig.savefig(DIR_FIG / arquivo)
    plt.close(fig)


def fig_patrimonio_por_fator(df: pd.DataFrame) -> None:
    """Pequenos múltiplos: cada carteira contra o mesmo IBrX-100.

    Uma linha por painel elimina o cruzamento entre séries, e a
    referência cinza repetida em todos permite comparar os painéis
    entre si sem precisar seguir seis cores no mesmo eixo.
    """
    cols = ["Multifator", "Baixa_Vol", "Valor", "Qualidade", "Momentum", "Uniao_TCC"]
    bench = patrimonio(df["ret_ibrx"])

    fig, axes = plt.subplots(2, 3, figsize=(13, 7), sharex=True, sharey=True)
    for ax, c in zip(axes.ravel(), cols):
        pat = patrimonio(df[c])
        dd = drawdown(pat).min() * 100
        ax.fill_between(bench.index, bench, 100, color="#5B6570",
                        alpha=0.13, linewidth=0)
        ax.plot(bench, color="#5B6570", linestyle="--", linewidth=1.2)
        ax.plot(pat, color=COR[c], linewidth=2.2)
        marca_covid(ax)
        ax.axhline(100, color="#555", linewidth=0.7)
        ax.set_title(ROT[c], loc="left", fontsize=11.5, color=COR[c],
                     fontweight="600", pad=6)
        ax.set_ylim(60, 660)
        ax.text(0.035, 0.94,
                f"final {pat.iloc[-1]:.0f}   pior queda {dd:.0f}%",
                transform=ax.transAxes, fontsize=8.8, va="top", color="#3A4045")
        ax.text(0.035, 0.86, f"IBrX-100 {bench.iloc[-1]:.0f}",
                transform=ax.transAxes, fontsize=8.5, va="top", color="#5B6570")
    for ax in axes[:, 0]:
        ax.set_ylabel("Base 100")
    fig.suptitle("Cada carteira contra o IBrX-100 — mesma escala nos seis painéis",
                 x=0.012, ha="left", fontsize=13, y=0.985)
    fig.text(0.012, 0.012,
             "Linha tracejada e área cinza: IBrX-100, repetido em todos os painéis "
             "como referência. Faixa vermelha: crise de 2020.",
             fontsize=8.5, color="#61686D")
    fig.tight_layout(rect=[0, 0.035, 1, 0.96])
    fig.savefig(DIR_FIG / "patrimonio_por_fator.png")
    plt.close(fig)


# ──────────────────────────────────────────────────────────────
# [4.2] RETORNOS ANUAIS
#
# Antes: cinquenta barras agrupadas. Para saber se a carteira bateu
# o índice num ano era preciso caçar duas cores entre cinco.
#
# Agora: mapa de calor com o número escrito em cada célula — lê-se
# o valor exato e a magnitude pela cor, ao mesmo tempo. Abaixo, o
# excesso sobre o IBrX-100, que é a pergunta que o trabalho faz.
# ──────────────────────────────────────────────────────────────
def fig_retornos_anuais(df: pd.DataFrame) -> pd.DataFrame:
    cols = ["Multifator", "Baixa_Vol", "Valor", "Qualidade", "Momentum",
            "Uniao_TCC", "ret_ibrx", "ret_ise"]
    anual = ((df[cols].fillna(0) + 1).groupby(df.index.year).prod() - 1) * 100
    anual.index.name = "Ano"

    m = anual.T
    m.index = [ROT[c] for c in cols]
    exc = (m.loc[[ROT[c] for c in cols[:6]]] - m.loc[ROT["ret_ibrx"]])

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11.5, 8.4),
                                   gridspec_kw={"height_ratios": [8, 6]})
    mapa_calor(ax1, m, fmt="{:+.0f}")
    ax1.set_title("Retorno de cada ano (%)", loc="left", fontsize=13, pad=12)
    ax1.axhline(5.5, color="#1A1D21", linewidth=1.4)

    mapa_calor(ax2, exc, fmt="{:+.0f}")
    ax2.set_title("Excesso sobre o IBrX-100 no ano (pontos percentuais)",
                  loc="left", fontsize=11.5, pad=10)

    fig.text(0.012, 0.012,
             "Verde: acima. Vermelho: abaixo. A linha separa as carteiras dos índices.",
             fontsize=8.5, color="#61686D")
    fig.tight_layout(rect=[0, 0.03, 1, 1])
    fig.savefig(DIR_FIG / "retornos_anuais.png")
    plt.close(fig)
    return anual.round(2)


# ──────────────────────────────────────────────────────────────
# [4.3] COMPOSIÇÃO DAS CARTEIRAS
# ──────────────────────────────────────────────────────────────
def tabela_composicao() -> tuple[pd.DataFrame, pd.DataFrame]:
    comp = pd.read_csv(DIR_DADOS / "composicao_carteiras.csv")
    freq = (comp.groupby(["Estrategia", "Ticker"]).size()
                .rename("Anos").reset_index()
                .sort_values(["Estrategia", "Anos"], ascending=[True, False]))
    setor = comp.drop_duplicates("Ticker").set_index("Ticker")["Setor"]
    freq["Setor"] = freq["Ticker"].map(setor)
    larga = (comp.groupby(["Estrategia", "Ano"])["Ticker"]
                 .apply(lambda x: ", ".join(sorted(x)))
                 .unstack(0))
    return freq, larga


def fig_persistencia() -> None:
    """Quantas ações se repetem de um ano para o outro, em mapa de calor."""
    comp = pd.read_csv(DIR_DADOS / "composicao_carteiras.csv")
    ests = ["Multifator", "Baixa_Vol", "Valor", "Qualidade", "Momentum", "Uniao_TCC"]
    linhas = {}
    for e in ests:
        sub = comp[comp.Estrategia == e]
        anos = sorted(sub.Ano.unique())
        linhas[ROT[e]] = {b: 100 * len(set(sub[sub.Ano == a].Ticker)
                                       & set(sub[sub.Ano == b].Ticker))
                          / len(set(sub[sub.Ano == b].Ticker))
                          for a, b in zip(anos[:-1], anos[1:])}
    m = pd.DataFrame(linhas).T

    fig, ax = plt.subplots(figsize=(10.5, 3.9))
    mapa_calor(ax, m, fmt="{:.0f}", centro_zero=False, vmin=0, vmax=100)
    ax.set_title("Quanto da carteira do ano anterior foi mantida (%)",
                 loc="left", fontsize=12.5, pad=12)
    fig.text(0.012, 0.02,
             "Mais escuro = mais estável. Um valor baixo significa que o "
             "rebalanceamento trocou quase toda a carteira.",
             fontsize=8.5, color="#61686D")
    fig.tight_layout(rect=[0, 0.06, 1, 1])
    fig.savefig(DIR_FIG / "persistencia_carteiras.png")
    plt.close(fig)


# ──────────────────────────────────────────────────────────────
# [4.4] DISTRIBUIÇÃO POR SETOR
#
# Antes: quatro áreas empilhadas com nove faixas cada. Só a faixa
# de baixo era legível; comparar um setor entre dois anos era
# impossível.
#
# Agora: barras horizontais ordenadas para o peso médio (responde
# "quais setores dominam") e um mapa de calor setor x ano para a
# carteira multifatorial (responde "isso mudou ao longo do tempo").
# ──────────────────────────────────────────────────────────────
def distribuicao_setorial() -> pd.DataFrame:
    comp = pd.read_csv(DIR_DADOS / "composicao_carteiras.csv")
    setor = (comp.groupby(["Estrategia", "Ano", "Setor"])["Peso"].sum()
                 .rename("Peso").reset_index())
    setor["Peso"] = (setor["Peso"] * 100).round(2)
    return setor


def fig_setorial(setor: pd.DataFrame) -> None:
    ests = ["Multifator", "Baixa_Vol", "Valor", "Qualidade", "Momentum", "Uniao_TCC"]
    med = (setor.groupby(["Estrategia", "Setor"])["Peso"].mean()
                .unstack(0).fillna(0))
    med = med[[e for e in ests if e in med.columns]]
    med = med.loc[med.mean(axis=1).sort_values().index][-9:]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 6.4),
                                   gridspec_kw={"width_ratios": [1.15, 1]})

    y = np.arange(len(med))
    n = len(med.columns)
    alt = 0.82 / n
    for i, e in enumerate(med.columns):
        ax1.barh(y + (i - (n - 1) / 2) * alt, med[e], alt,
                 label=ROT[e], color=COR[e], edgecolor="white", linewidth=0.4)
    ax1.set_yticks(y)
    ax1.set_yticklabels(med.index)
    ax1.set_xlabel("Peso médio no período (%)")
    ax1.set_title("Quais setores dominam cada carteira", loc="left",
                  fontsize=12.5, pad=12)
    ax1.legend(fontsize=8.8, ncol=3, loc="upper center",
               bbox_to_anchor=(0.5, -0.09), frameon=False)
    ax1.grid(axis="y", visible=False)

    sub = setor[setor.Estrategia == "Multifator"]
    piv = sub.pivot_table(index="Setor", columns="Ano", values="Peso",
                          aggfunc="sum").fillna(0)
    piv = piv.loc[piv.mean(axis=1).sort_values(ascending=False).index][:9]
    mapa_calor(ax2, piv, fmt="{:.0f}", centro_zero=False, vmin=0, vmax=60)
    ax2.set_title("Carteira multifatorial, ano a ano (% do peso)", loc="left",
                  fontsize=12.5, pad=12)

    fig.text(0.012, 0.014,
             "Célula em branco ou zero: o setor não teve nenhuma ação na carteira "
             "daquele ano.", fontsize=8.5, color="#61686D")
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    fig.savefig(DIR_FIG / "distribuicao_setorial.png")
    plt.close(fig)


# ──────────────────────────────────────────────────────────────
# [4.5] PERÍODOS DE ESTRESSE
# ──────────────────────────────────────────────────────────────
def episodios_drawdown(ret: pd.Series, limiar: float = 0.15) -> list[dict]:
    """Episódios de queda do benchmark de pelo menos `limiar`."""
    pat = patrimonio(ret)
    dd = drawdown(pat)
    eps, i, n = [], 0, len(pat)
    while i < n:
        if dd.iloc[i] == 0:
            j = i + 1
            while j < n and dd.iloc[j] < 0:
                j += 1
            if j > i + 1:
                trecho = dd.iloc[i:j]
                fundo_pos = int(trecho.values.argmin())
                if -trecho.iloc[fundo_pos] >= limiar:
                    eps.append({"pico": pat.index[i],
                                "fundo": trecho.index[fundo_pos],
                                "recuperacao": pat.index[min(j, n - 1)],
                                "queda": float(trecho.iloc[fundo_pos])})
            i = j
        else:
            i += 1
    return eps


def tabela_estresse(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    eps = episodios_drawdown(df["ret_ibrx"])
    linhas = []
    for e in eps:
        for fase, ini, fim in [("queda", e["pico"], e["fundo"]),
                               ("recuperação", e["fundo"], e["recuperacao"])]:
            if ini >= fim:
                continue
            jan = df.loc[ini:fim, cols]
            reg = {"Episódio": f"{e['pico'].date()} a {e['recuperacao'].date()}",
                   "Fase": fase,
                   "Pregões": len(jan),
                   "Queda do IBrX (%)": round(e["queda"] * 100, 1)}
            for c in cols:
                reg[ROT[c]] = round(((1 + jan[c].fillna(0)).prod() - 1) * 100, 2)
            linhas.append(reg)
    return pd.DataFrame(linhas)


def capturas(df: pd.DataFrame, cols: list[str], bench: str = "ret_ibrx") -> pd.DataFrame:
    b = df[bench]
    alta, baixa = b > 0, b < 0
    linhas = []
    for c in cols:
        if c == bench:
            continue
        r = df[c]
        cap_alta = 100 * r[alta].mean() / b[alta].mean()
        cap_baixa = 100 * r[baixa].mean() / b[baixa].mean()
        d = pd.DataFrame({"r": r, "b": b}).dropna()
        X = pd.DataFrame({"const": 1.0,
                          "b_alta": d["b"].where(d["b"] > 0, 0.0),
                          "b_baixa": d["b"].where(d["b"] <= 0, 0.0)})
        mod = sm.OLS(d["r"], X).fit(
            cov_type="HAC", cov_kwds={"maxlags": 8, "use_correction": True})
        linhas.append({
            "Carteira": ROT[c],
            "Captura de alta (%)": round(float(cap_alta), 1),
            "Captura de baixa (%)": round(float(cap_baixa), 1),
            "Razão alta/baixa": round(float(cap_alta / cap_baixa), 2),
            "Beta em alta": round(float(mod.params["b_alta"]), 3),
            "Beta em baixa": round(float(mod.params["b_baixa"]), 3),
        })
    return pd.DataFrame(linhas)


def fig_captura(cap: pd.DataFrame) -> None:
    """Captura de alta contra captura de baixa, num plano.

    Deixa a leitura imediata: acima da diagonal é assimetria
    favorável (captura mais alta do que baixa).
    """
    inv = {v: k for k, v in ROT.items()}
    fig, ax = plt.subplots(figsize=(7.4, 6.6))
    lim = (60, 115)
    ax.plot(lim, lim, color="#9AA09A", linewidth=1, linestyle="--", zorder=1)
    ax.fill_between(lim, lim, lim[0], color="#9E2B25", alpha=0.05, zorder=0)
    ax.fill_between(lim, lim, lim[1], color="#1E5945", alpha=0.05, zorder=0)
    ax.text(112, 66, "cai mais do que sobe", ha="right", fontsize=9,
            color="#9E2B25", style="italic")
    ax.text(64, 111, "sobe mais do que cai", fontsize=9,
            color="#1E5945", style="italic")
    for _, r in cap.iterrows():
        k = inv.get(r["Carteira"], "Uniao_TCC")
        x, y = r["Captura de baixa (%)"], r["Captura de alta (%)"]
        ax.scatter(x, y, s=95, color=COR.get(k, "#5B6570"),
                   edgecolor="white", linewidth=1.4, zorder=4)
        # rótulo acima ou abaixo conforme o lado da diagonal, para que
        # pontos vizinhos (ex.: Carteira do TCC e ISE B3) não colidam
        dy = 9 if y >= x else -12
        ax.annotate(r["Carteira"], (x, y), xytext=(9, dy),
                    textcoords="offset points", fontsize=9.2,
                    color=COR.get(k, "#5B6570"), fontweight="600")
    ax.scatter(100, 100, s=70, marker="s", color="#1A1D21", zorder=4)
    ax.annotate("IBrX-100", (100, 100), xytext=(9, -3),
                textcoords="offset points", fontsize=9.2, fontweight="600")
    ax.set_xlim(*lim)
    ax.set_ylim(*lim)
    ax.set_xlabel("Captura de baixa (%) — quanto pegou das quedas do índice")
    ax.set_ylabel("Captura de alta (%) — quanto pegou das altas")
    ax.set_title("Perfil de risco: o que cada carteira captura do mercado",
                 loc="left", fontsize=12.5, pad=12)
    fig.tight_layout()
    fig.savefig(DIR_FIG / "captura_alta_baixa.png")
    plt.close(fig)


def fig_crise_2020(df: pd.DataFrame) -> None:
    cols = ["Multifator", "Baixa_Vol", "Uniao_TCC", "ret_ibrx", "ret_ise"]
    jan = df.loc["2020-01-02":"2020-12-30", cols]
    pat = (1 + jan.fillna(0)).cumprod() * 100
    fundo = pat["ret_ibrx"].idxmin()

    fig, ax = plt.subplots(figsize=(11.5, 5.6))
    marca_covid(ax)
    for c in cols:
        bench = c in LINHA
        ax.plot(pat[c], color=COR[c], linestyle=LINHA.get(c, "-"),
                linewidth=1.3 if bench else 2.1, alpha=0.85 if bench else 1.0)
    # anota o fundo de cada série
    for c in ("Baixa_Vol", "ret_ibrx"):
        v = pat[c].loc[fundo]
        ax.scatter([fundo], [v], s=42, color=COR[c], zorder=5,
                   edgecolor="white", linewidth=1.2)
        ax.annotate(f"{v - 100:+.0f}%", (fundo, v), xytext=(-34, -4),
                    textcoords="offset points", fontsize=9.4,
                    color=COR[c], fontweight="600")
    ax.axhline(100, color="#555", linewidth=0.9)
    ax.margins(x=0.11)
    rotula_fim_varios(ax, [(pat[c], f"{ROT[c]}  {pat[c].iloc[-1]:.0f}", COR[c])
                           for c in cols])
    ax.set_ylabel("Base 100 em 02/01/2020")
    ax.set_title("Crise da COVID-19: quem caiu menos e quem voltou mais rápido",
                 loc="left", fontsize=13, pad=12)
    fig.text(0.012, 0.015,
             f"Faixa vermelha: do topo (23/01) ao fundo do IBrX-100 "
             f"({fundo.date().strftime('%d/%m')}). Os rótulos marcam a perda "
             f"acumulada no fundo.", fontsize=8.5, color="#61686D")
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    fig.savefig(DIR_FIG / "crise_2020.png")
    plt.close(fig)


# ──────────────────────────────────────────────────────────────
def main() -> None:
    df = carregar()
    cols = ["Multifator", "Baixa_Vol", "Uniao_TCC", "ret_ibrx", "ret_ise"]
    todas = ["Momentum", "Baixa_Vol", "Valor", "Qualidade", "Multifator",
             "Uniao_TCC", "ret_ibrx", "ret_ise"]

    print("=" * 90)
    print(f"  Apresentação dos resultados — {len(df)} pregões, "
          f"{df.index[0].date()} a {df.index[-1].date()}")
    print("=" * 90)

    # [4.1] e [4.2]
    fig_patrimonio_drawdown(df, "Multifator", "patrimonio_multifator.png")
    fig_patrimonio_drawdown(df, "Baixa_Vol", "patrimonio_baixa_vol.png")
    fig_patrimonio_por_fator(df)
    anual = fig_retornos_anuais(df)
    print("\n--- [4.2] Retorno por ano civil (%) ---")
    print(anual.to_string())
    anual.to_csv(DIR_DADOS / "retornos_anuais.csv", encoding="utf-8-sig")

    # [4.3]
    freq, larga = tabela_composicao()
    fig_persistencia()
    print("\n--- [4.3] Ações mais persistentes por carteira (top 5) ---")
    for e in ["Multifator", "Baixa_Vol", "Valor", "Qualidade", "Momentum"]:
        sub = freq[freq.Estrategia == e].head(5)
        itens = ", ".join(f"{r.Ticker} ({r.Anos}x)" for r in sub.itertuples())
        print(f"  {ROT[e]:16} {itens}")
    freq.to_csv(DIR_DADOS / "frequencia_acoes.csv", index=False, encoding="utf-8-sig")
    larga.to_csv(DIR_DADOS / "composicao_por_ano.csv", encoding="utf-8-sig")

    # [4.4]
    setor = distribuicao_setorial()
    fig_setorial(setor)
    setor.to_csv(DIR_DADOS / "distribuicao_setorial.csv", index=False, encoding="utf-8-sig")
    print("\n--- [4.4] Peso setorial médio no período (%) ---")
    piv = (setor.groupby(["Estrategia", "Setor"])["Peso"].mean().unstack(0)
                .fillna(0).round(1))
    piv["media"] = piv.mean(axis=1)
    piv = piv.sort_values("media", ascending=False).drop(columns="media").head(10)
    print(piv.to_string())

    # [4.5]
    est = tabela_estresse(df, cols)
    print("\n--- [4.5] Episódios de queda do IBrX-100 de 15% ou mais (%) ---")
    print(est.to_string(index=False))
    est.to_csv(DIR_DADOS / "periodos_estresse.csv", index=False, encoding="utf-8-sig")

    cap = capturas(df, todas)
    print("\n--- [4.5] Captura de alta e de baixa contra o IBrX-100 ---")
    print(cap.to_string(index=False))
    cap.to_csv(DIR_DADOS / "captura_alta_baixa.csv", index=False, encoding="utf-8-sig")
    fig_captura(cap)

    fig_crise_2020(df)

    print(f"\nFiguras em {DIR_FIG}")
    for f in ["patrimonio_multifator.png", "patrimonio_baixa_vol.png",
              "patrimonio_por_fator.png", "retornos_anuais.png",
              "crise_2020.png", "captura_alta_baixa.png",
              "distribuicao_setorial.png", "persistencia_carteiras.png"]:
        print(f"  {f}")


if __name__ == "__main__":
    main()
