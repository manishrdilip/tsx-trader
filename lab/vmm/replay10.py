"""VMM v1 10-year paper-trade replay (Nov 2016 to Oct 2026). Rules = claude/vm-momentum-plan-v1.md, unchanged.
Account: $5,000 start + $100 deposited on the first trading day of each month. Whole shares, cash kept.
Momentum sleeve: v3 rules, signals after close, fills at NEXT day's close, 0.5%/side.
Small-account rule: momentum slots = 5 while sleeve < $2,000, 10 while < $5,000, else 20.
Monthly (first trading day): momentum share = vol60(XIU) / vol60(sleeve), cap 100% (50% until 60 days of history).
Rebalance by trading whole XIU shares; sleeve gets/gives cash (if sleeve lacks cash, it sells its weakest holdings).
XIU part also earns ~3%/yr dividends, paid monthly into cash.
Outputs: trades.csv, monthly.csv, yearly table, final holdings. Same data caveat: survivors only, chosen on this data.
"""
import sys, numpy as np, pandas as pd

P = pd.read_parquet(sys.argv[1] if len(sys.argv) > 1 else "prices.parquet")
P["Date"] = pd.to_datetime(P["Date"]); P = P.drop_duplicates(["ticker", "Date"])
xiu = P[P.ticker == "XIU.TO"].set_index("Date")["Close"].sort_index()
S = P[P.ticker.str.endswith(".TO") & ~P.ticker.isin(["XIU.TO", "XIC.TO"])]
bad = S.groupby("ticker")["Close"].min() <= 0; S = S[~S.ticker.isin(bad[bad].index)]
mv = S.sort_values("Date").groupby("ticker")["Close"].pct_change().abs()
S = S[~S.ticker.isin(S.loc[mv > 0.40, "ticker"].unique())]
C = S.pivot(index="Date", columns="ticker", values="Close").sort_index()
V = S.pivot(index="Date", columns="ticker", values="Volume").reindex(C.index)
idx = C.index[C.index >= "2015-01-01"]; C, V = C.loc[idx].ffill(limit=5), V.loc[idx]
xiu = xiu.reindex(idx).ffill()
DV = (C * V).rolling(20, min_periods=15).median(); S200 = C.rolling(200, min_periods=200).mean()
R12 = C / C.shift(252) - 1; X200 = xiu.rolling(200).mean()
Cv, Sv, Dv, Rv, tick = C.values, S200.values, DV.values, R12.values, np.array(C.columns)
start = np.searchsorted(idx, pd.Timestamp("2016-11-01"))
COST = 0.005

cash, pos, xsh = 5000.0, {}, 0          # account cash, {col: shares}, XIU shares
deposits = 5000.0; sleeve_cash = 0.0     # cash earmarked for momentum
trades, monthly = [], []; pend_buy, pend_sell = [], []
hist_s, hist_x, prev_sleeve, prev_x = [], [], None, None

def sleeve_val(px): return sleeve_cash + sum(s * px[j] for j, s in pos.items() if not np.isnan(px[j]))
def log(d, side, tk, sh, price, why):
    trades.append(dict(date=idx[d].date(), side=side, ticker=tk, shares=int(sh), price=round(float(price), 2),
                       value=round(float(sh * price), 2), reason=why))

for d in range(start, len(idx)):
    px, xp = Cv[d], xiu.iat[d]
    # 1) fills at today's close
    for j in pend_sell:
        if j in pos and not np.isnan(px[j]):
            sh = pos.pop(j); sleeve_cash += sh * px[j] * (1 - COST); log(d, "SELL", tick[j], sh, px[j], "rule exit")
    sv = sleeve_val(px); slots = 5 if sv < 2000 else (10 if sv < 5000 else 20)
    for j in pend_buy:
        if len(pos) >= slots or j in pos or np.isnan(px[j]): continue
        amt = min(sv / slots, sleeve_cash); sh = int(amt // (px[j] * (1 + COST)))
        if sh >= 1:
            pos[j] = sh; sleeve_cash -= sh * px[j] * (1 + COST); log(d, "BUY", tick[j], sh, px[j], "momentum signal")
    pend_buy, pend_sell = [], []
    # 1b) daily returns BEFORE any money moves today (flow-free) for the vol ratio
    sv0 = sleeve_val(px)
    if prev_sleeve: hist_s.append(sv0 / prev_sleeve - 1)
    if prev_x: hist_x.append(xp / prev_x - 1)
    # 2) month start: deposit, dividends, rebalance
    if d == start or idx[d].month != idx[d - 1].month:
        if d != start: cash += 100; deposits += 100
        cash += xsh * xp * 0.03 / 12
        sv = sleeve_val(px); total = cash + sv + xsh * xp
        if len(hist_s) >= 60:
            ss, sx = np.std(hist_s[-60:]), np.std(hist_x[-60:]); w = min(1.0, sx / ss) if ss > 0 else 1.0
        else: w = 0.5
        target_s = total * w
        if sv > target_s:  # move money out of sleeve
            need = sv - target_s
            if sleeve_cash < need:  # sell weakest holdings until enough cash
                for j in sorted(pos, key=lambda j: Rv[d][j] if not np.isnan(Rv[d][j]) else -9):
                    if sleeve_cash >= need: break
                    sh = pos.pop(j); sleeve_cash += sh * px[j] * (1 - COST); log(d, "SELL", tick[j], sh, px[j], "monthly rebalance")
            mvd = min(need, sleeve_cash); sleeve_cash -= mvd; cash += mvd
        else:
            mvd = min(target_s - sv, cash); cash -= mvd; sleeve_cash += mvd
        tx = int((total - target_s) // xp); dx = tx - xsh
        if dx > 0:
            dx = min(dx, int(cash // (xp * (1 + COST))))
        if dx != 0:
            if dx > 0: cash -= dx * xp * (1 + COST)
            else: cash += -dx * xp * (1 - COST)
            xsh += dx; log(d, "BUY" if dx > 0 else "SELL", "XIU.TO", abs(dx), xp, "monthly rebalance")
        # if XIU part couldn't absorb, park leftover cash back to sleeve
        sleeve_cash += cash; cash = 0.0
        monthly.append(dict(date=idx[d].date(), total=round(total), deposits=round(deposits), momentum_share=round(w * 100),
                            holdings=len(pos), xiu_shares=xsh))
    prev_sleeve, prev_x = sleeve_val(px), xp  # value AFTER today's money moves
    # 4) signals for tomorrow
    elig = (px >= 1) & (px <= 100) & (Dv[d] >= 3e5) & ~np.isnan(Rv[d])
    if elig.sum() < 20: continue
    er = Rv[d][elig]; rank = np.full(len(px), np.nan); rank[elig] = 1 - er.argsort().argsort() / (len(er) - 1)
    for j in pos:
        if np.isnan(px[j]) or px[j] <= Sv[d][j] or not (rank[j] <= 0.40): pend_sell.append(j)
    if xp > X200.iat[d]:
        cand = np.where(elig & (rank <= 0.10) & (px > Sv[d]))[0]
        cand = [j for j in cand[np.argsort(rank[cand])] if j not in pos]
        pend_buy = cand[:max(slots - (len(pos) - len(pend_sell)), 0)]

# XIU-only comparison with the same deposits
xc, xs, xd = 5000.0, 0.0, []
for d in range(start, len(idx)):
    if d == start or idx[d].month != idx[d - 1].month:
        if d != start: xc += 100
        xc += xs * xiu.iat[d] * 0.03 / 12
        b = int(xc // (xiu.iat[d] * (1 + COST))); xs += b; xc -= b * xiu.iat[d] * (1 + COST)
    xd.append(xc + xs * xiu.iat[d])
xonly = pd.Series(xd, index=idx[start:])

px = Cv[-1]; final = sleeve_cash + cash + sum(s * px[j] for j, s in pos.items()) + xsh * xiu.iat[-1]
M = pd.DataFrame(monthly); T = pd.DataFrame(trades)
M["xiu_only"] = [round(xonly.loc[pd.Timestamp(d)]) for d in M.date]
M["date"] = pd.to_datetime(M["date"])
Y = M.groupby(M.date.dt.year).last()[["total", "xiu_only", "deposits", "momentum_share", "holdings"]]
eq = M.set_index("date")["total"]; xo = M.set_index("date")["xiu_only"]
print(f"PERIOD {idx[start].date()} to {idx[-1].date()}")
print(f"DEPOSITED ${deposits:,.0f} | VMM FINAL ${final:,.0f} | XIU-ONLY FINAL ${xonly.iat[-1]:,.0f}")
print(f"WORST DROP (month-end) VMM {((eq/eq.cummax())-1).min()*100:.1f}% | XIU {((xo/xo.cummax())-1).min()*100:.1f}%")
print(f"TRADES {len(T)} (stocks {len(T[T.ticker!='XIU.TO'])}, XIU {len(T[T.ticker=='XIU.TO'])}); per year ~{len(T)/10:.0f}")
st = T[(T.ticker != 'XIU.TO')]
print("\nYEAR-END (value at first trading day of last month of year)\n" + Y.to_string())
print("\nFINAL HOLDINGS:", ", ".join(f"{tick[j]} x{s}" for j, s in pos.items()), f"| XIU x{xsh} | cash ${sleeve_cash+cash:,.0f}")
print("\nLAST 15 TRADES\n" + T.tail(15).to_string(index=False))
import os; os.makedirs("results/vmm_replay10", exist_ok=True)
T.to_csv("results/vmm_replay10/trades.csv", index=False); M.to_csv("results/vmm_replay10/monthly.csv", index=False)
