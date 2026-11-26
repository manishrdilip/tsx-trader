"""Monitor the turnover campaign, resume healthy pauses, publish compact snapshots."""
import base64,json,subprocess,sys,time
from pathlib import Path
from campaign_watchdog import health,guard
root=Path(sys.argv[1])
out=root/"results/development-turnover-3m"
lab=Path(__file__).parent
endpoint="repos/manishrdilip/tsx-trader/contents/research/universal_quant_lab/PROVISIONAL_PROGRESS.json"
branch="research/universal-quant-lab"
published=None
healthy=0
while True:
    s=json.loads((out/"progress.json").read_bytes())
    key=(s["status"],s["engineering_completed"]//250000)
    if key!=published:
        body={k:s[k] for k in ("status","engineering_completed","engineering_target","official_completed","updated_utc","session_evaluations_per_second")}
        body["run"]=out.name
        bench=out/"memory-benchmark.json"
        if bench.exists(): body["last_memory_benchmark"]=json.loads(bench.read_bytes())
        try:
            sha=subprocess.check_output(["gh","api",endpoint+"?ref="+branch,"--jq",".sha"],text=True).strip()
            payload=dict(sha=sha,branch=branch,message="Report turnover campaign checkpoint",
                         content=base64.b64encode(json.dumps(body,indent=2).encode()).decode())
            subprocess.run(["gh","api","-X","PUT",endpoint,"--input","-"],input=json.dumps(payload),
                           text=True,stdout=subprocess.DEVNULL,check=True)
            published=key
        except subprocess.SubprocessError: pass
    if s["status"] in ("complete","failed") and published==key: break
    if (out/"PAUSE").exists(): break
    healthy=healthy+1 if s["status"]=="paused" and not guard(health(root)) else 0
    if healthy>=3:
        child=subprocess.Popen([sys.executable,"-B",str(lab/"turnover_low_memory.py"),str(root)])
        healthy=0
        time.sleep(5)
    time.sleep(20)
