import sys; sys.path.insert(0,'lab')
import numpy as np, pandas as pd, indicators, sim, portfolio
def prep():
    P=indicators.load_panel(exclude=indicators.non_stocks()); I=indicators.build(P)
    for k,v in list(I.items()):
        if isinstance(v,(pd.DataFrame,pd.Series)): I[k]=v.loc["2009-01-01":]
    C=I["C"]
    I["stage2"]=((C>I["sma50"])&(I["sma50"]>I["sma150"])&(I["sma150"]>I["sma200"])&(I["sma200"]>I["sma200"].shift(21))
        &(C>=1.3*I["lo252"])&(C>=0.75*I["hi252"]))
    nxt=pd.Series(C.index.month,index=C.index).shift(-5)
    tv=(pd.Series(C.index.month,index=C.index)!=nxt).values[:,None]
    I["tom"]=pd.DataFrame(np.repeat(tv,C.shape[1],1),index=C.index,columns=C.columns)
    I["mktc"]=pd.DataFrame(np.repeat(I["mkt_up"].reindex(C.index).fillna(False).values[:,None],C.shape[1],1),index=C.index,columns=C.columns)
    return I
def signals(I):
    s2,rs,r2,liq=I["stage2"],I["rs_rank"],I["rsi2"],I["liquid"]
    lead=(s2&(rs>.8)&(r2<10)&liq&I["mktc"]).fillna(False)
    return {
     "A Leader dip - swing (ATR 2.5 stop / 5 target, 25d)": (lead, dict(stop_atr=2.5,tgt_atr=5,hold=25)),
     "B Leader dip - quick bounce (exit close>SMA5, stop -8%)": (lead, dict(mr=1,stop_pct=.08,hold=10)),
     "C Leader dip at month-end - quick bounce": ((lead&I["tom"]).fillna(False), dict(mr=1,stop_pct=.08,hold=10)),
     "D Leader dip - YOUR +3%/-1% rule": (lead, dict(tgt_pct=.03,stop_pct=.01,hold=10)),
     "E Leader dip - +3% target / -5% stop": (lead, dict(tgt_pct=.03,stop_pct=.05,hold=20)),
    }
if __name__=="__main__":
    I=prep(); dates=I["C"].index.values; rank=I["rs_rank"].values
    out=[]; yearly={}
    for name,(sg,kw) in signals(I).items():
        ti,ei,xi,r=sim.simulate(I,sg,mode=0,**kw)
        k=rank[ei,ti]
        for slots in (3,5):
            p=portfolio.run(dates,ti,ei+1,xi,r,rank=k,slots=slots)
            out.append(dict(strategy=name,slots=slots,trades=len(r),win=(r>0).mean(),avg=r.mean(),
                monthly=p["monthly"],cagr=p["cagr"],win_months=p["win_months"],max_dd=p["max_dd"],worst_month=p["worst_month"]))
            if slots==5:
                y=p["curve"].resample("YE").last(); y=pd.concat([pd.Series([1.0],index=[y.index[0]-pd.offsets.YearEnd(1)]),y])
                yearly[name[:1]]=y.pct_change().dropna()
    xic=I["C"]["XIC.TO"].dropna(); yx=xic.resample("YE").last().pct_change().dropna()
    yearly["XIC buy&hold"]=yx
    m=xic.resample("ME").last().pct_change().dropna()
    out.append(dict(strategy="XIC.TO buy & hold (whole TSX)",slots=0,monthly=(xic.iloc[-1]/xic.iloc[0])**(1/len(m))-1,
        cagr=(xic.iloc[-1]/xic.iloc[0])**(12/len(m))-1,win_months=(m>0).mean(),max_dd=-(xic/xic.cummax()-1).min(),worst_month=m.min()))
    pd.set_option('display.width',250)
    o=pd.DataFrame(out); print(o.round(4).to_string(index=False))
    Y=pd.DataFrame(yearly); Y.index=Y.index.year; print(Y.round(3).to_string())
    o.to_csv("lab/results/portfolio.csv",index=False); Y.to_csv("lab/results/yearly.csv")
