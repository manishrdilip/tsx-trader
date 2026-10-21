import sys, itertools; sys.path.insert(0,'lab')
import numpy as np, pandas as pd, indicators, setups, sim
pd.set_option('display.width',250); pd.set_option('display.max_rows',300)
P=indicators.load_panel(exclude=indicators.non_stocks()); I=indicators.build(P)
for k,v in list(I.items()):
    if isinstance(v,(pd.DataFrame,pd.Series)): I[k]=v.loc["2009-01-01":]
dates=I["C"].index.values; C=I["C"]; liq=I["liquid"]
stage2=((C>I["sma50"])&(I["sma50"]>I["sma150"])&(I["sma150"]>I["sma200"])&(I["sma200"]>I["sma200"].shift(21))
        &(C>=1.3*I["lo252"])&(C>=0.75*I["hi252"]))
nxt=pd.Series(C.index.month,index=C.index).shift(-5)
tomv=(pd.Series(C.index.month,index=C.index)!=nxt).values[:,None]
tom=pd.DataFrame(np.repeat(tomv,C.shape[1],1),index=C.index,columns=C.columns)
mkt=I["mkt_up"].reindex(C.index).fillna(False).values[:,None]
rs=I["rs_rank"]
cand={
 "S2 RS>.7 RSI2<10": stage2&(rs>.7)&(I["rsi2"]<10),
 "S2 RS>.8 RSI2<10": stage2&(rs>.8)&(I["rsi2"]<10),
 "S2 RS>.8 RSI2<5": stage2&(rs>.8)&(I["rsi2"]<5),
 "S2 RS>.8 RSI2<10 IBS<.25": stage2&(rs>.8)&(I["rsi2"]<10)&(I["ibs"]<.25),
 "S2 RS>.8 RSI2<10 TOM": stage2&(rs>.8)&(I["rsi2"]<10)&tom,
 "S2 RS>.7 TOM RSI2<30": stage2&(rs>.7)&tom&(I["rsi2"]<30),
 "S2 TOM RSI2<30": stage2&tom&(I["rsi2"]<30),
 "S2 RS>.8 3down": stage2&(rs>.8)&(C<C.shift(1))&(C.shift(1)<C.shift(2))&(C.shift(2)<C.shift(3)),
 "S2 RS>.8 pullback 20EMA": stage2&(rs>.8)&(I["L"]<=I["ema20"])&(C>I["ema20"]),
 "S2 RS>.9 RSI2<15": stage2&(rs>.9)&(I["rsi2"]<15),
 "BASE S2 RS>.8": stage2&(rs>.8),
}
ex={}
for t,s,h in itertools.product([.03],[.01,.02,.03,.04,.05,.06,.08],[10,20]): ex[f"+3%/-{s*100:g}% {h}d"]=dict(tgt_pct=t,stop_pct=s,hold=h)
for sa,ta,h in [(1.5,3,20),(2,4,20),(2,5,25),(2,6,30),(2.5,5,25),(3,6,30),(1,2,10),(2,3,15)]: ex[f"ATR {sa}/{ta} {h}d"]=dict(stop_atr=sa,tgt_atr=ta,hold=h)
ex["MR close>SMA5 stop-8% 10d"]=dict(mr=1,stop_pct=.08,hold=10)
ex["MR close>prevHigh stop-8% 10d"]=dict(mr=2,stop_pct=.08,hold=10)
rows=[]
for n,sg in cand.items():
  for reg in ("all","mkt"):
    s=(sg&liq).fillna(False); s=s&mkt if reg=="mkt" else s
    for en,kw in ex.items():
        ti,ei,xi,r=sim.simulate(I,s,mode=0,**kw)
        if len(r)==0: continue
        tr,te=sim.summarize(dates,ti,ei+1,xi,r,"2019-01-01")
        rows.append(dict(setup=n,reg=reg,exit=en,n_tr=tr and tr["trades"],win_tr=tr and tr["win"],avg_tr=tr and tr["avg"],
            n_te=te["trades"],win_te=te["win"],avg_te=te["avg"],pf_te=te["pf"],aw=te["avg_win"],al=te["avg_loss"],hold=te["hold"],yr=te["per_year"]))
d=pd.DataFrame(rows); d.to_csv("lab/results/explore.csv",index=False)
