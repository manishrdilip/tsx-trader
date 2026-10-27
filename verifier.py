"""
Core Claude API trade verification engine.
Called by both india_monitor.py and tsx_monitor.py
"""

import json
import anthropic

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

# ── Plan rules (mirrors your memory files) ──────────────────────────────────

PLANS = {
    "india": {
        "broker": "Zerodha/Kite (NSE/BSE)",
        "strategy": "Swing trading (weeks/months)",
        "entry_signal": "Scanner confirms bullish setup, uptrend only, bullish candlestick pattern",
        "profit_target_pct": 3.0,
        "stop_loss_pct": 1.0,
        "monthly_goal_pct": 2.5,
        "max_positions": 10,
        "currency": "INR (₹)",
        "notes": "New trades only. Legacy positions (APCL, WIPRO, TRIDENT, IBULLSLTD) being closed."
    },
    "tsx": {
        "broker": "Wealthsimple TFSA (TSX)",
        "strategy": "Leader Pullback swing trading",
        "entry_signal": "Multiple independent scans ALL agree on same stock, bullish candlestick pattern, uptrend only, enter at market open after evening scan",
        "profit_target_pct": 3.0,
        "stop_loss_pct": 1.0,
        "monthly_goal_pct": 2.0,
        "max_positions": 5,
        "currency": "CAD ($)",
        "notes": "Max $100 CAD in play initially. Only enter when all scans agree."
    }
}


def verify_trade(trade: dict, portfolio: str = "india") -> dict:
    """
    Verifies a trade against the plan. Returns structured verdict.

    trade dict keys:
        symbol       str   e.g. "SUZLON" or "MSA.TO"
        action       str   "BUY" or "SELL"
        qty          int   number of shares
        price        float execution price
        order_id     str   broker order ID
        avg_cost     float (for SELL only) original buy price
        triggered_by str   "scanner" | "manual" | "unknown"
        timestamp    str   ISO datetime

    Returns:
        verdict      str   "APPROVED" | "FLAG" | "ERROR"
        reason       str   brief plain-English explanation
        bugs         list  any code/logic bugs detected
        violations   list  plan rule violations
        suggestion   str   what to do now
        pnl_check    dict  for SELL: actual vs target/stop
    """
    plan = PLANS.get(portfolio)
    if not plan:
        return {"verdict": "ERROR", "reason": f"Unknown portfolio: {portfolio}"}

    prompt = f"""You are a strict trade verification system for a swing trader.
Your job: check if this trade follows the plan EXACTLY and flag any bugs or violations.
Be fast and precise. Respond ONLY with valid JSON, no extra text.

=== PLAN ({portfolio.upper()}) ===
Broker: {plan['broker']}
Strategy: {plan['strategy']}
Entry signal required: {plan['entry_signal']}
Profit target: +{plan['profit_target_pct']}% from entry
Stop-loss: -{plan['stop_loss_pct']}% from entry
Monthly goal: {plan['monthly_goal_pct']}%
Currency: {plan['currency']}
Notes: {plan['notes']}

=== TRADE DETAILS ===
{json.dumps(trade, indent=2)}

=== VERIFICATION TASKS ===
1. BUY trade: Was there a valid scanner signal? Is entry reasonable?
2. SELL trade: Calculate actual P&L%. Did it hit +{plan['profit_target_pct']}% target or -{plan['stop_loss_pct']}% stop? Or was it an early/late exit?
3. Any bugs: wrong symbol format, zero quantity, price = 0, missing fields?
4. Any plan violations: no signal, wrong direction, sizing issues?

Respond ONLY with this JSON:
{{
  "verdict": "APPROVED" or "FLAG" or "ERROR",
  "reason": "one sentence plain English",
  "bugs": ["list bugs found, or empty list"],
  "violations": ["list plan violations, or empty list"],
  "suggestion": "what to do right now",
  "pnl_check": {{
    "entry_price": null or number,
    "exit_price": null or number,
    "actual_pnl_pct": null or number,
    "vs_target": null or "hit target" or "below target" or "hit stop" or "exceeded stop"
  }}
}}"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = response.content[0].text.strip()
        # Strip markdown code fences if Claude wrapped the JSON
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        result = json.loads(raw)
        result["order_id"] = trade.get("order_id", "unknown")
        result["symbol"] = trade.get("symbol", "unknown")
        result["portfolio"] = portfolio
        return result
    except json.JSONDecodeError as e:
        return {
            "verdict": "ERROR",
            "reason": f"Claude returned non-JSON: {str(e)}",
            "raw_response": raw,
            "bugs": ["verifier.py: JSON parse failed"],
            "violations": [],
            "suggestion": "Check Claude API response manually",
            "pnl_check": {}
        }
    except Exception as e:
        return {
            "verdict": "ERROR",
            "reason": str(e),
            "bugs": [f"verifier.py exception: {type(e).__name__}"],
            "violations": [],
            "suggestion": "Check API key and network",
            "pnl_check": {}
        }


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
        lines.append("🐛 Bugs: " + " | ".join(result["bugs"]))
    if result.get("violations"):
        lines.append("📋 Violations: " + " | ".join(result["violations"]))
    pnl = result.get("pnl_check", {})
    if pnl.get("actual_pnl_pct") is not None:
        lines.append(f"P&L: `{pnl['actual_pnl_pct']:+.2f}%` ({pnl.get('vs_target', '')})")
    if result.get("suggestion"):
        lines.append(f"💡 {result['suggestion']}")
    return "\n".join(lines)
