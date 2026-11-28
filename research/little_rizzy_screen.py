"""Little Rizzy interpretation, research only; not original discretionary rules.
Daily or intraday OHLC input; no trading or broker access.
"""
import numpy as np
import pandas as pd

def signals(d, k=3):
    h,l,c=(d[x].to_numpy(float) for x in ("High","Low","Close"))
    out=np.full((len(d),3),np.nan)
    piv=[]
    for t in range(2*k,len(d)):
        j=t-k
        if h[j]==max(h[j-k:t+1]) and sum(h[j]==h[j-k:t+1])==1:
            piv.append(j)
        if len(piv)<2: continue
        a,b=piv[-2:]
        if h[b]>=h[a]: continue
        slope=(h[b]-h[a])/(b-a)
        line=h[b]+slope*(t-b)
        prev=line-slope
        depth=max(h[a]+slope*(i-a)-l[i] for i in range(a,b+1))
        if depth>0 and c[t]>line and c[t-1]<=prev:
            out[t]=[line,line+depth,min(l[b:t+1])]
    return pd.DataFrame(out,index=d.index,columns=["line","target","stop"])

def screen(d,k=3,cost=.0025):
    s=signals(d,k)
    trades=[]
    i=0
    while i<len(d)-1:
        if not np.isfinite(s.target.iloc[i]): i+=1; continue
        entry=float(d.Open.iloc[i+1]); stop=s.stop.iloc[i]; target=s.target.iloc[i]
        if not stop<entry<target: i+=1; continue
        for j in range(i+1,len(d)):
            o,h,l,c=map(float,d.iloc[j][["Open","High","Low","Close"]])
            # Conservative stop-first ambiguity; gap-through stop at open.
            if o<=stop: exit=o
            elif o>=target: exit=target
            elif l<=stop: exit=stop
            elif h>=target: exit=target
            elif j>=i+20: exit=c
            else: continue
            trades.append((i,j,exit*(1-cost)/(entry*(1+cost))-1))
            i=j+1
            break
        else: break
    return trades

def self_test():
    rng=np.random.default_rng(20261125)
    c=100+np.cumsum(rng.normal(size=300))
    d=pd.DataFrame(dict(Open=c,High=c+1,Low=c-1,Close=c))
    full=signals(d)
    for n in range(10,len(d),7):
        pd.testing.assert_frame_equal(full.iloc[:n],signals(d.iloc[:n]))
    assert all(a<b for a,b,r in screen(d))
    print("Synthetic causality checks passed; not market evidence")

if __name__=="__main__":
    self_test()
