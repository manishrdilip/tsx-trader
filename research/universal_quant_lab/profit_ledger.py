"""Cross-job range ledger. The campaign manifest defines disjoint ID domains."""
import json
from pathlib import Path

import duckdb
import numpy as np
import pyarrow.parquet as pq

from daily_campaign import digest, sampled_ids
from campaign_plan import hashed


class Ledger:
    def __init__(self, directory, manifest):
        self.root = Path(directory)
        self.target = manifest["target"]
        jobs = manifest["jobs"]
        self.jobs = {job["id"]: job for job in jobs}
        if len(self.jobs) != len(jobs) or sum(job["quota"] for job in jobs) != self.target:
            raise ValueError("Job domains must be unique and quotas must equal the target")
        self.db = duckdb.connect(str(self.root / "global.duckdb"))
        try:
            self.db.execute("CREATE TABLE IF NOT EXISTS run (fingerprint VARCHAR PRIMARY KEY)")
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS ranges (
                    job VARCHAR, first_index BIGINT, size INTEGER, state VARCHAR,
                    sha256 VARCHAR, bytes BIGINT, compute_seconds DOUBLE,
                    PRIMARY KEY (job, first_index)
                )
            """)
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS errors (
                    job VARCHAR, first_index BIGINT, error_type VARCHAR, occurred TIMESTAMP
                )
            """)
            fingerprint = hashed(manifest)
            self.db.execute("INSERT INTO run SELECT ? WHERE NOT EXISTS (SELECT 1 FROM run)", [fingerprint])
            if self.db.execute("SELECT fingerprint FROM run").fetchall() != [(fingerprint,)]:
                raise ValueError("Global manifest drift")
        except Exception:
            self.close()
            raise

    def close(self):
        self.db.close()

    def file(self, job, first):
        return self.root / "parquet" / job / f"{first:012}.parquet"

    def ids(self, job, first, size):
        spec = self.jobs[job]
        return sampled_ids(first, size, spec["capacity"], spec["seed"])

    def counts(self):
        completed = self.db.execute(
            "SELECT job, sum(size) FROM ranges WHERE state='complete' GROUP BY job"
        ).fetchall()
        return {job: int(size) for job, size in completed}

    def reconcile(self):
        for job, spec in self.jobs.items():
            offset = 0
            rows = self.db.execute("""
                SELECT first_index,size,state,sha256,bytes FROM ranges
                WHERE job=? ORDER BY first_index
            """, [job]).fetchall()
            for first, size, state, checksum, length in rows:
                if first != offset or not 0 < size <= spec["quota"] - offset:
                    raise ValueError("Out-of-range or overlapping lease")
                if state == "leased":
                    if first != rows[-1][0]:
                        raise ValueError("Outstanding lease precedes a committed range")
                    break
                if state != "complete":
                    raise ValueError("Unknown lease state")
                path = self.file(job, first)
                if path.stat().st_size != length or digest(path) != checksum:
                    raise ValueError("Committed output checksum mismatch")
                self.verify_ids(path, job, first, size)
                offset += size
        if sum(self.counts().values()) > self.target:
            raise ValueError("Ledger exceeds campaign target")

    def verify_ids(self, path, job, first, size):
        actual = pq.read_table(path, columns=["strategy_id"])["strategy_id"].to_numpy()
        if not np.array_equal(actual, self.ids(job, first, size)):
            raise ValueError("Batch identifiers do not match the canonical reservation")

    def reserve(self, job, max_size):
        counts = self.counts()
        first = counts.get(job, 0)
        remaining = min(self.jobs[job]["quota"] - first, self.target - sum(counts.values()))
        if remaining <= 0:
            return None
        pending = self.db.execute(
            "SELECT size FROM ranges WHERE job=? AND first_index=? AND state='leased'", [job, first]
        ).fetchone()
        if pending:
            if not 0 < pending[0] <= remaining:
                raise ValueError("Outstanding lease exceeds quota")
            return first, pending[0]
        size = min(remaining, max_size)
        if size < 1:
            raise ValueError("Invalid batch size")
        self.db.execute("INSERT INTO ranges VALUES (?, ?, ?, 'leased', NULL, NULL, NULL)", [job, first, size])
        return first, size

    def commit(self, job, first, compute_seconds):
        lease = self.db.execute(
            "SELECT size,state,sha256 FROM ranges WHERE job=? AND first_index=?", [job, first]
        ).fetchone()
        if lease is None:
            raise ValueError("Missing lease")
        size, state, prior = lease
        file = self.file(job, first)
        self.verify_ids(file, job, first, size)
        checksum = digest(file)
        if state == "complete":
            if checksum != prior:
                raise ValueError("Committed batch changed")
            return
        if self.counts().get(job, 0) != first:
            raise ValueError("Commit would leave a gap")
        self.db.execute("""
            UPDATE ranges SET state='complete', sha256=?, bytes=?, compute_seconds=?
            WHERE job=? AND first_index=? AND state='leased'
        """, [checksum, file.stat().st_size, compute_seconds, job, first])

    def failure(self, job, first, error):
        self.db.execute("INSERT INTO errors VALUES (?, ?, ?, current_timestamp)", [job, first, type(error).__name__])
