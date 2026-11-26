"use strict";
function range(a,b,s=1){return Array.from({length:Math.floor((b-a)/s)+1},(_,i)=>a+i*s)}

function registry(){
 const r={};const add=(family,params,ops)=>{(r[family]??=[]).push(...ops.map(op=>({family,params,op})))};
 for(const n of range(5,100))for(const level of range(20,80,5))add("RSI",{n,level},["above","below","cross_up","cross_down"]);
 for(const n of range(5,200))for(const f of ["EMA","SMA"])add(f,{n},["above","below","cross_up","cross_down"]);
 for(const fast of range(5,15))for(const slow of range(16,40))for(const signal of range(3,12))add("MACD",{fast,slow,signal},["above","below","cross_up","cross_down"]);
 add("VWAP",{},["above","below","cross_up","cross_down"]);
 for(const n of range(5,60,5))for(const level of [1,1.25,1.5,2,3])add("RVOL",{n,level},["above","below"]);
 for(const n of range(2,20))add("BOS",{n},["bull_break","bear_break"]);
 for(const n of range(2,60))for(const level of [-.01,-.005,0,.005,.01])add("ROC",{n,level},["above","below","cross_up","cross_down"]);
 for(const n of range(5,50))for(const level of [.001,.002,.005,.01,.02])add("ATR",{n,level},["above","below"]);
 for(const n of range(5,50))for(const k of [1,1.5,2,2.5,3])add("BB",{n,k},["above_upper","below_lower"]);
 return Object.entries(r).map(([name,rules])=>({name,rules}));
}

function makeSpace(families,minDepth=1,maxDepth=families.length){
 if(!Number.isInteger(minDepth)||!Number.isInteger(maxDepth)||minDepth<1||maxDepth<minDepth||maxDepth>families.length)throw Error("invalid depth");
 const memo=new Map();
 function count(i,k){if(k===0)return 1n;if(i>=families.length||k<0||families.length-i<k)return 0n;const key=i+":"+k;if(!memo.has(key))memo.set(key,count(i+1,k)+BigInt(families[i].rules.length)*count(i+1,k-1));return memo.get(key)}
 let total=0n;for(let k=minDepth;k<=maxDepth;k++)total+=count(0,k);
 function at(id){id=BigInt(id);if(id<0n||id>=total)throw Error("candidate ID out of range");let k=minDepth;while(id>=count(0,k)){id-=count(0,k);k++}const rules=[];for(let i=0;k>0;i++){const tail=count(i+1,k-1),block=BigInt(families[i].rules.length)*tail;if(id<block){rules.push(families[i].rules[Number(id/tail)]);id%=tail;k--}else id-=block}return rules}
 return {total,at,count};
}

function roll(a,n,fn){return a.map((_,i)=>i+1<n?NaN:fn(a.slice(i+1-n,i+1)))}

function avg(a){return a.reduce((s,x)=>s+x,0)/a.length}

function ema(a,n,alpha=2/(n+1)){let v=NaN,seed=[];return a.map(x=>{if(!Number.isFinite(x)){v=NaN;seed=[];return NaN}if(!Number.isFinite(v)){seed.push(x);if(seed.length<n)return NaN;v=avg(seed)}else v+=alpha*(x-v);return v})}

function testRule(bars,rule){
 const c=bars.map(b=>b.close),h=bars.map(b=>b.high),l=bars.map(b=>b.low),v=bars.map(b=>b.volume);
 const {family,params:p,op}=rule;let a=c,b;
 if(family==="RSI"){const delta=c.map((x,i)=>i?x-c[i-1]:NaN),u=ema(delta.map(x=>Math.max(x,0)),p.n,1/p.n),d=ema(delta.map(x=>Math.max(-x,0)),p.n,1/p.n);a=u.map((x,i)=>!Number.isFinite(x)||!Number.isFinite(d[i])?NaN:d[i]===0?x===0?50:100:100-100/(1+x/d[i]));b=c.map(()=>p.level)}
 else if(family==="EMA")b=ema(c,p.n);
 else if(family==="SMA")b=roll(c,p.n,avg);
 else if(family==="MACD"){const f=ema(c,p.fast),s=ema(c,p.slow);a=f.map((x,i)=>x-s[i]);b=ema(a,p.signal)}
 else if(family==="VWAP"){let session,sv=0,sp=0;b=bars.map(x=>{if(x.session!==session){session=x.session;sv=0;sp=0}if(!Number.isFinite(x.volume))return NaN;sv+=x.volume;sp+=(x.high+x.low+x.close)/3*x.volume;return sv>0?sp/sv:NaN})}
 else if(family==="RVOL"){const m=roll(v,p.n,avg);a=v.map((x,i)=>i&&m[i-1]>0?x/m[i-1]:NaN);b=c.map(()=>p.level)}
 else if(family==="ROC"){a=c.map((x,i)=>i>=p.n?x/c[i-p.n]-1:NaN);b=c.map(()=>p.level)}
 else if(family==="ATR"){const tr=h.map((x,i)=>i?Math.max(x-l[i],Math.abs(x-c[i-1]),Math.abs(l[i]-c[i-1])):x-l[i]);a=ema(tr,p.n,1/p.n).map((x,i)=>x/c[i]);b=c.map(()=>p.level)}
 else if(family==="BB"){const m=roll(c,p.n,avg);const sd=roll(c,p.n,x=>{const mu=avg(x);return Math.sqrt(avg(x.map(y=>(y-mu)**2)))});b=m.map((x,i)=>x+(op==="above_upper"?1:-1)*p.k*sd[i])}
 else if(family==="BOS"){const out=[];let hi=NaN,lo=NaN;for(let i=0;i<c.length;i++){const j=i-p.n;if(j>=p.n){const left=j-p.n,right=j+p.n;const hh=h.slice(left,right+1),ll=l.slice(left,right+1);if(h[j]===Math.max(...hh)&&hh.filter(x=>x===h[j]).length===1)hi=h[j];if(l[j]===Math.min(...ll)&&ll.filter(x=>x===l[j]).length===1)lo=l[j]}let bull=Number.isFinite(hi)&&c[i]>hi,bear=Number.isFinite(lo)&&c[i]<lo;out.push(op==="bull_break"?bull:bear);if(bull)hi=NaN;if(bear)lo=NaN}return out}
 else throw Error("unimplemented family "+family);
 return a.map((x,i)=>{const y=b[i];if(!Number.isFinite(x)||!Number.isFinite(y))return false;if(op==="above"||op==="above_upper")return x>y;if(op==="below"||op==="below_lower")return x<y;if(i===0||!Number.isFinite(a[i-1])||!Number.isFinite(b[i-1]))return false;if(op==="cross_up")return x>y&&a[i-1]<=b[i-1];if(op==="cross_down")return x<y&&a[i-1]>=b[i-1];throw Error("unknown operator")})
}

function validate(bars){if(!Array.isArray(bars)||bars.length<3)throw Error("at least three bars required");let prev=-Infinity;for(const b of bars){let t=Date.parse(b.timestamp);if(!Number.isFinite(t)||t<=prev||!/(Z|[+-]\d\d:\d\d)$/.test(b.timestamp))throw Error("timestamps must be increasing and timezone aware");prev=t;if(typeof b.session!=="string"||!b.session)throw Error("explicit session required");if(![b.open,b.high,b.low,b.close].every(x=>Number.isFinite(x)&&x>0)||b.high<Math.max(b.open,b.close,b.low)||b.low>Math.min(b.open,b.close)||!(b.volume===null||Number.isFinite(b.volume)&&b.volume>=0))throw Error("invalid OHLCV")}}

function simulate(bars,signals,{start=0,end=bars.length,hold=3,cash=5000,sideCost=.0005,direction=1}={}){
 if(!Number.isInteger(hold)||hold<1||!(sideCost>=0&&sideCost<1)||!(cash>0)||![1,-1].includes(direction)||start<0||end>bars.length||end<=start)throw Error("invalid simulation settings");
 let equity=cash,peak=cash,dd=0,trades=0,wins=0,gp=0,gl=0;
 for(let i=Math.max(0,start);i+1+hold<end;i++){
  if(!signals[i])continue;let entry=i+1,exit=entry+hold;if(bars[i].session!==bars[entry].session||bars[entry].session!==bars[exit].session)continue;
  let p=bars[entry].open,q=bars[exit].open,qty=Math.floor(equity/(p*(1+sideCost)));if(qty<1)continue;
  let pnl=qty*(direction*(q-p)-sideCost*(p+q));equity+=pnl;trades++;if(pnl>0){wins++;gp+=pnl}else gl-=pnl;peak=Math.max(peak,equity);dd=Math.max(dd,1-equity/peak);i=exit-1;if(equity<=0)break;
 }
 return {trades,net:equity-cash,final:equity,winRate:trades?wins/trades:null,maxClosedTradeDrawdown:dd,profitFactor:gl?gp/gl:null,expectancy:trades?(equity-cash)/trades:null};
}

function evaluate(bars,space,{offset=0n,limit=100,hold=3,sideCost=.0005,direction=1,cash=5000}={}){
 validate(bars);let n=bars.length,train=Math.floor(n*.6),dev=Math.floor(n*.8);
 if(!Number.isInteger(limit)||limit<1||limit>10000||train<2||offset<0n)throw Error("invalid bounded batch");
 // Only the first 80% are used. Do not calculate features on the holdout.
 const visible=bars.slice(0,dev),cache=new Map(),out=[];
 for(let id=offset;id<space.total&&id<offset+BigInt(limit);id++){
  const rules=space.at(id);
  if(rules.some(r=>["VWAP","RVOL"].includes(r.family))&&visible.some(b=>b.volume===null)){out.push({id:String(id),rules,status:"unsupported_missing_volume"});continue}
  const arrays=rules.map(r=>{let key=JSON.stringify(r);if(!cache.has(key)){if(cache.size>=512)cache.delete(cache.keys().next().value);cache.set(key,testRule(visible,r))}return cache.get(key)});
  let signal=visible.map((_,i)=>arrays.every(x=>x[i]));
  const cfg={hold,sideCost,direction,cash};
  out.push({id:String(id),rules,train:simulate(visible,signal,{...cfg,end:train}),validation:simulate(visible,signal,{...cfg,start:train,end:dev})});
 }
 return {total:String(space.total),next:String(offset+BigInt(out.length)),trainBars:train,validationBars:dev-train,reservedBars:n-dev,results:out};
}

function smoke(){
 const check=(x,msg)=>{if(!x)throw Error(msg)};
 const f=[{name:"a",rules:["a1","a2"]},{name:"b",rules:["b1","b2","b3"]},{name:"c",rules:["c1"]}];const s=makeSpace(f,1,3);check(s.total===23n,"weighted combination count");check(new Set(Array.from({length:Number(s.total)},(_,i)=>JSON.stringify(s.at(i)))).size===23,"unique candidate IDs");check(makeSpace(f,2,2).total===11n,"depth count");
 const bars=Array.from({length:120},(_,i)=>{let x=100+Math.sin(i*.7)*3+i*.02;return {timestamp:new Date(Date.UTC(2026,0,1,0,i)).toISOString(),session:"S",open:x,high:x+1,low:x-1,close:x+.1,volume:100+i}});
 validate(bars);const space=makeSpace(registry(),1,3);const all=registry().flatMap(f=>f.rules);for(const fam of registry()){let r=fam.rules[0];check(JSON.stringify(testRule(bars,r).slice(0,90))===JSON.stringify(testRule(bars.slice(0,90),r)),fam.name+" causal prefix")}
 const sig=bars.map((_,i)=>i===4);let sim=simulate(bars,sig,{hold:2,sideCost:0});let expected=Math.floor(5000/bars[5].open)*(bars[7].open-bars[5].open);check(sim.trades===1&&Math.abs(sim.net-expected)<1e-9,"next-open fill");check(simulate(bars,sig,{hold:2,sideCost:.001}).net<sim.net,"cost penalty");
 const b2=bars.map((b,i)=>({...b,session:i<7?"A":"B"}));check(simulate(b2,sig,{hold:2}).trades===0,"session boundary");
 let result=evaluate(bars,space,{limit:3});check(result.results.length===3&&result.next==="3"&&result.reservedBars===24,"bounded batch");let altered=bars.map((b,i)=>i<96?b:{...b,open:b.open*2,high:b.high*2,low:b.low*2,close:b.close*2});check(JSON.stringify(evaluate(altered,space,{limit:3}))===JSON.stringify(result),"holdout invariance");
 return {status:"PASS",families:registry().map(f=>[f.name,f.rules.length]),variants:all.length,depth1to3:String(space.total),depth1to10:String(makeSpace(registry()).total),checks:"weighted counts, unique IDs, 10 causal prefix checks, fills, costs, session boundary, batch and holdout isolation"};
}

if(require.main===module){
 const fs=require("node:fs");
 const [cmd,...args]=process.argv.slice(2);
 if(cmd==="selftest")console.log(JSON.stringify(smoke(),null,2));
 else if(cmd==="plan"){const s=makeSpace(registry(),1,Number(args[0]||3));console.log(JSON.stringify({total:String(s.total),families:registry().map(f=>[f.name,f.rules.length]),sample:s.at(BigInt(args[1]||0))},null,2))}
 else if(cmd==="run"){const [file,depth="3",offset="0",limit="100",hold="3",cost="0.0005",direction="1"]=args;const bars=JSON.parse(fs.readFileSync(file,"utf8"));const s=makeSpace(registry(),1,Number(depth));console.log(JSON.stringify(evaluate(bars,s,{offset:BigInt(offset),limit:Number(limit),hold:Number(hold),sideCost:Number(cost),direction:Number(direction)})))}
 else throw Error("use selftest | plan [depth] [id] | run bars.json [depth] [offset] [limit] [hold] [sideCost] [direction]");
}
module.exports={registry,makeSpace,testRule,validate,simulate,evaluate,smoke};
