"""Independent daily mean-reversion grid, research-only. No trading orders.
Next-open entry and next-close liquidation, fixed $5k; conservative costs.
Survivorship-biased Yahoo sample; screening only, not independently validated.
"""
import itertools,json,pathlib
import numpy as np,pandas as pd,yfinance as yf
from daily_grid_discovery import TICKERS,load
OUT=pathlib.Path("research/mean_reversion_results")
def main():
 OUT.mkdir(parents=True,exist_ok=True)
 data=load()
 dates=pd.DatetimeIndex(sorted(set().union(*(set(d.index) for d in data.values()))))
 C=pd.DataFrame({t:d.Close.reindex(dates) for t,d in data.items()})
 O=pd.DataFrame({t:d.Open.reindex(dates) for t,d in data.items()})
 V=pd.DataFrame({t:d.Volume.reindex(dates) for t,d in data.items()})
 # Signals at prior close, orders at next open, liquidation at SAME next close.
 overnight=O/C.shift(1)-1
 intraday=C/O-1
 ma={n:C.rolling(n,min_periods=n).mean() for n in (10,20,50,100)}
 z={n:(C-ma[n])/C.rolling(n,min_periods=n).std().replace(0,np.nan) for n in (10,20,50,100)}
 rsi={}
 delta=C.diff();up=delta.clip(lower=0);dn=-delta.clip(upper=0)
 for n in (2,5,10,14):
  rs=up.ewm(alpha=1/n,adjust=False).mean()/dn.ewm(alpha=1/n,adjust=False).mean().replace(0,np.nan)
  rsi[n]=100-100/(1+rs)
 rv=V/V.shift(1).rolling(20,min_periods=20).mean()
 configurations=list(itertools.product((10,20,50,100),(2,5,10,14),(-1.,-1.5,-2.,-2.5),(15,25,35,45),(0.5,1.,1.5,2.),(False,True)))
 assert len(configurations)==2048
 periods={"train":dates<"2022-01-01","validation":(dates>="2022-01-01")&(dates<"2024-01-01"),"recent_diagnostic":dates>="2024-01-01"}
 rows=[]
 for i,(window,rsi_window,zcut,rsicut,volume_min,trend) in enumerate(configurations):
  signal=(z[window]<zcut)&(rsi[rsi_window]<rsicut)&(rv>volume_min)
  if trend:signal &= C>C.rolling(200,min_periods=200).mean()
  # signal(t-1) can enter next session open(t). No same-day signal leakage.
  active=signal.shift(1).fillna(False)
  # Rank most negative z-score; no future data in ranks.
  scores=z[window].shift(1).where(active)
  chosen=scores.rank(axis=1,method="first",ascending=True).le(3)&active
  w=chosen.div(chosen.sum(axis=1).replace(0,np.nan),axis=0).fillna(0)
  # No overnight exposure: close-to-open gaps affect entry price, not P&L.
  gross=(w*intraday.fillna(0)).sum(axis=1)
  # Round-trip fixed cost proxy; no intraday stops or real quote spreads.
  for cost in (.001,.0025,.005):
   net=gross-2*cost*w.sum(axis=1)
   for name,mask in periods.items():
    r=net.loc[mask];eq=(1+r).cumprod()
    if len(r)<100:continue
    rows.append(dict(config=i,window=window,rsi_window=rsi_window,zcut=zcut,
     rsicut=rsicut,volume_min=volume_min,trend=trend,cost=cost,split=name,
     cagr=float(eq.iloc[-1]**(252/len(r))-1) if eq.iloc[-1]>0 else -1,
     max_dd=float((eq/eq.cummax()-1).min()),net_profit=float(5000*(eq.iloc[-1]-1)),
     trade_days=int((w.loc[mask].sum(axis=1)>0).sum())))
 result=pd.DataFrame(rows);result.to_csv(OUT/"all_results.csv",index=False)
 top=result[(result.split=="train")&(result.cost==.0025)].nlargest(30,"cagr")
 validation=result[(result.split=="validation")&(result.cost==.0025)]
 joined=top.merge(validation,on="config",suffixes=("_train","_validation"))
 joined.to_csv(OUT/"top30_validation.csv",index=False)
 (OUT/"audit.json").write_text(json.dumps({"tickers":list(data),"distinct_configs":len(configurations),
 "data_start":str(dates.min()),"data_end":str(dates.max()),
 "limitations":["surviving-stock sample only","Yahoo daily, not EODHD","open-to-close price proxy; no actual fill, spread or liquidity",
 "no intraday stop or gap-stop accounting","not matched VMM comparison",
 "2024 onward is previously explored, not untouched holdout",
 "multiple testing means training winners are not independent evidence"]},indent=2))
 print("NEW MEAN REVERSION SCREEN",len(configurations),"configs, 3 costs",len(data),"tickers")
 print(joined[["config","cagr_train","max_dd_train","cagr_validation","max_dd_validation"]].to_string(index=False))
if __name__=="__main__":main()
