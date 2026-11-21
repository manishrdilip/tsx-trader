"""Research-only TSX leader pullback test. No broker connections or orders.
Uses current ticker list: survivorship bias remains. No performance claims without data.
"""
import argparse, json, math
from pathlib import Path
import numpy as np
import pandas as pd
import yfinance as yf

TICKERS = "RY.TO TD.TO BNS.TO BMO.TO CM.TO NA.TO ENB.TO TRP.TO SU.TO CNQ.TO CVE.TO IMO.TO TOU.TO CNR.TO CP.TO WCN.TO ATD.TO DOL.TO L.TO MRU.TO GIB-A.TO CSU.TO SHOP.TO OTEX.TO NTR.TO FNV.TO AEM.TO ABX.TO K.TO WPM.TO TECK-B.TO FM.TO CCO.TO BCE.TO T.TO FTS.TO EMA.TO POW.TO MFC.TO SLF.TO IFC.TO GWO.TO QSR.TO MG.TO AC.TO WSP.TO STN.TO XIC.TO XIU.TO".split()

def load(start):
    raw=yf.download(TICKERS,start=start,auto_adjust=True,progress=False,threads=True,group_by="ticker")
    panels={}
    for ticker in TICKERS:
        try:
            x=raw[ticker][["Open","High","Low","Close","Volume"]].copy()
            if x["Close"].notna().sum()>260: panels[ticker]=x
        except (KeyError,TypeError): continue
    if "XIU.TO" not in panels or "XIC.TO" not in panels: raise RuntimeError("Benchmark data unavailable")
    return panels

def rsi2(close):
    d=close.diff()
    gain=d.clip(lower=0).ewm(alpha=.5,adjust=False).mean()
    loss=(-d.clip(upper=0)).ewm(alpha=.5,adjust=False).mean()
    return 100-100/(1+gain/loss.replace(0,np.nan))

def features(panels):
    idx=panels["XIU.TO"].index
    xi=panels["XIU.TO"]["Close"].reindex(idx)
    market=(xi>xi.rolling(200,min_periods=200).mean()).shift(1).fillna(False)
    rows={}
    for ticker,x in panels.items():
        if ticker in ("XIU.TO","XIC.TO"):continue
        x=x.reindex(idx)
        c=x["Close"]; s50=c.rolling(50).mean();s150=c.rolling(150).mean();s200=c.rolling(200).mean()
        stage=(c>s50)&(s50>s150)&(s150>s200)&(s200>s200.shift(21))&(c>=1.3*c.rolling(252).min())&(c>=.75*c.rolling(252).max())
        # 12-month momentum proxy; cross-sectional rank computed below.
        mom=c/c.shift(252)-1
        tr=pd.concat([(x.High-x.Low),(x.High-c.shift()).abs(),(x.Low-c.shift()).abs()],axis=1).max(axis=1)
        atr=tr.rolling(14).mean()
        liq=(c*x.Volume).rolling(20).mean()>=1_000_000
        rows[ticker]={"ohlcv":x,"stage":stage,"mom":mom,"atr":atr,"rsi":rsi2(c),"liq":liq}
    rank=pd.DataFrame({k:v["mom"] for k,v in rows.items()}).rank(axis=1,pct=True)
    for k,v in rows.items():
        v["signal"]=(v["stage"]&(rank[k]>.8)&(v["rsi"]<10)&v["liq"]&market).shift(1).fillna(False)
        v["rank"]=rank[k].shift(1)
        v["atrprev"]=v["atr"].shift(1)
    return idx,rows

def simulate(idx,rows,start,end,slots=3,stop_atr=2.5,target_atr=5,hold=25,cost=.001,capital=5000):
    cash=float(capital);positions={};equity=[];trades=[]; prev=None
    for day,dt in enumerate(idx):
        if dt<pd.Timestamp(start) or dt>pd.Timestamp(end):continue
        # Exit decisions at today's OHLC; gaps fill at open, stop-first if both levels reached.
        for ticker,p in list(positions.items()):
            x=rows[ticker]["ohlcv"].iloc[day]
            if pd.isna(x.Open):continue
            price=None;reason=None
            if x.Open<=p["stop"]:price=float(x.Open);reason="stop_gap"
            elif x.Low<=p["stop"]:price=p["stop"];reason="stop"
            elif x.Open>=p["target"]:price=float(x.Open);reason="target_gap"
            elif x.High>=p["target"]:price=p["target"];reason="target"
            elif day-p["day"]>=hold:price=float(x.Close);reason="time"
            if price is not None:
                proceeds=p["qty"]*price*(1-cost);cash+=proceeds
                trades.append(dict(ticker=ticker,entry=str(idx[p["day"]].date()),exit=str(dt.date()),net_pnl=round(proceeds-p["spent"],2),reason=reason))
                del positions[ticker]
        # Signals based on prior close, buy next open; reserve cash immediately.
        if len(positions)<slots:
            picks=[]
            for ticker,v in rows.items():
                if ticker in positions:continue
                if not bool(v["signal"].iloc[day]):continue
                x=v["ohlcv"].iloc[day]; atr=v["atrprev"].iloc[day]
                if not(np.isfinite(x.Open) and np.isfinite(atr) and atr>0):continue
                prevclose=v["ohlcv"]["Close"].iloc[day-1] if day else np.nan
                if np.isfinite(prevclose) and x.Open>prevclose*1.02:continue
                picks.append((float(v["rank"].iloc[day]),ticker,float(x.Open),float(atr)))
            for _,ticker,op,atr in sorted(picks,reverse=True):
                if len(positions)>=slots:break
                # Risk 0.5% of current marked equity, max 1/slots capital per position.
                marked=cash+sum(p["qty"]*float(rows[t]["ohlcv"]["Close"].iloc[day-1]) for t,p in positions.items() if day and np.isfinite(rows[t]["ohlcv"]["Close"].iloc[day-1]))
                risk_budget=max(0,marked*.005)
                qty=int(min(cash/(op*(1+cost)),marked/slots/(op*(1+cost)),risk_budget/(stop_atr*atr+op*cost*2)))
                if qty<=0:continue
                spent=qty*op*(1+cost);cash-=spent
                positions[ticker]={"qty":qty,"day":day,"stop":op-stop_atr*atr,"target":op+target_atr*atr,"spent":spent}
        marked=cash
        for ticker,p in positions.items():
            cl=rows[ticker]["ohlcv"]["Close"].iloc[day]
            if np.isfinite(cl):p["last"]=float(cl)
            marked+=p["qty"]*p.get("last",p["spent"]/p["qty"])
        equity.append((dt,marked))
    if not equity:raise RuntimeError("No price dates in test interval")
    curve=pd.Series(dict(equity)).sort_index()
    # Liquidate final holdings at final close, with costs, to measure realized end wealth.
    for ticker,p in positions.items():
        cash+=p["qty"]*p.get("last",p["spent"]/p["qty"])*(1-cost)
    final=cash
    years=max((curve.index[-1]-curve.index[0]).days/365.25,.01)
    dd=float((curve/curve.cummax()-1).min())
    return dict(start=start,end=end,initial=capital,final=round(final,2),net_profit=round(final-capital,2),cagr=round((final/capital)**(1/years)-1,4),max_drawdown=round(dd,4),trades=len(trades),win_rate=round(sum(t["net_pnl"]>0 for t in trades)/len(trades),4) if trades else None,worst_day=round(curve.pct_change().min(),4),trades_detail=trades)

def main():
    p=argparse.ArgumentParser();p.add_argument("--start",default="2010-01-01");p.add_argument("--out",default="research/results");args=p.parse_args()
    panels=load(args.start);idx,rows=features(panels)
    Path(args.out).mkdir(parents=True,exist_ok=True)
    results=[]
    for label,begin,end in [("train","2012-01-01","2021-12-31"),("holdout","2022-01-01","2026-11-20")]:
        for slots in (3,5):
            for stop,target in [(2.5,5),(2,4),(3,6)]:
                z=simulate(idx,rows,begin,end,slots=slots,stop_atr=stop,target_atr=target)
                trades=z.pop("trades_detail")
                z.update(segment=label,slots=slots,stop_atr=stop,target_atr=target,ticker_count=len(rows),survivorship_bias=True)
                results.append(z)
                pd.DataFrame(trades).to_csv(f"{args.out}/{label}_{slots}_{stop}_{target}_trades.csv",index=False)
    pd.DataFrame(results).to_csv(f"{args.out}/summary.csv",index=False)
    with open(f"{args.out}/summary.json","w") as f:json.dump(results,f,indent=2)
    print(pd.DataFrame(results).to_string(index=False))
if __name__=="__main__":main()
