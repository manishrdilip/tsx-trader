"""
Headline risk check before entry: dilution, executive exits, investigations.

Fixes in the reviewer's version:
- yfinance changed its news format in 2025: the title now sits under item["content"]["title"].
  The reviewer's item.get("title") returns nothing on current versions, so every stock
  would show "No recent headlines found" and look safe. This reads both formats.
- Dates are kept and old headlines dropped (default 14 days); an undated top-3 list
  can be months old.
- The red-flag keywords are matched in Python, not left to Claude, so a hit always flags.
- "Feed unavailable" is returned as status UNKNOWN, never as all clear.
- TSX symbols need Yahoo's ".TO" (".V" for TSXV) suffix; to_yahoo() adds it.

Runs where Yahoo is reachable (your PC / GitHub Actions), not in a Claude cloud session.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

RED_FLAGS = [
    r"bought deal", r"private placement", r"(share|equity|stock) offering",
    r"public offering", r"\bdilut", r"at-the-market", r"\bATM program",
    r"(ceo|cfo|chief executive|chief financial).{0,40}(resign|depart|steps? down|terminat)",
    r"(resign|depart|steps? down).{0,40}(ceo|cfo|chief executive|chief financial)",
    r"class action", r"investigation", r"\bsubpoena", r"cease trade",
    r"going concern", r"restat(e|ement)", r"delist", r"halt(ed)? trading|trading halt",
]
_RX = re.compile("|".join(RED_FLAGS), re.I)


def to_yahoo(symbol: str, exchange: str = "TSX") -> str:
    """RY -> RY.TO, BBD.B -> BBD-B.TO (Yahoo writes share classes with a dash), ABC (TSXV) -> ABC.V."""
    if symbol.upper().endswith((".TO", ".V", ".NS")) or exchange.upper() not in ("TSX", "TSXV"):
        return symbol
    return f"{symbol.replace('.', '-')}{'.V' if exchange.upper() == 'TSXV' else '.TO'}"


def _parse(item: dict) -> tuple[str, datetime | None]:
    c = item.get("content") or {}
    title = c.get("title") or item.get("title") or ""
    when = None
    if c.get("pubDate"):                                    # new format: ISO string
        try:
            when = datetime.fromisoformat(c["pubDate"].replace("Z", "+00:00"))
        except ValueError:
            pass
    elif item.get("providerPublishTime"):                   # old format: epoch seconds
        when = datetime.fromtimestamp(item["providerPublishTime"], tz=timezone.utc)
    return title.strip(), when


def headline_risk(symbol: str, days: int = 14, limit: int = 10, news: list | None = None) -> dict:
    """status: CLEAR | FLAG | UNKNOWN. Pass `news` to test without network."""
    if news is None:
        try:
            import yfinance as yf
            news = yf.Ticker(symbol).news or []
        except Exception as e:
            return {"status": "UNKNOWN", "reason": f"news feed unavailable: {type(e).__name__}",
                    "headlines": [], "hits": []}
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = []
    for item in news[:limit]:
        title, when = _parse(item)
        if title and (when is None or when >= cutoff):
            rows.append({"title": title, "date": when.date().isoformat() if when else "undated"})
    hits = [r for r in rows if _RX.search(r["title"])]
    if hits:
        status, reason = "FLAG", f"red-flag headline: {hits[0]['title']}"
    elif rows:
        status, reason = "CLEAR", f"{len(rows)} recent headlines, no red flags"
    else:
        status, reason = "UNKNOWN", f"no headlines in the last {days} days (not proof of safety)"
    return {"status": status, "reason": reason, "headlines": rows, "hits": hits}
