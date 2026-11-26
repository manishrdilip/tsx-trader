"""Reproducible bookkeeping tests. No synthetic evaluations enter official counts."""
from pathlib import Path
import argparse
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np

from profit_campaign import write_batch
from profit_engine import METRICS, selftest as engine_test
from profit_ledger import Ledger
from profit_ranking import selftest as ranking_test
from profit_retention import merge


def ledger_test(directory):
    dates = ["2016-01-01", "2022-01-01", "2025-01-01"]
    jobs = [
        {"id": name, "quota": quota, "capacity": 101, "seed": 2,
         "currency": "CAD", "market": "TSX", "depth": 1}
        for name, quota in (("a", 6), ("b", 7))
    ]
    manifest = {"target": 13, "retention": True, "jobs": jobs, "dates": dates}
    ledger = Ledger(directory, manifest)
    try:
        assert ledger.reserve("a", 4) == (0, 4)
        assert ledger.reserve("b", 4) == (0, 4)
        for job in ("a", "b", "a", "b"):
            first, rows = ledger.reserve(job, 4)
            path = ledger.file(job, first)
            ids = ledger.ids(job, first, rows)
            values = np.zeros((rows, len(METRICS) * 2), dtype=np.float64)
            write_batch(path, ids, values)
            if job == "a" and first == 0:
                def fail(*args, **kwargs):
                    merge(*args, **kwargs)
                    raise RuntimeError("Injected transaction interruption")

                with patch("profit_ledger.merge", fail):
                    try:
                        ledger.commit(job, first, 0.)
                    except RuntimeError:
                        pass
                    else:
                        raise AssertionError("Injected interruption not detected")
                assert ledger.counts() == {}
                assert ledger.db.execute("SELECT count(*) FROM top_candidates").fetchone()[0] == 0
                assert ledger.db.execute("SELECT count(*) FROM batch_distribution").fetchone()[0] == 0
                ledger.close()
                ledger = Ledger(directory, manifest)
                ledger.reconcile()
            ledger.commit(job, first, 0.)
            ledger.commit(job, first, 0.)
        ledger.reconcile()
        assert ledger.counts() == {"a": 6, "b": 7}
        assert ledger.reserve("a", 4) is None and ledger.reserve("b", 4) is None
        assert ledger.db.execute("SELECT sum(rows) FROM batch_distribution").fetchone()[0] == 13
        assert ledger.db.execute(
            "SELECT job,strategy_id FROM top_candidates WHERE category='profit' ORDER BY job,strategy_id"
        ).fetchall() == sorted((job, int(x)) for job, quota in (("a", 6), ("b", 7))
                              for x in ledger.ids(job, 0, quota))
    finally:
        ledger.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scratch", type=Path)
    args = parser.parse_args()
    engine_test()
    ranking_test()
    with TemporaryDirectory(dir=args.scratch) as directory:
        ledger_test(Path(directory))
    print("PASS: objective, daily actions, exact global quota, transactional rollback, recovery and ties")
