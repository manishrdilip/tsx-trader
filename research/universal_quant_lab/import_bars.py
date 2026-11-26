"""Convert one real symbol's OHLCV CSV/Parquet to the lab's JSON input.
No downloading, synthetic bars, resampling, forward fills, or missing-volume imputation.
Exchange-local date sessions are appropriate for regular-hours equity data only.
For other assets supply an explicit session column from a verified market calendar.
"""
import argparse, hashlib, json
from pathlib import Path
import numpy as np
import pandas as pd

def convert(source, dest, symbol=None, tz=None, session_col=None):
    source, dest = Path(source), Path(dest)
    df = pd.read_parquet(source) if source.suffix.lower() in (".parquet", ".pq") else pd.read_csv(source)
    df.columns = [str(x).lower() for x in df.columns]
    if len(set(df.columns)) != len(df.columns):
        raise ValueError("duplicate column names")
    for key in ("sym", "symbol", "ticker"):
        if key in df:
            if symbol is None and df[key].nunique() != 1:
                raise ValueError("select one symbol with --symbol")
            if symbol is not None:
                df = df[df[key] == symbol].copy()
            else:
                symbol = str(df[key].iloc[0])
            break
    else:
        if not symbol:
            raise ValueError("provide --symbol for a single-symbol input")
    if df.empty:
        raise ValueError("no rows for requested symbol")
    ts_col = next((x for x in ("timestamp", "datetime", "date", "time") if x in df), None)
    idx = pd.DatetimeIndex(pd.to_datetime(df[ts_col] if ts_col else df.index))
    if idx.tz is None:
        raise ValueError("timestamps must already carry a timezone; do not guess")
    if idx.hasnans or idx.has_duplicates:
        raise ValueError("missing or duplicate timestamps")
    df.index = idx
    df = df.sort_index()
    cols = ["open", "high", "low", "close"]
    df[cols] = df[cols].apply(pd.to_numeric, errors="raise")
    if not np.isfinite(df[cols]).all().all() or (df[cols] <= 0).any().any():
        raise ValueError("nonpositive or nonfinite prices")
    if (df.high < df[["open","close","low"]].max(axis=1)).any() or (df.low > df[["open","close"]].min(axis=1)).any():
        raise ValueError("inconsistent OHLC")
    if "volume" in df:
        df["volume"] = pd.to_numeric(df.volume, errors="raise")
        if ((df.volume < 0) | np.isinf(df.volume)).any():
            raise ValueError("invalid volume")
    else:
        df["volume"] = np.nan
    if session_col:
        session_col = session_col.lower()
        if df[session_col].isna().any():
            raise ValueError("missing session ID")
        sessions = df[session_col].astype(str)
    elif tz:
        sessions = pd.Series(df.index.tz_convert(tz).strftime("%Y-%m-%d"), index=df.index)
    else:
        raise ValueError("provide --session-col or equity --timezone")
    records = [{"timestamp":t.isoformat(),"session":str(s),**{k:float(r[k]) for k in cols},"volume":None if pd.isna(r.volume) else float(r.volume)} for (t,r),s in zip(df.iterrows(),sessions)]
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(records, separators=(",",":"), allow_nan=False), encoding="utf-8")
    audit = {"symbol":symbol,"bars":len(records),"first":records[0]["timestamp"],"last":records[-1]["timestamp"],"sessions":int(sessions.nunique()),"missing_volume":int(df.volume.isna().sum()),"source_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),"output_sha256":hashlib.sha256(dest.read_bytes()).hexdigest(),"session_method":session_col or tz,"limitations":["No exchange-calendar completeness check", "No corporate-action or instrument eligibility audit", "Bar interval and timestamp semantics require provider verification"]}
    dest.with_suffix(".audit.json").write_text(json.dumps(audit,indent=2), encoding="utf-8")
    return audit

if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("source"); p.add_argument("dest")
    p.add_argument("--symbol"); p.add_argument("--timezone"); p.add_argument("--session-col")
    a=p.parse_args()
    print(json.dumps(convert(a.source,a.dest,a.symbol,a.timezone,a.session_col),indent=2))
