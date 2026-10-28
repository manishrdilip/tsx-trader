"""
Data caching system: Download once, use forever (with 30-day refresh).

Speeds up daily scans from 10 min → 30 sec by caching 10 years of price history.
Only refreshes data older than 30 days.
"""
import os
import pickle
from datetime import datetime
import pandas as pd


CACHE_DIR = "data_cache"


def ensure_cache_dir():
    """Create cache directory if it doesn't exist."""
    os.makedirs(CACHE_DIR, exist_ok=True)


def get_cache_path(ticker):
    """Get the cache file path for a ticker."""
    return os.path.join(CACHE_DIR, f"{ticker}.pkl")


def load_cached_data(ticker, max_age_days=30):
    """
    Load cached data if available and not too old.

    Args:
        ticker: Stock symbol
        max_age_days: Refresh cache if older than this (default 30 days)

    Returns:
        DataFrame if cached and fresh, None otherwise
    """
    cache_path = get_cache_path(ticker)

    if not os.path.exists(cache_path):
        return None

    try:
        # Check age
        age_days = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(cache_path))).days
        if age_days >= max_age_days:
            return None  # Cache is stale, trigger re-download

        with open(cache_path, 'rb') as f:
            df = pickle.load(f)
        return df
    except Exception as e:
        print(f"  ! cache error for {ticker}: {e}")
        return None


def save_cached_data(ticker, df):
    """Save data to cache."""
    ensure_cache_dir()
    cache_path = get_cache_path(ticker)
    try:
        with open(cache_path, 'wb') as f:
            pickle.dump(df, f)
    except Exception as e:
        print(f"  ! failed to cache {ticker}: {e}")


def get_data_with_cache(ticker, yfinance_fn, start, auto_adjust=True, progress=False):
    """
    Get price data from cache or download if missing/stale.

    Args:
        ticker: Stock symbol
        yfinance_fn: yfinance.download function
        start: Start date for download (if cache misses)
        auto_adjust: Auto-adjust for splits/dividends
        progress: Show yfinance progress bar

    Returns:
        DataFrame with OHLCV data
    """
    # Try cache first
    cached = load_cached_data(ticker, max_age_days=30)
    if cached is not None:
        print(f"  ✓ {ticker}: loaded from cache ({len(cached)} days)")
        return cached

    # Download if not cached
    print(f"  ↓ {ticker}: downloading...")
    df = yfinance_fn(ticker, start=start, auto_adjust=auto_adjust, progress=progress)

    if df is not None and not df.empty:
        # Handle MultiIndex columns
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        # Clean up
        df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
        save_cached_data(ticker, df)

    return df


def clear_cache(ticker=None):
    """Clear cache for a specific ticker or all."""
    if ticker:
        cache_path = get_cache_path(ticker)
        if os.path.exists(cache_path):
            os.remove(cache_path)
            print(f"  cleared {ticker} cache")
    else:
        for f in os.listdir(CACHE_DIR):
            if f.endswith(".pkl"):
                os.remove(os.path.join(CACHE_DIR, f))
        print(f"  cleared all cache")


def cache_stats():
    """Print cache statistics."""
    ensure_cache_dir()
    files = [f for f in os.listdir(CACHE_DIR) if f.endswith(".pkl")]
    total_size = sum(os.path.getsize(os.path.join(CACHE_DIR, f)) for f in files) / (1024 * 1024)
    print(f"  Cache: {len(files)} tickers, {total_size:.1f} MB")
