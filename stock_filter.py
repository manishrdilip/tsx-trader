"""Keep real operating companies only.
Drops ETFs, leveraged/inverse BetaPro products, CDRs (US stocks wrapped for Canada),
split-share corporations, bullion/physical trusts and cash/money-market funds.
Names come from the TSX/TSXV company directory (universe_names.json)."""
import json
import os
import re

_PAT = re.compile(r"\bETF\b|BetaPro|\bCDR\b|Split Corp|Bullion|Physical|Banc Corp|Money Market|"
                  r"Cash Management|Cash Maximizer|YIELD MAXIMIZER|Covered Call|Index Fund", re.I)
_NAMES = None


def names(path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "universe_names.json")):
    global _NAMES
    if _NAMES is None:
        _NAMES = json.load(open(path)) if os.path.exists(path) else {}
    return _NAMES


def is_stock(ticker):
    n = names().get(ticker)
    if n is None:
        return True          # unknown -> keep (name list may lag new listings)
    return not _PAT.search(f"{n.get('name') or ''} | {n.get('company') or ''}")


def company(ticker):
    n = names().get(ticker) or {}
    return n.get("company") or n.get("name") or ""
