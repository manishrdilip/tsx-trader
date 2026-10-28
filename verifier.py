"""
Claude risk check for every order. Corrected version of the reviewer's patch:

- KEEPS a current model. "claude-sonnet-4-6" is a valid, supported model ID.
  The reviewer's suggestions ("claude-3-5-sonnet-20241022", "claude-3-7-sonnet-20250219")
  are both RETIRED and would make every call fail. The model is read from an env var
  so you can upgrade (e.g. to "claude-sonnet-5-5") without a code change.
- Plan rules are generated from risk_levels.py, so they match the backtest
  (3x ATR stop, 6x ATR target) instead of the old +3% / -1%.
- Gives Claude the computed stop/target so it checks numbers, not vibes.
- format_alert() kept unchanged: india_monitor, tsx_monitor and auto_trader import it.
- BUYs get a headline check first (news_check.py): a red-flag headline blocks the
  trade without calling Claude; otherwise the recent headlines go into the prompt.
"""
from __future__ import annotations

import json
import os
import re

import anthropic

from news_check import headline_risk, to_yahoo
from risk_levels import MAX_STOP_PCT, STOP_ATR, TARGET_ATR, levels, wilder_atr

MODEL = os.environ.get("VERIFIER_MODEL", "claude-sonnet-4-6")
client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY

_ATR_RULES = (
    f"stop = entry - {STOP_ATR:g} x ATR14 (never more than {MAX_STOP_PCT:g}% below entry); "
    f"target = entry + {TARGET_ATR:g} x ATR14"
)

PLANS = {
    "tsx": {
        "broker": "Wealthsimple (manual orders, TSX)",
        "strategy": "Leader Pullback swing trade",
        "entry_signal": "Stage-2 uptrend, 12-month RS rank > 80, RSI(2) < 10, Stoch < 25, "
                        "sector momentum, no earnings inside the hold",
        "exits": _ATR_RULES,
        "currency": "CAD",
    },
    "india": {
        "broker": "Zerodha Kite (NSE, CNC delivery)",
        "strategy": "Stage-2 swing trade",
        "entry_signal": "Confirmed uptrend + volume expansion, limit order near LTP",
        "exits": _ATR_RULES,
        "currency": "INR",
    },
}

_SCHEMA = """{
  "verdict": "APPROVED" | "FLAG" | "ERROR",
  "reason": "one sentence",
  "bugs": [],
  "violations": [],
  "suggestion": "one concrete next step",
  "pnl_check": {"actual_pnl_pct": null, "vs_target": null}
}"""


def _extract_json(text: str) -> dict:
    """Accepts bare JSON or JSON inside a ``` fence."""
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("no JSON object in model reply")
    return json.loads(m.group(0))


def _yahoo_symbol(trade: dict, portfolio: str) -> str:
    sym = trade.get("symbol", "")
    if portfolio == "tsx":
        return to_yahoo(sym, trade.get("exchange", "TSX"))
    if sym.endswith("-BE"):                     # auto_trader routes these to BSE
        return f"{sym[:-3]}.BO"
    return f"{sym}.NS"


def _attach_levels(trade: dict, ysym: str, portfolio: str) -> None:
    """Manual / monitor BUYs arrive without stop/target: compute them from Yahoo daily
    bars with the same rule auto_trader uses, so Claude checks real numbers."""
    if trade.get("stop") and trade.get("target"):
        return
    try:
        import yfinance as yf
        bars = yf.Ticker(ysym).history(period="3mo", auto_adjust=False)
        tick = 0.05 if portfolio == "india" else 0.01
        lv = levels(float(trade["price"]), wilder_atr(bars), tick)
        trade.update(atr14=lv["atr"], stop=lv["stop"], target=lv["target"],
                     stop_capped_at_8pct=lv["capped"],
                     levels_source="computed by verifier from Yahoo daily bars")
    except Exception as e:
        trade["levels_source"] = f"could not compute ATR levels: {type(e).__name__}"


def verify_trade(trade: dict, portfolio: str = "tsx") -> dict:
    plan = PLANS.get(portfolio, PLANS["tsx"])
    side = trade.get("action") or trade.get("side") or trade.get("transaction_type") or ""
    is_buy = str(side).upper() == "BUY"

    news = None
    if is_buy:
        trade = dict(trade)                     # don't mutate the caller's dict
        ysym = _yahoo_symbol(trade, portfolio)
        _attach_levels(trade, ysym, portfolio)
        news = headline_risk(ysym, company=trade.get("company"))
        if news["status"] == "FLAG":            # hard rule: no Claude call needed to block it
            return {
                "verdict": "FLAG", "reason": news["reason"], "bugs": [],
                "violations": ["headline red flag"],
                "suggestion": "Skip this entry; re-check after the news settles",
                "news": news, "order_id": trade.get("order_id", "N/A"),
                "symbol": trade.get("symbol", "N/A"), "portfolio": portfolio, "model": None,
            }

    news_block = "" if news is None else f"""
RECENT HEADLINES (status {news['status']}: {news['reason']}):
{json.dumps(news['headlines'], indent=2)}
If status is UNKNOWN, say so in "reason" and use FLAG unless everything else is clean.
Also FLAG any headline suggesting dilution, an executive exit, an investigation or a halt,
even if worded differently from the usual phrases.
"""

    prompt = f"""You are the risk manager for a small personal swing-trading account.
Check this order strictly against the plan. Reply with JSON only, matching the schema.

PLAN ({portfolio.upper()}):
{json.dumps(plan, indent=2)}

ORDER (stop/target here were computed by code from ATR; check they follow the exit rule):
{json.dumps(trade, indent=2, default=str)}
{news_block}
Checks:
1. symbol present, price > 0, qty > 0. If order_type is given for a BUY it must be LIMIT;
   manual broker entries (no order_type field) are fine without it.
2. BUY: stop/target match the exit rule within one tick; put the stop and target in "suggestion"
   so the trader can set them. If levels_source says they could not be computed, FLAG.
   Entry signal: the scanner applies entry_signal, so triggered_by "scanner" counts as a valid
   signal; do NOT flag just because the individual indicator values are not listed.
   triggered_by "manual" or "unknown" means no scanner signal: FLAG as off-plan.
3. SELL: reason is one of target, stop, time/stagnation exit, or manual, and matches the prices.
Use FLAG for any rule break, ERROR only for malformed data.

SCHEMA:
{_SCHEMA}"""

    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in resp.content if b.type == "text")
        result = _extract_json(text)
    except Exception as e:  # never let the verifier crash the trader
        result = {
            "verdict": "ERROR",
            "reason": f"{type(e).__name__}: {e}",
            "bugs": [type(e).__name__],
            "violations": [],
            "suggestion": "Check ANTHROPIC_API_KEY and VERIFIER_MODEL",
        }
    result.update(
        order_id=trade.get("order_id", "N/A"),
        symbol=trade.get("symbol", "N/A"),
        portfolio=portfolio,
        model=MODEL,
        news=news,
    )
    return result


def format_alert(result: dict) -> str:
    """Format verification result as a Telegram message."""
    icon = {"APPROVED": "✅", "FLAG": "🚨", "ERROR": "⚠️"}.get(result["verdict"], "❓")
    lines = [
        f"{icon} *TRADE {result['verdict']}* — {result.get('portfolio', '').upper()}",
        f"Symbol: `{result.get('symbol', 'N/A')}`",
        f"Order: `{result.get('order_id', 'N/A')}`",
        f"Reason: {result.get('reason', '')}",
    ]
    if result.get("bugs"):
        lines.append("🐛 Bugs: " + " | ".join(map(str, result["bugs"])))
    if result.get("violations"):
        lines.append("📋 Violations: " + " | ".join(map(str, result["violations"])))
    pnl = result.get("pnl_check") or {}
    if pnl.get("actual_pnl_pct") is not None:
        lines.append(f"P&L: `{pnl['actual_pnl_pct']:+.2f}%` ({pnl.get('vs_target', '')})")
    if result.get("suggestion"):
        lines.append(f"💡 {result['suggestion']}")
    return "\n".join(lines)
