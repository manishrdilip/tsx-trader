"""V2 final report from the completed, prospective paper ledger."""
from datetime import date, datetime, timezone
import math
import os
from uuid import uuid4

import exchange_calendars as xc

from forward_v2 import hash_file, preregister
from run_universe import read


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(f".{uuid4().hex}.tmp")
    try:
        with temp.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)
    return hash_file(path)


def timestamp(value):
    parsed = datetime.fromisoformat(value)
    if parsed.utcoffset() is None:
        raise ValueError("Forward timestamps must include a timezone")
    return parsed.astimezone(timezone.utc)


def evaluate(result, shortlist, minimum_sessions):
    frozen = timestamp(shortlist["frozen_utc"])
    if result["state"] != "complete" or result["mode"] != "prospective-paper":
        raise RuntimeError("Prospective paper validation is incomplete")
    registered = {row["id"]: row for row in shortlist["candidates"]}
    if not 1 <= len(registered) == len(shortlist["candidates"]) <= 100:
        raise ValueError("Invalid frozen shortlist")
    seen = set()
    rows = []
    for candidate in result["candidates"]:
        identifier = candidate["id"]
        if identifier in seen or identifier not in registered:
            raise ValueError("Forward results include an unregistered or duplicate candidate")
        seen.add(identifier)
        initial = float(candidate["starting_equity"])
        if not math.isfinite(initial) or initial <= 0:
            raise ValueError("Invalid starting paper equity")
        history = candidate["sessions"]
        expected_sessions = candidate["expected_sessions"]
        if len(history) < minimum_sessions or [item["session"] for item in history] != expected_sessions:
            raise RuntimeError("Forward trading sessions are incomplete")
        if sorted(set(expected_sessions)) != expected_sessions:
            raise ValueError("Duplicate or unordered forward sessions")
        end = date.fromisoformat(expected_sessions[-1])
        calendar = xc.get_calendar(registered[identifier]["market_calendar"],
                                   start=frozen.date(), end=end)
        scheduled = [session for session in calendar.sessions if calendar.session_open(session) > frozen]
        if [session.date().isoformat() for session in scheduled] != expected_sessions:
            raise ValueError("Forward dates do not cover consecutive eligible trading sessions")
        peak, drawdown = initial, 0.0
        equity = benchmark = initial
        for item, session in zip(history, scheduled, strict=True):
            opened = timestamp(item["market_open_utc"])
            closed = timestamp(item["market_close_utc"])
            observed = timestamp(item["logged_utc"])
            if (not frozen < opened < closed <= observed or opened != calendar.session_open(session)
                    or closed != calendar.session_close(session)):
                raise ValueError("Paper record uses a session from at or before the freeze")
            if observed > datetime.now(timezone.utc):
                raise ValueError("Paper observation is dated in the future")
            equity, benchmark = [float(item[k]) for k in ("net_paper_equity", "net_buy_and_hold_equity")]
            if not all(math.isfinite(value) and value >= 0 for value in (equity, benchmark)):
                raise ValueError("Invalid net equity in forward ledger")
            peak = max(peak, equity)
            drawdown = max(drawdown, 1 - equity / peak)
        net, base = equity / initial - 1, benchmark / initial - 1
        rows.append({**registered[identifier], "forward_net_return": net,
                     "benchmark_net_return": base, "benchmark_delta": net - base,
                     "max_drawdown": drawdown, "trading_sessions": len(history),
                     "pass": net > 0 and net > base})
    if seen != set(registered):
        raise RuntimeError("Forward results are missing frozen candidates")
    return rows


def run(root, previous_hash, publish):
    phase5_path = root / "phase5_done.json"
    if hash_file(phase5_path) != previous_hash:
        raise RuntimeError("The Phase 5 completion marker changed")
    phase5 = read(phase5_path)
    phase4 = read(root / "phase4_done.json")
    _, plan = preregister(root)
    results = root / "results/capped-sequence/forward_validation.json"
    shortlist_path = root / "results/capped-sequence/shortlist.json"
    if (hash_file(results) != phase5["counts"]["forward_validation_sha256"]
            or hash_file(shortlist_path) != phase4["counts"]["shortlist_sha256"]):
        raise RuntimeError("Forward evidence hashes differ from the phase markers")
    result, shortlist = read(results), read(shortlist_path)
    tests = phase4["counts"]["candidates_tested"]
    if tests != shortlist["candidates_tested"] or tests < plan["discovery"]["target_unique_successful"]:
        raise RuntimeError("Discovery trial total does not reconcile")
    rows = evaluate(result, shortlist, plan["forward"]["minimum_trading_sessions"])
    survivors = sorted((row for row in rows if row["pass"]),
                       key=lambda row: (-row["forward_net_return"], row["max_drawdown"], row["id"]))
    counts = {"candidates_tested": tests, "forward_tested": len(rows), "survivors": len(survivors)}
    publish(counts)
    output = ["# Universal Quant Lab forward survivors", "",
              f"Historical candidates tested: {tests:,}",
              f"Candidates tested prospectively: {len(rows):,}", f"Survivors: {len(survivors):,}", ""]
    if not survivors:
        output.append("**ZERO PASSED.**")
    else:
        output.extend(["| Rule | Timeframe | Paper net return | Buy-and-hold net return | Excess return | Drawdown | Trading sessions |",
                       "|---|---|---:|---:|---:|---:|---:|"])
        for row in survivors:
            rule = row["rule"].replace("|", "&#124;").replace("\n", " ")
            output.append(f"| {rule} | {row['timeframe']} | {row['forward_net_return']:.2%} | "
                          f"{row['benchmark_net_return']:.2%} | {row['benchmark_delta']:+.2%} | "
                          f"{row['max_drawdown']:.2%} | {row['trading_sessions']} |")
    summary = ["# Universal Quant Lab V2 summary", "",
               f"Shortlist frozen at {shortlist['frozen_utc']}.",
               f"Forward validation SHA-256 {hash_file(results)}.", "",
               "| Phase | Finished UTC |", "|---|---|"]
    for number, filename in enumerate(("phase1_done.json", "phase2_done.json", "phase3_sealed.json",
                                       "phase4_done.json", "phase5_done.json"), 1):
        summary.append(f"| {number} | {read(root / filename)['finished']} |")
    counts["run_summary_sha256"] = write(root / "reports/RUN_SUMMARY.md", "\n".join(summary) + "\n")
    counts["survivors_sha256"] = write(root / "reports/SURVIVORS.md", "\n".join(output) + "\n")
    return counts
