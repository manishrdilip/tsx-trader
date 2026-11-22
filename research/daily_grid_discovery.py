"""Research-only 3,072-configuration DAILY signal discovery SCREEN, not a broker backtest.
Daily adjusted Yahoo OHLCV; signals close t, returns close t+1 (optimistic close execution proxy).
Chronological discovery/validation; NO untouched holdout or validated VMM comparison.
"""
import itertools, json, pathlib
import numpy as np
import pandas as pd
import yfinance as yf

TICKERS="RY.TO TD.TO BNS.TO BMO.TO ENB.TO CNQ.TO SU.TO CVE.TO SHOP.TO AEM.TO ABX.TO CCO.TO TECK-B.TO WPM.TO AC.TO".split()
OUT=pathlib.Path("research/daily_discovery_results")
COSTS=(.001,.0025,.005)
def load():
    out={}
    for t in TICKERS:
        try:
            d=yf.download(t,start="2016-01-01",auto_adjust=True,progress=False,threads=False)
            if isinstance(d.columns,pd.MultiIndex):d.columns=d.columns.get_level_values(0)
            d=d[["Open","High","Low","Close","Volume"]].dropna()
            if len(d)>=750:out[t]=d
        except Exception as e:print("DATA FAILURE",t,str(e)[:120])
    if len(out)<10:raise RuntimeError("Insufficient real daily history")
    return out
def features(data):
    ix=pd.DatetimeIndex(sorted(set().union(*(set(d.index) for d in data.values()))))
    close=pd.DataFrame({t:d.Close.reindex(ix) for t,d in data.items()})
    volume=pd.DataFrame({t:d.Volume.reindex(ix) for t,d in data.items()})
    ret=close.pct_change(fill_method=None).shift(-1)
    # Signal at close t, next CLOSE return is an optimistic screening proxy.
    return ix,close,volume,ret
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    data=load(); ix,c,v,ret=features(data)
    # 4*4*4*4*4*3=3072 genuinely distinct parameter sets
    configs=list(itertools.product((10,20,40,80),(50,100,150,200),(.02,.05,.10,.20),
                                   (1.,1.5,2.,3.),(0.,.02,.05,.10),(1,3,5)))
    mom={n:c/c.shift(n)-1 for n in (10,20,40,80)}
    trend={n:c.rolling(n,min_periods=n).mean() for n in (50,100,150,200)}
    highs={n:c.rolling(60,min_periods=60).max() for n in (1,3,5)}
    volratio=v/v.shift(1).rolling(20,min_periods=20).mean()
    dates=ix
    # 2016-2021 discovery, 2022-2023 validation, 2024 onward diagnostic only
    periods={"train":(dates<"2022-01-01"),"validation":((dates>="2022-01-01")&(dates<"2024-01-01")),
             "recent_diagnostic":(dates>="2024-01-01")}
    rows=[]
    for i,(momentum,ma,pullback,rvol,minimum,hold) in enumerate(configs):
        sig=(mom[momentum]>minimum)&(c>trend[ma])&(c>=highs[hold]*(1-pullback))&(volratio>=rvol)
        # Shift by 1 session per ticker: no same-close fill; no future bars in signal.
        # Hold=1/3/5 is a rolling-high LOOKBACK parameter, NOT position holding duration.
        # Equal weight among active names, max five simultaneous, deterministic alphabetical order.
        active=sig.shift(1).fillna(False)
        active=active.astype(int).cumsum(axis=1).le(5)&active
        w=active.div(active.sum(axis=1).replace(0,np.nan),axis=0).fillna(0)
        # Return close(t-1) to close(t) from signal(t-1); mark to market.
        gross=(w*c.pct_change(fill_method=None).fillna(0)).sum(axis=1)
        turnover=w.diff().abs().sum(axis=1).fillna(w.abs().sum(axis=1))
        for cost in COSTS:
            net=gross-cost*turnover
            for name,mask in periods.items():
                r=net.loc[mask];eq=(1+r).cumprod()
                if len(r)<100:continue
                yrs=len(r)/252
                cagr=float(eq.iloc[-1]**(1/yrs)-1) if eq.iloc[-1]>0 else -1.
                dd=float((eq/eq.cummax()-1).min())
                rows.append(dict(config=i,momentum=momentum,ma=ma,pullback=pullback,
                    rvol=rvol,min_momentum=minimum,high_lookback=hold,cost=cost,
                    split=name,cagr=cagr,max_dd=dd,net_return=float(eq.iloc[-1]-1),
                    active_days=int((w.loc[mask].sum(axis=1)>0).sum()),
                    avg_turnover=float(turnover.loc[mask].mean())))
    result=pd.DataFrame(rows)
    result.to_csv(OUT/"all_9216_cost_configurations_by_split.csv",index=False)
    a=result[(result.split=="train")&(result.cost==.0025)].sort_values("cagr",ascending=False)
    shortlist=a.head(30)[["config","cagr","max_dd"]].merge(
        result[(result.split=="validation")&(result.cost==.0025)][["config","cagr","max_dd"]],
        on="config",suffixes=("_train","_validation"))
    shortlist.to_csv(OUT/"train_top30_validation.csv",index=False)
    audit={"tickers":list(data),"first":str(ix.min()),"last":str(ix.max()),
       "configurations":len(configs),"cost_levels":list(COSTS),
       "discovery":"2016-2021","validation":"2022-2023",
       "recent_diagnostic":"2024 onward (NOT untouched: already researched)",
       "critical_limitations":["Yahoo surviving ticker sample; delisted stocks missing",
       "not EODHD data; no credential available to runner",
       "daily adjusted close returns are screening proxy, not executable next-open fills",
       "no stops/gaps, broker fills or intraday risk model",
       "no corrected matched VMM baseline; no 3x claim permitted",
       "multiple testing, selected validation already inspected; no untouched holdout",
       "transaction cost estimated; turnover approximate"]}
    (OUT/"audit.json").write_text(json.dumps(audit,indent=2))
    print("SCREENED",len(configs),"configs across",len(data),"tickers, 3 costs; rows",len(result))
    print(shortlist.to_string(index=False))
if __name__=="__main__":main()
