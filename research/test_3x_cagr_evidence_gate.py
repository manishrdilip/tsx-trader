"""Independent 3x CAGR claim gate; research only. Synthetic contract tests, not market evidence."""
import math

def assess(baseline, candidate):
    required=("cagr","max_dd","start_capital","start","end","fees","slippage","execution","allocation","stop_gaps","cash_accounting")
    if any(k not in baseline or k not in candidate for k in required):
        return False,"missing matched assumptions"
    for key in required[2:]:
        if baseline[key]!=candidate[key]:
            return False,"unmatched "+key
    b,c=baseline["cagr"],candidate["cagr"]
    if not all(math.isfinite(x) for x in (b,c,baseline["max_dd"],candidate["max_dd"])):
        return False,"nonfinite performance"
    if b<=0: return False,"nonpositive baseline: ratio undefined"
    if c<3*b: return False,"less than 3x baseline CAGR"
    if candidate["max_dd"]<baseline["max_dd"]: return False,"worse maximum drawdown"
    for k in ("baseline_reproduced","candidate_independent","untouched_oos","forward_paper","tail_risk_acceptable","survivorship_controlled"):
        if not candidate.get(k,False): return False,"missing evidence: "+k
    return True,"eligible for independent review, not automatic declaration"

def tests():
    b=dict(cagr=.20,max_dd=-.25,start_capital=5000,start="2016-01-01",end="2026-01-01",fees=.0025,slippage=.001,execution="next-bar",allocation="cash integer shares",stop_gaps="open-through-stop",cash_accounting="reconciled")
    c=dict(b,cagr=.61,max_dd=-.20,baseline_reproduced=True,candidate_independent=True,untouched_oos=True,forward_paper=True,tail_risk_acceptable=True,survivorship_controlled=True)
    assert assess(b,c)[0]
    for changes in (dict(cagr=.59),dict(max_dd=-.26),dict(fees=.001),dict(start_capital=10000),dict(untouched_oos=False),dict(forward_paper=False),dict(survivorship_controlled=False),dict(tail_risk_acceptable=False)):
        assert not assess(b,dict(c,**changes))[0],changes
    assert not assess(dict(b,cagr=0),c)[0]
    assert not assess(dict(b,cagr=-.20),c)[0]
    assert not assess(b,dict(c,cagr=float("nan")))[0]
    assert not assess(b,dict(c,execution="same-bar"))[0]
    print("PASS: 3x CAGR evidence gate; 13 synthetic contracts; zero market claims")
if __name__=="__main__":tests()
