"""AI drop judge: is a sudden drop in a held stock normal, or a real company problem?

Used by both live monitors (TSX: vmm_bot/live_watch.py, India: india_vmm/vmm_watch.py).

1. detect(): a drop counts as "sudden" only when the stock falls far more than the market,
   measured against that stock's own history (no fixed %): today's move minus the market's move,
   divided by the 60-day standard deviation of that same daily difference. Trigger at <= -3 sigma.
   Market-wide falls do not trigger (the bots' market filter and loss halt cover those).
2. gather_facts(): technicals (200d/50d, 12m return, volume), fundamentals (yfinance), news headlines.
3. debate(): Claude and Gemini argue it out, each with live web search.
   Round 1: one AI argues SELL, the other KEEP; both rebut; then each gives its OWN honest verdict.
   Agree -> done. Disagree -> Round 2 with roles swapped (full transcript passed on).
   Still split -> Round 3: each sees the other's final reasons and must hold or change.
   Still split, or any AI error -> KEEP (the bot's own tested rules stay in charge).
   SELL needs BOTH AIs to say SELL with a company-specific cause.
Never raises: failures return a KEEP decision with the error noted.
"""
from __future__ import annotations

import json
import math
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

SIGMA = float(os.environ.get("AI_JUDGE_SIGMA", "3"))
CLAUDE_MODEL = os.environ.get("AI_JUDGE_CLAUDE_MODEL", "claude-opus-5-5")
GEMINI_MODEL = os.environ.get("AI_JUDGE_GEMINI_MODEL", "gemini-3.1-pro-preview")
BLOCK_DAYS = int(os.environ.get("AI_JUDGE_BLOCK_DAYS", "30"))

RULE = ("SELL only if the drop comes from company-specific bad news that damages the business outlook "
        "(CEO/CFO exit, fraud or accounting issue, regulator action, guidance cut, big earnings miss, "
        "dilutive share sale, lost key customer, delisting risk). KEEP if it is market or sector noise, "
        "a normal pullback, profit taking, or no clear company reason. The bot already sells on its own "
        "trend rules (close below 200-day line), so only an early SELL for a real problem is in question.")


# ---------------------------------------------------------------- detection
def drop_score(stock_closes, market_closes, stock_now, market_now):
    """Return (z, excess_today, sigma). Pure function (unit-tested).
    stock_closes / market_closes: lists of past daily closes (oldest first, NOT including today)."""
    n = min(len(stock_closes), len(market_closes))
    s, m = stock_closes[-n:], market_closes[-n:]
    diffs = [(s[i] / s[i - 1] - 1) - (m[i] / m[i - 1] - 1) for i in range(1, n) if s[i - 1] > 0 and m[i - 1] > 0]
    diffs = diffs[-60:]
    if len(diffs) < 20:
        return None, None, None
    mu = sum(diffs) / len(diffs)
    sd = math.sqrt(sum((d - mu) ** 2 for d in diffs) / (len(diffs) - 1))
    sd = max(sd, 0.005)
    excess = (stock_now / s[-1] - 1) - (market_now / m[-1] - 1)
    return excess / sd, excess, sd


def _closes(ticker, period="6mo"):
    import yfinance as yf
    d = yf.download(ticker, period=period, interval="1d", auto_adjust=False, progress=False,
                    threads=False, multi_level_index=False)
    return d


def _last_price(ticker):
    import yfinance as yf
    i = yf.download(ticker, period="1d", interval="1m", auto_adjust=False, progress=False,
                    threads=False, multi_level_index=False)["Close"].dropna()
    return float(i.iloc[-1])


def detect(ticker, stock_now, market_ticker, today):
    """{'trigger': bool, 'z':..., ...}. Uses daily closes before `today` (a date)."""
    try:
        sd = _closes(ticker)["Close"].dropna()
        md = _closes(market_ticker)["Close"].dropna()
        sd = sd[sd.index.date < today]
        md = md[md.index.date < today]
        m_now = _last_price(market_ticker)
        z, ex, sig = drop_score([float(x) for x in sd], [float(x) for x in md], float(stock_now), m_now)
        if z is None:
            return {"trigger": False, "why": "not enough history"}
        return {"trigger": z <= -SIGMA, "z": round(z, 2), "excess_pct": round(ex * 100, 2),
                "sigma_pct": round(sig * 100, 2), "stock_chg_pct": round((stock_now / float(sd.iloc[-1]) - 1) * 100, 2),
                "market_chg_pct": round((m_now / float(md.iloc[-1]) - 1) * 100, 2)}
    except Exception as e:
        return {"trigger": False, "why": f"detect failed: {e}"}


# ---------------------------------------------------------------- facts
def gather_facts(ticker, stock_now, det, company=None):
    f = {"ticker": ticker, "price_now": stock_now, "drop": det}
    try:
        d = _closes(ticker, "2y")
        c = d["Close"].dropna()
        f["technical"] = {
            "sma200": round(float(c.iloc[-200:].mean()), 2) if len(c) >= 200 else None,
            "sma50": round(float(c.iloc[-50:].mean()), 2),
            "ret_12m_pct": round((stock_now / float(c.iloc[-253]) - 1) * 100, 1) if len(c) > 253 else None,
            "high_52w": round(float(c.iloc[-253:].max()), 2),
            "vol_today_vs_20d": round(float(d["Volume"].iloc[-1]) / max(1.0, float(d["Volume"].iloc[-21:-1].mean())), 2),
        }
    except Exception as e:
        f["technical"] = f"unavailable: {e}"
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info or {}
        keys = ["longName", "sector", "industry", "marketCap", "trailingPE", "forwardPE", "revenueGrowth",
                "earningsGrowth", "profitMargins", "debtToEquity", "returnOnEquity", "recommendationKey"]
        f["fundamental"] = {k: info.get(k) for k in keys if info.get(k) is not None}
        company = company or info.get("longName")
    except Exception as e:
        f["fundamental"] = f"unavailable: {e}"
    try:
        import news_check
        items, src = news_check.fetch_news(ticker, company, days=7)
        heads = []
        for it in items[:12]:
            t, when = news_check._parse(it)
            if t:
                heads.append(f"{when.date().isoformat() if when else '?'}: {t}")
        f["headlines"] = heads
        f["headline_flags"] = [h["title"] for h in news_check.headline_risk(ticker, days=7, news=items, company=company).get("hits", [])]
    except Exception as e:
        f["headlines"] = f"unavailable: {e}"
    return f


# ---------------------------------------------------------------- the two AIs
def _post(url, body, headers, timeout=240):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"content-type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def ask_claude(system, prompt):
    key = os.environ["ANTHROPIC_API_KEY"]
    r = _post("https://api.anthropic.com/v1/messages", {
        "model": CLAUDE_MODEL, "max_tokens": 3000, "system": system,
        "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}],
        "messages": [{"role": "user", "content": prompt}]},
        {"x-api-key": key, "anthropic-version": "2023-06-01"})
    return "\n".join(b.get("text", "") for b in r.get("content", []) if b.get("type") == "text").strip()


def ask_gemini(system, prompt):
    key = os.environ["GEMINI_API_KEY"]
    r = _post(f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={key}", {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "tools": [{"google_search": {}}]}, {})
    parts = r["candidates"][0]["content"]["parts"]
    return "\n".join(p.get("text", "") for p in parts).strip()


AIS = {"claude": ask_claude, "gemini": ask_gemini}


def parse_verdict(text):
    """Last {...} JSON object in the text -> normalized verdict, or None."""
    for m in reversed(list(re.finditer(r"\{[^{}]*\}", text or "", re.S))):
        try:
            v = json.loads(m.group(0))
        except Exception:
            continue
        verdict = str(v.get("verdict", "")).upper()
        if verdict in ("SELL", "KEEP"):
            return {"verdict": verdict, "cause": str(v.get("cause", "unknown")).lower(),
                    "confidence": v.get("confidence"), "reason": str(v.get("reason", ""))[:600]}
    return None


SYSTEM = ("You are one of two independent analysts deciding about a stock held by an automated momentum bot "
          "that just dropped far more than the market. Search the web for today's news about the company. "
          "Be rigorous, cite concrete facts (dates, sources), and do not simply agree with the other analyst. "
          + RULE)

VERDICT_ASK = ('Now drop any assigned role. Give YOUR honest decision. End with one JSON line: '
               '{"verdict": "SELL" or "KEEP", "cause": "company" | "sector" | "market" | "none", '
               '"confidence": 0-100, "reason": "one or two sentences"}')


def _round(facts, sell_ai, keep_ai, history, ask):
    brief = "FACTS:\n" + json.dumps(facts, default=str, indent=1)
    prior = ("\n\nEARLIER DEBATE (roles were the other way round):\n" + history) if history else ""
    log = []
    open_sell = ask[sell_ai](SYSTEM, f"{brief}{prior}\n\nYour role this round: argue the strongest honest case to SELL now.")
    open_keep = ask[keep_ai](SYSTEM, f"{brief}{prior}\n\nYour role this round: argue the strongest honest case to KEEP.")
    log += [(sell_ai, "SELL case", open_sell), (keep_ai, "KEEP case", open_keep)]
    reb_sell = ask[sell_ai](SYSTEM, f"{brief}\n\nYour SELL case:\n{open_sell}\n\nOpponent's KEEP case:\n{open_keep}\n\n"
                                    "Rebut the opponent point by point. Concede anything they got right.")
    reb_keep = ask[keep_ai](SYSTEM, f"{brief}\n\nYour KEEP case:\n{open_keep}\n\nOpponent's SELL case:\n{open_sell}\n\n"
                                    "Rebut the opponent point by point. Concede anything they got right.")
    log += [(sell_ai, "rebuttal", reb_sell), (keep_ai, "rebuttal", reb_keep)]
    debate_txt = "\n\n".join(f"[{a} - {k}]\n{t}" for a, k, t in log)
    verdicts = {}
    for ai in (sell_ai, keep_ai):
        txt = ask[ai](SYSTEM, f"{brief}{prior}\n\nDEBATE THIS ROUND:\n{debate_txt}\n\n{VERDICT_ASK}")
        verdicts[ai] = parse_verdict(txt)
        log.append((ai, "verdict", txt))
    return verdicts, log


def _agreed(v):
    a, b = v.get("claude"), v.get("gemini")
    if not a or not b or a["verdict"] != b["verdict"]:
        return None
    if a["verdict"] == "SELL" and not (a["cause"] == "company" and b["cause"] == "company"):
        return "KEEP"   # both said SELL but not for a company-specific reason -> not our job, bot rules handle it
    return a["verdict"]


def debate(facts, ask=None):
    """Returns {'decision': 'SELL'|'KEEP', 'consensus': bool, 'rounds': [...], 'summary': str}."""
    ask = ask or AIS
    out = {"rounds": [], "consensus": False, "decision": "KEEP"}
    try:
        history = ""
        for i, (s_ai, k_ai) in enumerate((("claude", "gemini"), ("gemini", "claude"))):
            v, log = _round(facts, s_ai, k_ai, history, ask)
            out["rounds"].append({"sell_side": s_ai, "keep_side": k_ai, "verdicts": v,
                                  "log": [{"ai": a, "step": k, "text": t} for a, k, t in log]})
            history += "\n\n".join(f"[{a} - {k}]\n{t}" for a, k, t in log)[-20000:]
            d = _agreed(v)
            if d:
                out.update(decision=d, consensus=True)
                break
        else:
            # round 3: each sees the other's final verdict and reasons, must hold or change
            last = out["rounds"][-1]["verdicts"]
            v3 = {}
            for ai, other in (("claude", "gemini"), ("gemini", "claude")):
                mine, theirs = last.get(ai), last.get(other)
                txt = ask[ai](SYSTEM, "FACTS:\n" + json.dumps(facts, default=str, indent=1) +
                              f"\n\nAfter two rounds you still disagree.\nYour verdict: {json.dumps(mine)}\n"
                              f"Other analyst's verdict: {json.dumps(theirs)}\n\nDEBATE SO FAR:\n{history[-15000:]}\n\n"
                              "Weigh their strongest point honestly. Hold your view only if the facts support it. "
                              + VERDICT_ASK)
                v3[ai] = parse_verdict(txt)
                out.setdefault("final_log", []).append({"ai": ai, "text": txt})
            out["final_verdicts"] = v3
            d = _agreed(v3)
            if d:
                out.update(decision=d, consensus=True)
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"[:300]
        out.update(decision="KEEP", consensus=False)
    fv = out.get("final_verdicts") or (out["rounds"][-1]["verdicts"] if out["rounds"] else {})
    reasons = "; ".join(f"{a}: {v['verdict']} ({v['cause']}) {v['reason'][:160]}" for a, v in fv.items() if v)
    out["summary"] = (f"{out['decision']} - " + ("both AIs agreed" if out["consensus"] else
                      "no agreement or AI error, so KEEP (bot's own rules stay in charge)")
                      + (f". {reasons}" if reasons else "") + (f" Error: {out['error']}" if out.get("error") else ""))
    return out


# ---------------------------------------------------------------- state helpers
def load(path, default):
    try:
        return json.load(open(path))
    except Exception:
        return default


def save(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(obj, open(path, "w"), indent=1, default=str)


def blocked(block_path, today_iso):
    """Tickers the AI sold recently: the bot must not buy them back (expires after BLOCK_DAYS)."""
    b = load(block_path, {})
    out = set()
    for t, until in b.items():
        if str(until) >= today_iso:
            out.add(t)
    return out


def add_block(block_path, ticker, today):
    from datetime import timedelta
    b = load(block_path, {})
    b[ticker] = (today + timedelta(days=BLOCK_DAYS)).isoformat()
    save(block_path, b)


def check_holding(ticker, stock_now, market_ticker, today, seen, results_dir, company=None, ask=None, detector=None):
    """Full pipeline for one holding. Returns None (no sudden drop / already judged today) or the debate result.
    `seen` is a dict persisted by the caller: one judgement per ticker per day."""
    key = f"{ticker}:ai"
    if seen.get(key) == today.isoformat():
        return None
    det = (detector or detect)(ticker, stock_now, market_ticker, today)
    print(f"ai_judge {ticker}: {det}")
    if not det.get("trigger"):
        return None
    seen[key] = today.isoformat()
    if not (os.environ.get("ANTHROPIC_API_KEY") and os.environ.get("GEMINI_API_KEY")) and ask is None:
        return {"decision": "KEEP", "consensus": False, "detect": det,
                "summary": "KEEP - AI check skipped: ANTHROPIC_API_KEY or GEMINI_API_KEY missing"}
    facts = gather_facts(ticker, stock_now, det, company) if ask is None else {"ticker": ticker, "drop": det}
    res = debate(facts, ask)
    res["detect"] = det
    res["time"] = datetime.now(timezone.utc).isoformat()
    save(os.path.join(results_dir, "ai_judge", f"{today.isoformat()}_{ticker}.json"), res)
    return res
