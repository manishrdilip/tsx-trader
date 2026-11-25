"""ML opportunity discovery v1 — standalone research engine. See PREREGISTRATION.md.

Usage:
  python engine.py fetch      # download prices -> data/prices.pkl
  python engine.py dev        # run 48-setup grid on 2019-2022, pick one -> results/dev_grid.csv, chosen.json
  python engine.py eval       # run chosen ML setup + VMM once on 2023+ -> results/eval.md
"""
import json, os, sys
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "prices.pkl")
RES = os.path.join(HERE, "results")

CANDIDATES = """RY TD BNS BMO CM NA MFC SLF GWO IFC POW FFH ENB TRP CNQ SU CVE IMO TOU ARX CPG WCP MEG
PPL KEY CNR CP TFII WSP STN CAE BBD-B AC SHOP CSU OTEX GIB-A DSG BCE T RCI-B QBR-B ATD L MRU WN DOL CTC-A
SAP EMP-A ABX AEM K FNV WPM CCO TECK-B FM LUN NTR AGI ELD IMG BTO SSL MG IAG BAM BN BIP-UN BEP-UN FTS EMA
H AQN CU ALA CCL-B WFG IFP CAR-UN REI-UN""".split()
CANDIDATES = [c + ".TO" for c in CANDIDATES]
BENCH = "XIU.TO"
N_STOCKS = 50

START_CASH = 5000.0
COST = 0.005
SLOTS = 5
DEV = ("2019-01-01", "2022-12-31")
EVAL_START = "2023-01-01"


# ---------------------------------------------------------------- data
def fetch():
    import yfinance as yf
    os.makedirs(os.path.dirname(DATA), exist_ok=True)
    d = yf.download(CANDIDATES + [BENCH], start="2015-01-01", auto_adjust=True, progress=False, threads=True)
    d.to_pickle(DATA)
    print("saved", d.shape, d.index[0].date(), d.index[-1].date())


def load():
    d = pd.read_pickle(DATA)
    px = {f: d[f] for f in ["Open", "High", "Low", "Close", "Volume"]}
    dv = (px["Close"] * px["Volume"]).loc["2016":"2018"].median()
    ok = [t for t in CANDIDATES if t in dv.index and px["Close"][t].loc[:"2016-01-31"].notna().sum() > 200]
    uni = dv[ok].sort_values(ascending=False).index[:N_STOCKS].tolist()
    return px, uni


# ---------------------------------------------------------------- features
def features(px, uni):
    C, O, H, L, V = (px[k] for k in ["Close", "Open", "High", "Low", "Volume"])
    xiu = C[BENCH]
    rows = []
    for t in uni:
        c, o, h, l, v = C[t], O[t], H[t], L[t], V[t]
        f = pd.DataFrame(index=C.index)
        for n in [1, 5, 10, 20, 60, 120, 250]:
            f[f"r{n}"] = c.pct_change(n, fill_method=None)
        for n in [20, 50, 200]:
            f[f"sma{n}"] = c / c.rolling(n).mean() - 1
        lr = np.log(c).diff()
        f["vol20"] = lr.rolling(20).std()
        f["vol60"] = lr.rolling(60).std()
        tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
        f["atr14"] = tr.rolling(14).mean() / c
        f["vrel"] = v / v.rolling(20).mean()
        f["ldv"] = np.log1p((c * v).rolling(20).mean())
        hi, lo = c.rolling(20).max(), c.rolling(20).min()
        f["pos20"] = (c - lo) / (hi - lo)
        f["gap"] = o / c.shift() - 1
        f["mkt60"] = xiu.pct_change(60, fill_method=None)
        f["mktup"] = (xiu > xiu.rolling(200).mean()).astype(float)
        # forward return from next open to close H days later (labels only)
        for hd in [5, 10]:
            f[f"fwd{hd}"] = c.shift(-hd) / o.shift(-1) - 1
        f["ticker"] = t
        rows.append(f)
    F = pd.concat(rows).reset_index(names="date")
    feats = [c for c in F.columns if c not in ("date", "ticker", "fwd5", "fwd10")]
    F = F.replace([np.inf, -np.inf], np.nan).dropna(subset=feats)
    return F, feats


def make_model(kind):
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import HistGradientBoostingClassifier
    if kind == "logit":
        return make_pipeline(StandardScaler(), LogisticRegression(C=0.1, max_iter=2000))
    return HistGradientBoostingClassifier(max_iter=200, learning_rate=0.05, max_depth=3,
                                          min_samples_leaf=200, random_state=0)


def walk_forward_probs(F, feats, k, kind, hold, years):
    """Yearly expanding-window retrain. Training rows end hold+1 trading days before the year starts."""
    lab = f"fwd{hold}"
    dates = np.sort(F["date"].unique())
    out = []
    for y in years:
        start = pd.Timestamp(f"{y}-01-01")
        idx = np.searchsorted(dates, start)
        if idx <= hold + 1:
            continue
        cutoff = dates[idx - hold - 1]
        tr = F[(F["date"] < cutoff) & F[lab].notna()]
        te = F[(F["date"] >= start) & (F["date"] < pd.Timestamp(f"{y + 1}-01-01"))]
        if te.empty:
            continue
        m = make_model(kind)
        m.fit(tr[feats].values, (tr[lab] > k).astype(int).values)
        p = te[["date", "ticker"]].copy()
        p["p"] = m.predict_proba(te[feats].values)[:, 1]
        out.append(p)
    P = pd.concat(out)
    return P.pivot(index="date", columns="ticker", values="p")


# ---------------------------------------------------------------- portfolio engine
class Book:
    def __init__(self):
        self.cash = START_CASH
        self.pos = {}      # t -> dict(sh, entry_px, entry_cost, day_in, peak)
        self.trades = []   # net P/L per closed trade
        self.eq = {}

    def equity(self, closes):
        return self.cash + sum(p["sh"] * closes[t] for t, p in self.pos.items() if np.isfinite(closes[t]))

    def buy(self, t, px, budget, i):
        if not np.isfinite(px) or px <= 0:
            return
        sh = int(min(budget, self.cash) // (px * (1 + COST)))
        if sh < 1:
            return
        cost = sh * px * (1 + COST)
        self.cash -= cost
        self.pos[t] = dict(sh=sh, cost=cost, i=i, peak=px)

    def sell(self, t, px):
        p = self.pos.pop(t)
        if not np.isfinite(px):
            raise ValueError(f"no price to sell {t}")
        got = p["sh"] * px * (1 - COST)
        self.cash += got
        self.trades.append(got - p["cost"])


def last_valid(series_row_func):
    return series_row_func


def run_ml(px, uni, P, thr, hold, start, end):
    C, O = px["Close"][uni], px["Open"][uni]
    days = C.loc[start:end].index
    b = Book()
    pending_buys, pending_sells = [], []
    for i, d in enumerate(days):
        o, c = O.loc[d], C.loc[d]
        # execute at today's open (decided at yesterday's close)
        for t in pending_sells:
            px_ = o[t] if np.isfinite(o[t]) else c[t]
            if np.isfinite(px_):
                b.sell(t, px_)
        eq_open = b.cash + sum(p["sh"] * (o[t] if np.isfinite(o[t]) else c[t]) for t, p in b.pos.items())
        for t in pending_buys:
            if len(b.pos) < SLOTS and t not in b.pos:
                b.buy(t, o[t], eq_open / SLOTS, i)
        pending_buys, pending_sells = [], []
        b.eq[d] = b.equity(c.ffill() if False else c.fillna(C.loc[:d].ffill().iloc[-1]))
        # decide at close
        for t, p in b.pos.items():
            if i - p["i"] >= hold - 1:
                pending_sells.append(t)
        free = SLOTS - len(b.pos) + len(pending_sells)
        if d in P.index and free > 0:
            row = P.loc[d].dropna().sort_values(ascending=False)
            for t, pr in row.items():
                if pr < thr or free == 0:
                    break
                if t in b.pos or t in pending_buys:
                    continue
                pending_buys.append(t)
                free -= 1
    return b


def run_vmm(px, uni, start, end):
    C, O = px["Close"][uni], px["Open"][uni]
    xiu = px["Close"][BENCH]
    r12 = C.pct_change(252, fill_method=None)
    sma = C.rolling(200).mean()
    xok = xiu > xiu.rolling(200).mean()
    days = C.loc[start:end].index
    b = Book()
    pend_b, pend_s = [], []
    for i, d in enumerate(days):
        o, c = O.loc[d], C.loc[d]
        for t in pend_s:
            px_ = o[t] if np.isfinite(o[t]) else c[t]
            if np.isfinite(px_):
                b.sell(t, px_)
        eq_open = b.cash + sum(p["sh"] * (o[t] if np.isfinite(o[t]) else c[t]) for t, p in b.pos.items())
        for t in pend_b:
            if len(b.pos) < SLOTS and t not in b.pos:
                b.buy(t, o[t], eq_open / SLOTS, i)
        pend_b, pend_s = [], []
        b.eq[d] = b.equity(c.fillna(C.loc[:d].ffill().iloc[-1]))
        r = r12.loc[d].dropna()
        if r.empty:
            continue
        top10, top40 = r.quantile(0.9), r.quantile(0.6)
        for t, p in b.pos.items():
            if not np.isfinite(c[t]):
                continue
            p["peak"] = max(p["peak"], c[t])
            if c[t] < sma.loc[d, t] or r.get(t, np.nan) < top40 or c[t] < p["peak"] * 0.72:
                pend_s.append(t)
        free = SLOTS - len(b.pos) + len(pend_s)
        if xok.loc[d] and free > 0:
            for t in r[(r >= top10)].sort_values(ascending=False).index:
                if free == 0:
                    break
                if t in b.pos or not (c[t] > sma.loc[d, t]):
                    continue
                pend_b.append(t)
                free -= 1
    return b


def metrics(b):
    eq = pd.Series(b.eq)
    rets = eq.pct_change().dropna()
    yrs = (eq.index[-1] - eq.index[0]).days / 365.25
    tr = np.array(b.trades)
    gains, losses = tr[tr > 0].sum(), -tr[tr < 0].sum()
    return {
        "end_equity": eq.iloc[-1],
        "net_profit": eq.iloc[-1] - START_CASH,
        "cagr": (eq.iloc[-1] / START_CASH) ** (1 / yrs) - 1,
        "max_dd": (eq / eq.cummax() - 1).min(),
        "sharpe": rets.mean() / rets.std() * np.sqrt(252) if rets.std() > 0 else 0.0,
        "profit_factor": gains / losses if losses > 0 else float("inf"),
        "trades": len(tr),
        "open_positions": len(b.pos),
    }


GRID = [(k, m, thr, h) for k in [0.01, 0.02, 0.03, 0.05] for m in ["logit", "gbt"]
        for thr in [0.55, 0.60, 0.65] for h in [5, 10]]


def dev():
    px, uni = load()
    F, feats = features(px, uni)
    os.makedirs(RES, exist_ok=True)
    cache, rows = {}, []
    for k, m, thr, h in GRID:
        key = (k, m, h)
        if key not in cache:
            cache[key] = walk_forward_probs(F, feats, k, m, h, range(2019, 2023))
        b = run_ml(px, uni, cache[key], thr, h, *DEV)
        r = dict(k=k, model=m, thr=thr, hold=h, **metrics(b))
        rows.append(r)
        print({x: (round(v, 3) if isinstance(v, float) else v) for x, v in r.items()})
    G = pd.DataFrame(rows)
    G.to_csv(os.path.join(RES, "dev_grid.csv"), index=False)
    ok = G[G["trades"] >= 30].sort_values(["sharpe", "trades"], ascending=[False, True])
    ch = ok.iloc[0][["k", "model", "thr", "hold"]].to_dict()
    ch["hold"] = int(ch["hold"])
    json.dump({"chosen": ch, "universe": uni}, open(os.path.join(RES, "chosen.json"), "w"), indent=1)
    print("CHOSEN", ch)


def evaluate():
    px, uni = load()
    cfg = json.load(open(os.path.join(RES, "chosen.json")))
    assert cfg["universe"] == uni, "universe changed since dev"
    ch = cfg["chosen"]
    F, feats = features(px, uni)
    end = px["Close"].index[-1]
    P = walk_forward_probs(F, feats, ch["k"], ch["model"], ch["hold"], range(2023, end.year + 1))
    ml = metrics(run_ml(px, uni, P, ch["thr"], ch["hold"], EVAL_START, end))
    vm = metrics(run_vmm(px, uni, EVAL_START, end))
    xiu = px["Close"][BENCH].loc[EVAL_START:end]
    fmt = {
        "Starting capital": lambda m: "$5,000",
        "Trading cost per side": lambda m: "0.5%",
        "Evaluation period": lambda m: f"{xiu.index[0].date()} to {end.date()}",
        "Net profit": lambda m: f"${m['net_profit']:,.0f}",
        "CAGR": lambda m: f"{m['cagr']*100:.1f}%",
        "Maximum drawdown": lambda m: f"{m['max_dd']*100:.1f}%",
        "Sharpe ratio": lambda m: f"{m['sharpe']:.2f}",
        "Profit factor": lambda m: f"{m['profit_factor']:.2f}",
        "Total trades": lambda m: f"{m['trades']} (+{m['open_positions']} open)",
    }
    lines = ["| Metric | VMM | ML strategy |", "|---|---|---|"]
    lines += [f"| {n} | {f(vm)} | {f(ml)} |" for n, f in fmt.items()]
    md = "\n".join(lines)
    md += f"\n\nChosen ML setup (from 2019-2022 only): {ch}\n"
    md += f"XIU buy-and-hold over the same period: {(xiu.iloc[-1]/xiu.iloc[0]-1)*100:.1f}% (no costs)\n"
    open(os.path.join(RES, "eval.md"), "w").write(md)
    json.dump({"vmm": vm, "ml": ml, "chosen": ch}, open(os.path.join(RES, "eval.json"), "w"), indent=1, default=float)
    print(md)


if __name__ == "__main__":
    {"fetch": fetch, "dev": dev, "eval": evaluate}[sys.argv[1]]()
