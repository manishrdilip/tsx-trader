"""Research-only TSX cross-sectional dispersion/leadership rotation SCREEN.
Close-t signals; enter next open and exit following open. No broker connection.
2,304 distinct configurations, three cost assumptions. NOT VMM-comparable.
"""
import itertools,json,pathlib
import numpy as np,pandas as pd,yfinance as yf
OUT=pathlib.Path("research/dispersion_rotation_results")
TICKERS="RY.TO TD.TO BNS.TO BMO.TO ENB.TO CNQ.TO SU.TO CVE.TO SHOP.TO AEM.TO ABX.TO CCO.TO TECK-B.TO WPM.TO AC.TO".split()
def main():
 OUT.mkdir(parents=True,exist_ok=True);data={}
 for t in TICKERS+["XIU.TO"]:
  try:
   d=yf.download(t,start="2016-01-01",auto_adjust=True,progress=False,threads=False)
   if isinstance(d.columns,pd.MultiIndex):d.columns=d.columns.get_level_values(0)
   d=d[["Open","High","Low","Close","Volume"]].dropna()
   if len(d)>=750:data[t]=d
  except Exception as e:print("DATA_FAILURE",t,str(e)[:120])
 if "XIU.TO" not in data or len(data)<11:raise RuntimeError("insufficient real bars")
 m=data.pop("XIU.TO")
 ix=pd.DatetimeIndex(sorted(set().union(*(set(d.index) for d in data.values()))))
 c=pd.DataFrame({t:d.Close.reindex(ix) for t,d in data.items()})
 o=pd.DataFrame({t:d.Open.reindex(ix) for t,d in data.items()})
 v=pd.DataFrame({t:d.Volume.reindex(ix) for t,d in data.items()})
 mc=m.Close.reindex(ix).ffill()
 # Cross-sectional dispersion, market breadth and leadership strength use only close-t information.
 ret1=c.pct_change(fill_method=None)
 dispersion=ret1.std(axis=1)
 breadth=(c>c.rolling(50,min_periods=50).mean()).sum(axis=1)/c.notna().sum(axis=1)
 rv=v/v.shift(1).rolling(20,min_periods=20).mean()
 market_up=mc>mc.rolling(200,min_periods=200).mean()
 # 4 * 4 * 3 * 4 * 3 * 4 = 2304
 cfg=list(itertools.product((5,10,20,40),(.005,.01,.02,.035),
                            ("high","low","all"),(.25,.4,.6,.75),
                            (1.,1.5,2.),(1,2,3,5)))
 assert len(cfg)==2304 and len(set(cfg))==2304
 # Signal close t -> next open t+1 -> following open t+2.
 openret=o.shift(-1)/o-1
 momentum={n:c/c.shift(n)-1 for n in (5,10,20,40)}
 periods={"train":ix<"2022-01-01","validation":(ix>="2022-01-01")&(ix<"2024-01-01"),
          "recent_diagnostic":ix>="2024-01-01"}
 rows=[]
 for k,(lookback,dispmin,regime,breadthmin,volmin,slots) in enumerate(cfg):
  if regime=="high":gate=market_up
  elif regime=="low":gate=~market_up
  else:gate=pd.Series(True,index=ix)
  # Dispersion threshold gates trading days; breadth threshold gates strength.
  gate=gate&(dispersion>=dispmin)&(breadth>=breadthmin)
  score=momentum[lookback]
  sig=(score>0)&(rv>=volmin)&gate.to_numpy()[:,None]
  eligible=sig.shift(1).fillna(False)&openret.notna()
  rank=score.shift(1).where(eligible).rank(axis=1,ascending=False,method="first")
  active=rank.le(slots)
  weights=active.astype(float).div(active.sum(axis=1).replace(0,np.nan),axis=0).fillna(0)
  gross=(weights*openret.fillna(0)).sum(axis=1)
  turnover=2*weights.sum(axis=1)
  for cost in (.001,.0025,.005):
   r=gross-cost*turnover
   for name,mask in periods.items():
    x=r.loc[mask]
    if len(x)<100:continue
    eq=(1+x).cumprod()
    rows.append(dict(config=k,lookback=lookback,dispersion_min=dispmin,
     regime=regime,breadth_min=breadthmin,volume_min=volmin,slots=slots,
     cost_per_side=cost,split=name,
     cagr=float(eq.iloc[-1]**(252/len(x))-1) if eq.iloc[-1]>0 else -1.,
     max_dd=float((eq/eq.cummax()-1).min()),
     net_profit_cad=float(5000*(eq.iloc[-1]-1)),
     sharpe=float(x.mean()/x.std()*np.sqrt(252)) if x.std()>0 else 0.,
     active_days=int((weights.loc[mask].sum(axis=1)>0).sum())))
 df=pd.DataFrame(rows);df.to_csv(OUT/"all_results.csv",index=False)
 train=df[(df.split=="train")&(df.cost_per_side==.0025)].sort_values("cagr",ascending=False).head(30)
 val=df[(df.split=="validation")&(df.cost_per_side==.0025)]
 summary=train.merge(val,on="config",suffixes=("_train","_validation"))
 summary.to_csv(OUT/"top30_validation.csv",index=False)
 audit={"configurations":len(cfg),"unique":len(set(cfg)),"tickers":list(data),
 "start":str(ix.min()),"end":str(ix.max()),"train":"2016-2021","validation":"2022-2023",
 "recent":"2024 onward already researched; NOT untouched OOS",
 "execution":"close t signal, open t+1 entry, open t+2 exit; optimistic daily proxy",
 "limitations":["Survivorship bias; no delisted stocks","Yahoo adjusted OHLCV, not EODHD",
 "No observed spreads/slippage or executable fill validation","No stop-gap modeling",
 "No corrected matched VMM baseline","No untouched OOS or forward paper trading",
 "Open-to-open proxy, no actual cash ledger or fractional-share constraints",
 "Fixed transaction costs charged on both sides"]}
 (OUT/"audit.json").write_text(json.dumps(audit,indent=2))
 print("DISPERSION ROTATION",len(cfg),"unique configurations",len(data),"tickers")
 print(summary[["config","cagr_train","max_dd_train","cagr_validation","max_dd_validation"]].head(15).to_string(index=False))
if __name__=="__main__":main()
