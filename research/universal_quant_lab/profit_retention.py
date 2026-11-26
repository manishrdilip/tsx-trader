"""Transaction-ready top-100 reducer for comparable development scopes."""
from datetime import date
import json
from pathlib import Path

from daily_engine import HOLDS, RULES_PER_FAMILY

CATEGORIES = (
    ("profit", "validation_net_profit", 1e30), ("cagr", "cagr", 1e30),
    ("monthly_profit", "monthly_profit", 1e30), ("risk_adjusted", "risk_adjusted", 1e30),
    ("drawdown_10", "validation_net_profit", .10), ("drawdown_20", "validation_net_profit", .20),
    ("drawdown_30", "validation_net_profit", .30), ("drawdown_40", "validation_net_profit", .40),
    ("unrestricted", "validation_net_profit", 1e30),
)


def initialize(db):
    db.execute("""
        CREATE TABLE IF NOT EXISTS top_candidates (
            scope VARCHAR, category VARCHAR, family BIGINT, job VARCHAR, strategy_id BIGINT,
            score DOUBLE, profit DOUBLE, drawdown DOUBLE, tail DOUBLE, stability DOUBLE,
            PRIMARY KEY(scope, category, family, job, strategy_id)
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS batch_distribution (
            job VARCHAR, first_index BIGINT, rows BIGINT, mean_profit DOUBLE, sd_profit DOUBLE,
            min_profit DOUBLE, max_profit DOUBLE, loss_count BIGINT, drawdown_over_40 BIGINT,
            PRIMARY KEY(job, first_index)
        )
    """)


def merge(db, job, first, path, dates, limit=100):
    start, stop = map(date.fromisoformat, dates[1:])
    years = (stop - start).days / 365.2425
    scope = json.dumps([job["currency"], job["market"], "1d", "swing", *dates[1:]])
    width = len(HOLDS) * RULES_PER_FAMILY ** job["depth"]
    identifier = job["id"]
    db.execute("""
        CREATE OR REPLACE TEMP TABLE incoming AS
        SELECT *, ? + strategy_id // ? AS family,
            power(greatest(0,1+validation_net_profit/5000),1/?) - 1 AS cagr,
            validation_net_profit/(?*12) AS monthly_profit,
            validation_net_profit/greatest(.0001, validation_mtm_drawdown) AS risk_adjusted
        FROM read_parquet(?)
    """, [job["depth"] * 1000, width, years, years, Path(path).as_posix()])
    db.execute("""
        INSERT INTO batch_distribution
        SELECT ?,?,count(*),avg(validation_net_profit),stddev_pop(validation_net_profit),
               min(validation_net_profit),max(validation_net_profit),
               count(*) FILTER (WHERE validation_net_profit<0),
               count(*) FILTER (WHERE validation_mtm_drawdown>.4)
        FROM incoming
        ON CONFLICT DO NOTHING
    """, [identifier, first])
    for category, metric, cap in (*CATEGORIES, ("family_profit", "validation_net_profit", 1e30)):
        family = "family" if category == "family_profit" else "-1"
        db.execute(f"""
            CREATE OR REPLACE TEMP TABLE merged_top AS
            WITH pool AS (
                SELECT * FROM top_candidates WHERE scope=? AND category=?
                UNION ALL
                SELECT ?, ?, {family}, ?, strategy_id, {metric}, validation_net_profit,
                       validation_mtm_drawdown, validation_tail_loss, validation_stability
                FROM incoming WHERE validation_mtm_drawdown<=?
            )
            SELECT * FROM (SELECT DISTINCT * FROM pool) AS deduplicated
            QUALIFY row_number() OVER (
                PARTITION BY family ORDER BY score DESC, profit DESC, drawdown, tail, stability DESC, job, strategy_id
            )<=?
        """, [scope, category, scope, category, identifier, cap, limit])
        db.execute("DELETE FROM top_candidates WHERE scope=? AND category=?", [scope, category])
        db.execute("INSERT INTO top_candidates SELECT * FROM merged_top")
