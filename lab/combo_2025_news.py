"""2025 only: ATR 3/6 + VMM combo with and without a simple world-news event filter.

News windows (skip new entries / rebalances):
- DeepSeek AI shock: 2025-01-27 to 2025-01-31
- Liberation Day tariffs: 2025-04-02 to 2025-04-15

Reports starting $2000 equity at end of 2025 for:
  plain combo, news-filtered combo, and the two legs.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import candidates, sim, portfolio, indicators  # noqa: E402

SLOTS_ATR = 2
SLOTS_VMM = 10
START_CAP = 2000.0
YEAR = 2025

# World-news / stress windows in 2025 (skip new risk)
NEWS_WINDOWS = [
    ("2025-01-27", "2025-01-31"),  # DeepSeek
    ("2025-04-02", "2025-04-15"),  # Liberation Day tariffs
]


def in_news(dt):
    d = pd.Timestamp(dt).normalize()
    for a, b in NEWS_WINDOWS:
        if pd.Timestamp(a) <= d <= pd.Timestamp(b):
            return True
    return False


def vmm_curve(I, skip_news=False):
    C = I["C"]
    dates = C.index
    r12 = C.pct_change(252)
    above = C > I["sma200"]
    mkt = I["mkt_up"].reindex(dates).fillna(False)
    liquid = I["liquid"]
    month_ends = C.resample("ME").last().index
    equity = 1.0
    curve = {}
    for i, me in enumerate(month_ends):
        if me not in C.index:
            loc = dates[dates <= me]
            if len(loc) == 0:
                continue
            me = loc[-1]
        if not bool(mkt.loc[me]) or (skip_news and in_news(me)):
            curve[me] = equity
            continue
        rr = r12.loc[me]
        ok = above.loc[me] & liquid.loc[me] & rr.notna()
        ok = ok & (rr.index != "XIU.TO")
        ranked = rr[ok].nlargest(max(1, int(0.1 * ok.sum())))
        picks = list(ranked.index[:SLOTS_VMM])
        if not picks:
            curve[me] = equity
            continue
        if i + 1 < len(month_ends):
            nxt = month_ends[i + 1]
            loc = dates[dates <= nxt]
            nxt = loc[-1] if len(loc) else me
        else:
            nxt = dates[-1]
        rets = []
        for t in picks:
            if me in C.index and nxt in C.index and pd.notna(C.at[me, t]) and pd.notna(C.at[nxt, t]):
                rets.append(C.at[nxt, t] / C.at[me, t] - 1)
        if rets:
            equity *= (1 + np.mean(rets))
        curve[me] = equity
    return pd.Series(curve).sort_index()


def main():
    I = candidates.prep()
    dates = I["C"].index.values
    # restrict to 2025 for reporting (signals can use prior history for indicators)
    mask_2025 = (pd.to_datetime(dates) >= "2025-01-01") & (pd.to_datetime(dates) <= "2025-12-31")

    # ATR 3/6
    s2, rs, r2, liq, mk = I["stage2"], I["rs_rank"], I["rsi2"], I["liquid"], I["mktc"]
    lead = (s2 & (rs > 0.8) & (r2 < 10) & liq & mk).fillna(False)

    def run_atr(skip_news=False):
        sg = lead.copy()
        if skip_news:
            for i, dt in enumerate(dates):
                if in_news(dt):
                    sg.iloc[i] = False
        ti, ei, xi, r = sim.simulate(I, sg, mode=0, stop_atr=3, tgt_atr=6, hold=30)
        # keep only 2025 entries for the portfolio curve start
        keep = mask_2025[ei]
        ti, ei, xi, r = ti[keep], ei[keep], xi[keep], r[keep]
        if len(r) == 0:
            return None, 0
        rank = I["rs_rank"].values[ei, ti]
        p = portfolio.run(dates, ti, ei + 1, xi, r, rank=rank, slots=SLOTS_ATR, start="2025-01-01")
        return p, len(r)

    p_plain, n_plain = run_atr(False)
    p_news, n_news = run_atr(True)

    # VMM for 2025
    vmm_plain = vmm_curve(I, skip_news=False)
    vmm_news = vmm_curve(I, skip_news=True)
    # restrict to 2025
    vmm_plain = vmm_plain[(vmm_plain.index >= "2025-01-01") & (vmm_plain.index <= "2025-12-31")]
    vmm_news = vmm_news[(vmm_news.index >= "2025-01-01") & (vmm_news.index <= "2025-12-31")]

    def final_eq(curve_or_p, label):
        if curve_or_p is None:
            return 1.0
        if isinstance(curve_or_p, dict):
            return float(curve_or_p["final"])
        s = curve_or_p
        if len(s) == 0:
            return 1.0
        return float(s.iloc[-1] / s.iloc[0]) if s.iloc[0] != 0 else 1.0

    atr_plain_f = final_eq(p_plain, "atr")
    atr_news_f = final_eq(p_news, "atr_news")
    vmm_plain_f = final_eq(vmm_plain, "vmm")
    vmm_news_f = final_eq(vmm_news, "vmm_news")

    # simple 50/50 on the 2025 multiples
    combo_plain = (atr_plain_f + vmm_plain_f) / 2
    combo_news = (atr_news_f + vmm_news_f) / 2

    rows = [
        {"version": "ATR 3/6 plain", "trades": n_plain, "multiple": atr_plain_f, "equity_2000": round(START_CAP * atr_plain_f, 2)},
        {"version": "ATR 3/6 + news filter", "trades": n_news, "multiple": atr_news_f, "equity_2000": round(START_CAP * atr_news_f, 2)},
        {"version": "VMM plain", "trades": "", "multiple": vmm_plain_f, "equity_2000": round(START_CAP * vmm_plain_f, 2)},
        {"version": "VMM + news filter", "trades": "", "multiple": vmm_news_f, "equity_2000": round(START_CAP * vmm_news_f, 2)},
        {"version": "50/50 combo plain", "trades": "", "multiple": combo_plain, "equity_2000": round(START_CAP * combo_plain, 2)},
        {"version": "50/50 combo + news filter", "trades": "", "multiple": combo_news, "equity_2000": round(START_CAP * combo_news, 2)},
    ]
    out = pd.DataFrame(rows)
    os.makedirs("lab/results", exist_ok=True)
    out.to_csv("lab/results/combo_2025_news.csv", index=False)
    print(out.to_string(index=False))
    print("\nNews windows skipped: DeepSeek (Jan 27-31), Liberation Day (Apr 2-15)")


if __name__ == "__main__":
    main()
