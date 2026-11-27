"""Historical, shared-cash portfolio research over a versioned equity universe."""
import argparse
import hashlib
from itertools import product
import json
from pathlib import Path

import duckdb
import exchange_calendars as xc
import numpy as np
import pandas as pd
from numba import njit

from campaign_watchdog import guard, health
from eodhd import atomic_json
from execution_actions import actions
from profit_admission import cpu_guard

CAPITAL = 5000.
FEE = 2.
FRICTION = .003


def read(path):
    return json.loads(path.read_bytes())


def load_equity(root, db, job, start, end, calendar):
    row = db.execute("""select parquet_glob from datasets where source=? and market=? and symbol=?
                        and bar_interval='1d' and sha256=?""",
                     [job[k] for k in ("source", "market", "symbol", "data_sha256")]).fetchone()
    if not row:
        raise ValueError("Missing frozen price revision")
    frame = db.execute("""select session, open, high, low, close, adjusted_close, volume
                        from read_parquet(?) where session >= ? and session < ? order by session""",
                       [row[0], start, end]).df().set_index("session")
    if len(frame) < 254 or frame.index.has_duplicates:
        raise ValueError("Unavailable or insufficient session history")
    expected = calendar[(calendar >= frame.index[0]) & (calendar < end)]
    if not frame.index.equals(expected):
        raise ValueError("Incomplete calendar in the selected trading window")
    prices = frame[["open", "low", "close"]].to_numpy()
    if not np.isfinite(prices).all() or (prices <= 0).any():
        raise ValueError("Invalid execution prices")
    factors, dividend, claims, pays, slots = actions(root, job, frame.index, (pd.Timestamp(end)-pd.Timedelta(days=1)).date().isoformat())
    columns = np.column_stack((prices, factors, dividend,
                               (frame.adjusted_close * frame.volume).rolling(20).min().shift(1).fillna(0)))
    # Non-sessions before listing are ineligible, with no artificial fills.
    aligned = pd.DataFrame(columns, index=frame.index).reindex(calendar)
    price = (frame.close * np.cumprod(factors)).reindex(calendar)
    cash_map = np.full((len(calendar), 2), -1, dtype=np.int64)
    ix = calendar.get_indexer(frame.index)
    cash_map[ix] = np.column_stack((claims, pays))
    return aligned.to_numpy(), price, cash_map, slots


def signal_bank(close):
    bank = {}
    for period in (5, 10, 14, 21, 30):
        change = close.diff()
        gain = change.clip(lower=0).ewm(alpha=1/period, min_periods=period, adjust=False).mean()
        loss = -change.clip(upper=0).ewm(alpha=1/period, min_periods=period, adjust=False).mean()
        rsi = 100 * gain / (gain+loss)
        for threshold in (20, 25, 30, 35, 40, 45, 50):
            label = f"RSI({period}) <= {threshold}"
            bank[label] = (rsi <= threshold).to_numpy()
    macd = close.ewm(span=12, min_periods=26, adjust=False).mean()-close.ewm(span=26, min_periods=26, adjust=False).mean()
    line = macd.ewm(span=9, min_periods=9, adjust=False).mean()
    bank["MACD > signal"] = (macd > line).to_numpy()
    bank["MACD crosses above signal"] = ((macd > line) & (macd.shift(1) <= line.shift(1))).to_numpy()
    return bank


@njit(cache=True)
def simulate(bars, cash_dates, max_slots, entries, exits, holding, start, stop, slots, priority, trace=False):
    days, names = entries.shape
    units = np.zeros(names, np.int64)
    age = np.zeros(names, np.int64)
    receivables = np.zeros(names)
    due = np.zeros((names, max_slots))
    cash = CAPITAL
    equity = CAPITAL
    peak = CAPITAL
    drawdown = 0.
    buys = 0
    equity_curve = np.zeros(stop-start)
    traded = np.zeros(names, np.bool_)
    fills = np.zeros((stop-start if trace else 0, names, 2), np.int64)
    for d in range(start, stop):
        open_equity = cash
        for t in range(names):
            opening, _, _, factor, dividend, _ = bars[d,t]
            pay = cash_dates[d,t,1]
            if pay >= 0:
                cash += due[t,pay]
                receivables[t] -= due[t,pay]
                open_equity += due[t,pay]
            if units[t]:
                units[t] = int(units[t] * factor)
                claim = cash_dates[d,t,0]
                if claim >= 0:
                    due[t,claim] += units[t] * dividend
                    receivables[t] += units[t] * dividend
                if d == stop-1 or d-age[t] >= holding or exits[d-1,t]:
                    income = units[t] * opening * (1-FRICTION) - FEE
                    cash += income
                    if trace:
                        fills[d-start,t,0] = units[t]
                    open_equity += income
                    units[t] = 0
                else:
                    open_equity += units[t] * opening
            open_equity += receivables[t]
        if d < stop-1:
            for t in priority[d-1]:
                if np.count_nonzero(units) >= slots:
                    break
                opening, _, _, _, _, turnover = bars[d,t]
                if units[t] or not entries[d-1,t] or not np.isfinite(opening):
                    continue
                price = opening * (1+FRICTION)
                stake = min(open_equity/slots, cash, turnover*.0001)
                qty = max(0, int((stake-FEE)//price))
                if qty:
                    cash -= qty*price+FEE
                    units[t] = qty
                    age[t] = d
                    buys += 1
                    traded[t] = True
                    if trace:
                        fills[d-start,t,1] = qty
        equity = cash + np.sum(receivables)
        downside = equity
        for t in range(names):
            if units[t]:
                equity += units[t]*bars[d,t,2]
                downside += units[t]*bars[d,t,1]
        peak = max(peak, open_equity, equity)
        drawdown = max(drawdown, 1 - downside/peak)
        equity_curve[d-start] = equity
    return equity-CAPITAL, drawdown, buys, np.count_nonzero(traded), equity_curve, fills


def run(root, spec, result_path):
    if guard(health(root)) or cpu_guard(root,85) == "cpu_temperature":
        raise RuntimeError("Laptop resource guard paused research")
    first, middle, end = (spec[k] for k in ("start", "validation", "end_exclusive"))
    report = dict(scope=spec, official_evaluations=0, provisional_evaluations=0, accounts={},
                  code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  benchmark_note="Simplified VMM entry and exit filters on the admitted universe; same portfolio fill model. USD uses momentum without the TSX market gate.",
                  model=dict(capital=CAPITAL, friction_per_side=FRICTION, fee_per_side=FEE, max_slots=5,
                             entry_turnover_limit=.0001, prior_close_signals=True, final_open_liquidation=True))
    with duckdb.connect(str(root/"database/warehouse/catalog.duckdb"),read_only=True,config={"threads":1,"memory_limit":"192MB"}) as db:
        for currency in sorted(set(j["currency"] for j in spec["jobs"])):
            jobs=sorted((j for j in spec["jobs"] if j["currency"]==currency),key=lambda x:x["symbol"])
            cal=xc.get_calendar("XTSE" if currency=="CAD" else "XNYS",start=first,end=end)
            calendar=pd.Index(cal.sessions.strftime("%Y-%m-%d"))
            calendar=calendar[calendar<end]
            records=[]; closes=[]; mappings=[]; fails={}; max_slots=1; symbols=[]
            for job in jobs:
                try:
                    data, close, mapping, slots = load_equity(root,db,job,max(first,job.get("eligible_from",first)),end,calendar)
                except ValueError as error:
                    fails[job["symbol"]]=str(error)
                    continue
                records.append(data); closes.append(close); mappings.append(mapping)
                max_slots=max(max_slots,slots); symbols.append(job["symbol"])
            if not symbols:
                continue
            bars=np.ascontiguousarray(np.stack(records,axis=1))
            cashmap=np.ascontiguousarray(np.stack(mappings,axis=1))
            close=pd.concat(closes,axis=1); close.columns=symbols
            bank=signal_bank(close)
            false=np.zeros(bars.shape[:2],dtype=bool)
            priority=np.tile(np.arange(len(symbols)),(len(calendar),1))
            roc=close/close.shift(252)-1
            eligible=(roc.notna() & close.notna() & (bars[:,:,2]>=1) & (bars[:,:,2]<=100)
                      & (pd.DataFrame(bars[:,:,2],index=calendar,columns=symbols)*0+bars[:,:,5]>=300000))
            if "XIU.TO" in symbols:
                eligible["XIU.TO"]=False
            rs=roc.where(eligible)
            sma=close.rolling(200).mean()
            vmm=(rs.ge(rs.quantile(.9,axis=1),axis=0)&(close>sma))
            if "XIU.TO" in symbols:
                vmm=vmm.mul(close["XIU.TO"]>sma["XIU.TO"],axis=0)
            sell=(close<sma)|rs.lt(rs.quantile(.6,axis=1),axis=0)
            by_momentum=np.argsort(-rs.fillna(-np.inf).to_numpy(),axis=1,kind="stable")
            strategies=[(("VMM-style momentum baseline" if currency=="CAD" else "USD momentum baseline"),vmm.to_numpy(dtype=bool),sell.to_numpy(),10000,by_momentum)]
            for label, rsi in bank.items():
                if not label.startswith("RSI"):
                    continue
                for filt, holding in product(("", "MACD > signal", "MACD crosses above signal", "VMM momentum filter"),(5,10,20,40)):
                    valid = rsi if not filt else rsi & (vmm.to_numpy(dtype=bool) if filt=="VMM momentum filter" else bank[filt])
                    strategies.append((f"{label}"+(f" + {filt}" if filt else ""), valid, false, holding,
                                       by_momentum if filt=="VMM momentum filter" else priority))
            split=int(calendar.searchsorted(middle))
            rows=[]
            def results(a,b):
                profit, dd, trades, breadth, _, _ = simulate(bars,cashmap,max_slots,signal,exit_,hold,a,b,5,order)
                return dict(net_profit=round(profit,2),drawdown_pct=round(dd*100,2),trades=int(trades),
                            traded_symbols=int(breadth))
            for idx,(name,signal,exit_,hold,order) in enumerate(strategies):
                if idx%40==0 and (guard(health(root)) or cpu_guard(root,85) == "cpu_temperature"):
                    raise RuntimeError("Laptop resource guard paused research")
                dev=results(1,split)
                val=results(split,len(calendar))
                full=results(1,len(calendar))
                rows.append(dict(id=idx,strategy=name,hold_sessions=None if hold==10000 else hold,development=dev,validation=val,full=full))
            rows.sort(key=lambda x:(-x["development"]["net_profit"],x["development"]["drawdown_pct"],x["id"]))
            chosen=rows[0]["id"]
            _, signal, exit_, hold, order = strategies[chosen]
            _, _, _, _, curve, fills = simulate(bars,cashmap,max_slots,signal,exit_,hold,
                                                1,len(calendar),5,order,True)
            trade_log=[]
            for day, ticker, side in np.argwhere(fills):
                raw_open=bars[day+1,ticker,0]
                factor=1+FRICTION if side else 1-FRICTION
                trade_log.append(dict(date=calendar[day+1],symbol=symbols[ticker],
                    side="buy" if side else "sell",shares=int(fills[day,ticker,side]),
                    fill_price=round(float(raw_open*factor),6),fee=FEE))
            trade_log.sort(key=lambda x:(x["date"],x["side"]!="sell",x["symbol"]))
            report["provisional_evaluations"]+=len(rows)
            report["accounts"][currency]=dict(symbols=symbols,excluded=fails,development_rank=rows,development_leader_trade_log=trade_log,
                development_leader_equity=[dict(date=day,equity=round(float(eq),2)) for day,eq in zip(calendar[1:],curve)])
    atomic_json(result_path, report)
    for currency, account in report["accounts"].items():
        rows=account["development_rank"]
        print(currency,account["symbols"],"evaluations",len(rows),"train leader",rows[0],flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root",type=Path)
    parser.add_argument("scope",type=Path)
    parser.add_argument("result",type=Path)
    args=parser.parse_args()
    run(args.root,read(args.scope),args.result)
