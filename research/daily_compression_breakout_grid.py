"""Research-only TSX volatility contraction + upside breakout grid.
Signal at day t close; enter next open t+1; exit next open t+2.
This is a SCREENING proxy, not an executable stop-gap/cash-ledger backtest.
"""
import itertools,json,pathlib
import numpy as np,pandas as pd,yfinance as yf
OUT=pathlib.Path("research/compression_breakout_results")
TICKERS="RY.TO TD.TO BNS.TO BMO.TO ENB.TO CNQ.TO SU.TO CVE.TO SHOP.TO AEM.TO ABX.TO CCO.TO TECK-B.TO WPM.TO AC.TO".split()
def main():
 OUT.mkdir(parents=True,exist_ok=True)
 data={}
 for t in TICKERS+["XIU.TO"]:
  try:
   d=yf.download(t,start="2016-01-01",auto_adjust=True,progress=False,threads=False)
   if isinstance(d.columns,pd.MultiIndex):d.columns=d.columns.get_level_values(0)
   d=d[["Open","High","Low","Close","Volume"]].dropna()
   if len(d)>750:data[t]=d
  except Exception as e:print("FETCH_FAIL",t,str(e)[:120])
 if len(data)<11 or "XIU.TO" not in data:raise RuntimeError("Insufficient real market history")
 ix=data["XIU.TO"].index; names=sorted(set(data)-{"XIU.TO"})
 c=pd.DataFrame({t:data[t].Close.reindex(ix) for t in names})
 o=pd.DataFrame({t:data[t].Open.reindex(ix) for t in names})
 h=pd.DataFrame({t:data[t].High.reindex(ix) for t in names})
 l=pd.DataFrame({t:data[t].Low.reindex(ix) for t in names})
 v=pd.DataFrame({t:data[t].Volume.reindex(ix) for t in names})
 market=data["XIU.TO"].Close.reindex(ix)
 tr=pd.concat([(h-l),(h-c.shift(1)).abs(),(l-c.shift(1)).abs()],keys=["a","b","c"]).groupby(level=1).max()
 atr={n:tr.rolling(n,min_periods=n).mean()/c for n in (5,10,20)}
 volratio=v/v.shift(1).rolling(20,min_periods=20).mean()
 highs={n:h.shift(1).rolling(n,min_periods=n).max() for n in (10,20,40,60)}
 avol={n:atr[n].shift(1).rolling(100,min_periods=100).median() for n in (5,10,20)}
 trend={n:c.rolling(n,min_periods=n).mean() for n in (50,100,200)}
 gate={n:(market>market.rolling(n,min_periods=n).mean()).fillna(False) for n in (50,100,200)}
 # 3 ATR windows x 4 breakout windows x 3 contraction x 3 volume x 3 slots x 3 market = 972 configs
 configs=list(itertools.product((5,10,20),(10,20,40,60),(.5,.75,1.),(1.,1.5,2.),(1,3,5),(50,100,200)))
 returns=o.shift(-1)/o-1
 splits={"train":ix<"2022-01-01","validation":(ix>="2022-01-01")&(ix<"2024-01-01"),
         "recent_diagnostic":ix>="2024-01-01"}
 rows=[]
 for k,(atrwin,breakout,compression,rv,slots,marketma) in enumerate(configs):
  eligible=(atr[atrwin]<avol[atrwin]*compression)&(c>highs[breakout])&(volratio>=rv)&(c>trend[marketma])
  eligible=eligible.mul(gate[marketma],axis=0).fillna(False)
  score=(c/highs[breakout]-1).where(eligible)
  rank=score.rank(axis=1,ascending=False,method="first")
  desired=(rank<=slots).astype(float)
  positions=desired.shift(1).fillna(0)
  positions=positions.div(positions.sum(axis=1).replace(0,np.nan),axis=0).fillna(0)
  # Avoid silent zero-return assumptions on missing active ticker prices.
  if (positions.gt(0)&returns.isna()).iloc[:-1].any().any():continue
  turnover=positions.diff().abs().sum(axis=1);turnover.iloc[0]=positions.iloc[0].abs().sum()
  gross=(positions*returns).sum(axis=1,min_count=1).fillna(0)
  for cost in (.001,.0025,.005):
   net=(gross-cost*turnover).iloc[:-1]
   for label,mask in splits.items():
    rr=net.loc[mask[:-1]]
    if len(rr)<100:continue
    eq=(1+rr).cumprod()
    rows.append(dict(config=k,atr_window=atrwin,breakout_window=breakout,
      contraction=compression,min_rvol=rv,slots=slots,market_ma=marketma,
      cost=cost,split=label,cagr=float(eq.iloc[-1]**(252/len(rr))-1) if eq.iloc[-1]>0 else -1.,
      max_dd=float((eq/eq.cummax()-1).min()),sharpe=float(rr.mean()/rr.std()*np.sqrt(252)) if rr.std()>0 else 0.,
      net_profit_cad=float(5000*(eq.iloc[-1]-1)),
      active_days=int((positions.sum(axis=1).iloc[:-1].loc[mask[:-1]]>0).sum()),
      turnover=float(turnover.iloc[:-1].loc[mask[:-1]].sum())))
 df=pd.DataFrame(rows)
 if df.empty:raise RuntimeError("No complete configurations")
 df.to_csv(OUT/"full_grid.csv",index=False)
 top=df[(df.split=="train")&(df.cost==.0025)].sort_values("cagr",ascending=False).head(30)
 val=df[(df.split=="validation")&(df.cost==.0025)]
 ranked=top.merge(val,on="config",suffixes=("_train","_validation"))
 ranked.to_csv(OUT/"top30_validation.csv",index=False)
 (OUT/"audit.json").write_text(json.dumps({"planned":len(configs),"completed":df.config.nunique(),
  "tickers":names,"dates":[str(ix.min()),str(ix.max())],
  "limitations":["Survivorship-biased Yahoo universe; no delisted stocks",
  "One-day open-to-open screening proxy, no real stop gaps or order book",
  "No corrected VMM benchmark or untouched holdout; 2024 onward already researched",
  "Estimated costs; turnover approximates fills; no forward paper evidence",
  "Parameter combinations may yield identical positions on sparse signal days"]},indent=2))
 print("COMPRESSION BREAKOUT",len(configs),"planned",df.config.nunique(),"completed; 3 costs")
 print(ranked[["config","cagr_train","max_dd_train","cagr_validation","max_dd_validation"]].head(12).to_string(index=False))
if __name__=="__main__":main()
