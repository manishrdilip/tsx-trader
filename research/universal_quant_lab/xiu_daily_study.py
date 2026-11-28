"""Test one preregistered two-sided XIU trend-and-breakout rule."""
import argparse
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import exchange_calendars as xc
import numpy as np
import pandas as pd

from available_intraday_screen import check, digest
from eodhd import atomic_json
from run_universe import read


SYMBOL = "XIU.TO"
PERIODS = (("2016-01-01", "2020-01-01"), ("2020-01-01", "2022-01-01"),
           ("2022-01-01", "2024-11-27"))
CAPITAL, FEE, COST = 5000., 1., .003
RISK, BORROW = .01, .03


def load(root):
    with duckdb.connect(str(root/"database/warehouse/catalog.duckdb"),read_only=True) as db:
        row=db.execute("""SELECT sha256, parquet_glob FROM datasets
            WHERE source='eodhd' AND market='TSX' AND symbol=? AND bar_interval='1d'
              AND json_extract_string(audit,'$.last') <= '2024-11-26'
            ORDER BY CAST(json_extract_string(audit,'$.bars') AS INTEGER) DESC,sha256 LIMIT 1""",[SYMBOL]).fetchone()
    if row is None:
        raise RuntimeError("No XIU warehouse revision at cutoff")
    rev, pattern = row
    files=[p for p in sorted(Path(pattern).parent.parent.glob("year=*/bars.parquet"))
           if 2014<=int(p.parent.name[5:])<=2024]
    src=pd.read_parquet(files,columns=["session","open","high","low","close","adjusted_close"])
    sessions=xc.get_calendar("XTSE",start="2014-01-02",end="2024-11-26").sessions.strftime("%Y-%m-%d")
    bars=src[src.session.isin(sessions)].sort_values("session").reset_index(drop=True)
    if list(bars.session)!=list(sessions):
        raise ValueError("Incomplete or duplicate XIU sessions in the declared range")
    factor=bars.adjusted_close/bars.close
    for field in ("open","high","low","close"):
        bars[field]*=factor
    return bars,rev,{p.parent.name:digest(p) for p in files},len(src)-len(bars)


def signals(bars):
    c,h,l = bars.close,bars.high,bars.low
    sma = c.rolling(200).mean()
    upper = h.shift(1).rolling(20).max()
    lower = l.shift(1).rolling(20).min()
    exit_upper = h.shift(1).rolling(10).max()
    exit_lower = l.shift(1).rolling(10).min()
    tr=pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
    return pd.DataFrame({"sma200":sma,"upper20":upper,"lower20":lower,
                         "buy":c.gt(sma)&c.gt(upper),"short":c.lt(sma)&c.lt(lower),
                         "sell":c.lt(exit_lower),"cover":c.gt(exit_upper),"atr":tr.rolling(14).mean()})


def replay(bars, indicators, a, b, allowed, borrow):
    sub=bars.iloc[a:b].reset_index(drop=True)
    vars_=indicators.iloc[a:b].reset_index(drop=True)
    cash, quantity, direction, stop = CAPITAL,0.,0,0.
    start_value, entry_index, total_borrow=CAPITAL,0,0.
    values, trades = [], []
    stamps=pd.to_datetime(sub.session)
    days=np.r_[0,stamps.diff().dt.days.iloc[1:].to_numpy()]
    p=sub[["open","high","low","close"]].to_numpy()
    buy, short, sell, cover, atr=(vars_[name].to_numpy() for name in ("buy","short","sell","cover","atr"))

    def close_trade(price, i, reason):
        nonlocal cash, quantity, direction
        cash+=direction*quantity*price*(1-direction*COST)-FEE
        trades.append({"entry":sub.session.iloc[entry_index],"exit":sub.session.iloc[i],
                       "side":"long" if direction==1 else "short","reason":reason,
                       "profit":cash-start_value,"holding_sessions":i-entry_index})
        quantity,direction=0.,0

    for i,(opening,high,low,close) in enumerate(p):
        exited=False
        if direction==-1:
            fee=quantity*p[i-1,3]*borrow*days[i]/365
            cash-=fee
            total_borrow+=fee
        if direction:
            if (direction==1 and sell[i-1]) or (direction==-1 and cover[i-1]) or i==len(p)-1:
                close_trade(opening,i,"channel or window end")
                exited=True
            elif (direction==1 and opening<=stop) or (direction==-1 and opening>=stop):
                close_trade(opening,i,"stop gap")
                exited=True
        if not direction and not exited and 0<i<len(p)-1:
            choice=1 if buy[i-1] and 1 in allowed else -1 if short[i-1] and -1 in allowed else 0
            distance=2*atr[i-1]
            if choice and np.isfinite(distance) and opening>distance>0 and cash>FEE:
                start_value=cash
                quantity=min((cash-FEE)/(opening*(1+COST)),RISK*cash/distance)
                cash-=choice*quantity*opening*(1+choice*COST)+FEE
                direction,entry_index,stop=choice,i,opening-choice*distance
        if (direction==1 and low<=stop) or (direction==-1 and high>=stop):
            close_trade(stop,i,"intraday stop")
        values.append(cash+direction*quantity*close*(1-direction*COST)-(FEE if direction else 0))
    curve=np.asarray(values)
    peak=np.maximum.accumulate(np.r_[CAPITAL,curve])[1:]
    return {"net_return":cash/CAPITAL-1,"max_drawdown":float(np.max(1-curve/peak)),
            "trades":len(trades),"wins":sum(int(r["profit"]>0) for r in trades),"borrow_cost":total_borrow,
            "long_pnl":sum(r["profit"] for r in trades if r["side"]=="long"),
            "short_pnl":sum(r["profit"] for r in trades if r["side"]=="short"),
            "trade_log":trades,"equity":values}


def trend_filter(bars, indicators, first, last):
    prices = bars.open.to_numpy()
    months = pd.DatetimeIndex(bars.session).to_period("M")
    active = bars.close.gt(indicators.sma200).to_numpy()
    qty, cash, trades, start_trade = 0., CAPITAL, 0, CAPITAL
    wins = 0
    curve = []
    for i in range(first,last):
        if i == last-1:
            desired = False
        elif i == first or months[i] != months[i-1]:
            desired = active[i-1]
        else:
            desired = qty > 0
        if desired and qty == 0 and cash > FEE:
            start_trade = cash
            qty = (cash-FEE)/(prices[i]*(1+COST))
            cash = 0.
        elif not desired and qty > 0:
            cash = qty*prices[i]*(1-COST)-FEE
            qty = 0.
            wins += int(cash > start_trade)
            trades += 1
        curve.append(cash if qty == 0 else qty*bars.close.iloc[i]*(1-COST)-FEE)
    equity = np.asarray(curve)
    peak = np.maximum.accumulate(np.r_[CAPITAL,equity])[1:]
    return {"net_return":float(equity[-1]/CAPITAL-1),"max_drawdown":float((1-equity/peak).max()),
            "trades":trades,"wins":wins,"equity":curve}


def run(root,out):
    check(root)
    bars,rev,parts,extra=load(root)
    out.mkdir(parents=True,exist_ok=True)
    plan={"phase":"historical development","registered_utc":datetime.now(timezone.utc).isoformat(),
          "input_revision":rev,"input_parts":parts,"ignored_non_session_rows":extra,
          "periods":PERIODS,"code_sha256":digest(Path(__file__)),
          "entry":"Above 200-day MA and above prior 20-session high for long. Below MA and below prior 20-session low for short.",
          "exit":"Close crosses the opposite prior 10-session channel, next open, or 2 x ATR14 stop with gap-aware fills.",
          "separate_control":"Monthly SMA200 long/cash added after first separate breakout replay; no data-based parameter search.","capital":CAPITAL,"side_cost":COST,"fee":FEE,"borrow_rates":[BORROW,.08],"risk_fraction":RISK}
    atomic_json(out/"plan.json",plan)
    decisions=signals(bars)
    results={}
    for start,until in PERIODS:
        lo,hi=(int(bars.session.searchsorted(date)) for date in (start,until))
        passive=((CAPITAL-FEE)/(bars.open.iloc[lo]*(1+COST))*bars.open.iloc[hi-1]*(1-COST)-FEE)/CAPITAL-1
        results[f"{start}/{until}"]={
             "sessions":list(bars.session.iloc[lo:hi]),"passive":passive,
             "long_only":replay(bars,decisions,lo,hi,[1],BORROW),
             "monthly_trend_control":trend_filter(bars,decisions,lo,hi),
             "short_only":replay(bars,decisions,lo,hi,[-1],BORROW),
             "long_short":replay(bars,decisions,lo,hi,[1,-1],BORROW),
             "long_short_8pct_borrow":replay(bars,decisions,lo,hi,[1,-1],.08)}
    atomic_json(out/"report.json",{
         "symbol":SYMBOL,"interval":"1d","scope":"provisional development","plan_sha256":digest(out/"plan.json"),
         "results":results,"limitations":["Borrow availability and borrow fees are assumptions, not observed XIU history.",
            "Distribution-adjusted OHLC proxy for prices and the economic effect of distributions. No borrow recalls, taxes or cash yield.",
            "Periods previously available to research. No independent forward test."]})
    print({k:{m:(v["net_return"],v["max_drawdown"],v["trades"],v["wins"]) for m,v in x.items() if isinstance(v,dict)}
           for k,x in results.items()},flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root",type=Path)
    parser.add_argument("out",type=Path)
    args=parser.parse_args()
    run(args.root,args.out)
