"""Export local profit-first risk and family leaderboards from verified batches."""
import argparse
import json
from collections import defaultdict
from datetime import date
from pathlib import Path

import duckdb
import pyarrow as pa

from daily_engine import HOLDS, RULES_PER_FAMILY
from eodhd import atomic_json
from profit_ledger import Ledger
from profit_ranking import BANDS


def export(run, limit):
    manifest = json.loads((run / "manifest.json").read_bytes())
    groups = defaultdict(list)
    ledger = Ledger(run, manifest)
    try:
        ledger.reconcile()
        counts = ledger.counts()
        for job in manifest["jobs"]:
            if counts.get(job["id"], 0) != job["quota"]:
                raise ValueError("Report requires completed engineering quotas")
            groups[(job["currency"], job["market"], "1d", "swing")].append(job)
    finally:
        ledger.close()
    start, end = map(date.fromisoformat, manifest["dates"][1:])
    years = (end - start).days / 365.2425
    output = []
    with duckdb.connect() as db:
        db.execute("SET temp_directory = ?", [(run / "ranking-temp").as_posix()])
        for scope, jobs in sorted(groups.items()):
            files = []
            metadata = []
            for j in jobs:
                width = len(HOLDS) * RULES_PER_FAMILY ** j["depth"]
                metadata.append((j["id"], j["depth"], width, j["symbol"]))
                files.extend(f.as_posix() for f in sorted((run / "parquet" / j["id"]).glob("*.parquet")))
            db.register("jobs", pa.table(dict(zip(
                ("job_id", "depth", "family_width", "symbol"), zip(*metadata),
            ))))
            db.execute("DROP TABLE IF EXISTS ranked")
            columns = {row[0] for row in db.execute("DESCRIBE SELECT * FROM read_parquet(?)", [files]).fetchall()}
            insolvency = "validation_insolvency <> 0" if "validation_insolvency" in columns else "NULL::BOOLEAN"
            db.execute(f"""
                CREATE TEMP TABLE ranked AS
                SELECT j.job_id,j.symbol,j.depth,strategy_id,strategy_id // family_width AS family,
                       validation_net_profit AS net_profit,validation_mtm_drawdown AS mtm_drawdown,
                       validation_tail_loss AS tail_loss,validation_stability AS stability,
                       validation_capital_loss AS capital_loss, {insolvency} AS insolvency,
                       validation_trades::BIGINT AS trades,
                       validation_wins/nullif(validation_trades,0) AS win_rate,
                       validation_gross_wins/nullif(validation_wins,0) AS average_win,
                       validation_gross_losses/nullif(validation_losses,0) AS average_loss,
                       validation_gross_wins/nullif(validation_gross_losses,0) AS profit_factor,
                       average_win/nullif(average_loss,0) AS payoff_ratio,
                       validation_net_profit/nullif(validation_trades,0) AS expectancy,
                       power(greatest(0,1+validation_net_profit/5000),1/?) - 1 AS cagr
                FROM read_parquet(?, filename=true) r
                JOIN jobs j ON split_part(replace(r.filename, chr(92), '/'), '/', -2)=j.job_id
            """, [years, files])
            if db.execute("SELECT count(*) FROM ranked").fetchone()[0] != sum(x["quota"] for x in jobs):
                raise ValueError("Leaderboard inputs did not reconcile")
            order = "ORDER BY net_profit DESC, mtm_drawdown, tail_loss, stability DESC, job_id, strategy_id"

            def records(query, params):
                cursor = db.execute(query, params)
                return [dict(zip([column[0] for column in cursor.description], row)) for row in cursor.fetchall()]

            bands = {}
            for cap in BANDS:
                ceiling = cap if cap is not None else float("inf")
                bands[str(cap)] = {
                    "overall": records(f"SELECT * FROM ranked WHERE mtm_drawdown <= ? {order} LIMIT ?",
                                       [ceiling, limit]),
                    "by_family": records(f"""
                        SELECT * FROM ranked WHERE mtm_drawdown <= ?
                        QUALIFY row_number() OVER (PARTITION BY depth,family {order}) <= ?
                        {order}
                    """, [ceiling, limit]),
                }
            # Sorted distinct objective vectors. A later vector cannot dominate an earlier one.
            ordered = db.execute(f"""
                SELECT net_profit,mtm_drawdown,tail_loss,stability,
                       first(job_id ORDER BY job_id,strategy_id), first(strategy_id ORDER BY job_id,strategy_id)
                FROM ranked GROUP BY ALL
                {order.replace(', job_id, strategy_id', '')}
            """)
            skyline = []
            while page := ordered.fetchmany(8192):
                for p, d, t, s, jid, sid in page:
                    if any(old[1] <= d and old[2] <= t and old[3] >= s for old in skyline):
                        continue
                    skyline.append((p, d, t, s, jid, sid))
            output.append({"scope": dict(zip(("currency","market","interval","style"),scope)),
                           "risk_bands": bands, "pareto": [
                               dict(zip(("net_profit","mtm_drawdown","tail_loss","stability","job_id","strategy_id"), r))
                               for r in skyline
                           ]})
            db.unregister("jobs")
    return {"mode": "engineering", "official_completed": 0, "validation_dates": [str(start), str(end)],
            "ranking": "descending validation net profit; win rate diagnostic only",
            "pareto_ties": "one representative per identical objective vector; all IDs remain in Parquet",
            "scopes": output}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    if not 1 <= args.limit <= 100:
        parser.error("Limit must be between 1 and 100")
    result = export(args.run, args.limit)
    atomic_json(args.output, result)
    print(f"Exported {len(result['scopes'])} independent engineering leaderboard scopes")
