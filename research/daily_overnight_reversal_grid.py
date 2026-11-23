"""Research-only TSX overnight reversal screen. NOT executable backtest.
Signal after close t; buy at close t is NOT allowed. Enter next OPEN, exit following OPEN.
A one-session overnight hold is based on the OPEN(t+1) to OPEN(t+2) return.
"""
import itertools,json,pathlib
import numpy as np,pandas as pd,yfinance as yf
OUT=pathlib.Path("research/overnight_reversal_results")
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
 v=pd.DataFrame({t:d.Volume.reindex(ix) for t,d in data.items()})
 m=market.Close.reindex(ix).ffill()
 up=m>m.rolling(200,min_periods=200).mean()
 dayret=c/c.shift(1)-1
 intraday=c/o-1
 rv=v/v.shift(1).rolling(20,min_periods=20).mean()
 # 4*4*3*3*3*3 = 1296 distinct combinations
 cfg=list(itertools.product((1,2,3,5),(-.01,-.025,-.04,-.07),
                            (0.,1.,1.5),("all","up","down"),(1,3,5),("day","intraday","both")))
 # Signal at close t; entry open t+1, exit open t+2, no use of t+1 high/low
 openret=o.shift(-1)/o-1
 periods={"train":ix<"2022-01-01","validation":(ix>="2022-01-01")&(ix<"2024-01-01"),
          "recent_diagnostic":ix>="2024-01-01"}
 rows=[]
 for k,(lookback,threshold,vol,regime,slots,trigger) in enumerate(cfg):
  cumulative=c/c.shift(lookback)-1
  if trigger=="day":sig=cumulative<threshold
  elif trigger=="intraday":sig=intraday<threshold
  else:sig=(cumulative<threshold)&(intraday<threshold/2)
  sig=sig&(rv>=vol)
  if regime=="up":sig=sig&up.to_numpy()[:,None]
  if regime=="down":sig=sig&(~up).to_numpy()[:,None]
  # Shift by one full session before sizing; all features are close-t only
  score=(-cumulative).shift(1)
  rank=score.where(sig.shift(1).fillna(False)).rank(axis=1,ascending=False,method="first")
  active=rank.le(slots)&openret.notna()
  weights=active.astype(float).div(active.sum(axis=1).replace(0,np.nan),axis=0).fillna(0)
  # positions opened on each day and closed at following open; non-overlapping by construction
  gross=(weights*openret.fillna(0)).sum(axis=1)
  turn=2*weights.sum(axis=1)
  for cost in (.001,.0025,.005):
   r=gross-cost*turn
   for name,mask in periods.items():
    x=r.loc[mask]
    if len(x)<100:continue
    eq=(1+x).cumprod();yrs=len(x)/252
    rows.append(dict(config=k,lookback=lookback,threshold=threshold,volume=vol,
      regime=regime,slots=slots,trigger=trigger,cost_per_side=cost,split=name,
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
   "execution":"signal close t, next open t+1 entry, next open t+2 exit",
   "limitations":["Surviving stocks only; delisted names absent","Yahoo adjusted daily prices, no verified broker fills",
   "No stop gaps or intrabar drawdowns, no VMM matched baseline","No untouched holdout or forward paper trading",
   "Fixed estimated costs; overnight gaps can exceed modeled risk",
   "Cost charged on entry and exit, but exits at future open are proxy fills"]},indent=2))
 print("OVERNIGHT REVERSAL",len(cfg),"distinct configs",len(data),"tickers")
 print(summary[["config","cagr_train","max_dd_train","cagr_validation","max_dd_validation"]].head(15).to_string(index=False))
if __name__=="__main__":main()
