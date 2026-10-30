"""
Data caching system: Download once, use for 30 days.
Speeds up daily scans from ~10 min → ~30 sec.
Hardened against corrupted pickle files.
"""
import os
import pickle
from datetime import datetime
import pandas as pd

CACHE_DIR = "data_cache"


def ensure_cache_dir():
    os.makedirs(CACHE_DIR, exist_ok=True)


def get_cache_path(ticker):
    return os.path.join(CACHE_DIR, f"{ticker}.pkl")


def load_cached_data(ticker, max_age_days=30):
    cache_path = get_cache_path(ticker)
    if not os.path.exists(cache_path):
        return None

    try:
        age_days = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(cache_path))).days
        if age_days >= max_age_days:
            return None

        with open(cache_path, "rb") as f:
            df = pickle.load(f)

        if not isinstance(df, pd.DataFrame) or df.empty:
            raise ValueError("invalid cache content")

        return df
    except Exception as e:
        print(f"  ! cache error for {ticker} ({e}) — deleting bad cache")
        try:
            os.remove(cache_path)
        except OSError:
            pass
        return None


def save_cached_data(ticker, df):
    ensure_cache_dir()
    cache_path = get_cache_path(ticker)
    try:
        with open(cache_path, "wb") as f:
            pickle.dump(df, f)
    except Exception as e:
        print(f"  ! failed to cache {ticker}: {e}")


def get_data_with_cache(ticker, yfinance_fn, start, auto_adjust=True, progress=False):
    cached = load_cached_data(ticker, max_age_days=30)
    if cached is not None:
        print(f"  ✓ {ticker}: loaded from cache ({len(cached)} days)")
        return cached

    print(f"  ↓ {ticker}: downloading...")
    try:
        df = yfinance_fn(ticker, start=start, auto_adjust=auto_adjust, progress=progress)
    except Exception as e:
        print(f"  ! download failed for {ticker}: {e}")
        return None

    if df is not None and not df.empty:
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
        if not df.empty:
            save_cached_data(ticker, df)

    return df


def clear_cache(ticker=None):
    ensure_cache_dir()
    if ticker:
        path = get_cache_path(ticker)
        if os.path.exists(path):
            os.remove(path)
            print(f"  cleared {ticker} cache")
    else:
        for f in os.listdir(CACHE_DIR):
            if f.endswith(".pkl"):
                os.remove(os.path.join(CACHE_DIR, f))
        print("  cleared all cache")


def cache_stats():
    ensure_cache_dir()
    files = [f for f in os.listdir(CACHE_DIR) if f.endswith(".pkl")]
    total_size = sum(os.path.getsize(os.path.join(CACHE_DIR, f)) for f in files) / (1024 * 1024)
    print(f"  Cache: {len(files)} tickers, {total_size:.1f} MB")
