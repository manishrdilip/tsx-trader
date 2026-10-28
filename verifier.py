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
"""
from __future__ import annotations

import json
import os
import re

import anthropic

from risk_levels import MAX_STOP_PCT, STOP_ATR, TARGET_ATR

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


def verify_trade(trade: dict, portfolio: str = "tsx") -> dict:
    plan = PLANS.get(portfolio, PLANS["tsx"])
    prompt = f"""You are the risk manager for a small personal swing-trading account.
Check this order strictly against the plan. Reply with JSON only, matching the schema.

PLAN ({portfolio.upper()}):
{json.dumps(plan, indent=2)}

ORDER (stop/target here were computed by code from ATR; check they follow the exit rule):
{json.dumps(trade, indent=2, default=str)}

Checks:
1. symbol present, price > 0, qty > 0, order type is LIMIT for buys.
2. BUY: if stop/target are given, they match the exit rule within one tick (manual TSX entries
   may omit them: then just state the expected levels in suggestion); signal fields satisfy entry_signal.
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
