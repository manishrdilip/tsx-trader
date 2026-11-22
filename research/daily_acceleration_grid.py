"""Research-only cross-sectional momentum ACCELERATION screen (not executable).
Signal at close t; position at open t+1; return open t+1 to open t+2.
No live orders. Yahoo surviving-stock universe and estimated costs.
"""
import itertools,json,pathlib
import numpy as np,pandas as pd,yfinance as yf
OUT=pathlib.Path("research/acceleration_results")
TICKERS="RY.TO TD.TO BNS.TO BMO.TO ENB.TO CNQ.TO SU.TO CVE.TO SHOP.TO AEM.TO ABX.TO CCO.TO TECK-B.TO WPM.TO AC.TO".split()
def main():
 OUT.mkdir(parents=True,exist_ok=True)
 data={}
 for t in TICKERS+["XIU.TO"]:
  try:
   d=yf.download(t,start="2016-01-01",auto_adjust=True,progress=False,threads=False)
   if isinstance(d.columns,pd.MultiIndex):d.columns=d.columns.get_level_values(0)
   d=d[["Open","Close","Volume"]].dropna()
   if len(d)>750:data[t]=d
  except Exception as e:print("FETCH_FAIL",t,str(e)[:100])
 if "XIU.TO" not in data or len(data)<11:raise RuntimeError("Insufficient real market history")
 ix=data["XIU.TO"].index; names=sorted(set(data)-{"XIU.TO"})
 c=pd.DataFrame({t:data[t].Close.reindex(ix) for t in names})
 o=pd.DataFrame({t:data[t].Open.reindex(ix) for t in names})
 v=pd.DataFrame({t:data[t].Volume.reindex(ix) for t in names})
 market=data["XIU.TO"].Close.reindex(ix)
 # 4 x 4 x 3 x 3 x 3 x 3 = 1296 genuinely distinct configurations.
 configs=list(itertools.product((5,10,20,40),(20,40,60,120),
          (0,.01,.03),(1.,1.5,2.),(1,3,5),(50,100,200)))
 short={n:c.pct_change(n,fill_method=None) for n in (5,10,20,40)}
 long={n:c.pct_change(n,fill_method=None) for n in (20,40,60,120)}
 vol=v/v.shift(1).rolling(20,min_periods=20).mean()
 trend={n:market.rolling(n,min_periods=n).mean() for n in (50,100,200)}
 ret=o.shift(-1)/o-1
 splits={"train":ix<"2022-01-01","validation":(ix>="2022-01-01")&(ix<"2024-01-01"),
         "recent_diagnostic":ix>="2024-01-01"}
 rows=[]
 for k,(s,l,minimum,rvol,slots,ma) in enumerate(configs):
  # acceleration: recent daily momentum exceeds longer-horizon daily momentum
  score=short[s]/s-long[l]/l
  eligible=(score>minimum/s)&(short[s]>0)&(vol>=rvol)&(market>trend[ma])
  rank=score.where(eligible).rank(axis=1,ascending=False,method="first")
  signal=(rank<=slots).astype(float)
  pos=signal.shift(1).fillna(0)
  pos=pos.div(pos.sum(axis=1).replace(0,np.nan),axis=0).fillna(0)
  # Reject missing open prices for active positions rather than silently giving zero returns.
  missing=(pos.gt(0)&ret.isna()).iloc[:-1]
  if missing.any().any():continue
  turnover=pos.diff().abs().sum(axis=1);turnover.iloc[0]=pos.iloc[0].abs().sum()
  gross=(pos*ret).sum(axis=1,min_count=1).fillna(0)
  for cost in (.001,.0025,.005):
   net=(gross-cost*turnover).iloc[:-1]
   for split,mask in splits.items():
    rr=net.loc[mask[:-1]]
    if len(rr)<100:continue
    eq=(1+rr).cumprod();dd=(eq/eq.cummax()-1).min()
    rows.append(dict(config=k,short=s,long=l,min_acceleration=minimum,
     min_relative_volume=rvol,slots=slots,market_ma=ma,cost=cost,split=split,
     cagr=float(eq.iloc[-1]**(252/len(rr))-1) if eq.iloc[-1]>0 else -1.,
     max_dd=float(dd),sharpe=float(rr.mean()/rr.std()*np.sqrt(252)) if rr.std()>0 else 0.,
     net_profit_cad=float(5000*(eq.iloc[-1]-1)),
     active_days=int((pos.sum(axis=1).iloc[:-1].loc[mask[:-1]]>0).sum()),
     turnover=float(turnover.iloc[:-1].loc[mask[:-1]].sum())))
 result=pd.DataFrame(rows)
 if result.empty:raise RuntimeError("No configurations passed strict price completeness; fix data universe, do not fabricate fills")
 result.to_csv(OUT/"full_grid.csv",index=False)
 a=result[(result.split=="train")&(result.cost==.0025)].sort_values("cagr",ascending=False).head(30)
 b=result[(result.split=="validation")&(result.cost==.0025)]
 ranked=a.merge(b,on="config",suffixes=("_train","_validation"))
 ranked.to_csv(OUT/"train_top30_validation.csv",index=False)
 (OUT/"audit.json").write_text(json.dumps({"planned_configs":len(configs),"completed_configs":result.config.nunique(),
  "tickers":names,"first":str(ix.min()),"last":str(ix.max()),
  "limitations":["surviving Yahoo tickers only, no delisted stocks",
  "next-open allocation/open-to-open returns are a proxy, not executable broker fills",
  "estimated costs, no bid/ask spreads or stop-gap execution",
  "no corrected VMM benchmark, untouched OOS or forward paper trading",
  "same 2016-2023 periods as prior research, selection overfitting risk"]},indent=2))
 print("ACCELERATION",len(configs),"planned configs,",result.config.nunique(),"completed x 3 costs")
 print(ranked[["config","cagr_train","max_dd_train","cagr_validation","max_dd_validation"]].head(12).to_string(index=False))
if __name__=="__main__":main()
