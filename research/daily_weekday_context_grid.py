"""Research only: next-session intraday weekday/overnight-context grid.
Signal after close t; buy OPEN t+1; liquidate CLOSE t+1.
One session positions, no margin or shorts, all capital available each morning.
This is a SCREEN: no stop-gap model, delisted stocks or observed spreads.
"""
import itertools,json,pathlib
import numpy as np,pandas as pd,yfinance as yf
OUT=pathlib.Path("research/weekday_context_results")
TICKERS="RY.TO TD.TO BNS.TO BMO.TO ENB.TO CNQ.TO SU.TO CVE.TO SHOP.TO AEM.TO ABX.TO CCO.TO TECK-B.TO WPM.TO AC.TO".split()
def main():
 OUT.mkdir(parents=True,exist_ok=True);data={}
 for t in TICKERS+["XIU.TO"]:
  try:
   d=yf.download(t,start="2016-01-01",auto_adjust=True,progress=False,threads=False)
   if isinstance(d.columns,pd.MultiIndex):d.columns=d.columns.get_level_values(0)
   d=d[["Open","High","Low","Close","Volume"]].dropna()
   if len(d)>=750:data[t]=d
  except Exception as e:print("FETCH_FAILED",t,str(e)[:100])
 if "XIU.TO" not in data or len(data)<11:raise RuntimeError("Not enough genuine daily bars")
 market=data.pop("XIU.TO")
 ix=pd.DatetimeIndex(sorted(set().union(*(set(d.index) for d in data.values()))))
 c=pd.DataFrame({t:d.Close.reindex(ix) for t,d in data.items()})
 o=pd.DataFrame({t:d.Open.reindex(ix) for t,d in data.items()})
 v=pd.DataFrame({t:d.Volume.reindex(ix) for t,d in data.items()})
 mom={n:c/c.shift(n)-1 for n in (3,10,20,60)}
 rv=v/v.shift(1).rolling(20,min_periods=20).mean()
 market_close=market.Close.reindex(ix).ffill()
 market_trend=(market_close>market_close.rolling(200,min_periods=200).mean())
 # weekday is known before entry; t+1 weekday used as a calendar-only feature
 weekday=pd.Series(ix.dayofweek,index=ix)
 # 6 weekday masks * 4 momentum windows * 4 min returns * 3 trend * 3 RVOL * 3 slots = 2592
 configs=list(itertools.product(("all","mon","tue","wed","thu","fri"),
     (3,10,20,60),(-.05,0.,.03,.08),("all","up","down"),(0.,1.,1.5),(1,3,5)))
 intraday=c/o-1
 periods={"train":ix<"2022-01-01","validation":(ix>="2022-01-01")&(ix<"2024-01-01"),
          "recent_diagnostic":ix>="2024-01-01"}
 rows=[]
 for k,(wd,lookback,threshold,regime,volume,slots) in enumerate(configs):
  signal=(mom[lookback]>=threshold)&(rv>=volume)&o.notna()&c.notna()
  if regime=="up":signal=signal&market_trend.to_numpy()[:,None]
  if regime=="down":signal=signal&(~market_trend).to_numpy()[:,None]
  # Signal close t, position on t+1, not same session.
  signal=signal.shift(1).fillna(False)
  if wd!="all":
   wanted={"mon":0,"tue":1,"wed":2,"thu":3,"fri":4}[wd]
   signal=signal&(weekday==wanted).to_numpy()[:,None]
  strength=mom[lookback].shift(1).where(signal)
  rank=strength.rank(axis=1,ascending=False,method="first")
  active=rank.le(slots)&intraday.notna()
  weights=active.astype(float).div(active.sum(axis=1).replace(0,np.nan),axis=0).fillna(0)
  gross=(weights*intraday.fillna(0)).sum(axis=1)
  # Full buy and sell each day: conservative flat-to-flat turnover 2x exposure
  turnover=2*weights.sum(axis=1)
  for cost in (.001,.0025,.005):
   daily=gross-cost*turnover
   for name,mask in periods.items():
    r=daily.loc[mask]
    if len(r)<100:continue
    eq=(1+r).cumprod();yrs=len(r)/252
    rows.append(dict(config=k,weekday=wd,momentum_window=lookback,min_momentum=threshold,
      market_regime=regime,relative_volume=volume,slots=slots,cost_per_side=cost,
      split=name,cagr=float(eq.iloc[-1]**(1/yrs)-1) if eq.iloc[-1]>0 else -1.,
      max_dd=float((eq/eq.cummax()-1).min()),net_profit_cad=float(5000*(eq.iloc[-1]-1)),
      sharpe=float(r.mean()/r.std()*np.sqrt(252)) if r.std()>0 else 0.,
      active_days=int((weights.loc[mask].sum(axis=1)>0).sum()),
      mean_daily_turnover=float(turnover.loc[mask].mean())))
 df=pd.DataFrame(rows)
 df.to_csv(OUT/"all_results.csv",index=False)
 train=df[(df.split=="train")&(df.cost_per_side==.0025)].sort_values("cagr",ascending=False).head(30)
 valid=df[(df.split=="validation")&(df.cost_per_side==.0025)]
 summary=train.merge(valid,on="config",suffixes=("_train","_validation"))
 summary.to_csv(OUT/"top30_validation.csv",index=False)
 audit={"labeled_configs":len(configs),"distinct_configs":len(set(configs)),
   "tickers":list(data),"market":"XIU.TO","date_start":str(ix.min()),"date_end":str(ix.max()),
   "entry":"open t+1 based only on signal through close t",
   "exit":"close t+1","capital":"$5000, equal weight among up to slots, no leverage, cash on idle days",
   "train":"2016-2021","validation":"2022-2023","recent":"2024+ previously inspected; NOT untouched",
   "limitations":["Yahoo surviving ticker sample; delisted stocks omitted",
   "No verified EODHD data or corrected matched VMM baseline",
   "Open/close price proxy; real fills, bid/ask and market impact unverified",
   "No stop loss or stop-gap modeling; cannot establish 3x winner",
   "Transaction costs assumed; no independent forward paper evidence",
   "Selection across many parameters creates multiple-testing risk"]}
 (OUT/"audit.json").write_text(json.dumps(audit,indent=2))
 print("WEEKDAY CONTEXT SCREEN",len(configs),"unique configurations x 3 cost scenarios; tickers",len(data))
 print(summary[["config","cagr_train","max_dd_train","cagr_validation","max_dd_validation"]].head(15).to_string(index=False))
if __name__=="__main__":main()
