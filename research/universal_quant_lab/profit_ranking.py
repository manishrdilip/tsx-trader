"""Produce independent profit-first leaderboards and a Pareto set."""
import numpy as np

BANDS = (0.10, 0.20, 0.30, 0.40, None)
PARTITION = ("currency", "market", "interval", "style")


def validate(rows):
    for row in rows:
        if not all(np.isfinite(row[key]) for key in ("net_profit", "mtm_drawdown", "tail_loss", "stability")):
            raise ValueError("Nonfinite result metrics")


def leaderboards(rows, limit=25):
    validate(rows)
    partitions = {}
    for row in rows:
        partitions.setdefault(tuple(row[key] for key in PARTITION), []).append(row)
    output = []
    for partition, candidates in sorted(partitions.items()):
        ordered = sorted(candidates, key=lambda x: (
            -x["net_profit"], x["mtm_drawdown"], x["tail_loss"], -x["stability"],
            x["job_id"], x["strategy_id"],
        ))
        output.append({
            "scope": dict(zip(PARTITION, partition)),
            "bands": {str(cap): [row for row in ordered if cap is None or row["mtm_drawdown"] <= cap][:limit]
                      for cap in BANDS},
            "pareto": frontier(ordered),
        })
    return output


def frontier(ordered):
    """Exact skyline. Equal risk/profit vectors retain their distinct strategies."""
    result = []
    points = []
    for row in ordered:
        point = (row["net_profit"], -row["mtm_drawdown"], -row["tail_loss"], row["stability"])
        if any(all(a >= b for a, b in zip(previous, point)) and previous != point for previous in points):
            continue
        points.append(point)
        result.append(row)
    return result


def selftest():
    base = dict(currency="CAD", market="TSX", interval="1d", style="swing",
                job_id="a", mtm_drawdown=.08, tail_loss=.02, stability=.01)
    rows = [
        dict(base, strategy_id=1, net_profit=500, win_rate=.30),
        dict(base, strategy_id=2, net_profit=300, win_rate=.95),
        dict(base, strategy_id=3, net_profit=700, mtm_drawdown=.25, win_rate=.15),
    ]
    result = leaderboards(rows)[0]
    assert result["bands"]["0.1"][0]["strategy_id"] == 1
    assert result["bands"]["0.3"][0]["strategy_id"] == 3
    assert [r["strategy_id"] for r in result["pareto"]] == [3, 1]


if __name__ == "__main__":
    selftest()
    print("PASS: lower win rate wins on profit; independent risk bands and dominance")
