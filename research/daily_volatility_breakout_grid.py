"""Research-only 1,728 distinct TSX daily volatility breakout configurations.
Close-t signal, open-(t+1) entry, open-(t+2) exit. Explicit cash and round-trip costs.
No live trading, no claim of VMM comparability; Yahoo survivor bias remains.
"""
import itertools,json,pathlib
import numpy as np,pandas as pd,yfinance as yf
OUT=pathlib.Path("research/volatility_breakout_results")
TICKERS="RY.TO TD.TO BNS.TO BMO.TO ENB.TO CNQ.TO SU.TO CVE.TO SHOP.TO AEM.TO ABX.TO CCO.TO TECK-B.TO WPM.TO AC.TO".split()
def download():
 d={}
 for t in TICKERS:
  try:
   z=yf.download(t,start="2016-01-01",auto_adjust=True,progress=False,threads=False)
   if isinstance(z.columns,pd.MultiIndex):z.columns=z.columns.get_level_values(0)
   z=z[["Open","High","Low","Close","Volume"]].dropna()
   if len(z)>750:d[t]=z
  except Exception as e:print("FETCH_FAILED",t,str(e)[:100])
 if len(d)<10:raise RuntimeError("Insufficient genuine historical data")
 return d
def main():
 OUT.mkdir(parents=True,exist_ok=True)
 d=download();ix=pd.DatetimeIndex(sorted(set().union(*(set(z.index) for z in d.values()))))
 c=pd.DataFrame({t:z.Close.reindex(ix) for t,z in d.items()})
 o=pd.DataFrame({t:z.Open.reindex(ix) for t,z in d.items()})
 h=pd.DataFrame({t:z.High.reindex(ix) for t,z in d.items()})
 l=pd.DataFrame({t:z.Low.reindex(ix) for t,z in d.items()})
 v=pd.DataFrame({t:z.Volume.reindex(ix) for t,z in d.items()})
 # 4 breakout x 3 ATR x 4 range expansion x 3 volume x 3 trend x 4 max positions = 1728
 configs=list(itertools.product((10,20,40,80),(10,14,21),(1.,1.5,2.,3.),
                                 (1.,1.5,2.),("none","ma50","ma200"),(1,2,3,5)))
 prev=c.shift(1);tr=pd.concat([(h-l).stack(),(h-prev).abs().stack(),(l-prev).abs().stack()],axis=1).max(axis=1).unstack()
 atr={n:tr.rolling(n,min_periods=n).mean() for n in (10,14,21)}
 prior_high={n:h.shift(1).rolling(n,min_periods=n).max() for n in (10,20,40,80)}
 volratio=v/v.shift(1).rolling(20,min_periods=20).mean()
 ma={n:c.rolling(n,min_periods=n).mean() for n in (50,200)}
 overnight=o.shift(-2)/o.shift(-1)-1
 splits={"train":ix<"2022-01-01","validation":(ix>="2022-01-01")&(ix<"2024-01-01"),"recent_diagnostic":ix>="2024-01-01"}
 rows=[]
 for k,(look,atr_n,expand,rv,trend,slots) in enumerate(configs):
  sig=(c>prior_high[look])&((h-l)>atr[atr_n]*expand)&(volratio>=rv)
  if trend!="none":sig=sig&(c>ma[int(trend[2:])])
  # rank by normalized close breakout magnitude, select at most slots
  strength=((c/prior_high[look])-1).where(sig)
  rank=strength.rank(axis=1,ascending=False,method="first")
  weights=(rank<=slots).astype(float)
  weights=weights.div(weights.sum(axis=1).replace(0,np.nan),axis=0).fillna(0)
  # No holding beyond a day: buy next open, sell following open. No overnight intraday stop.
  valid=o.shift(-1).notna()&o.shift(-2).notna()
  weights=weights.where(valid,0)
  gross=(weights*overnight.fillna(0)).sum(axis=1)
  # Each one-day position incurs both buy and sell costs, no recycled capital or leverage.
  turnover=2*weights.sum(axis=1)
  for cost in (.001,.0025,.005):
   net=(gross-cost*turnover).iloc[:-2]
   for name,mask in splits.items():
    r=net.loc[mask[:-2]]
    if len(r)<100:continue
    eq=(1+r).cumprod();yrs=len(r)/252
    dd=float((eq/eq.cummax()-1).min())
    cagr=float(eq.iloc[-1]**(1/yrs)-1) if eq.iloc[-1]>0 else -1.
    rows.append(dict(config=k,breakout=look,atr=atr_n,range_multiplier=expand,
       rvol=rv,trend=trend,slots=slots,cost=cost,split=name,cagr=cagr,max_dd=dd,
       sharpe=float(r.mean()/r.std()*np.sqrt(252)) if r.std()>0 else 0.,
       net_profit_cad=float(5000*(eq.iloc[-1]-1)),
       traded_days=int((weights.sum(axis=1).iloc[:-2].loc[mask[:-2]]>0).sum())))
 df=pd.DataFrame(rows);df.to_csv(OUT/"full_grid.csv",index=False)
 trn=df[(df.split=="train")&(df.cost==.0025)].sort_values("cagr",ascending=False).head(30)
 val=df[(df.split=="validation")&(df.cost==.0025)]
 summ=trn.merge(val,on="config",suffixes=("_train","_validation"))
 summ.to_csv(OUT/"top30_validation.csv",index=False)
 audit={"distinct_configs":len(configs),"tickers":list(d),"start":str(ix.min()),"end":str(ix.max()),
 "limitations":["Surviving Yahoo tickers only, no EODHD delisted data","Cost per side estimated, no observed spread/slippage",
 "One-day open-to-open returns; no stop-gap or intraday path simulation","Open-to-open exit at following session; not day-trading",
 "Not matched to corrected VMM benchmark","2024+ already exposed, not untouched holdout","No forward paper evidence"]}
 (OUT/"audit.json").write_text(json.dumps(audit,indent=2))
 print("VOLATILITY BREAKOUT",len(configs),"distinct configs, 3 costs",len(d),"tickers")
 print(summ[["config","cagr_train","max_dd_train","cagr_validation","max_dd_validation"]].head(15).to_string(index=False))
if __name__=="__main__":main()
