"use strict";
const fs=require("node:fs"),path=require("node:path"),crypto=require("node:crypto");
const engine=require("./engine.cjs");
function batchPlan(total,budget,batch,index){
 total=BigInt(total);budget=BigInt(budget);batch=BigInt(batch);index=BigInt(index);
 if(total<1n||budget<1n||budget>total||batch<1n||batch>10000n||index<0n)throw Error("invalid search budget");
 const count=(budget+batch-1n)/batch;if(index>=count)return null;
 const remainder=total%count,left=total/count*index+(index<remainder?index:remainder),width=total/count+(index<remainder?1n:0n);
 const size=budget/count+(index<budget%count?1n:0n);
 if(size>width)throw Error("budget exceeds stratum");
 return {offset:String(left+(width-size)/2n),limit:Number(size)};
}
function testPlan(){
 for(let total=1;total<=60;total++)for(let budget=1;budget<=total;budget++)for(const batch of [1,3,8,100]){
  let prev=0n,sum=0;for(let i=0;;i++){const x=batchPlan(total,budget,batch,i);if(!x)break;let o=BigInt(x.offset);if(o<prev||o+BigInt(x.limit)>BigInt(total)||x.limit>batch)throw Error("invalid overlapping batch");prev=o+BigInt(x.limit);sum+=x.limit}
  if(sum!==budget)throw Error("budget mismatch");
 }
 const a=batchPlan(10n**40n,1000000,1000,999);if(BigInt(a.offset)<=Number.MAX_SAFE_INTEGER)throw Error("BigInt regression");
 return "PASS: exhaustive small-space budgets, disjoint ranges, bounds, batch sizes, BigInt offsets";
}
function sha(bytes){return crypto.createHash("sha256").update(bytes).digest("hex")}
function writeNew(file,obj){
 const tmp=file+".tmp-"+process.pid;fs.writeFileSync(tmp,JSON.stringify(obj)+"\n",{flag:"wx"});
 fs.renameSync(tmp,file);
}
function run(configPath,out,maxMinutes){
 if(!Number.isFinite(maxMinutes)||maxMinutes<=0)throw Error("positive runtime budget required");
 const configBytes=fs.readFileSync(configPath),cfg=JSON.parse(configBytes);
 if(!Array.isArray(cfg.jobs)||!cfg.jobs.length)throw Error("jobs required");
 fs.mkdirSync(out,{recursive:true});
 const lock=path.join(out,"RUNNING.lock");const fd=fs.openSync(lock,"wx");
 try{
  fs.writeFileSync(fd,String(process.pid));const deadline=Date.now()+maxMinutes*60000;
  const codeHash=sha(Buffer.concat([fs.readFileSync(__filename),fs.readFileSync(require.resolve("./engine.cjs"))]));
  const ids=new Set();
  const jobs=cfg.jobs.map(j=>{
   if(!/^[a-zA-Z0-9_-]+$/.test(j.id||"")||ids.has(j.id))throw Error("invalid or duplicate job ID");ids.add(j.id);
   if(!j.symbol||!j.market||!j.interval||!j.currency||!j.source)throw Error("missing instrument provenance");
   if(!Number.isInteger(j.depth)||j.depth<1||j.depth>engine.registry().length)throw Error("exact depth required");
   if(!Number.isInteger(j.hold)||j.hold<1||!Number.isFinite(j.sideCost)||j.sideCost<0||j.sideCost>=1||!Number.isFinite(j.cash)||j.cash<=0)throw Error("explicit execution assumptions required");
   if(j.direction!==1)throw Error("campaign v0.1 supports long-only cash-unit screening");
   const file=path.resolve(path.dirname(configPath),j.file),space=engine.makeSpace(engine.registry(),j.depth,j.depth);
   const budget=BigInt(j.budget),batch=BigInt(j.batch);
   batchPlan(space.total,budget,batch,0);
   return {...j,file,hash:sha(fs.readFileSync(file)),total:String(space.total),batches:String((budget+batch-1n)/batch)};
  });
  const manifest={version:1,configHash:sha(configBytes),codeHash,jobs};
  const mf=path.join(out,"manifest.json");
  if(fs.existsSync(mf)){if(JSON.stringify(JSON.parse(fs.readFileSync(mf)))!==JSON.stringify(manifest))throw Error("manifest mismatch; use a new output directory")}else writeNew(mf,manifest);
  let processed=0,screened=0,unsupported=0,done=0;
  for(const j of jobs){
   const dir=path.join(out,j.id);fs.mkdirSync(dir,{recursive:true});const bytes=fs.readFileSync(j.file);if(sha(bytes)!==j.hash)throw Error("input changed");
   const bars=JSON.parse(bytes),space=engine.makeSpace(engine.registry(),j.depth,j.depth);
   for(let k=0n;k<BigInt(j.batches);k++){
    const p=batchPlan(space.total,j.budget,j.batch,k),file=path.join(dir,"batch-"+k+".json");
    if(fs.existsSync(file)){const old=JSON.parse(fs.readFileSync(file));if(old.offset!==p.offset||old.limit!==p.limit||old.results.length!==p.limit)throw Error("bad checkpoint "+file);continue}
    if(Date.now()>=deadline){console.log(JSON.stringify({status:"paused",processed,screened,unsupported,done}));return}
    const started=Date.now(),r=engine.evaluate(bars,space,{offset:BigInt(p.offset),limit:p.limit,hold:j.hold,cash:j.cash,sideCost:j.sideCost,direction:j.direction});
    if(r.results.length!==p.limit)throw Error("incomplete batch");
    writeNew(file,{...p,elapsedMs:Date.now()-started,...r});
    processed+=r.results.length;unsupported+=r.results.filter(x=>x.status).length;screened+=r.results.filter(x=>!x.status).length;
    console.log(JSON.stringify({job:j.id,batch:String(k),processed,screened,unsupported,elapsedMs:Date.now()-started}));
   }
   done++;
  }
  console.log(JSON.stringify({status:"complete",processed,screened,unsupported,done}));
 }finally{fs.closeSync(fd);fs.unlinkSync(lock)}
}
if(require.main===module){
 const [cmd,...args]=process.argv.slice(2);
 if(cmd==="selftest")console.log(testPlan());
 else if(cmd==="run"&&args.length===3)run(args[0],args[1],Number(args[2]));
 else throw Error("selftest | run config.json output-directory max-minutes");
}
module.exports={batchPlan,testPlan};
