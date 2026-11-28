"""Preregistered daily rotation across a Canadian-listed multi-asset ETF basket."""
import argparse
from datetime import datetime, timezone
import hashlib
from itertools import product
from pathlib import Path

import duckdb
import exchange_calendars as xc
import numpy as np
import pandas as pd

from eodhd import atomic_json
from portfolio_robustness import check, read


TICKERS = ("XIU.TO", "ZSP.TO", "XEF.TO", "XEC.TO", "XBB.TO", "XSB.TO", "CGL-C.TO", "XEG.TO", "XRE.TO")
WINDOWS = (126, 252)
POSITIONS = (1, 2)
PERIODS = {"train":"2016-01-01/2020-01-01", "validation":"2020-01-01/2022-01-01",
           "late_development":"2022-01-01/2024-11-27"}
CAPITAL, SIDE_COST, FEE = 5000., .003, 1.


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(root):
    close, opening, revisions = {}, {}, {}
    with duckdb.connect(str(root/"database/warehouse/catalog.duckdb"), read_only=True) as db:
        for ticker in TICKERS:
            rows = db.execute("""
                SELECT parquet_glob,sha256 FROM datasets
                WHERE market='TSX' AND source='eodhd' AND symbol=? AND bar_interval='1d'
                  AND json_extract_string(audit,'$.last')<='2024-11-26'
                ORDER BY CAST(json_extract_string(audit,'$.bars') AS INTEGER) DESC, sha256
            """,[ticker]).fetchall()
            if not rows:
                raise ValueError("No valid warehouse revision for "+ticker)
            pattern, revisions[ticker] = rows[0]
            files = sorted(Path(pattern).parent.parent.glob("year=*/bars.parquet"))
            bars = pd.read_parquet(files,columns=["session","open","close","adjusted_close"]).set_index("session").sort_index()
            if bars.index.has_duplicates or bars.index.max() >= "2024-11-27":
                raise ValueError("Overlapping dates or unexpected source revision")
            close[ticker] = bars.adjusted_close.astype(float)
            opening[ticker] = (bars.open*bars.adjusted_close/bars.close).astype(float)
    sessions = xc.get_calendar("XTSE",start="2013-01-01",end="2024-11-26").sessions.strftime("%Y-%m-%d")
    return (pd.DataFrame(close).reindex(sessions),pd.DataFrame(opening).reindex(sessions),revisions)


def simulation(open_, close, targets, freq, baseline=False):
    first, last = 0, len(close)-1
    cash, units = CAPITAL, np.zeros(open_.shape[1])
    curve, fills = [], 0
    allocation = ()
    for index in range(len(close)):
        held = units > 0
        if held.any() and (not np.isfinite(open_[index,held]).all() or not np.isfinite(close[index,held]).all()):
            raise ValueError("Missing valuation of an open position")
        requested = tuple(sorted(targets[index])) if (index==first or (freq[index] and not baseline)) else allocation
        if index==first or requested != allocation:
            allocation = requested
            # Sell the old sleeve, then buy each new sleeve at the next open.
            if held.any():
                cash += np.dot(units[held],open_[index,held])*(1-SIDE_COST)-held.sum()*FEE
                fills += int(held.sum())
                units[:] = 0
            active = list(allocation)
            if len(active):
                sleeve = max(0., cash/len(active)-FEE)
                if sleeve > 0:
                    units[active] = sleeve/(open_[index,active]*(1+SIDE_COST))
                    cash = max(0.,cash-(sleeve+FEE)*len(active))
                    fills += len(active)
        held = units > 0
        equity = cash + np.dot(units[held],close[index,held])
        if index==last and held.any():
            equity -= np.dot(units[held],close[index,held])*SIDE_COST+held.sum()*FEE
            fills += int(held.sum())
        curve.append(equity)
    value = np.array(curve)
    peak = np.maximum.accumulate(np.r_[CAPITAL,value])[1:]
    return {"net_return":value[-1]/CAPITAL-1,"max_drawdown":float(np.max(1-value/peak)),"fills":fills}


def run(root, output):
    check(root)
    close, opening, revisions = load(root)
    evaluation = (close.index >= "2016-01-01") & (close.index < "2024-11-27")
    verify_close, verify_open = close.loc[evaluation], opening.loc[evaluation]
    usable = verify_close.notna().all() & verify_open.notna().all() & verify_close.gt(0).all() & verify_open.gt(0).all()
    assets = close.columns[usable]
    if len(assets) < 6:
        raise ValueError("Fewer than six ETFs have continuous data for all folds")
    close, opening = close[assets], opening[assets]
    started = datetime.now(timezone.utc).isoformat()
    plan = {"started":started,"periods":PERIODS,"windows":WINDOWS,"positions":POSITIONS,
            "symbols":{ticker:revisions[ticker] for ticker in assets},"cash_yield":0,"capital":CAPITAL,"side_cost":SIDE_COST,"fee_per_fill":FEE,
            "code_sha256":sha(Path(__file__)),
            "trigger":"At the start of each month, rank ETFs on prior close total return, require positive trailing return and prior close above SMA200.",
            "selection":"Rank the four candidates by training return; show both development validation windows.",
            "rebalance":"Only trade when selected membership changes. Retain the original full monthly rebalance run as a separate sensitivity."}
    atomic_json(output.with_suffix(".plan.json"),plan)
    slopes = {window: (close/close.shift(window)-1).shift() for window in WINDOWS}
    above = close.gt(close.rolling(200).mean()).shift(fill_value=False)
    candidates = {f"momentum_{w}_top{n}":{} for w,n in product(WINDOWS,POSITIONS)}
    passive = {}
    for period, date_range in PERIODS.items():
        start,end = date_range.split("/")
        flags = (close.index>=start)&(close.index<end)
        c, o = close.loc[flags].copy(), opening.loc[flags].copy()
        periods = pd.DatetimeIndex(c.index).to_period("M")
        rebalance = np.r_[True,periods[1:] != periods[:-1]]
        passive[period] = {"assets":list(assets),**simulation(o.to_numpy(),c.to_numpy(),
            [np.arange(len(assets))]*len(c),rebalance,baseline=True)}
        for w,n in product(WINDOWS,POSITIONS):
            momentum = slopes[w].loc[flags,assets]
            evidence = momentum.where((momentum>0)&above.loc[flags,assets])
            targets = [np.flatnonzero(np.isfinite(row))[np.argsort(-row[np.isfinite(row)],kind="stable")[:n]]
                       for row in evidence.to_numpy()]
            result = simulation(o.to_numpy(),c.to_numpy(),targets,rebalance)
            candidates[f"momentum_{w}_top{n}"][period] = {
                **result,"passive_delta":result["net_return"]-passive[period]["net_return"]}
    leader = max(candidates,key=lambda name:candidates[name]["train"]["net_return"])
    report = {"phase":"provisional_development","official_v2_evaluations":0,"candidate_count":len(candidates),
              "train_selected":leader,"strategies":candidates,"equal_weight_buy_and_hold":passive,
              "plan_sha256":sha(output.with_suffix(".plan.json")),
              "limitations":["Previously available observations in every period.",
                  "Fractional, dividend-adjusted return approximation. No intraday fills or liquidity calibration.",
                  "ETF cohort is price-coverage selected. Monthly strategy keeps positions when membership is unchanged and reallocates when membership changes."]}
    atomic_json(output,report)
    print(leader,candidates[leader],flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root",type=Path)
    parser.add_argument("output",type=Path)
    args=parser.parse_args()
    run(args.root,args.output)
