"""Development-only daily, weekly and monthly screen of the frozen US cohort."""
import argparse
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
import hashlib

import duckdb
import exchange_calendars as xc
import numpy as np
import pandas as pd

from available_intraday_screen import CAPITAL, FEE, FRICTION, check, simulate
from eodhd import atomic_json
from run_universe import read


SETTINGS = {
    "1d": {"minimum": (250, 180), "rsi": (5, 14), "ema": (8, 21), "range": (12, 24), "hold": (5, 20)},
    "1w": {"minimum": (90, 65), "rsi": (5, 10), "ema": (4, 12), "range": (8, 16), "hold": (3, 8)},
    "1mo": {"minimum": (24, 18), "rsi": (3, 6), "ema": (3, 8), "range": (4, 8), "hold": (2, 5)},
}
START, SPLIT, END = "2016-01-01", "2022-01-01", "2024-11-27"
LABELS = ("rsi_short_recovery", "rsi_long_recovery", "rsi_with_ema_trend",
          "rsi_with_macd", "breakout_short", "breakout_long", "breakout_with_ema_trend",
          "breakout_with_macd", "ema_cross", "ema_cross_with_macd")
SL_TP = ((1., 1.5), (1.5, 2.5))


def digest(p):
    with p.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def build(root, out):
    symbols = list(read(root/"results/available-intraday-140-v1/plan.json")["source_windows"])
    with duckdb.connect(str(root/"database/warehouse/catalog.duckdb"), read_only=True) as db:
        paths = db.execute("""SELECT symbol, parquet_glob, sha256 FROM datasets
            WHERE source='eodhd' AND market='US' AND bar_interval='1d'
              AND json_extract_string(audit,'$.last') <= '2024-11-26'
            QUALIFY row_number() OVER (PARTITION BY symbol
             ORDER BY CAST(json_extract_string(audit,'$.bars') AS INT) DESC, sha256)=1""").fetchall()
    lookup = {symbol:(path, sha) for symbol,path,sha in paths}
    source = {}
    for ticker in symbols:
        source[ticker] = None
        if ticker in lookup:
            path, revision = lookup[ticker]
            files = [file for file in sorted(Path(path).parent.parent.glob("year=*/bars.parquet"))
                     if 2013 <= int(file.parent.name[5:]) <= 2024]
            if files:
                source[ticker] = {"revision":revision,"files":[
                    [file.relative_to(root).as_posix(),digest(file)] for file in files]}
    plan = {"created_utc":datetime.now(timezone.utc).isoformat(),"code_sha256":digest(Path(__file__)),
            "scope":"provisional development","source":source,
            "start":START,"validation_start":SPLIT,"end":END,"settings":SETTINGS,
            "atr_exits_stop_target":SL_TP,"costs":{"per_side":FRICTION,"fee_per_fill":FEE},
            "ranking":"Each timeframe ranked by 2016-2021 compounded sleeve return before comparison with 2022-2024."}
    atomic_json(out/"plan.json",plan)
    return plan


def bar_series(daily, expected, interval):
    if interval=="1d":
        return daily
    freq = "W-FRI" if interval=="1w" else "M"
    grouped = pd.to_datetime(daily.session).dt.to_period(freq)
    expected_counts = pd.DatetimeIndex(expected).to_period(freq).value_counts()
    aggregate = daily.groupby(grouped).agg(session=("session","last"),open=("open","first"),
                                          high=("high","max"),low=("low","min"),close=("close","last"),
                                          liquidity=("liquidity","median"),bars=("close","size"))
    complete = aggregate.index.end_time.normalize() < pd.Timestamp(END)
    return aggregate[complete & aggregate.bars.eq(aggregate.index.map(expected_counts))].reset_index(drop=True)


def signals(bars, config):
    price, high, low = bars.close, bars.high, bars.low
    prev = price.shift()
    tr = pd.concat([high-low,(high-prev).abs(),(low-prev).abs()],axis=1).max(axis=1)
    atr = tr.rolling(8).mean()
    def rsi_recovery(n, threshold):
        diff=price.diff()
        up=diff.clip(lower=0).ewm(alpha=1/n,adjust=False,min_periods=n).mean()
        down=(-diff.clip(upper=0)).ewm(alpha=1/n,adjust=False,min_periods=n).mean()
        rsi=100*up/(down+up).replace(0,np.nan)
        return rsi.gt(threshold)&rsi.shift().le(threshold)
    fast_n,slow_n = config["ema"]
    fast=price.ewm(span=fast_n,min_periods=fast_n,adjust=False).mean()
    slow=price.ewm(span=slow_n,min_periods=slow_n,adjust=False).mean()
    trend=fast.gt(slow)
    line=fast-slow
    macd=line.gt(line.ewm(span=max(3,fast_n//2),min_periods=3,adjust=False).mean())
    a,b = rsi_recovery(config["rsi"][0],30),rsi_recovery(config["rsi"][1],35)
    x,y = (price.gt(high.shift().rolling(n).max()) for n in config["range"])
    cross=trend&fast.shift().le(slow.shift())
    return np.column_stack((a,b,a&trend,b&macd,x,y,x&trend,y&macd,cross,cross&macd)),atr.to_numpy()


def run(root,out):
    out.mkdir(parents=True,exist_ok=True)
    plan_file=out/"plan.json"
    plan=read(plan_file) if plan_file.exists() else build(root,out)
    if plan["code_sha256"]!=digest(Path(__file__)):
        raise ValueError("Runner differs from the frozen plan")
    expected=xc.get_calendar("XNYS",start="2013-01-01",end="2024-11-26").sessions.strftime("%Y-%m-%d")
    saved=out/"progress.json"
    progress=read(saved) if saved.exists() else {"admitted":{},"excluded":{}}
    for symbol, record in plan["source"].items():
        if symbol in progress["admitted"] or symbol in progress["excluded"]:
            continue
        check(root)
        admitted, excluded = {}, {}
        daily=None
        if record:
            files=[]
            for name, expected_hash in record["files"]:
                path=root/name
                if digest(path)!=expected_hash:
                    raise RuntimeError("Frozen daily data changed")
                files.append(path)
            daily=pd.read_parquet(files,columns=["session","open","high","low","close","volume","adjusted_close"])
            daily=daily[daily.session.isin(expected)].sort_values("session").reset_index(drop=True)
            if daily.session.duplicated().any():
                raise ValueError(f"Overlapping daily rows for {symbol}")
            daily["liquidity"]=daily.volume*daily.close
            factor=daily.adjusted_close/daily.close
            for k in ("open","high","low","close"):
                daily[k]*=factor
        for interval, cfg in SETTINGS.items():
            if daily is None or daily.empty:
                excluded[interval]="No daily history at cutoff"
                continue
            bars=bar_series(daily,expected,interval)
            a,b,c=[int(bars.session.searchsorted(d)) for d in (START,SPLIT,END)]
            if b-a<cfg["minimum"][0] or c-b<cfg["minimum"][1]:
                excluded[interval]=f"Only {b-a} train and {c-b} validation bars"
                continue
            arr,atr=signals(bars,cfg)
            prices=np.ascontiguousarray(bars[["open","high","low","close"]].to_numpy())
            cap=bars.liquidity.rolling(3).min().fillna(0).to_numpy()*.001
            scores, passive = [], []
            for first,last in ((a,b),(b,c)):
                flags=np.zeros(len(bars),dtype=bool)
                flags[last-1]=True
                for rule,(sl,tp),hold in product(range(len(LABELS)),SL_TP,cfg["hold"]):
                    scores.append(list(simulate(prices,flags,arr[:,rule],atr,cap,tp,sl,hold,first,last)))
                passive.append(float(((CAPITAL-FEE)/(prices[first,0]*(1+FRICTION))
                                      *prices[last-1,0]*(1-FRICTION)-FEE)/CAPITAL-1))
            admitted[interval]={"scores":scores,"passive":passive,"train_bars":b-a,"validation_bars":c-b}
        progress["admitted"][symbol]=admitted
        progress["excluded"][symbol]=excluded
        atomic_json(saved,progress)
    output={}
    for interval,cfg in SETTINGS.items():
        data=[scopes[interval] for scopes in progress["admitted"].values() if interval in scopes]
        if not data:
            output[interval]={"eligible_symbols":0,"candidate_count":0,"reason":"No eligible instrument"}
            continue
        candidates=list(product(range(len(LABELS)),SL_TP,cfg["hold"]))
        values=np.asarray([x["scores"] for x in data]).reshape(len(data),2,len(candidates),6)
        passive=np.asarray([x["passive"] for x in data]).mean(axis=0)
        records=[]
        for i,(index,(sl,tp),hold) in enumerate(candidates):
            row={"rule":LABELS[index],"atr_stop":sl,"atr_target":tp,"maximum_hold_bars":hold}
            for part,name in enumerate(("train","validation")):
                data_slice=values[:,part,i,:]
                net=float(data_slice[:,0].mean())
                total=int(data_slice[:,2].sum())
                row[name]={"net":net,"passive":float(passive[part]),"passive_delta":net-float(passive[part]),
                           "median_drawdown":float(np.median(data_slice[:,1])),"trades":total,
                           "win_rate":float(data_slice[:,5].sum()/total) if total else None}
            records.append(row)
        records.sort(key=lambda x:-x["train"]["net"])
        output[interval]={"eligible_symbols":len(data),"candidate_count":len(candidates),
                          "symbol_candidate_replays":len(data)*len(candidates),"train_ranked":records}
    result={"status":"complete","scope":"provisional development","official_v2_evaluations":0,
            "source_symbols":len(plan["source"]),"plan_sha256":digest(plan_file),"timeframes":output,
            "limitations":["Previously observed validation history; no fresh holdout.",
                           "Separate equal-capital stock sleeves and adjusted-price execution proxy.",
                           "Weekly/monthly drawdown is marked at bar closes and can miss larger intraperiod losses.",
                           "ETF and delisted members are included whenever the available history meets coverage."]}
    atomic_json(out/"report.json",result)
    print({k:(v["eligible_symbols"],v["candidate_count"]) for k,v in output.items()},flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root",type=Path)
    parser.add_argument("out",type=Path)
    args=parser.parse_args()
    run(args.root,args.out)
