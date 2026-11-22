"""Research-only market-neutral TSX pairs mean-reversion screen.
No live orders. 576 distinct configs x 3 costs, chronological validation.
Positions selected at close t; execute open t+1, exit open t+2.
Historical Yahoo surviving tickers; spread/slippage are proxies.
"""
import itertools,json,pathlib
import numpy as np,pandas as pd,yfinance as yf
OUT=pathlib.Path("research/pairs_spread_results")
PAIRS=[("RY.TO","TD.TO"),("BMO.TO","BNS.TO"),("CNQ.TO","SU.TO"),("SU.TO","CVE.TO"),
       ("AEM.TO","ABX.TO"),("ENB.TO","TRP.TO")]
def load():
 d={}
 for t in sorted(set(sum(([a,b] for a,b in PAIRS),[]))):
  try:
   z=yf.download(t,start="2016-01-01",auto_adjust=True,progress=False,threads=False)
   if isinstance(z.columns,pd.MultiIndex):z.columns=z.columns.get_level_values(0)
   z=z[["Open","Close","Volume"]].dropna()
   if len(z)>750:d[t]=z
  except Exception as e:print("FETCH_FAIL",t,str(e)[:100])
 return d
def main():
 OUT.mkdir(parents=True,exist_ok=True)
 d=load(); pairs=[(a,b) for a,b in PAIRS if a in d and b in d]
 if len(pairs)<4:raise RuntimeError("Not enough verified pairs")
 ix=pd.DatetimeIndex(sorted(set().union(*(set(z.index) for z in d.values()))))
 c=pd.DataFrame({t:z.Close.reindex(ix) for t,z in d.items()})
 o=pd.DataFrame({t:z.Open.reindex(ix) for t,z in d.items()})
 # 4 windows x 4 entry thresholds x 3 trend gates x 3 volume gates x 4 holding periods = 576
 configs=list(itertools.product((20,40,60,120),(1.,1.5,2.,2.5),
   ("none","pair_ma50","pair_ma200"),(0.,.5,1.),(1,2,3,5)))
 splits={"train":ix<"2022-01-01","validation":(ix>="2022-01-01")&(ix<"2024-01-01"),
         "recent_diagnostic":ix>="2024-01-01"}
 # Equal-dollar long/short spread; cash collateral, borrowing and short fees NOT modeled.
 # Return from next open to open after hold days; exposure is non-overlapping per pair.
 rows=[]
 logratio={p:np.log(c[p[0]]/c[p[1]]) for p in pairs}
 for k,(window,threshold,gate,volgate,hold) in enumerate(configs):
  pair_returns=[]
  pair_activity=[]
  for p in pairs:
   a,b=p
   s=logratio[p];mean=s.shift(1).rolling(window,min_periods=window).mean()
   sd=s.shift(1).rolling(window,min_periods=window).std()
   z=(s-mean)/sd.replace(0,np.nan)
   direction=pd.Series(np.where(z>threshold,-1.,np.where(z< -threshold,1.,0.)),index=ix)
   if gate!="none":
    n=50 if gate=="pair_ma50" else 200
    # Trend guard: only fade when both names are above their own MA, avoids crash shorts.
    direction=direction.where((c[a]>c[a].rolling(n).mean())&(c[b]>c[b].rolling(n).mean()),0.)
   if volgate>0:
    va=d[a].Volume.reindex(ix);vb=d[b].Volume.reindex(ix)
    rv1=va/va.shift(1).rolling(20).mean();rv2=vb/vb.shift(1).rolling(20).mean()
    direction=direction.where((rv1>=volgate)&(rv2>=volgate),0.)
   # A fresh signal at close t enters next open; cannot enter again while holding.
   daily=pd.Series(0.,index=ix);activity=pd.Series(0.,index=ix)
   i=window+202
   while i+hold<len(ix):
    side=float(direction.iloc[i])
    if side==0 or not np.isfinite(side):
     i+=1;continue
    entry=i+1;exit_idx=entry+hold
    if exit_idx>=len(ix):break
    prices=(o[a].iloc[entry],o[b].iloc[entry],o[a].iloc[exit_idx],o[b].iloc[exit_idx])
    if not all(np.isfinite(x) and x>0 for x in prices):i+=1;continue
    # 50% long, 50% short; daily PnL credited at exit; zero until settlement.
    ra=prices[2]/prices[0]-1;rb=prices[3]/prices[1]-1
    daily.iloc[exit_idx]=side*.5*(ra-rb)
    activity.iloc[exit_idx]=1
    i=exit_idx
   pair_returns.append(daily);pair_activity.append(activity)
  # Equal fixed capital across six pairs; inactive allocations remain cash.
  gross=pd.concat(pair_returns,axis=1).sum(axis=1)/len(pairs)
  events=pd.concat(pair_activity,axis=1).sum(axis=1)/len(pairs)
  for cost in (.001,.0025,.005):
   # 4 one-way fills (two legs, entry+exit), each leg half pair capital.
   net=gross-2*cost*events
   for label,mask in splits.items():
    r=net.loc[mask]
    if len(r)<100:continue
    eq=(1+r).cumprod();dd=float((eq/eq.cummax()-1).min())
    cagr=float(eq.iloc[-1]**(252/len(r))-1) if eq.iloc[-1]>0 else -1.
    rows.append(dict(config=k,window=window,threshold=threshold,gate=gate,
       volume_gate=volgate,hold=hold,cost=cost,split=label,cagr=cagr,max_dd=dd,
       net_profit_cad=float(5000*(eq.iloc[-1]-1)),
       sharpe=float(r.mean()/r.std()*np.sqrt(252)) if r.std()>0 else 0.,
       pair_trade_events=int(pd.concat(pair_activity,axis=1).loc[mask].sum().sum())))
 df=pd.DataFrame(rows);df.to_csv(OUT/"all_results.csv",index=False)
 train=df[(df.split=="train")&(df.cost==.0025)].sort_values("cagr",ascending=False).head(30)
 validation=df[(df.split=="validation")&(df.cost==.0025)]
 top=train.merge(validation,on="config",suffixes=("_train","_validation"))
 top.to_csv(OUT/"top30_validation.csv",index=False)
 audit={"distinct_configurations":len(configs),"pairs":pairs,
  "limitations":["Daily open-to-open research proxy; PnL marked at exit rather than daily",
  "Yahoo survivor bias and missing delistings","Short borrowing availability, short borrow fees and collateral not modeled",
  "Equal gross pair exposure with assumed ability to short; not Wealthsimple TFSA executable",
  "Fixed fee/slippage proxies, no bid/ask history","No stop-gap model or corrected VMM baseline",
  "2024 onward previously observed, not untouched holdout","No forward paper validation"]}
 (OUT/"audit.json").write_text(json.dumps(audit,indent=2))
 print("PAIRS SCREEN",len(configs),"configs",len(pairs),"pairs")
 print(top[["config","cagr_train","max_dd_train","cagr_validation","max_dd_validation"]].to_string(index=False))
if __name__=="__main__":main()
