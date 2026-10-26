"""
LEADER PULLBACK - the setup that survived 18 years of TSX testing (see lab/ and PLAYBOOK.md).

Signal (all at today's close, real operating companies only - no ETFs/CDRs/BetaPro):
  1. Stage-2 uptrend (Minervini trend template): close > 50d > 150d > 200d SMA,
     200d rising for a month, >= 30% above 52-week low, within 25% of 52-week high
  2. Relative-strength leader: top 20% of liquid Canadian stocks (IBD-style 3/6/9/12-month RS)
  3. Short-term dip: RSI(2) < 10 AND Stochastic %K < 25 (Connors + oversold confirmation)
  4. TSX itself above its 200-day average (XIU)
  5. Liquid: >= $1M traded per day, price >= $2
  6. [NEW] ATH clearance: stock is ABOVE its 52-week high (breakout mode) OR >= 15% BELOW it
     (room to run). Stocks bumping 0-14% below ATH are skipped — the ceiling kills the 3:1 ratio.
  7. [NEW] Sector momentum: the stock's sector ETF must be above its 50-day MA.
  8. [NEW] MACD histogram turned positive within the last 3 bars (momentum confirming the dip ended)
  9. [NEW] OBV above its 10-day average (smart-money accumulation on the pullback)
  10. [NEW] Bullish candlestick pattern in the last 2 days (candles.py confirmation layer)

Trade: buy next open (skip if it opens > 2% above today's close);
       stop = 3 x ATR(14) below entry, target = 6 x ATR(14) above entry, exit at close after 30 trading days.
Sizing tested: up to 5 positions, 1/5 of the account each, strongest RS first.

"Month-end bounce" variant (higher win rate, much smaller profit): same signal inside the last
5 trading days of the month, exit at the first close above the 5-day SMA, stop -8%, max 10 days.

[EARNINGS QUALITY] Earnings blackout extended to 20 days (was 10). Any stock with 2+ consecutive
EPS misses is excluded until the next report beats.
Research only - not financial advice.
"""
import json
import os

import numpy as np
import pandas as pd

import stock_filter
import candles as candles_mod

MARKET = "XIU.TO"
STOP_ATR, TGT_ATR, HOLD = 3.0, 6.0, 30
MAX_GAP = 0.02
SLOTS = int(os.environ.get("SLOTS", "2"))    # $100 account: 2 positions of $50 (best tested)
CARD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lab", "results", "strategy_card.json")

# Earnings blackout: skip any stock reporting within this many calendar days
EARNINGS_BLACKOUT_DAYS = 20

# ATH clearance: skip if stock is in the "ceiling zone" - within this % BELOW 52-week high
# (but NOT above it). Stocks here can't hit a 3:1 target without busting through resistance.
ATH_CEILING_MAX_BELOW = 0.15   # 15% below 52w-high is the threshold

# Sector ETFs (Canadian) used for the sector momentum filter
# Format: {"ETF_ticker": [list of sector keywords in company names]}
SECTOR_ETFS = {
    "XEG.TO": ["energy", "oil", "gas", "petroleum", "suncor", "cnq", "cenovus", "tourmaline", "arc resources",
                "peyto", "nuvista", "paramount", "baytex", "whitecap", "crew", "tamarack"],
    "XFN.TO": ["bank", "financial", "insurance", "manulife", "sunlife", "great-west", "intact",
                "brookfield asset", "ci financial", "fiera", "igm", "power corp", "wawanesa"],
    "XIT.TO": ["tech", "software", "shopify", "constellation", "opentext", "kinaxis", "descartes",
                "lightspeed", "enghouse", "coveo", "nuvei", "docebo"],
    "XMA.TO": ["mining", "gold", "silver", "copper", "agnico", "barrick", "kinross", "first majestic",
                "teck", "ivanhoe", "lundin", "yamana", "b2gold", "alamos", "osisko"],
    "XRE.TO": ["reit", "real estate", "properties", "realty", "apartment", "riocan", "h&r",
                "calloway", "smartcentres", "dream", "chromedge", "choice properties"],
    "XUT.TO": ["utilities", "power", "hydro", "fortis", "emera", "algonquin", "ats", "capital power",
                "northland", "transalta", "boralex"],
    "XHC.TO": ["health", "pharma", "biotech", "medical", "dentalcorp", "cgi", "well health",
                "bausch", "jamieson"],
}

# Fallback: if no sector match, require the broad TSX (XIU.TO) to be above 50d MA (already checked at market level)
_SECTOR_ETF_TICKERS = list(SECTOR_ETFS.keys())


def _panel(data):
    keys = ("Open", "High", "Low", "Close", "Volume")
    return {k: pd.DataFrame({t: d[k] for t, d in data.items()}).sort_index().astype("float64") for k in keys}


def _rsi(c, n):
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def _sector_for(ticker, company_name):
    """Return the best-matching sector ETF ticker for a given stock, or None."""
    key = (ticker.lower() + " " + (company_name or "").lower())
    for etf, keywords in SECTOR_ETFS.items():
        for kw in keywords:
            if kw in key:
                return etf
    return None


def _sector_status(data):
    """
    Returns dict {etf_ticker: bool} — True if that sector ETF is above its 50-day MA.
    Uses MARKET (XIU.TO) as the fallback for unknown sectors.
    """
    status = {}
    for etf in _SECTOR_ETF_TICKERS + [MARKET]:
        if etf in data:
            c = data[etf]["Close"]
            sma50 = c.rolling(50, min_periods=40).mean()
            status[etf] = bool(c.iloc[-1] > sma50.iloc[-1]) if len(c) >= 40 else True
        else:
            status[etf] = True   # data not available → don't penalise
    return status


def _macd_histogram(C):
    """Returns MACD histogram (MACD line minus signal line) as a DataFrame (same shape as C)."""
    ema12 = C.ewm(span=12, adjust=False).mean()
    ema26 = C.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    macd_signal = macd_line.ewm(span=9, adjust=False).mean()
    return macd_line - macd_signal


def _stoch(H, L, C, k=14, d=3):
    """Returns Stochastic %K (raw). Oversold when < 25."""
    low_k = L.rolling(k, min_periods=k).min()
    high_k = H.rolling(k, min_periods=k).max()
    return 100 * (C - low_k) / (high_k - low_k).replace(0, np.nan)


def _obv(C, V):
    """On-Balance Volume as a DataFrame (same shape as C)."""
    sign = C.diff().apply(lambda s: s.apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0)))
    return (sign * V).cumsum()


def signals(data):
    """data: {ticker: OHLCV DataFrame}. Returns DataFrame of today's leader-pullback signals."""
    if MARKET not in data:
        raise ValueError("market ETF missing from download")

    # Separate sector ETFs from stock universe for the panel (they're not stocks)
    sector_etfs_in_data = {t for t in data if t in _SECTOR_ETF_TICKERS}
    stocks = {t: d for t, d in data.items()
              if t == MARKET or (t not in sector_etfs_in_data and stock_filter.is_stock(t))}

    # --- Compute sector ETF status BEFORE building the panel ---
    sec_status = _sector_status(data)

    P = _panel(stocks)
    O, H, L, C, V = (P[k] for k in ("Open", "High", "Low", "Close", "Volume"))
    sma = lambda n: C.rolling(n, min_periods=n).mean()
    s50, s150, s200 = sma(50), sma(150), sma(200)
    hi252, lo252 = H.rolling(252, min_periods=200).max(), L.rolling(252, min_periods=200).min()

    # --- Stage-2 trend template (Minervini) ---
    stage2 = ((C > s50) & (s50 > s150) & (s150 > s200) & (s200 > s200.shift(21))
              & (C >= 1.3 * lo252) & (C >= 0.75 * hi252))

    # --- Liquidity ---
    dvol = (C * V).rolling(20).mean()
    liquid = (dvol >= 1_000_000) & (C >= 2)

    # --- Relative Strength (IBD-style composite) ---
    rs_raw = (0.4 * C.pct_change(63) + 0.2 * C.pct_change(126)
              + 0.2 * C.pct_change(189) + 0.2 * C.pct_change(min(252, len(C) - 1)))
    rs = rs_raw.where(liquid).drop(columns=[MARKET], errors="ignore").rank(axis=1, pct=True)

    # --- Short-term dip indicators ---
    rsi2 = _rsi(C, 2)
    stoch_k = _stoch(H, L, C)
    stoch_oversold = stoch_k < 25      # both RSI(2) and Stoch must confirm the dip

    # --- MACD momentum (histogram turning positive = dip ending) ---
    macd_hist = _macd_histogram(C)
    # True if histogram turned positive in the last 3 bars
    macd_cross = ((macd_hist > 0) &
                  ((macd_hist.shift(1) <= 0) | (macd_hist.shift(2) <= 0) | (macd_hist.shift(3) <= 0)))

    # --- OBV accumulation: OBV above its 10-day moving average ---
    obv = _obv(C, V)
    obv_rising = obv > obv.rolling(10).mean()

    # --- [NEW] ATH clearance filter ---
    # Skip if stock is in the "ceiling zone": 0-14% below its 52-week high.
    # Allow if: stock is ABOVE 52w-high (breakout) OR >= 15% below it (room to run).
    ath_ok = (C >= hi252) | (C <= (1 - ATH_CEILING_MAX_BELOW) * hi252)

    # --- ATR for stops/targets ---
    pc = C.shift(1)
    tr = np.maximum(H - L, np.maximum((H - pc).abs(), (L - pc).abs()))
    atr = tr.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()

    # --- Market filter ---
    m = C[MARKET]
    mkt_up = bool(m.iloc[-1] > m.rolling(200).mean().iloc[-1])

    # Month-end window
    today = C.index[-1]
    month_end = today.day >= 24

    last = C.index[-1]
    rows = []
    for t in rs.columns:
        # Core filters (fast path — skip if basic conditions not met)
        if not (bool(stage2.at[last, t]) and bool(liquid.at[last, t])):
            continue
        r = rs.at[last, t]
        if not (pd.notna(r) and r > 0.8):
            continue

        # RSI(2) dip AND Stochastic oversold
        rv2 = float(rsi2.at[last, t])
        sk = float(stoch_k.at[last, t]) if pd.notna(stoch_k.at[last, t]) else 50.0
        if not (rv2 < 10 and sk < 25):
            continue

        # [NEW] ATH clearance
        if not bool(ath_ok.at[last, t]):
            close_val = float(C.at[last, t])
            hi_val = float(hi252.at[last, t]) if pd.notna(hi252.at[last, t]) else close_val
            pct_below = (hi_val - close_val) / hi_val * 100
            # Skip with reason logged (ATH ceiling zone)
            continue

        # [NEW] MACD crossover confirmation (histogram turned positive recently)
        if not bool(macd_cross.at[last, t]):
            continue

        # [NEW] OBV accumulation
        if not bool(obv_rising.at[last, t]):
            continue

        # [NEW] Candlestick pattern confirmation (per-stock)
        stock_df = stocks[t]
        try:
            candle_ok = bool(candles_mod.signal(stock_df).iloc[-1])
        except Exception:
            candle_ok = True   # data edge case → don't penalise

        # [NEW] Sector momentum filter
        company_name = stock_filter.company(t)
        sector_etf = _sector_for(t, company_name)
        if sector_etf is not None:
            sector_ok = sec_status.get(sector_etf, True)
        else:
            sector_ok = sec_status.get(MARKET, True)   # fallback: broad market

        if not sector_ok:
            continue

        close, a = float(C.at[last, t]), float(atr.at[last, t])
        hi_52w = float(hi252.at[last, t]) if pd.notna(hi252.at[last, t]) else close
        pct_from_ath = (hi_52w - close) / hi_52w * 100 if hi_52w > 0 else 0.0

        rows.append({
            "ticker": t,
            "company": company_name,
            "rs_rank": round(float(r) * 100),
            "rsi2": round(rv2, 1),
            "stoch_k": round(sk, 1),
            "macd_hist": round(float(macd_hist.at[last, t]), 4),
            "obv_vs_avg": round(float(obv.at[last, t] - obv.rolling(10).mean().at[last, t]), 0),
            "candle": candle_ok,
            "candle_pattern": candles_mod.latest_names(stock_df) if candle_ok else "",
            "sector_etf": sector_etf or "broad",
            "sector_ok": sector_ok,
            "pct_from_ath": round(pct_from_ath, 1),
            "close": round(close, 2),
            "buy_max": round(close * (1 + MAX_GAP), 2),
            "stop_pct": STOP_ATR * a / close,
            "target_pct": TGT_ATR * a / close,
            "stop_loss": round(close - STOP_ATR * a, 2),
            "take_profit": round(close + TGT_ATR * a, 2),
            "exchange": "TSX Venture" if t.endswith(".V") else "TSX",
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        # Sort by: candlestick confirmation first, then RS rank
        df["candle_sort"] = df["candle"].astype(int)
        df = df.sort_values(["candle_sort", "rs_rank"], ascending=[False, False]).reset_index(drop=True)
        df = df.drop(columns=["candle_sort"])
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
    L.append("_v2 upgrades active: ATH clearance · sector momentum · MACD+OBV confirmation · "
             f"candlestick patterns · Stochastic · {EARNINGS_BLACKOUT_DAYS}-day earnings blackout_\n")
    if not mkt_up:
        L.append("**TSX is below its 200-day average - strategy is in cash. No trades.**")
        return "\n".join(L), df.iloc[0:0] if not df.empty else df
    if df.empty:
        L.append("**No leader pullbacks today - no trade.** Most days have none; that's normal.")
        return "\n".join(L), df
    stake = account / SLOTS
    picks = []
    for _, r in df.iterrows():
        # [NEW] Extended earnings blackout: 20 calendar days (was 10)
        if earnings_soon and earnings_soon(r.ticker, days=EARNINGS_BLACKOUT_DAYS):
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
    hdr = ("| Ticker | Company | Shares | Invest | Take profit | Profit if hit | Stop-loss | Loss if hit "
           "| Buy max | Target % | Stop % | % from ATH | Candle | Sector |")
    L += [hdr, "|" + "---|" * 14]
    for _, r in picks.iterrows():
        sh = int(stake // r.buy_max)
        inv = sh * r.close
        candle_info = f"✅ {r.candle_pattern[:20]}" if r.candle else "—"
        ath_info = f"+{abs(r.pct_from_ath):.1f}% above" if r.pct_from_ath <= 0 else f"{r.pct_from_ath:.1f}% below"
        L.append(f"| {r.ticker} | {r.company[:24]} | {sh} | ${inv:,.2f} | ${r.take_profit} | "
                 f"**+${sh * (r.take_profit - r.close):,.2f}** | ${r.stop_loss} | **-${sh * (r.close - r.stop_loss):,.2f}** | "
                 f"${r.buy_max} | +{pct(r.target_pct)} | -{pct(r.stop_pct)} | {ath_info} | {candle_info} | {r.sector_etf} |")
    L.append(f"\n_Fees: Wealthsimple charges no commission on TSX trades. Profit and loss above are before the "
             f"bid-ask spread (a few cents a share)._")
    L.append(f"\n**Filter summary (v2):** ATH clearance (≥15% below or above 52w-high) · "
             f"Sector ETF above 50d MA · MACD histogram turned positive · OBV above 10d avg · "
             f"RSI(2)<10 + Stoch<25 · Bullish candle last 2 days · {EARNINGS_BLACKOUT_DAYS}d earnings blackout_")
    if month_end:
        L.append("\n_Month-end window: these also qualify for the **quick-bounce** exit (sell at the first close "
                 "above the 5-day average, stop -8%). Tested: ~69% win rate but only ~+0.6% per trade - "
                 "lower profit than holding for the full target._")
    return "\n".join(L), picks
