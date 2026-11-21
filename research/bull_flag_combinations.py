"""Research only: Bull Flag plus repository-inspired DAILY trend/RS/market filters.
Uses real five-minute data (up to 60d), current TSX universe, no broker actions.
No historical five-minute data before Yahoo's availability is claimed.
"""
import os,sys,json,time
from pathlib import Path
import pandas as pd
import numpy as np
import yfinance as yf
sys.path.insert(0,str(Path(__file__).resolve().parent))
import pro_intraday_test as core

MAX_TICKERS=int(os.getenv("MAX_TICKERS","100"))
OUT=Path("research/intraday_combo_results")
VARIANTS=("bull_flag","flag_market","flag_stage2","flag_rs","flag_stage2_market","flag_rs_market","flag_stage2_rs_market","flag_market_down_control","flag_rvol2","flag_rvol2_stage2")
def get_universe():
    p=Path("universe_tickers.json")
    tickers=json.loads(p.read_text())
    # The repo's ticker list is currently-listed, not point-in-time.
    return [x for x in tickers if x.endswith(".TO") and x not in ("XIU.TO","XIC.TO")][:MAX_TICKERS]
def daily_context(tickers):
    d=yf.download(tickers+["XIU.TO"],period="2y",interval="1d",auto_adjust=True,progress=False,threads=True,group_by="ticker")
    out={}
    xi=d["XIU.TO"]["Close"].dropna()
    mkt=(xi>xi.rolling(200,min_periods=200).mean()).shift(1).fillna(False)
    for t in tickers:
        try:
            x=d[t].dropna()
            if len(x)<260:continue
            c=x.Close
            stage=(c>c.rolling(50).mean())&(c.rolling(50).mean()>c.rolling(150).mean())&(c.rolling(150).mean()>c.rolling(200).mean())
            mom=c.pct_change(63)
            # Approximate RS percentile among available current survivors, computed only from past 63d closes.
            out[t]={"stage":stage.shift(1).fillna(False),"momentum":mom.shift(1)}
        except Exception:continue
    mom_frame=pd.DataFrame({t:v["momentum"] for t,v in out.items()})
    rank=mom_frame.rank(axis=1,pct=True)
    return out,rank,mkt
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    names=get_universe()
    data={};failed={}
    for j,t in enumerate(names):
        try:
            d=core.get_data(t)
            if d is not None:data[t]=d
            else:failed[t]="missing 5m"
        except Exception as e:failed[t]=str(e)[:100]
        if j%20==19:print("INTRADAY FETCH",j+1,len(data),flush=True)
        time.sleep(.06)
    if len(data)<10:raise RuntimeError("Insufficient intraday data; "+str(failed)[:400])
    context,rank,mkt=daily_context(list(data))
    data={t:d for t,d in data.items() if t in context}
    # Each signal uses PREVIOUS completed daily bar context, never today's close.
    # Map the preceding trading day to today's 5m bars; daily indicators are shifted by one.
    print("MARKET FILTER AUDIT",{"market_up_days":int(mkt.sum()),"total_days":len(mkt),"market_up_last_60":int(mkt.tail(60).sum())},flush=True)
    combos={}
    gate_audit={}
    for variant in VARIANTS:
        panel={}
        signal_before=0
        signal_after=0
        market_allowed_days=set()
        for t,d in data.items():
            f=core.signals(d,"bull_flag")
            days=pd.DatetimeIndex(pd.Index(d.index.date).unique())
            stage=context[t]["stage"].reindex(days,method="ffill").fillna(False).to_numpy(dtype=bool)
            rs=rank[t].reindex(days,method="ffill").fillna(0).to_numpy(dtype=float)
            mk=mkt.reindex(days,method="ffill").fillna(False).to_numpy(dtype=bool)
            gate=np.ones(len(days),dtype=bool)
            if "stage2" in variant:gate &= stage
            if "rs" in variant:gate &= rs>=.8
            if "market_down_control" in variant:gate &= ~mk
            elif "market" in variant:gate &= mk
            # Convert each 5-minute bar to the index of its completed session.
            # Avoid date/Timestamp map inference and pandas index alignment.
            day_codes=pd.Index(days).get_indexer(pd.DatetimeIndex(d.index.normalize().tz_localize(None)))
            if (day_codes<0).any():raise AssertionError("Intraday date missing from daily gate")
            gates=gate[day_codes]
            if "market_down_control" in variant and np.any(gates & mk[day_codes]):
                raise AssertionError("Down-market filter admitted up-market bar")
            if "market" in variant and "down_control" not in variant and np.any(gates & ~mk[day_codes]):
                raise AssertionError("Up-market filter admitted down-market bar")
            signal_before+=int(f["signal"].sum())
            signal_after+=int((f["signal"] & gates).sum())
            market_allowed_days.update(str(x) for x in days[gate])
            f["signal"]=f["signal"].to_numpy(dtype=bool) & gates
            if "rvol2" in variant:
                f["signal"]=f["signal"] & (f["rvol"]>2.0)
            # Count the final signals, including relative-volume confirmation,
            # rather than only the daily regime/stage gates.
            panel[t]=(d,f)
        combos[variant]=panel
        gate_audit[variant]={"signals_before":signal_before,"signals_after_daily_gate":signal_after,"signals_after_all_filters":sum(int(f["signal"].sum()) for _,f in panel.values()),"allowed_days":len(market_allowed_days)}
    print("FILTER AUDIT",json.dumps(gate_audit,sort_keys=True),flush=True)
    # Positive and negative controls must partition identical raw signals.
    if gate_audit["flag_market"]["signals_after_all_filters"] + gate_audit["flag_market_down_control"]["signals_after_gate"] != gate_audit["bull_flag"]["signals_before"]:
        raise AssertionError("Market regime filters do not partition raw Bull Flag signals")
    # A down-market control is a negative control: if it selects exactly the
    # same number of signals as the up-market filter, flag a regime issue.
    if gate_audit["flag_market"]["signals_after_gate"]==gate_audit["flag_market_down_control"]["signals_after_gate"]:
        print("WARNING: up/down regime controls admit identical signal counts; investigate XIU regime and date alignment",flush=True)
    # Adapt core simulator to precomputed filtered signal frames without modifying live bot.
    # Pass precomputed filters through a temporary override of the research module's signal function.
    orig=core.signals
    results=[]
    try:
        for variant,panel in combos.items():
            core.signals=lambda d,method, panel=panel: panel[d.attrs["ticker"]][1]
            marked={}
            for t,(d,f) in panel.items():
                copy=d.copy();copy.attrs["ticker"]=t;marked[t]=copy
            z,trades,daily=core.simulate(marked,"bull_flag")
            z["variant"]=variant
            results.append(z)
            pd.DataFrame(trades).to_csv(OUT/(variant+"_trades.csv"),index=False)
            pd.DataFrame(daily).to_csv(OUT/(variant+"_daily.csv"),index=False)
    finally:core.signals=orig
    pd.DataFrame(results).to_csv(OUT/"summary.csv",index=False)
    (OUT/"audit.json").write_text(json.dumps({"requested_tickers":len(names),"usable_tickers":len(data),"failures":failed,"filter_audit":gate_audit,"limitations":["currently listed universe only: survivorship bias","Yahoo 5-minute limited history; NOT full historical intraday TSX","daily filters based on preceding completed daily session","RS rank computed across available current survivors","no true spread/order book","same-bar OHLC stop-first approximation","multiple-testing: winning combination requires independent forward validation"]},indent=2))
    print(pd.DataFrame(results).to_string(index=False))
if __name__=="__main__":main()
