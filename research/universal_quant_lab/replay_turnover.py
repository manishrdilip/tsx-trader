import json
from pathlib import Path
import numpy as np
from campaign_evidence import rules_for
from profit_campaign import load
from profit_features import space
from profit_engine import simulate
r=Path(r"D:\UniversalQuantLab")
manifest=json.loads((r/"results/development-turnover-3m/manifest.json").read_bytes())
leaders=json.loads(Path("PROVISIONAL_LEADERS.json").read_bytes())["leaders"]
report=[]
for job in manifest["jobs"]:
    row=next(x for x in leaders if x["symbol"]==job["symbol"])
    hashes,prices,rules,splits,actions=load(r,job,manifest["dates"])
    assert hashes==job["development_hashes"]
    holding,family,variants=rules_for(row["strategy_id"],space(job["depth"])[0])
    a,b=splits[1:]
    params=(a,b,holding,5000.,.003,2.,*actions)
    args=(prices,rules,family,np.array(variants),*params)
    compiled=simulate(*args)
    replay=simulate.py_func(*args)
    np.testing.assert_allclose(compiled,replay)
    passive=simulate(prices,np.ones((1,1,len(prices)),dtype=bool),np.array([0]),np.array([0]),a,b,b-a-2,5000.,.003,2.,*actions)
    report.append(dict(symbol=job["symbol"],currency=job["currency"],strategy_id=row["strategy_id"],hold=int(holding),net=round(replay[0],2),drawdown_pct=round(replay[1]*100,2),passive_net=round(passive[0],2),vmm=None))
Path("TURNOVER_LEADER_REPLAY.json").write_text(json.dumps(report,indent=2))
print(report)
