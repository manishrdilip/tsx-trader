"""Research-only TSX defensive regime switching: low-vol vs high-momentum selection.
No live orders. Close t signals, open t+1 allocations, open-to-open returns.
Exploratory grid, NOT corrected VMM or independent holdout.
"""
import itertools,json,pathlib
import numpy as np,pandas as pd,yfinance as yf
OUT=pathlib.Path("research/regime_switch_results")
TICKERS="RY.TO TD.TO BNS.TO BMO.TO ENB.TO CNQ.TO SU.TO CVE.TO SHOP.TO AEM.TO ABX.TO CCO.TO TECK-B.TO WPM.TO AC.TO".split()
def main():
 OUT.mkdir(parents=True,exist_ok=True)
 data={}
 for t in TICKERS+["XIU.TO"]:
  try:
   d=yf.download(t,start="2016-01-01",auto_adjust=True,progress=False,threads=False)
   if isinstance(d.columns,pd.MultiIndex):d.columns=d.columns.get_level_values(0)
   d=d[["Open","Close"]].dropna()
   if len(d)>750:data[t]=d
  except Exception as e:print("FETCH_FAIL",t,str(e)[:100])
 if len(data)<11 or "XIU.TO" not in data:raise RuntimeError("Missing market or insufficient stocks")
 ix=data["XIU.TO"].index
 names=sorted(set(data)-{"XIU.TO"})
 c=pd.DataFrame({t:data[t].Close.reindex(ix) for t in names})
 o=pd.DataFrame({t:data[t].Open.reindex(ix) for t in names})
 market=data["XIU.TO"].Close.reindex(ix)
 mr=market.pct_change(fill_method=None)
 ret=o.shift(-1)/o-1
 daily=c.pct_change(fill_method=None)
 # 4 momentum x 4 volatility x 4 market trend x 3 slots x 3 volatility gate x 3 styles = 1728
 configs=list(itertools.product((20,60,120,250),(10,20,40,60),(50,100,150,200),
                                (1,3,5),(.012,.018,.025),("momentum","lowvol","switch")))
 momentum={n:c/c.shift(n)-1 for n in (20,60,120,250)}
 vol={n:daily.rolling(n,min_periods=n).std() for n in (10,20,40,60)}
 market_ma={n:market.rolling(n,min_periods=n).mean() for n in (50,100,150,200)}
 market_vol=mr.rolling(20,min_periods=20).std()
 splits={"train":ix<"2022-01-01","validation":(ix>="2022-01-01")&(ix<"2024-01-01"),
         "recent_diagnostic":ix>="2024-01-01"}
 rows=[]
 for k,(m,v,trend,slots,threshold,style) in enumerate(configs):
  high=market_vol>threshold
  if style=="momentum": score=momentum[m]
  elif style=="lowvol":score=-vol[v]
  else:score=momentum[m].where(~high,-vol[v])
  eligible=(momentum[m].notna()&vol[v].notna()&(c>0))
  rank=score.where(eligible).rank(axis=1,ascending=False,method="first")
  # Defensive market regime: invest only when XIU above historical trend.
  risk_ok=(~high) if style!="switch" else pd.Series(True,index=ix)
  signal=(rank<=slots).astype(float).mul(((market>market_ma[trend])&risk_ok).fillna(False),axis=0)
  # Signal at t close, allocation at t+1 open. No same-day signal execution.
  pos=signal.shift(1).fillna(0)
  pos=pos.div(pos.sum(axis=1).replace(0,np.nan),axis=0).fillna(0)
  turnover=pos.diff().abs().sum(axis=1);turnover.iloc[0]=pos.iloc[0].abs().sum()
  gross=(pos*ret).sum(axis=1,min_count=1).fillna(0)
  for cost in (.001,.0025,.005):
   net=(gross-cost*turnover).iloc[:-1]
   for split,mask in splits.items():
    r=net.loc[mask[:-1]]
    if len(r)<100:continue
    eq=(1+r).cumprod(); dd=(eq/eq.cummax()-1).min()
    rows.append(dict(config=k,momentum=m,vol_lookback=v,trend=trend,slots=slots,
     market_vol_gate=threshold,style=style,cost=cost,split=split,
     cagr=float(eq.iloc[-1]**(252/len(r))-1) if eq.iloc[-1]>0 else -1.,
     max_dd=float(dd),sharpe=float(r.mean()/r.std()*np.sqrt(252)) if r.std()>0 else 0.,
     net_profit_cad=float(5000*(eq.iloc[-1]-1)),active_days=int((pos.sum(axis=1).iloc[:-1].loc[mask[:-1]]>0).sum()),
     turnover=float(turnover.iloc[:-1].loc[mask[:-1]].sum())))
 result=pd.DataFrame(rows)
 result.to_csv(OUT/"full_grid.csv",index=False)
 a=result[(result.split=="train")&(result.cost==.0025)].sort_values("cagr",ascending=False).head(30)
 b=result[(result.split=="validation")&(result.cost==.0025)]
 a.merge(b,on="config",suffixes=("_train","_validation")).to_csv(OUT/"train_top30_validation.csv",index=False)
 (OUT/"audit.json").write_text(json.dumps({"configurations":len(configs),"costs":[.001,.0025,.005],
  "tickers":names,"first":str(ix.min()),"last":str(ix.max()),"train":"2016-2021",
  "validation":"2022-2023","recent":"2024 onward, already researched",
  "limitations":["surviving Yahoo tickers only","no delisted stocks","open-to-open return proxy; cannot model intraday stops or gaps",
  "estimated turnover fees, not observed spreads","not corrected matched VMM baseline",
  "no untouched OOS or forward paper trading","ranking overfits training; no 3x claim permitted"]},indent=2))
 print("REGIME SWITCH GRID",len(configs),"configs x 3 costs, tickers",len(names))
 print(a.merge(b,on="config",suffixes=("_train","_validation"))[["config","cagr_train","max_dd_train","cagr_validation","max_dd_validation"]].head(12).to_string(index=False))
if __name__=="__main__":main()
