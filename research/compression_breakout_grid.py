"""Research-only TSX volatility-compression breakout grid.
Signals at prior close; buy next open; sell following open. Integer shares and cash.
Not a matched VMM test or proof of an executable edge.
"""
import itertools,json,pathlib
import numpy as np,pandas as pd
from research.daily_cash_ledger_audit import fetch
OUT=pathlib.Path("research/compression_breakout_results")
def evaluate(op,cl,hi,lo,vol,params,cost):
    window,ratio,breakout,volume,trend,slots=params
    tr=hi.rolling(window,min_periods=window).max()-lo.rolling(window,min_periods=window).min()
    atr=(hi-lo).rolling(14,min_periods=14).mean()
    compression=tr/(atr*window).replace(0,np.nan)
    threshold=compression.rolling(120,min_periods=120).quantile(ratio)
    prevhigh=hi.shift(1).rolling(breakout,min_periods=breakout).max()
    rv=vol/vol.shift(1).rolling(20,min_periods=20).mean()
    ma=cl.rolling(200,min_periods=200).mean()
    signal=(compression.shift(1)<threshold.shift(1))&(cl>prevhigh)&(rv>volume)
    if trend:signal &= cl>ma
    cash=5000.; held={}; curve=[]; trades=[]
    for i in range(220,len(op)):
        day=op.index[i];price=op.iloc[i]
        for t,p in list(held.items()):
            px=float(price[t])
            if not np.isfinite(px) or px<=0:raise ValueError("missing exit "+t)
            proceeds=p[0]*px*(1-cost);cash+=proceeds;trades.append(proceeds-p[1]);del held[t]
        if i<len(op)-1:
            prev=op.index[i-1]
            names=[t for t in op.columns if bool(signal.loc[prev,t]) and np.isfinite(price[t]) and price[t]>0]
            names.sort(key=lambda t:(-float(rv.loc[prev,t]),t))
            budget=cash/slots
            for t in names[:slots]:
                px=float(price[t]);qty=int(min(budget,cash)/(px*(1+cost)))
                if qty:
                    spent=qty*px*(1+cost);cash-=spent;held[t]=(qty,spent)
        if cash< -1e-6 or len(held)>slots:raise AssertionError("cash or slots")
        equity=cash+sum(q*float(price[t])*(1-cost) for t,(q,_) in held.items())
        curve.append((day,equity))
    return pd.Series(dict(curve)),np.array(trades)
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    data=fetch()
    ix=pd.DatetimeIndex(sorted(set.intersection(*(set(d.index) for d in data.values()))))
    op=pd.DataFrame({t:d.Open.reindex(ix) for t,d in data.items()})
    cl=pd.DataFrame({t:d.Close.reindex(ix) for t,d in data.items()})
    # Original fetch only returns Open/Close/Volume: retrieve high/low separately
    import yfinance as yf
    highs={};lows={}
    for t in data:
        d=yf.download(t,start="2016-01-01",auto_adjust=True,progress=False,threads=False)
        if isinstance(d.columns,pd.MultiIndex):d.columns=d.columns.get_level_values(0)
        highs[t]=d.High.reindex(ix);lows[t]=d.Low.reindex(ix)
    hi=pd.DataFrame(highs);lo=pd.DataFrame(lows)
    vol=pd.DataFrame({t:d.Volume.reindex(ix) for t,d in data.items()})
    configs=list(itertools.product((10,20,30,40),(.1,.2,.3,.4),(10,20,40),(1.,1.5,2.),(False,True),(1,3,5)))
    # 4*4*3*3*2*3 = 864 configurations; 3 costs => 2592 tests.
    rows=[]
    for n,p in enumerate(configs):
        for cost in (.001,.0025,.005):
            curve,pnl=evaluate(op,cl,hi,lo,vol,p,cost)
            for split,mask in {"train":curve.index<"2022-01-01","validation":(curve.index>="2022-01-01")&(curve.index<"2024-01-01"),"recent_diagnostic":curve.index>="2024-01-01"}.items():
                c=curve.loc[mask]
                if len(c)<100:continue
                start=curve.iloc[curve.index.get_loc(c.index[0])-1] if curve.index.get_loc(c.index[0]) else 5000.
                gross=float(c.iloc[-1]/start)
                daily=c.pct_change().dropna()
                rows.append(dict(config=n,window=p[0],compression_quantile=p[1],breakout=p[2],relative_volume=p[3],trend=p[4],slots=p[5],cost=cost,split=split,
                    cagr=gross**(252/len(c))-1,max_dd=float((c/c.cummax()-1).min()),
                    net_profit_cad=float(c.iloc[-1]-start),sharpe=float(daily.mean()/daily.std()*np.sqrt(252)) if daily.std()>0 else None,
                    note="profit factor and expectancy require split-aligned trade ledger"))
    df=pd.DataFrame(rows);df.to_csv(OUT/"grid.csv",index=False)
    train=df[(df.split=="train")&(df.cost==.0025)].sort_values("cagr",ascending=False).head(20)
    validation=df[(df.split=="validation")&(df.cost==.0025)]
    train.merge(validation,on="config",suffixes=("_train","_validation")).to_csv(OUT/"train_top20_validation.csv",index=False)
    (OUT/"audit.json").write_text(json.dumps({"distinct_configurations":len(configs),"cost_scenarios":3,"tickers":list(data),
      "limitations":["Survivorship bias; surviving Yahoo symbols only","Adjusted open prices are not broker executions",
      "No observed spreads, borrow constraints or intraday stops","No untouched out-of-sample or forward paper trading",
      "No matched corrected VMM baseline","No intraday gap stop model","Profit factor and expectancy not yet split-accounted"]},indent=2))
    print("Completed",len(configs),"unique configurations, 3 cost scenarios")
    print(train.merge(validation,on="config",suffixes=("_train","_validation")).head(10).to_string(index=False))
if __name__=="__main__":main()
