"""Turn a list of trades into a realistic account curve.
Rules: max `slots` positions at once, each gets 1/slots of equity at entry.
When more signals than free slots appear on one day, take the highest `rank` first.
Reports monthly return, % winning months, max drawdown."""
import numpy as np
import pandas as pd


def run(dates, ti, ei, xi, r, rank=None, slots=5, start=None):
    df = pd.DataFrame({"t": ti, "e": ei, "x": xi, "r": r,
                       "k": rank if rank is not None else np.zeros(len(r))})
    if start is not None:
        df = df[dates[df.e.values] >= np.datetime64(start)]
    df = df.sort_values(["e", "k"], ascending=[True, False])
    equity = 1.0
    open_pos = []                    # (exit_idx, stake, ret)
    daily = {}
    for e, grp in df.groupby("e", sort=True):
        # close positions that exited before this entry day
        still = []
        for x, stake, rr in open_pos:
            if x < e:
                equity += stake * rr
                daily[x] = equity
            else:
                still.append((x, stake, rr))
        open_pos = still
        for _, row in grp.iterrows():
            if len(open_pos) >= slots:
                break
            stake = equity / slots
            open_pos.append((int(row.x), stake, float(row.r)))
    for x, stake, rr in sorted(open_pos):
        equity += stake * rr
        daily[x] = equity
    if not daily:
        return None
    s = pd.Series(daily).sort_index()
    s.index = pd.to_datetime(dates[s.index.values])
    s = s.groupby(level=0).last()
    m = s.resample("ME").last().ffill()
    m = pd.concat([pd.Series([1.0], index=[m.index[0] - pd.offsets.MonthEnd(1)]), m])
    mr = m.pct_change().dropna()
    dd = (s / s.cummax() - 1).min()
    months = len(mr)
    return dict(final=float(s.iloc[-1]), cagr=float(s.iloc[-1] ** (12 / max(months, 1)) - 1),
                monthly=float(s.iloc[-1] ** (1 / max(months, 1)) - 1),
                win_months=float((mr > 0).mean()), max_dd=float(-dd), months=months,
                worst_month=float(mr.min()), curve=s, monthly_series=mr)
