"""Recompute lab/results/strategy_card.json (shown at the top of the daily report)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, pandas as pd
import candidates, sim, portfolio

I = candidates.prep(); dates = I["C"].index.values
s2, rs, r2, liq, mk, tom = I["stage2"], I["rs_rank"], I["rsi2"], I["liquid"], I["mktc"], I["tom"]
lead = (s2 & (rs > .8) & (r2 < 10) & liq & mk).fillna(False)
card = {}
for key, sg, kw in [("leader_pullback", lead, dict(stop_atr=3, tgt_atr=6, hold=30)),
                    ("month_end_bounce", (lead & tom).fillna(False), dict(mr=1, stop_pct=.08, hold=10)),
                    ("your_3_1_rule", lead, dict(tgt_pct=.03, stop_pct=.01, hold=10))]:
    ti, ei, xi, r = sim.simulate(I, sg, mode=0, **kw)
    p = portfolio.run(dates, ti, ei + 1, xi, r, rank=I["rs_rank"].values[ei, ti], slots=5)
    tr = dates[ei + 1] < np.datetime64("2019-01-01"); w = r > 0
    yr = p["curve"].resample("YE").last()
    yret = yr.pct_change().fillna(yr.iloc[0] - 1)
    card[key] = dict(trades=int(len(r)), win=float(w.mean()), avg=float(r.mean()),
                     avg_win=float(r[w].mean()), avg_loss=float(r[~w].mean()), hold=float((xi - ei).mean()),
                     win_train=float(w[tr].mean()), win_test=float(w[~tr].mean()),
                     avg_train=float(r[tr].mean()), avg_test=float(r[~tr].mean()),
                     cagr=p["cagr"], monthly=p["monthly"], max_dd=p["max_dd"], win_months=p["win_months"],
                     worst_month=p["worst_month"], losing_years=int((yret < 0).sum()), years=int(len(yret)))
xic = I["C"]["XIC.TO"].dropna(); m = xic.resample("ME").last().pct_change().dropna()
card["xic_buy_hold"] = dict(cagr=float((xic.iloc[-1] / xic.iloc[0]) ** (12 / len(m)) - 1),
                            max_dd=float(-(xic / xic.cummax() - 1).min()), win_months=float((m > 0).mean()))
card["period"] = f"{pd.Timestamp(dates[0]).date()} to {pd.Timestamp(dates[-1]).date()}"
card["universe"] = int(I["C"].shape[1] - 2)
json.dump(card, open("lab/results/strategy_card.json", "w"), indent=1)
print(json.dumps(card["leader_pullback"], indent=1))
