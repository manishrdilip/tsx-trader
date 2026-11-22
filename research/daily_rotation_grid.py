"""Research-only distinct cross-sectional TSX momentum/rotation grid.
No trading, no live code. Close t-1 signal, open t entry, open t+1 exit/mark.
Screening proxy: daily open-to-open, not stop-gap simulation. Surviving Yahoo tickers.
"""
import itertools,json,pathlib
import numpy as np
import pandas as pd
import yfinance as yf
OUT=pathlib.Path("research/rotation_results")
TICKERS="RY.TO TD.TO BNS.TO BMO.TO ENB.TO CNQ.TO SU.TO CVE.TO SHOP.TO AEM.TO ABX.TO CCO.TO TECK-B.TO WPM.TO AC.TO".split()
def download():
    d={}
    for t in TICKERS+["XIU.TO"]:
        try:
            x=yf.download(t,start="2016-01-01",auto_adjust=True,progress=False,threads=False)
            if isinstance(x.columns,pd.MultiIndex):x.columns=x.columns.get_level_values(0)
            if len(x)>=700:d[t]=x[["Open","Close","Volume"]].dropna()
        except Exception as e:print("FETCH_FAIL",t,str(e)[:120])
    if len(d)<11 or "XIU.TO" not in d:raise RuntimeError("Insufficient real data")
    return d
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    d=download(); names=sorted(set(d)-{"XIU.TO"})
    ix=d["XIU.TO"].index
    c=pd.DataFrame({t:d[t].Close.reindex(ix) for t in names})
    o=pd.DataFrame({t:d[t].Open.reindex(ix) for t in names})
    market=d["XIU.TO"].Close.reindex(ix)
    # 4 momentum x 4 skip x 4 trend x 3 slots x 3 rebalance x 3 market = 1728 configs.
    configs=list(itertools.product((20,60,120,250),(0,5,10,20),(50,100,150,200),
                                   (1,3,5),(1,5,20),("none","ma100","ma200")))
    next_open_return=o.shift(-1)/o-1
    mom={(m,s):c.shift(s)/c.shift(m+s)-1 for m,s in itertools.product((20,60,120,250),(0,5,10,20))}
    ma={n:c.rolling(n,min_periods=n).mean() for n in (50,100,150,200)}
    market_ok={"none":pd.Series(True,index=ix),"ma100":market>market.rolling(100).mean(),
               "ma200":market>market.rolling(200).mean()}
    splits={"train":ix<"2022-01-01","validation":(ix>="2022-01-01")&(ix<"2024-01-01"),
            "recent_diagnostic":ix>="2024-01-01"}
    rows=[]
    for k,(m,skip,trend,slots,rebalance,gate) in enumerate(configs):
        eligible=(c>ma[trend])&mom[(m,skip)].notna()
        rank=mom[(m,skip)].where(eligible).rank(axis=1,ascending=False,method="first")
        # Signals at close, holdings at next open. Rebalance every N exchange sessions;
        # carry holdings across non-rebalance dates; exit on market filter failure.
        desired=(rank<=slots).astype(float)
        mask=(np.arange(len(ix))%rebalance)==0
        desired.loc[~mask]=np.nan
        desired=desired.ffill().fillna(0)
        desired=desired.mul(market_ok[gate].fillna(False),axis=0)
        positions=desired.shift(1).fillna(0)
        positions=positions.div(positions.sum(axis=1).replace(0,np.nan),axis=0).fillna(0)
        turnover=positions.diff().abs().sum(axis=1)
        turnover.iloc[0]=positions.iloc[0].abs().sum()
        gross=(positions*next_open_return).sum(axis=1,min_count=1).fillna(0)
        # Last row has no next open: exclude.
        for cost in (.001,.0025,.005):
            net=(gross-cost*turnover).iloc[:-1]
            for label,period in splits.items():
                r=net.loc[period[:-1]]
                if len(r)<100:continue
                equity=(1+r).cumprod()
                yrs=len(r)/252
                cagr=float(equity.iloc[-1]**(1/yrs)-1) if equity.iloc[-1]>0 else -1
                dd=float((equity/equity.cummax()-1).min())
                annvol=float(r.std()*np.sqrt(252))
                sharpe=float(r.mean()/r.std()*np.sqrt(252)) if r.std()>0 else 0
                rows.append(dict(config=k,momentum=m,skip=skip,trend=trend,slots=slots,
                  rebalance=rebalance,market_gate=gate,cost=cost,split=label,
                  cagr=cagr,max_dd=dd,sharpe=sharpe,annual_vol=annvol,
                  net_profit_cad=float(5000*(equity.iloc[-1]-1)),
                  active_days=int((positions.sum(axis=1).iloc[:-1].loc[period[:-1]]>0).sum()),
                  turnover=float(turnover.iloc[:-1].loc[period[:-1]].sum())))
    df=pd.DataFrame(rows)
    df.to_csv(OUT/"full_grid.csv",index=False)
    train=df[(df.split=="train")&(df.cost==.0025)].sort_values("cagr",ascending=False).head(30)
    val=df[(df.split=="validation")&(df.cost==.0025)]
    summary=train.merge(val,on="config",suffixes=("_train","_validation"))
    summary.to_csv(OUT/"top30_validation.csv",index=False)
    (OUT/"audit.json").write_text(json.dumps({"configs":len(configs),"tickers":names,
      "dates":[str(ix.min()),str(ix.max())],"train":"2016-2021","validation":"2022-2023",
      "recent":"2024 onward (not untouched)","limitations":["Yahoo survivors; no delisted universe",
      "open-to-open fills are proxy, no actual spreads or intraday stop gaps",
      "not comparable corrected VMM baseline","no untouched holdout or forward paper evidence",
      "no 3x conclusion permitted"]},indent=2))
    print("NEW ROTATION SCREEN",len(configs),"configs 3 costs",len(names),"tickers")
    print(summary[["config","cagr_train","max_dd_train","cagr_validation","max_dd_validation"]].head(15).to_string(index=False))
if __name__=="__main__":main()
