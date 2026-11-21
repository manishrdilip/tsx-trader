"""Research only: five TSX intraday strategies on real 5-minute OHLCV.
Not live/paper forward trading. No brokerage connection. No fabricated candles.
Signals at bar close; fill at NEXT bar open. Flat before session close.
Survivorship bias, no bid/ask data, and limited 5m history remain.
"""
import json, math, os
from pathlib import Path
import numpy as np
import pandas as pd
import yfinance as yf

TICKERS="RY.TO TD.TO BNS.TO BMO.TO ENB.TO CNQ.TO SU.TO CVE.TO SHOP.TO AEM.TO ABX.TO CCO.TO TECK-B.TO WPM.TO AC.TO".split()
START_CASH=5000.; COST=.001; RISK=.005; SLOTS=3
TZ="America/Toronto"
OUT=Path("research/intraday_results")

def get_data(ticker):
    d=yf.download(ticker,period="60d",interval="5m",auto_adjust=True,progress=False,threads=False)
    if d.empty:return None
    if isinstance(d.columns,pd.MultiIndex):
        d.columns=d.columns.get_level_values(0)
    if d.index.tz is None: raise ValueError("5m timestamps must include timezone")
    d=d.tz_convert(TZ)
    d=d.between_time("09:30","15:55").copy()
    d=d[["Open","High","Low","Close","Volume"]].dropna()
    d=d[(d.Volume>0)&(d.Open>0)]
    if len(d)<150:return None
    return d

def signals(d,method):
    c=d.Close; vol=d.Volume
    day=pd.Series(d.index.date,index=d.index)
    n=day.groupby(day).cumcount()
    vwap=(c*vol).groupby(day).cumsum()/vol.groupby(day).cumsum().replace(0,np.nan)
    relvol=vol/(vol.shift(1).rolling(78,min_periods=30).mean()).replace(0,np.nan)
    first_high=d.High.where(n<6).groupby(day).transform("max")
    first_low=d.Low.where(n<6).groupby(day).transform("min")
    prior_high=d.High.shift(1).rolling(12,min_periods=12).max()
    prior_low=d.Low.shift(1).rolling(12,min_periods=12).min()
    ema9=c.ewm(span=9,adjust=False).mean()
    ema20=c.ewm(span=20,adjust=False).mean()
    # All features are available by the CLOSE of this bar only.
    if method=="orb":
        s=(n>=6)&(n<42)&(c>first_high)&(c.shift(1)<=first_high)&(relvol>1.5)
        stop=first_high-(first_high-first_low)*.25
    elif method=="vwap":
        s=(n>=12)&(n<55)&(c>vwap)&(c.shift(1)<=vwap.shift(1))&(ema9>ema20)&(relvol>1)
        stop=vwap-d.Close*.004
    elif method=="bull_flag":
        surge=(c/c.shift(6)-1)>.012
        flag=surge.shift(1).rolling(8,min_periods=8).max().fillna(0)>0
        s=(n>=12)&(n<55)&flag&(c>prior_high)&(relvol>1.5)
        stop=prior_low
    elif method=="resistance":
        s=(n>=12)&(n<55)&(c>prior_high)&(c.shift(1)<=prior_high.shift(1))&(relvol>1.5)
        stop=prior_low
    elif method=="mean_reversion":
        dev=(c-vwap)/vwap
        s=(n>=12)&(n<55)&(dev.shift(1)<-.012)&(c>c.shift(1))&(c<vwap)&(relvol>1)
        stop=d.Low.shift(1).rolling(5,min_periods=5).min()
    else:raise ValueError(method)
    # No entries after 14:05 ET; close everything by 15:55.
    return pd.DataFrame({"signal":s.fillna(False),"stop":stop,"vwap":vwap,"rvol":relvol},index=d.index)

def simulate(data,method):
    byday={}
    for ticker,d in data.items():
        f=signals(d,method)
        for i,ts in enumerate(d.index):
            byday.setdefault(ts,[]).append((ticker,i))
        data[ticker]=(d,f)
    cash=START_CASH;positions={};trades=[];daily=[];all_ts=sorted(byday)
    last_day=None
    for ts in all_ts:
        # Always flatten at final available bar of day. This is an approximate close fill.
        for ticker,i in byday[ts]:
            d,f=data[ticker];row=d.iloc[i]
            if ticker not in positions:continue
            p=positions[ticker]
            reason=None;px=None
            if row.Open<=p["stop"]:px=float(row.Open);reason="gap_stop"
            elif row.Low<=p["stop"]:px=p["stop"];reason="stop"
            elif row.Open>=p["target"]:px=float(row.Open);reason="gap_target"
            elif row.High>=p["target"]:px=p["target"];reason="target"
            elif ts.strftime("%H:%M")>="15:50" or (i==len(d)-1) or (i+1<len(d) and d.index[i+1].date()!=ts.date()):
                px=float(row.Close);reason="end_of_day"
            if px is not None:
                proceeds=p["qty"]*px*(1-COST);cash+=proceeds
                trades.append(dict(strategy=method,ticker=ticker,entry=str(p["time"]),exit=str(ts),reason=reason,pnl=round(proceeds-p["spent"],2),return_pct=round(100*(proceeds/p["spent"]-1),3)))
                del positions[ticker]
        # A signal at bar i-1 CLOSE may enter at bar i OPEN, same ticker/session only.
        picks=[]
        for ticker,i in byday[ts]:
            if ticker in positions or i==0:continue
            d,f=data[ticker]
            if d.index[i-1].date()!=ts.date() or ts.strftime("%H:%M")>="14:05":continue
            if not bool(f["signal"].iloc[i-1]):continue
            op=float(d.Open.iloc[i]);stop=float(f["stop"].iloc[i-1])
            if not(np.isfinite(op) and np.isfinite(stop) and stop>0 and op>stop):continue
            # Reject extreme gap between signal close and next open.
            if abs(op/float(d.Close.iloc[i-1])-1)>.01:continue
            picks.append((float(f["rvol"].iloc[i-1]),ticker,op,stop))
        for _,ticker,op,stop in sorted(picks,reverse=True):
            if len(positions)>=SLOTS:break
            marked=cash
            for t,p in positions.items():
                d,_=data[t];hist=d.loc[d.index<=ts,"Close"]
                marked+=p["qty"]*float(hist.iloc[-1]) if len(hist) else p["spent"]
            qty=int(min(cash/(op*(1+COST)),marked/SLOTS/(op*(1+COST)),marked*RISK/(op-stop+2*op*COST)))
            if qty<1:continue
            spent=qty*op*(1+COST);cash-=spent
            positions[ticker]={"qty":qty,"stop":stop,"target":op+2*(op-stop),"spent":spent,"time":ts}
        if last_day is not None and ts.date()!=last_day:
            daily.append(dict(date=str(last_day),equity=round(cash,2)))
        last_day=ts.date()
    # Any unclosed holdings are valued at last available close, minus sell costs.
    final=cash
    for ticker,p in positions.items():
        d,_=data[ticker];final+=p["qty"]*float(d.Close.iloc[-1])*(1-COST)
    if last_day:daily.append(dict(date=str(last_day),equity=round(final,2)))
    curve=pd.Series({r["date"]:r["equity"] for r in daily},dtype=float)
    mdd=float((curve/curve.cummax()-1).min()) if len(curve) else None
    return dict(strategy=method,start=START_CASH,final=round(final,2),net=round(final-START_CASH,2),trades=len(trades),win_rate=round(sum(t["pnl"]>0 for t in trades)/len(trades),4) if trades else None,max_dd=mdd,days=len(curve),data_tickers=len(data)),trades,daily

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    downloaded={};fail={}
    for t in TICKERS:
        try:
            d=get_data(t)
            if d is not None:downloaded[t]=d
            else:fail[t]="insufficient 5m data"
        except Exception as e:fail[t]=str(e)[:180]
    if len(downloaded)<5:raise RuntimeError(f"Insufficient real intraday data: {fail}")
    results=[]
    for method in ("orb","vwap","bull_flag","resistance","mean_reversion"):
        z,trades,daily=simulate(dict(downloaded),method)
        results.append(z)
        pd.DataFrame(trades).to_csv(OUT/f"{method}_trades.csv",index=False)
        pd.DataFrame(daily).to_csv(OUT/f"{method}_daily.csv",index=False)
    pd.DataFrame(results).to_csv(OUT/"summary.csv",index=False)
    (OUT/"data_audit.json").write_text(json.dumps({"downloaded":list(downloaded),"failures":fail,"data_window":"Yahoo 5-minute bars, latest 60 days only","limitations":["survivorship bias","short sample","no spread/order-book/slippage model beyond 0.1% each side","same-bar stop-first assumption","no proof of executable prices"]},indent=2))
    print(pd.DataFrame(results).to_string(index=False))
    print("DATA AUDIT:",json.dumps(fail))
if __name__=="__main__":main()
