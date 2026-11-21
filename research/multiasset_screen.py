"""Research-only cross-asset screening; real OHLCV, no orders, no options proxies.
Five-year DAILY candles. Next-open entries, stop-first OHLC exits, fees, no leverage.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import yfinance as yf

ASSETS={
"TSX_ETF":["XIU.TO","XIC.TO","ZSP.TO","HXT.TO"],
"US_ETF":["SPY","QQQ","IWM"],
"US_STOCK":["NVDA","AAPL","MSFT","AMD","TSLA"],
"GOLD_ETF":["CGL.C","KILO.TO","GLD"],
"CRYPTO":["BTC-USD","ETH-USD","SOL-USD"],
"FUTURES_RESEARCH_ONLY":["GC=F","ES=F","NQ=F"],
}
# Futures research only: historical continuous contracts are NOT directly executable Wealthsimple instruments.
# US assets and USD crypto are evaluated in native quote currency; CAD conversion is NOT modeled.
# The $5000 figure is a normalized starting amount, NOT CAD profit for USD series.
COST={"CRYPTO":.007,"FUTURES_RESEARCH_ONLY":.0015}
START=5000.
OUT=Path("research/multiasset_results")
def download(t):
    d=yf.download(t,period="5y",interval="1d",auto_adjust=True,progress=False,threads=False)
    if isinstance(d.columns,pd.MultiIndex):d.columns=d.columns.get_level_values(0)
    if d.empty or len(d)<260:return None
    return d[["Open","High","Low","Close","Volume"]].dropna()
def features(d):
    c=d.Close
    tr=pd.concat([d.High-d.Low,(d.High-c.shift()).abs(),(d.Low-c.shift()).abs()],axis=1).max(axis=1)
    atr=tr.rolling(14).mean()
    sma50=c.rolling(50).mean();sma200=c.rolling(200).mean()
    return atr,sma50,sma200
def test(d,method,cost,start,end):
    atr,s50,s200=features(d)
    # Signal is evaluated at previous day's close, never current day's future high.
    if method=="trend_breakout":
        signal=(d.Close>d.High.shift(1).rolling(20).max())&(d.Close>s200)&(s50>s200)
    elif method=="trend_pullback":
        signal=(d.Close>s200)&(s50>s200)&(d.Close<s50)&(d.Close>d.Close.shift(1))
    elif method=="mean_reversion":
        signal=(d.Close>s200)&(d.Close/d.Close.shift(5)<.95)&(d.Close>d.Close.shift(1))
    elif method=="momentum_60":
        signal=(d.Close>s200)&(d.Close/d.Close.shift(60)>1.12)&(d.Close>d.High.shift(1).rolling(10).max())
    else:raise ValueError(method)
    cash=START; pos=None; trades=[];curve=[]
    for i in range(1,len(d)):
        dt=d.index[i]
        if dt<pd.Timestamp(start) or dt>pd.Timestamp(end):continue
        r=d.iloc[i]
        if pos is not None:
            px=None;reason=None
            if r.Open<=pos["stop"]:px=float(r.Open);reason="gap_stop"
            elif r.Low<=pos["stop"]:px=pos["stop"];reason="stop"
            elif r.Open>=pos["target"]:px=float(r.Open);reason="gap_target"
            elif r.High>=pos["target"]:px=pos["target"];reason="target"
            elif i-pos["i"]>=10: px=float(r.Close);reason="time"
            if px is not None:
                cash+=pos["qty"]*px*(1-cost)
                trades.append({"entry":str(d.index[pos["i"]].date()),"exit":str(dt.date()),"pnl":round(pos["qty"]*px*(1-cost)-pos["spent"],2),"reason":reason})
                pos=None
        if pos is None and bool(signal.iloc[i-1]) and np.isfinite(atr.iloc[i-1]):
            op=float(r.Open); a=float(atr.iloc[i-1])
            if op>0 and a>0 and op<=float(d.Close.iloc[i-1])*1.03:
                # 0.5% risk, cap 80% of equity, fractional quantities allowed for cross-asset comparison.
                risk=min(.025*op,2*a)
                qty=min(cash*.8/(op*(1+cost)),cash*.005/(risk+2*op*cost))
                if qty>0:
                    spent=qty*op*(1+cost);cash-=spent
                    pos={"qty":qty,"stop":op-risk,"target":op+2*risk,"spent":spent,"i":i}
        equity=cash+(pos["qty"]*float(r.Close) if pos is not None else 0)
        curve.append((dt,equity))
    if not curve:return None,[]
    if pos:
        cash+=pos["qty"]*float(d.Close.iloc[-1])*(1-cost)
        trades.append({"entry":str(d.index[pos["i"]].date()),"exit":str(d.index[-1].date()),"pnl":round(pos["qty"]*float(d.Close.iloc[-1])*(1-cost)-pos["spent"],2),"reason":"final_liquidation"})
    s=pd.Series(dict(curve))
    return {"start":START,"final":round(cash,2),"return_pct":round((cash/START-1)*100,2),"max_dd_pct":round(float((s/s.cummax()-1).min())*100,2),"trades":len(trades),"win_rate":round(sum(t["pnl"]>0 for t in trades)/len(trades),3) if trades else None},trades
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    results=[]; failures={}; data={}
    for category,tickers in ASSETS.items():
        for ticker in tickers:
            try:
                d=download(ticker)
                if d is None:failures[ticker]="missing/insufficient historical data";continue
                data[ticker]=d
            except Exception as e:failures[ticker]=str(e)[:160]
    for category,tickers in ASSETS.items():
        for ticker in tickers:
            if ticker not in data:continue
            d=data[ticker];fee=COST.get(category,.001)
            split=d.index[int(len(d)*.7)]
            for method in ("trend_breakout","trend_pullback","mean_reversion","momentum_60"):
                for period,start,end in (("train",d.index[0],d.index[int(len(d)*.7)-1]),("holdout",split,d.index[-1])):
                    z,trades=test(d,method,fee,start,end)
                    if z is None:continue
                    z.update(category=category,ticker=ticker,method=method,period=period,fee_per_side=fee)
                    results.append(z)
    pd.DataFrame(results).to_csv(OUT/"summary.csv",index=False)
    (OUT/"audit.json").write_text(json.dumps({"failures":failures,"downloaded":list(data),"limitations":["Daily, not intraday","No options prices: options NOT tested","No Wealthsimple futures contract mapping","Native USD or CAD denomination, not currency converted","Current survivor selection bias","No borrow, margin, funding, overnight gap insurance","No reliable bid-ask historical spread","Crypto assumed 0.7% each side as illustrative fee plus spread; actual Wealthsimple spread varies","Historical futures continuous series can have roll artifacts"]},indent=2))
    print("DATA",len(data),"failed",failures)
    x=pd.DataFrame(results)
    print("HOLDOUT RESULTS (ranked; exploratory only):")
    print(x[x.period=="holdout"].sort_values("return_pct",ascending=False).head(25).to_string(index=False))
    print("CATEGORY HOLDOUT MEDIANS:")
    print(x[x.period=="holdout"].groupby(["category","method"]).agg(n=("ticker","count"),median_return=("return_pct","median"),median_drawdown=("max_dd_pct","median"),median_trades=("trades","median")).to_string())
if __name__=="__main__":main()
