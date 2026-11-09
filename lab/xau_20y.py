"""20-year XAUUSD 1h test. Data: Dukascopy monthly hourly BID candles (fetched directly)."""
import os, lzma, struct, urllib.request, time, pandas as pd, numpy as np
os.makedirs('results', exist_ok=True); CACHE='results/xau_1h.csv'
def one(ym):
    y,m=ym; t0=pd.Timestamp(y,m+1,1,tz='UTC'); out=[]
    url=f'https://datafeed.dukascopy.com/datafeed/XAUUSD/{y}/{m:02d}/BID_candles_hour_1.bi5'
    raw=b''
    for a in range(3):
        try:
            raw=urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=20).read(); break
        except Exception as e: err=e; time.sleep(2)
    if not raw: print('miss',y,m+1,err,flush=True); return out
    b=lzma.decompress(raw)
    for i in range(0,len(b),24):
        s_,o,c,l,h,v=struct.unpack('>IIIIIf',b[i:i+24])
        if v>0: out.append((t0+pd.Timedelta(seconds=s_),o/1000,h/1000,l/1000,c/1000))
    print('ok',y,m+1,len(out),flush=True); return out
def fetch():
    from concurrent.futures import ThreadPoolExecutor
    now=pd.Timestamp.utcnow(); ym=[(y,m) for y in range(2004,now.year+1) for m in range(12) if pd.Timestamp(y,m+1,1,tz='UTC')<now]
    with ThreadPoolExecutor(12) as ex: rows=[x for part in ex.map(one,ym) for x in part]
    d=pd.DataFrame(rows,columns=['t','Open','High','Low','Close']).set_index('t').sort_index(); d.to_csv(CACHE); return d
d=pd.read_csv(CACHE,index_col=0,parse_dates=True) if os.path.exists(CACHE) else fetch()
d.index=pd.to_datetime(d.index,utc=True).tz_convert('America/New_York')
c=d.Close; r=c.pct_change().fillna(0); BPY=len(r)/((d.index[-1]-d.index[0]).days/365.25)
print(f'bars={len(d)} from {d.index[0]} to {d.index[-1]} bars/yr={BPY:.0f}')
def run(pos,cost):
    pos=pos.fillna(0).shift(1).fillna(0); return pos*r-pos.diff().abs().fillna(0)*cost
def summ(ret):
    yrs=len(ret)/BPY; eq=(1+ret).cumprod(); 
    return eq.iloc[-1]**(1/yrs)-1,(eq/eq.cummax()-1).min(),ret.mean()/ret.std()*np.sqrt(BPY) if ret.std()>0 else 0
def ema(a,b,lo=True): p=(c.ewm(span=a).mean()>c.ewm(span=b).mean()).astype(float); return p if lo else 2*p-1
h=d.index.hour
S={'Buy & hold':pd.Series(1.0,index=c.index),
   'EMA9/21 long':ema(9,21),'EMA9/21 L/S':ema(9,21,False),'EMA5/13 long':ema(5,13),'EMA12/26 long':ema(12,26),
   'EMA20/50 long':ema(20,50),'EMA50/200 long':ema(50,200),
   'Overnight 17-08 long':pd.Series(((h>=17)|(h<8)).astype(float),index=c.index)}
print('\n=== FULL PERIOD (CAGR / maxDD / Sharpe) by cost per side')
for n,p in S.items():
    print(f'{n:22s}'+' '.join(f'{k}bp: {a*100:5.1f}% {dd*100:5.0f}% {s:4.2f} |' for k in [1,2,4] for a,dd,s in [summ(run(p,k/1e4))]))
print('\n=== YEAR BY YEAR, cost 2bp (strategy%/buyhold%)')
yr=r.index.year
for n in ['EMA9/21 long','EMA20/50 long','Overnight 17-08 long']:
    rs=run(S[n],2e-4); bh=run(S['Buy & hold'],0)
    out=[]; beat=0
    for y in sorted(set(yr)):
        a=(1+rs[yr==y]).prod()-1; b=(1+bh[yr==y]).prod()-1; beat+=a>b; out.append(f'{y}:{a*100:+.0f}/{b*100:+.0f}')
    print(n,f'(beat B&H {beat}/{len(set(yr))} yrs)'); print('  '+'  '.join(out))
print('\n=== REGIMES, cost 2bp')
for lab,a,b in [('2004-08 bull','2004','2008'),('2009-12 bull','2009','2012'),('2013-15 BEAR','2013','2015'),('2016-19 chop','2016','2019'),('2020-23 mixed','2020','2023'),('2024-now bull','2024','2026')]:
    m=(r.index.year>=int(a))&(r.index.year<=int(b))
    line=f'{lab:14s}'
    for n in ['Buy & hold','EMA9/21 long','EMA9/21 L/S','EMA20/50 long','Overnight 17-08 long']:
        cg,dd,_=summ(run(S[n],2e-4 if n!='Buy & hold' else 0)[m]); line+=f' {n.split()[0]}{"" if "L/S" not in n else "LS"}:{cg*100:+5.1f}%/{dd*100:.0f}%'
    print(line)
print('\n=== PARAMETER GRID (fast/slow long only, 2bp) CAGR%/DD%')
for a in [3,5,9,12,20]:
    print(f'fast{a:2d}: '+'  '.join(f's{b}:{summ(run(ema(a,b),2e-4))[0]*100:5.1f}/{summ(run(ema(a,b),2e-4))[1]*100:.0f}' for b in [13,21,34,50,100] if b>a))
print('\n=== WALK-FORWARD: each year pick best fast/slow by prior 3y Sharpe, trade it next year (2bp)')
grid=[(a,b) for a in [3,5,9,12,20] for b in [13,21,34,50,100] if b>a]; rets={g:run(ema(*g),2e-4) for g in grid}; wf=[]
for y in range(2007,yr.max()+1):
    tr=(yr>=y-3)&(yr<y); best=max(grid,key=lambda g:summ(rets[g][tr])[2]); wf.append(rets[best][yr==y]); print(y,best,end='; ')
wf=pd.concat(wf); a,dd,s=summ(wf); bh=summ(r[r.index.year>=2007]); print(f'\nWF result {a*100:.1f}%/yr DD {dd*100:.0f}% Sh {s:.2f}  vs B&H {bh[0]*100:.1f}% DD {bh[1]*100:.0f}% Sh {bh[2]:.2f}')
