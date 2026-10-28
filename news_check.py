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

Source: Google News RSS first (no key needed; Yahoo's news feed returned zero items
for every symbol in Oct 2026), Yahoo as backup. Google searches by company name
(universe_names.json for TSX, the Kite instrument name for India when the caller
passes it) and keeps only headlines that mention the company or its ticker.
"""
from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

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
    elif item.get("providerPublishTime"):  # old yfinance format / Google RSS: epoch seconds                   # old format: epoch seconds
        when = datetime.fromtimestamp(item["providerPublishTime"], tz=timezone.utc)
    return title.strip(), when


_NAMES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "universe_names.json")
_NAMES: dict | None = None
_SUFFIX = re.compile(
    r"[,.]?\s+(inc|incorporated|ltd|limited|corp|corporation|co|company|plc|trust|fund|"
    r"holdings?|group|class [a-z]|cl [a-z])\.?$", re.I)


def company_name(symbol: str) -> str | None:
    """'SHOP.TO' -> 'Shopify', from universe_names.json (TSX / TSXV only)."""
    global _NAMES
    if _NAMES is None:
        try:
            with open(_NAMES_FILE, encoding="utf-8") as f:
                _NAMES = json.load(f)
        except (OSError, ValueError):
            _NAMES = {}
    row = _NAMES.get(symbol) or {}
    return row.get("company") or row.get("name")


def _clean(name: str) -> str:
    name = re.sub(r"\s+", " ", name.replace("&amp;", "&")).strip()
    for _ in range(3):                                   # "Foo Holdings Inc." -> "Foo"
        name = _SUFFIX.sub("", name).strip(" ,.")
    return name


def _google_news(query: str, india: bool) -> list:
    """Google News RSS search, returned as old-format yfinance items."""
    hl, gl = ("en-IN", "IN") if india else ("en-CA", "CA")
    url = ("https://news.google.com/rss/search?q=" + urllib.parse.quote(query)
           + f"&hl={hl}&gl={gl}&ceid={gl}:en")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        root = ET.fromstring(r.read())
    items = []
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        try:
            when = int(parsedate_to_datetime(it.findtext("pubDate")).timestamp())
        except (TypeError, ValueError):
            when = None
        items.append({"title": title, "providerPublishTime": when})
    return items


def fetch_news(symbol: str, company: str | None = None, days: int = 14) -> tuple[list, str]:
    """Returns (items, source). Google News by company name, then Yahoo."""
    base = re.sub(r"\.(TO|V|NS|BO)$", "", symbol, flags=re.I).replace("-", ".")
    india = symbol.upper().endswith((".NS", ".BO"))
    name = _clean(company or company_name(symbol) or base)
    words = name.split()
    keys = {" ".join(words[:2]).lower()} if len(words) >= 2 else {name.lower()}
    if len(base) >= 3:
        keys.add(base.lower())
    try:
        items = _google_news(f'"{name}" {"share" if india else "stock"} when:{days}d', india)
        items = [i for i in items if any(k in i["title"].lower() for k in keys)]
        if items:
            return items, "google"
    except Exception:
        pass
    try:
        import yfinance as yf
        return yf.Ticker(symbol).news or [], "yahoo"
    except Exception:
        return [], "none"


def headline_risk(symbol: str, days: int = 14, limit: int = 10, news: list | None = None,
                  company: str | None = None) -> dict:
    """status: CLEAR | FLAG | UNKNOWN. Pass `news` to test without network."""
    source = "given"
    if news is None:
        news, source = fetch_news(symbol, company, days)
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
    return {"status": status, "reason": reason, "headlines": rows, "hits": hits, "source": source}
