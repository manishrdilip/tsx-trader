"""
LEADER PULLBACK - the setup that survived 18 years of TSX testing (see lab/ and PLAYBOOK.md).

Signal (all at today's close, real operating companies only - no ETFs/CDRs/BetaPro):
  1. Stage-2 uptrend (Minervini trend template): close > 50d > 150d > 200d SMA,
     200d rising for a month, >= 30% above 52-week low, within 25% of 52-week high
  2. Relative-strength leader: top 20% of liquid Canadian stocks (IBD-style 3/6/9/12-month RS)
  3. Short-term dip: RSI(2) < 10 (Connors)
  4. TSX itself above its 200-day average (XIU)
  5. Liquid: >= $1M traded per day, price >= $2
Trade: buy next open (skip if it opens > 2% above today's close);
       stop = 3 x ATR(14) below entry, target = 6 x ATR(14) above entry, exit at close after 30 trading days.
Sizing tested: up to 5 positions, 1/5 of the account each, strongest RS first.

"Month-end bounce" variant (higher win rate, much smaller profit): same signal inside the last
5 trading days of the month, exit at the first close above the 5-day SMA, stop -8%, max 10 days.
Research only - not financial advice.
"""
import json
import os

import numpy as np
import pandas as pd

import stock_filter

MARKET = "XIU.TO"
STOP_ATR, TGT_ATR, HOLD = 3.0, 6.0, 30
MAX_GAP = 0.02
SLOTS = int(os.environ.get("SLOTS", "2"))    # $100 account: 2 positions of $50 (best tested)
CARD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lab", "results", "strategy_card.json")


def _panel(data):
    keys = ("Open", "High", "Low", "Close", "Volume")
    return {k: pd.DataFrame({t: d[k] for t, d in data.items()}).sort_index().astype("float64") for k in keys}


def _rsi(c, n):
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def signals(data):
    """data: {ticker: OHLCV DataFrame}. Returns DataFrame of today's leader-pullback signals."""
    if MARKET not in data:
        raise ValueError("market ETF missing from download")
    stocks = {t: d for t, d in data.items() if t == MARKET or stock_filter.is_stock(t)}
    P = _panel(stocks)
    O, H, L, C, V = (P[k] for k in ("Open", "High", "Low", "Close", "Volume"))
    sma = lambda n: C.rolling(n, min_periods=n).mean()
    s50, s150, s200 = sma(50), sma(150), sma(200)
    hi252, lo252 = H.rolling(252, min_periods=200).max(), L.rolling(252, min_periods=200).min()
    stage2 = ((C > s50) & (s50 > s150) & (s150 > s200) & (s200 > s200.shift(21))
              & (C >= 1.3 * lo252) & (C >= 0.75 * hi252))
    dvol = (C * V).rolling(20).mean()
    liquid = (dvol >= 1_000_000) & (C >= 2)
    rs_raw = (0.4 * C.pct_change(63) + 0.2 * C.pct_change(126)
              + 0.2 * C.pct_change(189) + 0.2 * C.pct_change(min(252, len(C) - 1)))
    rs = rs_raw.where(liquid).drop(columns=[MARKET], errors="ignore").rank(axis=1, pct=True)
    rsi2 = _rsi(C, 2)
    pc = C.shift(1)
    tr = np.maximum(H - L, np.maximum((H - pc).abs(), (L - pc).abs()))
    atr = tr.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    m = C[MARKET]
    mkt_up = bool(m.iloc[-1] > m.rolling(200).mean().iloc[-1])
    # last 5 trading days of the month (approximation for the live scan: calendar day >= 24)
    today = C.index[-1]
    month_end = today.day >= 24

    last = C.index[-1]
    rows = []
    for t in rs.columns:
        if not (bool(stage2.at[last, t]) and bool(liquid.at[last, t])):
            continue
        r = rs.at[last, t]
        if not (pd.notna(r) and r > 0.8 and rsi2.at[last, t] < 10):
            continue
        close, a = float(C.at[last, t]), float(atr.at[last, t])
        rows.append({
            "ticker": t, "company": stock_filter.company(t), "rs_rank": round(float(r) * 100),
            "rsi2": round(float(rsi2.at[last, t]), 1), "close": round(close, 2),
            "buy_max": round(close * (1 + MAX_GAP), 2),
            "stop_pct": STOP_ATR * a / close, "target_pct": TGT_ATR * a / close,
            "stop_loss": round(close - STOP_ATR * a, 2), "take_profit": round(close + TGT_ATR * a, 2),
            "exchange": "TSX Venture" if t.endswith(".V") else "TSX",
        })
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("rs_rank", ascending=False).reset_index(drop=True)
    return df, mkt_up, month_end, last.date()


def card():
    try:
        return json.load(open(CARD))
    except Exception:
        return None


def report(df, mkt_up, month_end, asof, account, earnings_soon=None):
    pct = lambda x: f"{x * 100:.1f}%"
    L = ["## ⭐ LEADER PULLBACK - the tested strategy (top section to act on)"]
    c = card()
    if c:
        lp, xb = c["leader_pullback"], c["xic_buy_hold"]
        L.append(f"_Backtest {c['period']}, {c['universe']} real TSX/TSXV companies, max {c.get('slots', 5)} positions:_ "
                 f"**{pct(lp['cagr'])}/yr** (≈{pct(lp['monthly'])}/month) vs XIC buy-and-hold {pct(xb['cagr'])}/yr · "
                 f"win rate {pct(lp['win'])} · avg win +{pct(lp['avg_win'])} / avg loss {pct(lp['avg_loss'])} · "
                 f"worst drawdown {pct(lp['max_dd'])} · {lp['losing_years']} losing years of {lp['years']}.\n")
    if not mkt_up:
        L.append("**TSX is below its 200-day average - strategy is in cash. No trades.**")
        return "\n".join(L), df.iloc[0:0] if not df.empty else df
    if df.empty:
        L.append("**No leader pullbacks today - no trade.** Most days have none; that's normal.")
        return "\n".join(L), df
    stake = account / SLOTS
    picks = []
    for _, r in df.iterrows():
        if earnings_soon and earnings_soon(r.ticker):
            continue
        if int(stake // r.buy_max) < 1:          # can't afford one whole share with this position size
            continue
        picks.append(r)
        if len(picks) == SLOTS:
            break
    picks = pd.DataFrame(picks)
    if picks.empty:
        L.append("Signals today are all reporting earnings soon or cost more than one position - no trade.")
        return "\n".join(L), picks
    L.append(f"**Plan for a ${account:,.0f} account: up to {SLOTS} positions of ${stake:,.0f}.** "
             f"Buy at tomorrow's open with a limit order at *Buy max* (skip if it opens higher). "
             f"Right after it fills, enter the take-profit and stop-loss below (prices are from today's close; "
             f"if you fill a few cents different, use the % columns on your fill price). "
             f"If neither hits in {HOLD} trading days, sell at the close.\n")
    hdr = ("| Ticker | Company | Shares | Invest | Take profit at | Profit if hit | Stop-loss at | Loss if hit "
           "| Buy max | Target % | Stop % |")
    L += [hdr, "|" + "---|" * 11]
    for _, r in picks.iterrows():
        sh = int(stake // r.buy_max)
        inv = sh * r.close
        L.append(f"| {r.ticker} | {r.company[:26]} | {sh} | ${inv:,.2f} | ${r.take_profit} | "
                 f"**+${sh * (r.take_profit - r.close):,.2f}** | ${r.stop_loss} | **-${sh * (r.close - r.stop_loss):,.2f}** | "
                 f"${r.buy_max} | +{pct(r.target_pct)} | -{pct(r.stop_pct)} |")
    L.append(f"\n_Fees: Wealthsimple charges no commission on TSX trades. Profit and loss above are before the "
             f"bid-ask spread (a few cents a share)._")
    if month_end:
        L.append("\n_Month-end window: these also qualify for the **quick-bounce** exit (sell at the first close "
                 "above the 5-day average, stop -8%). Tested: ~69% win rate but only ~+0.6% per trade - "
                 "lower profit than holding for the full target._")
    return "\n".join(L), picks
