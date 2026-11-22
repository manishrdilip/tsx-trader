"""Research-only gap continuation/reversal daily grid, no live trading.
Signals use prior-session OHLCV and today's opening gap; entries at today's OPEN
are NOT executable from that gap observation, so entry is NEXT session open,
exit subsequent session open. This avoids same-open signal/fill leakage.
"""
import itertools,json,pathlib
import numpy as np,pandas as pd,yfinance as yf
OUT=pathlib.Path("research/gap_followthrough_results")
TICKERS="RY.TO TD.TO BNS.TO BMO.TO ENB.TO CNQ.TO SU.TO CVE.TO SHOP.TO AEM.TO ABX.TO CCO.TO TECK-B.TO WPM.TO AC.TO".split()
def main():
 OUT.mkdir(parents=True,exist_ok=True);d={}
 for t in TICKERS:
  try:
   z=yf.download(t,start="2016-01-01",auto_adjust=True,progress=False,threads=False)
   if isinstance(z.columns,pd.MultiIndex):z.columns=z.columns.get_level_values(0)
   z=z[["Open","High","Low","Close","Volume"]].dropna()
   if len(z)>750:d[t]=z
  except Exception as e:print("FETCH_FAILED",t,str(e)[:100])
 if len(d)<10:raise RuntimeError("Insufficient genuine history")
 ix=pd.DatetimeIndex(sorted(set().union(*(set(z.index) for z in d.values()))))
 c=pd.DataFrame({t:z.Close.reindex(ix) for t,z in d.items()})
 o=pd.DataFrame({t:z.Open.reindex(ix) for t,z in d.items()})
 v=pd.DataFrame({t:z.Volume.reindex(ix) for t,z in d.items()})
 gap=o/c.shift(1)-1
 dayret=c/o-1
 ma={n:c.rolling(n,min_periods=n).mean() for n in (20,50,200)}
 rv=v/v.shift(1).rolling(20,min_periods=20).mean()
 # 3 gap magnitudes x 2 signs x 3 day-return signs x 3 trend x 4 volume x 3 slots x 3 gap max = 1944 configs
 configs=list(itertools.product((.005,.01,.02),("up","down"),("same","opposite","any"),
                                  ("none","ma20","ma200"),(0.,1.,1.5,2.),(1,3,5),(.03,.06,.12)))
 ret=o.shift(-2)/o.shift(-1)-1
 periods={"train":ix<"2022-01-01","validation":(ix>="2022-01-01")&(ix<"2024-01-01"),"recent_diagnostic":ix>="2024-01-01"}
 rows=[]
 for k,(minimum,sign,daymode,trend,volume,slots,maxgap) in enumerate(configs):
  g=gap if sign=="up" else -gap
  sig=(g>=minimum)&(g<=maxgap)&(rv>=volume)
  if daymode=="same":sig=sig&((dayret if sign=="up" else -dayret)>0)
  if daymode=="opposite":sig=sig&((dayret if sign=="up" else -dayret)<0)
  if trend!="none":sig=sig&(c>ma[int(trend[2:])])
  strength=g.where(sig)
  rank=strength.rank(axis=1,ascending=False,method="first")
  w=(rank<=slots).astype(float)
  w=w.div(w.sum(axis=1).replace(0,np.nan),axis=0).fillna(0)
  w=w.where(o.shift(-1).notna()&o.shift(-2).notna(),0)
  gross=(w*ret.fillna(0)).sum(axis=1).iloc[:-2]
  turnover=(2*w.sum(axis=1)).iloc[:-2]
  for cost in (.001,.0025,.005):
   r=gross-cost*turnover
   for split,mask in periods.items():
    x=r.loc[mask[:-2]]
    if len(x)<100:continue
    equity=(1+x).cumprod();years=len(x)/252
    rows.append(dict(config=k,gap_min=minimum,sign=sign,daymode=daymode,trend=trend,
      volume=volume,slots=slots,gap_max=maxgap,cost=cost,split=split,
      cagr=float(equity.iloc[-1]**(1/years)-1) if equity.iloc[-1]>0 else -1.,
      max_dd=float((equity/equity.cummax()-1).min()),
      net_profit_cad=float(5000*(equity.iloc[-1]-1)),
      sharpe=float(x.mean()/x.std()*np.sqrt(252)) if x.std()>0 else 0.,
      active_days=int((w.sum(axis=1).iloc[:-2].loc[mask[:-2]]>0).sum())))
 df=pd.DataFrame(rows);df.to_csv(OUT/"all_results.csv",index=False)
 train=df[(df.split=="train")&(df.cost==.0025)].sort_values("cagr",ascending=False).head(30)
 valid=df[(df.split=="validation")&(df.cost==.0025)]
 summary=train.merge(valid,on="config",suffixes=("_train","_validation"))
 summary.to_csv(OUT/"top30_validation.csv",index=False)
 (OUT/"audit.json").write_text(json.dumps({"configurations":len(configs),"tickers":list(d),
  "first":str(ix.min()),"last":str(ix.max()),"signal":"close t after observing gap and same-day return",
  "entry":"open t+1","exit":"open t+2",
  "limitations":["Yahoo survivor-only sample","No EODHD data","No actual spread or slippage",
  "No stop-gap simulator or intraday stops","No VMM matched baseline",
  "No untouched out-of-sample or forward paper validation",
  "Costs are approximate and applied round-trip"]},indent=2))
 print("GAP FOLLOWTHROUGH",len(configs),"distinct labeled configs; 3 costs; tickers",len(d))
 print(summary[["config","cagr_train","max_dd_train","cagr_validation","max_dd_validation"]].head(15).to_string(index=False))
if __name__=="__main__":main()
