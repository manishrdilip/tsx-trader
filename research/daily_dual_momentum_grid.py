"""Research-only TSX dual-momentum rotation SCREEN. No brokerage connection.
Signals close t; buy next open t+1; sell next open t+2. No stop simulation.
"""
import itertools,json,pathlib
import numpy as np,pandas as pd,yfinance as yf
OUT=pathlib.Path("research/dual_momentum_results")
TICKERS="RY.TO TD.TO BNS.TO BMO.TO ENB.TO CNQ.TO SU.TO CVE.TO SHOP.TO AEM.TO ABX.TO CCO.TO TECK-B.TO WPM.TO AC.TO".split()
def main():
 OUT.mkdir(parents=True,exist_ok=True);data={}
 for t in TICKERS+["XIU.TO"]:
  try:
   d=yf.download(t,start="2016-01-01",auto_adjust=True,progress=False,threads=False)
   if isinstance(d.columns,pd.MultiIndex):d.columns=d.columns.get_level_values(0)
   d=d[["Open","High","Low","Close","Volume"]].dropna()
   if len(d)>=750:data[t]=d
  except Exception as e:print("DATA_FAILURE",t,str(e)[:100])
 if "XIU.TO" not in data or len(data)<11:raise RuntimeError("insufficient real bars")
 market=data.pop("XIU.TO")
 ix=pd.DatetimeIndex(sorted(set().union(*(set(d.index) for d in data.values()))))
 c=pd.DataFrame({t:d.Close.reindex(ix) for t,d in data.items()})
 o=pd.DataFrame({t:d.Open.reindex(ix) for t,d in data.items()})
 m=market.Close.reindex(ix).ffill()
 # Market filter computed using current close and applied only at following open.
 market200=m>m.rolling(200,min_periods=200).mean()
 market100=m>m.rolling(100,min_periods=100).mean()
 # 4*4*3*3*4*3 = 1728 distinct configurations.
 cfg=list(itertools.product((20,60,120,250),(5,10,20,40),
                           (0.,.03,.08),("all","above100","above200"),
                           (1,2,3,5),("none","positive_short","positive_long")))
 periods={"train":ix<"2022-01-01","validation":(ix>="2022-01-01")&(ix<"2024-01-01"),
          "recent_diagnostic":ix>="2024-01-01"}
 # Open-to-open return from entry t+1 to exit t+2, indexed at entry date.
 openret=o.shift(-1)/o-1
 longmom={n:c/c.shift(n)-1 for n in (20,60,120,250)}
 shortmom={n:c/c.shift(n)-1 for n in (5,10,20,40)}
 rows=[]
 for k,(lb,sb,threshold,regime,slots,guard) in enumerate(cfg):
  lm=longmom[lb];sm=shortmom[sb]
  # Two independent momentum horizons: relative strength score + acceleration.
  score=lm+0.5*sm
  sig=(lm>threshold)&lm.notna()&sm.notna()
  if guard=="positive_short":sig=sig&(sm>0)
  elif guard=="positive_long":sig=sig&(lm>lm.shift(20))
  if regime=="above100":sig=sig&market100.to_numpy()[:,None]
  elif regime=="above200":sig=sig&market200.to_numpy()[:,None]
  # Signal close t -> position at open t+1. Rank only prior-close features.
  rank=score.shift(1).where(sig.shift(1).fillna(False)).rank(axis=1,ascending=False,method="first")
  active=rank.le(slots)&openret.notna()&o.notna()
  weights=active.astype(float).div(active.sum(axis=1).replace(0,np.nan),axis=0).fillna(0)
  gross=(weights*openret.fillna(0)).sum(axis=1)
  turnover=2*weights.sum(axis=1)
  for cost in (.001,.0025,.005):
   net=gross-cost*turnover
   for name,mask in periods.items():
    x=net.loc[mask]
    if len(x)<100:continue
    eq=(1+x).cumprod();yrs=len(x)/252
    rows.append(dict(config=k,long_lookback=lb,short_lookback=sb,threshold=threshold,
      regime=regime,slots=slots,guard=guard,cost_per_side=cost,split=name,
      cagr=float(eq.iloc[-1]**(1/yrs)-1) if eq.iloc[-1]>0 else -1.,
      max_dd=float((eq/eq.cummax()-1).min()),net_profit_cad=float(5000*(eq.iloc[-1]-1)),
      sharpe=float(x.mean()/x.std()*np.sqrt(252)) if x.std()>0 else 0.,
      active_days=int((weights.loc[mask].sum(axis=1)>0).sum())))
 df=pd.DataFrame(rows);df.to_csv(OUT/"all_results.csv",index=False)
 train=df[(df.split=="train")&(df.cost_per_side==.0025)].sort_values("cagr",ascending=False).head(30)
 val=df[(df.split=="validation")&(df.cost_per_side==.0025)]
 summary=train.merge(val,on="config",suffixes=("_train","_validation"))
 summary.to_csv(OUT/"top30_validation.csv",index=False)
 (OUT/"audit.json").write_text(json.dumps({"configurations":len(cfg),"unique":len(set(cfg)),
  "tickers":list(data),"start":str(ix.min()),"end":str(ix.max()),
  "train":"2016-2021","validation":"2022-2023","recent":"2024+ previously researched",
  "execution":"close t signals, next open t+1 entry, following open t+2 exit; daily reset",
  "limitations":["Survivorship bias: only currently surviving tickers",
  "Daily Yahoo adjusted prices, no real broker fills or verified spreads",
  "Every day round-trip trading, not a multi-day VMM equivalent",
  "No stop gaps or intraday tail-risk accounting",
  "Fixed cost estimates, no corrected same-period VMM baseline",
  "No untouched holdout or forward paper-trading evidence"]},indent=2))
 print("DUAL MOMENTUM",len(cfg),"distinct configs",len(data),"tickers")
 print(summary[["config","cagr_train","max_dd_train","cagr_validation","max_dd_validation"]].head(15).to_string(index=False))
if __name__=="__main__":main()
