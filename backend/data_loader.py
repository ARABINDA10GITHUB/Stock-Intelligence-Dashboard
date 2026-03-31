"""
data_loader.py — Fetches, caches, and processes NSE stock market data.
Best version: V2 sector metadata + MA20/MA50 + V1 safe zero-division fix.
"""

import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import yfinance as yf

# ── Config ────────────────────────────────────────────────────────────────────
DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

CACHE_EXPIRY_HOURS = 6   # Refresh local CSV cache every 6 hours

# 10 NSE-listed stocks with sector classification (V2 addition)
COMPANIES = [
    {"symbol": "RELIANCE",   "name": "Reliance Industries",       "sector": "Energy"},
    {"symbol": "TCS",        "name": "Tata Consultancy Services", "sector": "IT"},
    {"symbol": "INFY",       "name": "Infosys",                   "sector": "IT"},
    {"symbol": "HDFCBANK",   "name": "HDFC Bank",                 "sector": "Banking"},
    {"symbol": "WIPRO",      "name": "Wipro",                     "sector": "IT"},
    {"symbol": "ICICIBANK",  "name": "ICICI Bank",                "sector": "Banking"},
    {"symbol": "HINDUNILVR", "name": "Hindustan Unilever",        "sector": "FMCG"},
    {"symbol": "ITC",        "name": "ITC Limited",               "sector": "FMCG"},
    {"symbol": "SBIN",       "name": "State Bank of India",       "sector": "Banking"},
    {"symbol": "BAJFINANCE", "name": "Bajaj Finance",             "sector": "Finance"},
]


# ── Internal helpers ──────────────────────────────────────────────────────────
def _yf_symbol(symbol: str) -> str:
    """Append .NS suffix for NSE-listed stocks (yfinance format)."""
    if not symbol.endswith(".NS") and not symbol.endswith(".BO"):
        return symbol + ".NS"
    return symbol


def _cache_path(symbol: str) -> Path:
    return DATA_DIR / f"{symbol}.csv"


def _is_cache_fresh(path: Path) -> bool:
    if not path.exists():
        return False
    mtime = datetime.fromtimestamp(path.stat().st_mtime)
    return (datetime.now() - mtime) < timedelta(hours=CACHE_EXPIRY_HOURS)


def _fetch_from_yfinance(symbol: str) -> pd.DataFrame | None:
    """Download 2 years of daily OHLCV data from Yahoo Finance."""
    try:
        ticker = yf.Ticker(_yf_symbol(symbol))
        df = ticker.history(period="2y", interval="1d", auto_adjust=True)
        if df.empty:
            return None
        df.index = pd.to_datetime(df.index.date)
        df.index.name = "Date"
        df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
        return df
    except Exception as e:
        print(f"[yfinance] Error fetching {symbol}: {e}")
        return None


def _add_derived_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add pre-computed derived columns saved to CSV cache:
      - Daily_Return  : safe (Close-Open)/Open — zero-division guarded (V1 fix)
      - MA_7/20/30/50 : standard moving averages (V2 addition: MA_20, MA_50)
      - High_52w / Low_52w : rolling 52-week high and low
    """
    df = df.copy()

    # ── BUG FIX (from V1): guard against Open == 0 to prevent inf/NaN ──
    df["Daily_Return"] = np.where(
        df["Open"] != 0,
        ((df["Close"] - df["Open"]) / df["Open"] * 100).round(4),
        0.0
    )

    # ── Moving averages — all 4 standard trader periods (V2: added MA_20, MA_50) ──
    df["MA_7"]  = df["Close"].rolling(7,   min_periods=1).mean().round(2)
    df["MA_20"] = df["Close"].rolling(20,  min_periods=1).mean().round(2)
    df["MA_30"] = df["Close"].rolling(30,  min_periods=1).mean().round(2)
    df["MA_50"] = df["Close"].rolling(50,  min_periods=1).mean().round(2)

    # ── 52-week rolling high / low ──
    df["High_52w"] = df["High"].rolling(252, min_periods=1).max().round(2)
    df["Low_52w"]  = df["Low"].rolling(252,  min_periods=1).min().round(2)

    return df


# ── Public API ────────────────────────────────────────────────────────────────
def get_stock_data(symbol: str) -> pd.DataFrame | None:
    """
    Return a fully-processed DataFrame for the given NSE symbol.

    Strategy:
      1. If local CSV cache is fresh (< 6 hrs old) → read from disk.
      2. Otherwise → fetch from yfinance, recompute derived columns, save.
      3. If yfinance fails → fall back to stale cache if it exists.
      4. Returns None only if no data is available at all.
    """
    symbol = symbol.upper()
    cache  = _cache_path(symbol)

    if _is_cache_fresh(cache):
        df = pd.read_csv(cache, index_col="Date", parse_dates=True)
        df = df[pd.to_datetime(df.index, errors="coerce").notna()]
        return df

    df = _fetch_from_yfinance(symbol)
    if df is None:
        if cache.exists():
            print(f"[cache] yfinance failed for {symbol} — using stale cache.")
            df = pd.read_csv(cache, index_col="Date", parse_dates=True)
            df = df[pd.to_datetime(df.index, errors="coerce").notna()]
            return df
        return None

    df = _add_derived_columns(df)
    df = df[pd.to_datetime(df.index, errors="coerce").notna()]
    df.to_csv(cache)
    return df


def get_all_symbols() -> list[dict]:
    """Return the full list of supported companies with sector info."""
    return COMPANIES


def prefetch_all() -> None:
    """
    Pre-download and cache data for all 10 companies.
    Run once before starting the server for faster first-load.
    """
    print("Pre-fetching stock data for all companies…")
    for company in COMPANIES:
        sym    = company["symbol"]
        sector = company.get("sector", "")
        df     = get_stock_data(sym)
        status = f"{len(df)} rows cached" if df is not None else "FAILED"
        print(f"  {sym:<14} [{sector:<8}]  →  {status}")
    print("Done.")


if __name__ == "__main__":
    prefetch_all()
