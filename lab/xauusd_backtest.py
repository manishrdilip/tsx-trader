import os, yfinance as yf
os.makedirs("results",exist_ok=True)
d=yf.download("GC=F",period="730d",interval="1h",progress=False); d.to_pickle("gc_1h.pkl")
import pandas as pd, numpy as np
d=pd.read_pickle('gc_1h.pkl'); d.columns=[c[0] for c in d.columns]; d=d.dropna()
d.index=d.index.tz_convert('America/New_York'); c=d.Close; r=c.pct_change().fillna(0)
COST=0.0001  # ~$0.35 per side
def st(pos,name):
    pos=pos.fillna(0).shift(1).fillna(0); ret=pos*r-pos.diff().abs().fillna(0)*COST
    yrs=len(r)/(23*252); eq=(1+ret).cumprod(); cagr=eq.iloc[-1]**(1/yrs)-1
    dd=(eq/eq.cummax()-1).min(); sh=ret.mean()/ret.std()*np.sqrt(23*252) if ret.std()>0 else 0
    h=ret[:len(ret)//2]; s=ret[len(ret)//2:]
    f=lambda x:((1+x).prod()**(2/yrs)-1)*100
    print(f"{name:36s} {cagr*100:6.1f}%/yr DD={dd*100:6.1f}% Sh={sh:5.2f} 1stHalf={f(h):6.1f}% 2ndHalf={f(s):6.1f}%")
h=d.index.hour; dow=d.index.dayofweek
st(pd.Series(1.0,index=c.index),'Buy & hold (1h data, 2.4y)')
# sessions
st(pd.Series(((h>=19)|(h<3)).astype(float),index=c.index),'Asia session only long')
st(pd.Series(((h>=3)&(h<8)).astype(float),index=c.index),'London session only long')
st(pd.Series(((h>=8)&(h<17)).astype(float),index=c.index),'New York session only long')
st(pd.Series(((h>=17)|(h<8)).astype(float),index=c.index),'Overnight (5pm-8am) long')
# EMA cross intraday
for a,b in [(9,21),(20,50),(50,200)]:
    p=np.sign(c.ewm(span=a).mean()-c.ewm(span=b).mean()); st(p,f'1h EMA{a}/{b} long+short'); st(p.clip(lower=0),f'1h EMA{a}/{b} long only')
# MACD
m=c.ewm(span=12).mean()-c.ewm(span=26).mean(); st(np.sign(m-m.ewm(span=9).mean()),'1h MACD signal long+short')
# Bollinger mean reversion
ma=c.rolling(20).mean(); sd=c.rolling(20).std(); p=pd.Series(np.nan,index=c.index)
p[c<ma-2*sd]=1; p[c>ma+2*sd]=-1; p[(c-ma).abs()<0.2*sd]=0; st(p.ffill(),'1h Bollinger mean-reversion')
# Supertrend-ish via ATR channel
tr=pd.concat([d.High-d.Low,(d.High-c.shift()).abs(),(d.Low-c.shift()).abs()],axis=1).max(axis=1); atr=tr.rolling(14).mean()
mid=(d.High+d.Low)/2; p=pd.Series(np.nan,index=c.index); p[c>mid.rolling(10).mean()+3*atr]=1; p[c<mid.rolling(10).mean()-3*atr]=-1
st(p.ffill(),'1h ATR-channel breakout (L/S)'); st(p.ffill().clip(lower=0),'1h ATR-channel breakout (long)')
# Asian range breakout: range 19:00-02:59, trade 3:00-11:59 breakout direction
day=(d.index+pd.Timedelta(hours=5)).normalize()
asia=((h>=19)|(h<3)); ah=d.High.where(asia).groupby(day).transform('max'); al=d.Low.where(asia).groupby(day).transform('min')
win=(h>=3)&(h<12); p=pd.Series(np.nan,index=c.index); p[win&(c>ah)]=1; p[win&(c<al)]=-1; p[~win]=0
p=p.groupby(day).ffill(); st(p,'Asian range breakout (London)'); st(p.clip(lower=0),'Asian range breakout long only')
# RSI14 30/70
dl=c.diff(); u=dl.clip(lower=0).ewm(alpha=1/14).mean(); dn=(-dl.clip(upper=0)).ewm(alpha=1/14).mean(); rsi=100-100/(1+u/dn)
p=pd.Series(np.nan,index=c.index); p[rsi<30]=1; p[rsi>70]=-1; p[(rsi>48)&(rsi<52)]=0; st(p.ffill(),'1h RSI 30/70 reversal')
# Day of week
for i,n in enumerate(['Mon','Tue','Wed','Thu','Fri']): st(pd.Series((dow==i).astype(float),index=c.index),f'Long only on {n}')
print('--- EMA9/21 long-only robustness')
p=(c.ewm(span=9).mean()>c.ewm(span=21).mean()).astype(float)
print('trades/yr',int(p.diff().abs().sum()/2/(len(r)/(23*252))))
for k in [0.0002,0.0004]:
    COST=k; st(p,f'EMA9/21 cost {k*1e4:.0f}bp/side')
