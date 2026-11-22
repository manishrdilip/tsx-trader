"""Research-only cross-sectional residual-reversal screen. Not an executable backtest.
Close-t signal; next-open allocation; next-open-to-following-open returns.
Survivorship bias and estimated transaction costs; never trade automatically.
"""
import itertools,json,pathlib
import numpy as np,pandas as pd,yfinance as yf
OUT=pathlib.Path("research/residual_reversal_results")
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
 if len(data)<11 or "XIU.TO" not in data:raise RuntimeError("Insufficient historical price coverage")
 ix=data["XIU.TO"].index; names=sorted(set(data)-{"XIU.TO"})
 c=pd.DataFrame({t:data[t].Close.reindex(ix) for t in names})
 o=pd.DataFrame({t:data[t].Open.reindex(ix) for t in names})
 v=pd.DataFrame({t:data[t].Volume.reindex(ix) for t in names})
 market=data["XIU.TO"].Close.reindex(ix)
 mret=market.pct_change(fill_method=None)
 ret=o.shift(-1)/o-1
 daily=c.pct_change(fill_method=None)
 # 4*4*4*4*4*2 = 2048 distinct parameter combinations
 configs=list(itertools.product((2,3,5,10),(20,40,60,120),
       (0.5,1.,1.5,2.),(1,2,3,5),(0.5,1.,1.5,2.),(False,True)))
 resid={}
 for n in (2,3,5,10):
  stock=c/c.shift(n)-1
  benchmark=market/market.shift(n)-1
  resid[n]=stock.sub(benchmark,axis=0)
 volatility={n:daily.rolling(n,min_periods=n).std() for n in (20,40,60,120)}
 volume=v/v.shift(1).rolling(20,min_periods=20).mean()
 splits={"train":ix<"2022-01-01","validation":(ix>="2022-01-01")&(ix<"2024-01-01"),
         "recent_diagnostic":ix>="2024-01-01"}
 rows=[]
 for k,(lookback,volwindow,zcut,slots,volume_min,trend_gate) in enumerate(configs):
  r=resid[lookback]
  z=r.div(volatility[volwindow]*np.sqrt(lookback)).replace([np.inf,-np.inf],np.nan)
  eligible=(z < -zcut)&(volume>=volume_min)&(c>0)
  if trend_gate:eligible=eligible&(c>c.rolling(200,min_periods=200).mean())
  # Most oversold residuals rank first; deterministic tie break by ticker order.
  rank=z.where(eligible).rank(axis=1,ascending=True,method="first")
  signal=(rank<=slots).astype(float)
  pos=signal.shift(1).fillna(0)
  pos=pos.div(pos.sum(axis=1).replace(0,np.nan),axis=0).fillna(0)
  turnover=pos.diff().abs().sum(axis=1);turnover.iloc[0]=pos.iloc[0].abs().sum()
  gross=(pos*ret).sum(axis=1,min_count=1).fillna(0)
  for cost in (.001,.0025,.005):
   net=(gross-cost*turnover).iloc[:-1]
   for split,mask in splits.items():
    rr=net.loc[mask[:-1]]
    if len(rr)<100:continue
    eq=(1+rr).cumprod();dd=(eq/eq.cummax()-1).min()
    rows.append(dict(config=k,lookback=lookback,vol_window=volwindow,
      zcut=zcut,slots=slots,volume_min=volume_min,trend_gate=trend_gate,
      cost=cost,split=split,cagr=float(eq.iloc[-1]**(252/len(rr))-1) if eq.iloc[-1]>0 else -1.,
      max_dd=float(dd),sharpe=float(rr.mean()/rr.std()*np.sqrt(252)) if rr.std()>0 else 0.,
      net_profit_cad=float(5000*(eq.iloc[-1]-1)),
      active_days=int((pos.sum(axis=1).iloc[:-1].loc[mask[:-1]]>0).sum()),
      turnover=float(turnover.iloc[:-1].loc[mask[:-1]].sum())))
 result=pd.DataFrame(rows);result.to_csv(OUT/"full_grid.csv",index=False)
 a=result[(result.split=="train")&(result.cost==.0025)].sort_values("cagr",ascending=False).head(30)
 b=result[(result.split=="validation")&(result.cost==.0025)]
 merged=a.merge(b,on="config",suffixes=("_train","_validation"))
 merged.to_csv(OUT/"train_top30_validation.csv",index=False)
 (OUT/"audit.json").write_text(json.dumps({"configurations":len(configs),
  "tickers":names,"first":str(ix.min()),"last":str(ix.max()),
  "train":"2016-2021","validation":"2022-2023","recent":"2024 onward already researched",
  "limitations":["Yahoo surviving tickers only, no delisted stocks",
  "open-to-open daily returns approximate next-open execution; no actual fills or intraday stop-gap model",
  "fixed estimated costs, no observed spreads or slippage",
  "equal-weight vectorized portfolio, not corrected VMM cash accounting",
  "no untouched out-of-sample or forward paper trading",
  "no corrected matched VMM baseline; no 3x claim permitted"]},indent=2))
 print("RESIDUAL REVERSAL",len(configs),"configs, three costs; tickers",len(names))
 print(merged[["config","cagr_train","max_dd_train","cagr_validation","max_dd_validation"]].head(12).to_string(index=False))
if __name__=="__main__":main()
