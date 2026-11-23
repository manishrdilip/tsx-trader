"""Deterministic executable-stop and cash-accounting reference audit.

Long-only daily OHLC. Signal at t close, entry at t+1 open. Stops cannot
execute before entry; gap-through fills at open, otherwise at stop on low touch.
Conservative OHLC ordering assumes stop before profit target when both hit.
This is an execution unit test, NOT an empirical backtest.
"""
from dataclasses import dataclass

@dataclass
class Fill:
    entry: float
    exit: float
    exit_reason: str
    end_cash: float
    pnl: float

def simulate(open_price, high, low, close, stop_fraction, target_fraction=None,
             cash=5000.0, cost_bps=10.0):
    assert 0 < low <= min(open_price, close) <= max(open_price, close) <= high
    assert 0 < stop_fraction < 1 and (target_fraction is None or target_fraction > 0)
    assert cash > 0 and cost_bps >= 0
    fee = cost_bps / 10000
    # Buy integer shares with entry fee; never borrow against cash.
    shares = int(cash / (open_price * (1 + fee)))
    assert shares > 0
    entry_debit = shares * open_price * (1 + fee)
    remaining = cash - entry_debit
    stop = open_price * (1 - stop_fraction)
    target = None if target_fraction is None else open_price * (1 + target_fraction)
    if low <= stop:
        # A same-session stop cannot gap below its entry-derived stop at the entry open.
        exit_price, reason = stop, "stop"
    elif target is not None and high >= target:
        exit_price, reason = target, "target"
    else:
        exit_price, reason = close, "close"
    proceeds = shares * exit_price * (1 - fee)
    final_cash = remaining + proceeds
    return Fill(open_price, exit_price, reason, final_cash, final_cash - cash)

def held_position_exit(open_price, high, low, close, stop, target=None):
    """Stop already active before session open: gap losses fill at open."""
    assert 0 < low <= min(open_price, close) <= max(open_price, close) <= high
    if open_price <= stop:
        return open_price, "gap_stop"
    if low <= stop:
        return stop, "stop"
    if target is not None and open_price >= target:
        return open_price, "gap_target"
    if target is not None and high >= target:
        return target, "target"
    return close, "close"

def run():
    a = held_position_exit(80, 85, 75, 83, 90)
    assert a == (80, "gap_stop"), a
    b = held_position_exit(100, 112, 88, 110, 95, 108)
    assert b == (95, "stop"), b  # adverse-first intrabar ambiguity
    c = held_position_exit(120, 125, 118, 121, 95, 110)
    assert c == (120, "gap_target"), c
    d = simulate(100, 110, 89, 108, .05, .08)
    assert d.exit_reason == "stop" and d.exit == 95
    e = simulate(100, 110, 96, 108, .05, .08)
    assert e.exit_reason == "target" and e.exit == 108
    f = simulate(100, 104, 96, 102, .05)
    assert f.exit_reason == "close" and f.exit == 102
    assert simulate(100, 110, 89, 108, .02).end_cash != simulate(100, 110, 89, 108, .08).end_cash
    for result in (d, e, f):
        assert result.end_cash > 0
        assert abs(result.pnl - (result.end_cash - 5000)) < 1e-9
    # Costs must reduce proceeds and account balance.
    assert simulate(100, 102, 99, 101, .05, cost_bps=50).end_cash < simulate(100, 102, 99, 101, .05, cost_bps=0).end_cash
    print("PASS: 9 executable stop/target/cash accounting assertions; synthetic only")

if __name__ == "__main__":
    run()
