"""Independent long-only TSX overnight momentum cash-ledger audit (research only).
Signals at close t, enter open t+1, exit open t+2. Integer shares, no leverage,
cash budget and explicit fees. Stops execute at next open with gap losses.
This is NOT an independently validated 3x candidate or a VMM comparison.
"""
import json,pathlib
import numpy as np,pandas as pd,yfinance as yf
OUT=pathlib.Path("research/cash_ledger_audit_results")
TICKERS="RY.TO TD.TO BNS.TO BMO.TO ENB.TO CNQ.TO SU.TO CVE.TO SHOP.TO AEM.TO ABX.TO CCO.TO TECK-B.TO WPM.TO AC.TO".split()
def fetch():
 d={}
 for t in TICKERS:
  try:
   x=yf.download(t,start="2016-01-01",auto_adjust=True,progress=False,threads=False)
   if isinstance(x.columns,pd.MultiIndex):x.columns=x.columns.get_level_values(0)
   x=x[["Open","Close","Volume"]].dropna()
   if len(x)>750:d[t]=x
  except Exception as e:print("FAIL",t,str(e)[:100])
 if len(d)<10:raise RuntimeError("insufficient genuine history")
 return d
def ledger(op,close,cost,slots,lookback,stop_pct):
 # Every signal is computed using previous CLOSE only; holdings never exceed slots.
 mom=close/close.shift(lookback)-1
 ma=close.rolling(200,min_periods=200).mean()
 sig=(mom>0)&(close>ma)
 cash=5000.;held={};trades=[];curve=[];prev_equity=5000.
 for i in range(201,len(op)-1):
  day=op.index[i];prices=op.iloc[i]
  # Sell yesterday's positions at today's open, including gap-through-stop losses.
  for t,p in list(held.items()):
   px=prices.get(t,np.nan)
   if not np.isfinite(px) or px<=0:raise RuntimeError("Missing exit price: "+t)
   received=p["qty"]*px*(1-cost);cash+=received
   trades.append({"ticker":t,"entry_date":str(p["date"].date()),"exit_date":str(day.date()),
     "entry":p["entry"],"exit":float(px),"pnl":received-p["spent"],
     "gap_beyond_stop":bool(px<p["entry"]*(1-stop_pct))})
   del held[t]
  # Signals are previous close, no future-bar ranking.
  prev=op.index[i-1]
  candidates=[t for t in op.columns if bool(sig.loc[prev,t]) and np.isfinite(prices[t]) and prices[t]>0]
  candidates.sort(key=lambda t:(-float(mom.loc[prev,t]),t))
  # Cash allocation fixed at today's opening equity; no fractional shares.
  equity=cash;budget=equity/slots
  for t in candidates[:slots]:
   px=float(prices[t]);qty=int(min(budget,cash)/(px*(1+cost)))
   if qty<1:continue
   spent=qty*px*(1+cost)
   if spent>cash+1e-7:raise AssertionError("overspend")
   cash-=spent;held[t]={"qty":qty,"entry":px,"spent":spent,"date":day}
  equity=cash+sum(p["qty"]*float(prices[t])*(1-cost) for t,p in held.items())
  if cash < -1e-6 or len(held)>slots:raise AssertionError("cash/slot invariant")
  curve.append((day,equity))
 # Liquidate at last next open; never value open positions at an unexecuted future close.
 day=op.index[-1];prices=op.iloc[-1]
 for t,p in held.items():
  px=float(prices[t]);received=p["qty"]*px*(1-cost);cash+=received
  trades.append({"ticker":t,"entry_date":str(p["date"].date()),"exit_date":str(day.date()),
   "entry":p["entry"],"exit":px,"pnl":received-p["spent"],
   "gap_beyond_stop":bool(px<p["entry"]*(1-stop_pct))})
 curve.append((day,cash))
 return pd.DataFrame(trades),pd.Series({d:e for d,e in curve},dtype=float)
def main():
 OUT.mkdir(parents=True,exist_ok=True);data=fetch()
 ix=pd.DatetimeIndex(sorted(set.intersection(*(set(x.index) for x in data.values()))))
 op=pd.DataFrame({t:x.Open.reindex(ix) for t,x in data.items()})
 cl=pd.DataFrame({t:x.Close.reindex(ix) for t,x in data.items()})
 rows=[]
 for lookback in (20,60,120):
  for slots in (1,3,5):
   for cost in (.001,.0025,.005):
    for stop in (.05,.10,.20):
     trades,curve=ledger(op,cl,cost,slots,lookback,stop)
     for split,mask in {"train":curve.index<"2022-01-01","validation":(curve.index>="2022-01-01")&(curve.index<"2024-01-01"),"recent_diagnostic":curve.index>="2024-01-01"}.items():
      c=curve.loc[mask]
      if len(c)<100:continue
      # Split returns start from previous close-to-close equity to avoid resetting cash to 5000.
      start=curve.iloc[curve.index.get_loc(c.index[0])-1] if curve.index.get_loc(c.index[0])>0 else 5000.
      total=float(c.iloc[-1]/start)
      boundary=curve.index.get_loc(c.index[0])
      path_equity=pd.concat([curve.iloc[[boundary-1]],c]) if boundary>0 else pd.concat([pd.Series([5000.],index=[c.index[0]-pd.Timedelta(days=1)]),c])
      # Continuous-account drawdown uses the peak from ALL preceding dates,
      # not just the preceding session (which can conceal an old drawdown).
      running_peak=curve.loc[:c.index[-1]].cummax().reindex(c.index)
      running_peak=running_peak.clip(lower=5000.)
      dd=float((c/running_peak-1).min())
      tr=trades[(pd.to_datetime(trades.exit_date)>=c.index[0])&(pd.to_datetime(trades.exit_date)<=c.index[-1])]
      pnl=tr.pnl.to_numpy(dtype=float)
      gp=pnl[pnl>0].sum();gl=-pnl[pnl<0].sum()
      daily=path_equity.pct_change().dropna()
      rows.append(dict(lookback=lookback,slots=slots,cost=cost,stop_audit_threshold=stop,
       split=split,cagr=total**(252/len(c))-1,max_dd=dd,
       net_profit_cad=float(c.iloc[-1]-start),trades=len(tr),
       profit_factor=float(gp/gl) if gl>0 else None,
       expectancy_cad=float(pnl.mean()) if len(pnl) else None,
       sharpe=float(daily.mean()/daily.std()*np.sqrt(252)) if daily.std()>0 else None,
       gap_beyond_stop_count=int(tr.gap_beyond_stop.sum())))
 df=pd.DataFrame(rows);df.to_csv(OUT/"ledger_metrics.csv",index=False)
 (OUT/"audit.json").write_text(json.dumps({"tickers":list(data),"start":str(ix.min()),"end":str(ix.max()),
 "distinct_executable_parameter_sets":27,"stop_thresholds_are_diagnostics_not_distinct_strategies":3,
 "limitations":["Historical Yahoo surviving stocks only; survivorship bias",
 "Adjusted OHLC is not executable broker pricing","No observed spread, liquidity or slippage",
 "Stop threshold only counts next-open gaps; NOT a protective stop order",
 "Daily overnight positions, no intraday stops; VMM not matched",
 "2024+ is previously researched, not untouched OOS",
 "No forward paper trading"],"cash_accounting":"integer shares, actual cash, explicit two-sided costs, next-open exits"},indent=2))
 print("LEDGER AUDIT",len(df),"split records")
 print(df[(df.split=="validation")&(df.cost==.0025)&(df.stop_audit_threshold==.10)].sort_values("cagr",ascending=False).head(10).to_string(index=False))
if __name__=="__main__":main()
