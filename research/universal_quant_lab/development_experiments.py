"""Separate provisional intraday and position-strategy scopes."""
import argparse
from itertools import combinations, product
from pathlib import Path

import numpy as np
import pandas as pd

from campaign_watchdog import guard, health
from daily_campaign import digest
from eodhd import atomic_json
from execution_actions import actions
from profit_admission import cpu_guard
from profit_campaign import load, write_batch
from profit_engine import simulate
from profit_features import signals

VERSION = "patterns-and-holds-v1"


def patterns(bars):
    span = (bars.high - bars.low).replace(0, float("nan"))
    body = (bars.close - bars.open).abs()
    lower = bars[["close", "open"]].min(axis=1) - bars.low
    engulf = ((bars.close > bars.open) & (bars.close.shift(1) < bars.open.shift(1))
              & (bars.open <= bars.close.shift(1)) & (bars.close >= bars.open.shift(1)))
    families = [
        [(lower / span >= level) & (body / span <= .35) for level in (.45, .55, .65, .75)],
        [engulf & (body / span >= level) for level in (.3, .4, .5, .6)],
        [bars.close > bars.high.shift(1).rolling(window).max() for window in (5, 10, 20, 40)],
    ]
    return np.asarray(families, dtype=bool)


def minute_inputs(root, symbol):
    source = root / "database/staging/coinbase" / f"{symbol}-20241101-20241108-1m.json"
    bars = pd.read_json(source, convert_dates=False)
    times = pd.to_datetime(bars.timestamp, utc=True)
    if len(bars) != 10080 or not (times.diff().iloc[1:] == pd.Timedelta(minutes=1)).all():
        raise ValueError("Expected the audited contiguous minute window")
    # A simulator unit is 0.001 coin. Prior completed minute turnover caps entry.
    prices = bars[["open", "low", "close"]].to_numpy(dtype=float) * .001
    cap = (bars.close * bars.volume).rolling(20).min().shift(1).fillna(0).to_numpy() * .001
    return digest(source), np.column_stack((prices, cap)), np.concatenate(
        (signals(bars)[:, [0, 7, 15, 23]], patterns(bars))), (0, 5760, len(bars)), actions(
        root, {}, bars.index, None)


def evaluate(root, directory, symbol, style, source, prices, signals_, splits, corporate, holds, friction, fee):
    name = f"{style}-{symbol}"
    metadata = dict(symbol=symbol, style=style, scope=VERSION, source=source, splits=list(map(int, splits)),
                    holds=holds, friction_per_side=friction, fee_per_order=fee,
                    code={f: digest(Path(__file__).with_name(f)) for f in (
                        "development_experiments.py", "profit_features.py", "profit_engine.py", "profit_campaign.py")})
    manifest = directory / f"{name}.json"
    if manifest.exists():
        import json
        if json.loads(manifest.read_bytes()) != metadata:
            raise ValueError("Experiment scope drift")
    else:
        atomic_json(manifest, metadata)
    target = directory / f"{name}.parquet"
    seen = directory / f"{name}-top100.json"
    if target.exists() and seen.exists():
        return
    assert np.isfinite(prices).all()
    choices = list(product(combinations(range(len(signals_)), 2), product(range(4), repeat=2), holds))
    rows = []
    for i, (family, variants, hold) in enumerate(choices):
        if i % 100 == 0 and (guard(health(root)) or cpu_guard(root, 85) == "cpu_temperature"):
            raise RuntimeError("Experiment paused by laptop resource guard")
        family, variants = np.asarray(family), np.asarray(variants)
        rows.append(tuple(v for a, b in zip(splits[:-1], splits[1:]) for v in simulate(
            prices, signals_, family, variants, a, b, hold, 5000., friction, fee, *corporate)))
    metrics = np.asarray(rows)
    ids = np.arange(len(rows))
    write_batch(target, ids, metrics)
    top = sorted(ids.tolist(), key=lambda i: (-metrics[i, 11], metrics[i, 12], i))[:100]
    atomic_json(seen, dict(evaluations=len(rows), official_completed=0, result_sha256=digest(target), top=[
        dict(strategy_id=i, families=choices[i][0], variants=choices[i][1], holding_bars=choices[i][2],
             net_profit=float(metrics[i, 11]), drawdown_pct=float(metrics[i, 12]*100),
             trade_count=int(metrics[i, 15])) for i in top]))
    print(name, len(rows), flush=True)


if __name__ == "__main__":
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    root = args.root
    directory = root / "results/development-experiments-v1"
    directory.mkdir(exist_ok=True)
    for symbol in ("BTC-USD", "ETH-USD"):
        data = minute_inputs(root, symbol)
        evaluate(root, directory, symbol, "intraday", *data, [5, 15, 60], .006, 0.)
    config = json.loads((root / "config/development-turnover-3m.json").read_bytes())
    for job in config["jobs"]:
        hashes, prices, rules, splits, corporate = load(root, job, config["dates"])
        source = dict(partitions=hashes, action_snapshot=job["action_snapshot_sha256"], dates=config["dates"])
        evaluate(root, directory, job["symbol"], "position", source, prices, rules[:, [0, 7, 15, 23]],
                 splits, corporate, [20, 40, 60], .003, 2.)
