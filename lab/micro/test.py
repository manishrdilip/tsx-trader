"""Clean intraday (micro) trading test. Rules FIXED before seeing results; no tuning.
Long only, one trade per stock per day per strategy, flat by close. Fills at next bar open.
Costs per round trip: TSX 0.10%, NSE 0.12% (brokerage+STT+charges+slippage, large caps)."""
import sys, numpy as np, pandas as pd
COST = {'.TO': 0.0010, '.NS': 0.0012}
def day_groups(df):
    parts = []
    for mk, tz, a, b in [('.TO', 'America/Toronto', '09:30', '15:59'), ('.NS', 'Asia/Kolkata', '09:15', '15:29')]:
        x = df[df.sym.str.endswith(mk)].copy(); x.index = pd.DatetimeIndex(x.index).tz_convert(tz)
        x = x.between_time(a, b); x['d'] = x.index.date; x.index = range(len(x)); parts.append(x)
    df = pd.concat(parts)
    return df.groupby(['sym', 'd'])
def trades_for(g, strat, iv):
    o, h, l, c, v = (g[k].values for k in ['Open', 'High', 'Low', 'Close', 'Volume'])
    n = len(c); out = []
    if n < 30: return out
    last = n - (3 if iv == '5m' else 15)                  # flat ~15 min before close
    if strat == 'ORB':                                    # 15-min opening range breakout
        k = 3 if iv == '5m' else 15
        hi, lo = h[:k].max(), l[:k].min()
        for i in range(k, last):
            if c[i] > hi:
                e = o[i + 1]; stop = lo
                for j in range(i + 1, last + 1):
                    if l[j] <= stop: return [(min(stop, o[j]) / e - 1)]
                return [(c[last] / e - 1)]
    if strat == 'VWAP':                                   # buy 1% below VWAP, exit at VWAP, stop -1%
        tp = (h + l + c) / 3; vw = np.cumsum(tp * v) / np.maximum(np.cumsum(v), 1)
        for i in range(6, last):
            if c[i] < vw[i] * 0.99:
                e = o[i + 1]
                for j in range(i + 1, last + 1):
                    if l[j] <= e * 0.99: return [-0.01]
                    if h[j] >= vw[j]: return [vw[j] / e - 1]
                return [c[last] / e - 1]
    if strat == 'BURST':                                  # big up bar on 2x volume, hold 30 min
        r = c[1:] / c[:-1] - 1; hold = 6 if iv == '5m' else 30
        for i in range(20, last - 1):
            sd = r[max(0, i - 60):i - 1].std(); va = v[max(0, i - 20):i].mean()
            if sd > 0 and r[i - 1] > 2.5 * sd and v[i] > 2 * va:
                e = o[i + 1]; x = min(i + 1 + hold, last)
                return [c[x] / e - 1]
    if strat == 'RSI2':                                   # RSI(2) < 5 buy, exit RSI > 70 or 20 bars
        d = np.diff(c, prepend=c[0]); up = pd.Series(np.clip(d, 0, None)).ewm(alpha=.5).mean().values
        dn = pd.Series(np.clip(-d, 0, None)).ewm(alpha=.5).mean().values; rsi = 100 - 100 / (1 + up / np.maximum(dn, 1e-12))
        for i in range(10, last):
            if rsi[i] < 5:
                e = o[i + 1]
                for j in range(i + 1, min(i + 21, last) + 1):
                    if rsi[j] > 70: return [c[j] / e - 1]
                return [c[min(i + 21, last)] / e - 1]
    return out
rows = []
for iv in ['1m', '5m']:
    df = pd.read_parquet(f'data/bars_{iv}.parquet').dropna()
    df = df[df.Volume > 0]
    for strat in ['ORB', 'VWAP', 'BURST', 'RSI2']:
        for (s, d), g in day_groups(df):
            for r in trades_for(g, strat, iv):
                mk = s[-3:]; rows.append((iv, strat, mk, d, r, r - COST[mk]))
T = pd.DataFrame(rows, columns=['iv', 'strat', 'mkt', 'd', 'gross', 'net'])
T.to_csv('results_trades.csv', index=False)
def stats(x):
    n = len(x); m = x.net.mean(); se = x.net.std() / np.sqrt(n) if n > 1 else np.nan
    daily = x.groupby('d').net.mean()                     # equal-weight book per day
    return pd.Series(dict(trades=n, gross_bp=x.gross.mean() * 1e4, net_bp=m * 1e4, t=m / se if se else np.nan,
                          win=(x.net > 0).mean() * 100, days=len(daily), book_total=(1 + daily).prod() - 1))
S = T.groupby(['iv', 'strat', 'mkt']).apply(stats).round(2)
print(S.to_string())
open('results.md', 'w').write(S.to_markdown())
