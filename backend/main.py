"""
Stock Data Intelligence Dashboard — FastAPI Backend
JarNox Internship Assignment · Best Version (V1 bug fixes + V2 features)
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import pandas as pd
import numpy as np
from pathlib import Path
import math

from data_loader import get_stock_data, get_all_symbols


# ── NaN / Inf sanitiser ────────────────────────────────────────────────────────
def clean_nan(obj):
    """Recursively replace NaN / Inf float values with None (→ JSON null)."""
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, dict):
        return {k: clean_nan(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [clean_nan(i) for i in obj]
    return obj


def df_to_records(df: pd.DataFrame) -> list:
    """Convert DataFrame to JSON-safe list of dicts (handles NaN/Inf)."""
    return clean_nan(df.to_dict(orient="records"))


def safe_float(val) -> float | None:
    """Return float or None — handles NaN, Inf, and None safely."""
    try:
        f = float(val)
        return None if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return None


# ── Technical Indicator Helpers ────────────────────────────────────────────────
def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Compute RSI (Relative Strength Index) using Wilder's smoothing."""
    delta    = series.diff()
    gain     = delta.clip(lower=0)
    loss     = -delta.clip(upper=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs       = avg_gain / avg_loss.replace(0, np.nan)
    rsi      = 100 - (100 / (1 + rs))
    return rsi.round(2)


def compute_macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """Compute MACD line, Signal line, and Histogram."""
    ema_fast    = series.ewm(span=fast, adjust=False).mean()
    ema_slow    = series.ewm(span=slow, adjust=False).mean()
    macd_line   = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram   = macd_line - signal_line
    return macd_line.round(4), signal_line.round(4), histogram.round(4)


def compute_bollinger_bands(series: pd.Series, window: int = 20, num_std: float = 2):
    """Compute Bollinger Bands (upper, middle/SMA, lower)."""
    sma   = series.rolling(window=window, min_periods=1).mean()
    std   = series.rolling(window=window, min_periods=1).std()
    upper = (sma + num_std * std).round(2)
    lower = (sma - num_std * std).round(2)
    return upper, sma.round(2), lower


def _safe_daily_return(close: pd.Series, open_: pd.Series) -> np.ndarray:
    """
    Compute (Close - Open) / Open safely.
    Returns 0 wherever Open == 0 to avoid division-by-zero / inf / NaN.
    (V1 bug fix applied here)
    """
    return np.where(
        open_ != 0,
        ((close - open_) / open_ * 100).round(4),
        0
    )


# ── App setup ──────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Stock Data Intelligence Dashboard",
    description=(
        "A production-quality financial data platform for 10 NSE-listed stocks. "
        "Built for JarNox Internship Assignment."
    ),
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/", include_in_schema=False)
def serve_frontend():
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "Stock Dashboard API is running. Visit /docs for API documentation."}


# ──────────────────────────────────────────────
# ENDPOINT 1: List all companies
# ──────────────────────────────────────────────
@app.get("/companies", summary="List all available companies with sector info")
def get_companies():
    symbols = get_all_symbols()
    return {"companies": symbols, "count": len(symbols)}


# ──────────────────────────────────────────────
# ENDPOINT 2: OHLCV + full technical indicators
# ──────────────────────────────────────────────
@app.get("/data/{symbol}", summary="Get OHLCV data with technical indicators")
def get_stock(
    symbol: str,
    days: int = Query(default=30, ge=7, le=365, description="Number of trading days to return"),
    indicators: bool = Query(default=True, description="Include RSI, MACD, Bollinger Bands"),
):
    symbol = symbol.upper()
    df = get_stock_data(symbol)
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"No data found for symbol: {symbol}")

    # ── BUG FIX (V1): safe division — no inf/NaN on zero-open rows ──
    df["daily_return_pct"] = _safe_daily_return(df["Close"], df["Open"])

    # ── Moving averages (all 4 standard periods) ──
    df["ma_7"]  = df["Close"].rolling(window=7,  min_periods=1).mean().round(2)
    df["ma_20"] = df["Close"].rolling(window=20, min_periods=1).mean().round(2)
    df["ma_30"] = df["Close"].rolling(window=30, min_periods=1).mean().round(2)
    df["ma_50"] = df["Close"].rolling(window=50, min_periods=1).mean().round(2)

    if indicators:
        df["rsi"] = compute_rsi(df["Close"])
        macd_line, signal_line, histogram = compute_macd(df["Close"])
        df["macd"]        = macd_line
        df["macd_signal"] = signal_line
        df["macd_hist"]   = histogram
        bb_upper, bb_mid, bb_lower = compute_bollinger_bands(df["Close"])
        df["bb_upper"] = bb_upper
        df["bb_mid"]   = bb_mid
        df["bb_lower"] = bb_lower

    df = df.tail(days).copy().reset_index()
    df["Date"] = df["Date"].astype(str)

    return {"symbol": symbol, "days": days, "data": df_to_records(df)}


# ──────────────────────────────────────────────
# ENDPOINT 3: 52-week summary
# ──────────────────────────────────────────────
@app.get("/summary/{symbol}", summary="52-week high/low, volatility, momentum, RSI")
def get_summary(symbol: str):
    symbol = symbol.upper()
    df = get_stock_data(symbol)
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"No data found for symbol: {symbol}")

    df_year = df.tail(252).copy()

    high_52w  = float(df_year["High"].max())
    low_52w   = float(df_year["Low"].min())
    avg_close = float(df_year["Close"].mean())

    # ── BUG FIX (V1): safe division for volatility calculation ──
    daily_returns    = _safe_daily_return(df_year["Close"], df_year["Open"]) / 100
    volatility_score = float(daily_returns.std() * 100)

    avg_30   = float(df_year.tail(30)["Close"].mean()) if len(df_year) >= 30 else avg_close
    avg_90   = float(df_year.tail(90)["Close"].mean()) if len(df_year) >= 90 else avg_close
    momentum = round(((avg_30 - avg_90) / avg_90) * 100, 2) if avg_90 else 0.0

    last_row      = df.iloc[-1]
    prev_row      = df.iloc[-2] if len(df) > 1 else last_row
    current_price = float(last_row["Close"])
    prev_close    = float(prev_row["Close"])
    daily_change_pct = round(
        ((current_price - prev_close) / prev_close) * 100, 2
    ) if prev_close != 0 else 0.0

    rsi_series  = compute_rsi(df["Close"])
    current_rsi = safe_float(rsi_series.iloc[-1]) if not rsi_series.empty else None

    price_range        = high_52w - low_52w
    price_position_pct = round(
        ((current_price - low_52w) / price_range) * 100, 1
    ) if price_range > 0 else 50.0

    avg_volume = int(df_year["Volume"].mean()) if "Volume" in df_year.columns else None

    return clean_nan({
        "symbol":               symbol,
        "current_price":        current_price,
        "daily_change_pct":     daily_change_pct,
        "52_week_high":         round(high_52w,  2),
        "52_week_low":          round(low_52w,   2),
        "avg_close_52w":        round(avg_close, 2),
        "volatility_score":     round(volatility_score, 4),
        "momentum_score_pct":   momentum,
        "current_rsi":          round(current_rsi, 2) if current_rsi is not None else None,
        "price_position_52w_pct": price_position_pct,
        "avg_daily_volume":     avg_volume,
        "data_points":          len(df_year),
    })


# ──────────────────────────────────────────────
# ENDPOINT 4: Compare two stocks
# ──────────────────────────────────────────────
@app.get("/compare", summary="Compare normalized performance of two stocks")
def compare_stocks(
    symbol1: str = Query(..., description="First stock symbol, e.g. INFY"),
    symbol2: str = Query(..., description="Second stock symbol, e.g. TCS"),
    days: int    = Query(default=30, ge=7, le=365),
):
    s1, s2 = symbol1.upper(), symbol2.upper()

    if s1 == s2:
        raise HTTPException(status_code=400, detail="Please provide two different symbols.")

    df1 = get_stock_data(s1)
    df2 = get_stock_data(s2)

    if df1 is None or df1.empty:
        raise HTTPException(status_code=404, detail=f"No data for {s1}")
    if df2 is None or df2.empty:
        raise HTTPException(status_code=404, detail=f"No data for {s2}")

    df1 = df1.tail(days)[["Close", "Volume"]].rename(columns={"Close": s1, "Volume": f"{s1}_vol"})
    df2 = df2.tail(days)[["Close", "Volume"]].rename(columns={"Close": s2, "Volume": f"{s2}_vol"})

    # Use pd.merge on index to safely align by Date regardless of index dtype
    merged = pd.merge(df1, df2, left_index=True, right_index=True, how="inner")
    if merged.empty:
        raise HTTPException(status_code=400, detail="No overlapping dates for the two symbols.")

    price_cols = [s1, s2]
    norm       = (merged[price_cols] / merged[price_cols].iloc[0] * 100).round(4)
    norm.index = norm.index.astype(str)

    correlation = round(float(merged[s1].corr(merged[s2])), 4)
    ret1 = round(((merged[s1].iloc[-1] - merged[s1].iloc[0]) / merged[s1].iloc[0]) * 100, 2)
    ret2 = round(((merged[s2].iloc[-1] - merged[s2].iloc[0]) / merged[s2].iloc[0]) * 100, 2)
    vol1 = round(float(merged[s1].pct_change(fill_method=None).std() * 100), 4)
    vol2 = round(float(merged[s2].pct_change(fill_method=None).std() * 100), 4)

    return clean_nan({
        "symbol1": s1, "symbol2": s2, "days": days,
        "correlation":       correlation,
        "total_return_pct":  {s1: ret1, s2: ret2},
        "volatility_pct":    {s1: vol1, s2: vol2},
        "normalized_prices": norm.reset_index().rename(columns={"Date": "date"}).to_dict(orient="records"),
    })


# ──────────────────────────────────────────────
# ENDPOINT 5: Top Gainers & Losers
# ──────────────────────────────────────────────
@app.get("/market/movers", summary="Top 5 gainers and losers by daily change")
def get_movers():
    movers = []
    for item in get_all_symbols():
        sym = item["symbol"]
        df  = get_stock_data(sym)
        if df is None or len(df) < 2:
            continue
        last   = df.iloc[-1]
        prev   = df.iloc[-2]
        prev_c = float(prev["Close"])
        if prev_c == 0:
            continue
        change = ((float(last["Close"]) - prev_c) / prev_c) * 100
        movers.append({
            "symbol":     sym,
            "name":       item["name"],
            "sector":     item.get("sector", ""),
            "change_pct": round(float(change), 2),
            "close":      round(float(last["Close"]), 2),
            "volume":     int(last["Volume"]) if "Volume" in last and not pd.isna(last["Volume"]) else None,
        })

    movers.sort(key=lambda x: x["change_pct"], reverse=True)
    return clean_nan({"top_gainers": movers[:5], "top_losers": movers[-5:][::-1]})


# ──────────────────────────────────────────────
# ENDPOINT 6: RSI + MACD buy/sell signals
# ──────────────────────────────────────────────
@app.get("/signals/{symbol}", summary="RSI + MACD-based buy/sell signal detection")
def get_signals(
    symbol: str,
    days: int = Query(default=90, ge=14, le=365),
):
    symbol = symbol.upper()
    df = get_stock_data(symbol)
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"No data found for symbol: {symbol}")

    df_full = df.copy()
    df_full["rsi"] = compute_rsi(df_full["Close"])
    macd_line, signal_line, histogram = compute_macd(df_full["Close"])
    df_full["macd"]        = macd_line
    df_full["macd_signal"] = signal_line
    df_full["macd_hist"]   = histogram

    df_slice = df_full.tail(days).copy().reset_index()
    df_slice["Date"] = df_slice["Date"].astype(str)

    signals = []
    for _, row in df_slice.iterrows():
        rsi  = row.get("rsi")
        macd = row.get("macd")
        sig  = row.get("macd_signal")

        # ── BUG FIX (V1): use `is not None` — never `if rsi` which drops RSI==0 ──
        rsi_valid  = rsi  is not None and not math.isnan(float(rsi))
        macd_valid = macd is not None and sig is not None \
                     and not math.isnan(float(macd)) and not math.isnan(float(sig))

        signal_type = "neutral"
        if rsi_valid:
            if rsi < 30:
                signal_type = "oversold"
            elif rsi > 70:
                signal_type = "overbought"

        if macd_valid:
            if float(macd) > float(sig) and signal_type == "oversold":
                signal_type = "buy"
            elif float(macd) < float(sig) and signal_type == "overbought":
                signal_type = "sell"

        signals.append({
            "date":        row["Date"],
            "close":       round(float(row["Close"]), 2),
            "rsi":         round(float(rsi),  2) if rsi_valid  else None,
            "macd":        round(float(macd), 4) if macd_valid else None,
            "macd_signal": round(float(sig),  4) if macd_valid else None,
            "signal":      signal_type,
        })

    return clean_nan({"symbol": symbol, "days": days, "signals": signals})


# ──────────────────────────────────────────────
# ENDPOINT 7: Volume trends and anomalies
# ──────────────────────────────────────────────
@app.get("/volume/{symbol}", summary="Volume trends, 20-day MA, high-volume day detection")
def get_volume(
    symbol: str,
    days: int = Query(default=30, ge=7, le=365),
):
    symbol = symbol.upper()
    df = get_stock_data(symbol)
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail=f"No data found for symbol: {symbol}")

    df_v = df.tail(days).copy()
    df_v["vol_ma_20"]  = df["Volume"].rolling(20, min_periods=1).mean().tail(days).values
    df_v["vol_ratio"]  = (df_v["Volume"] / df_v["vol_ma_20"]).round(3)
    df_v["high_volume"] = df_v["vol_ratio"] > 1.5   # 50% above 20-day avg = notable

    df_v = df_v.reset_index()
    df_v["Date"] = df_v["Date"].astype(str)

    records = []
    for _, row in df_v.iterrows():
        records.append({
            "date":       row["Date"],
            "volume":     int(row["Volume"])              if not pd.isna(row["Volume"])     else None,
            "vol_ma_20":  round(float(row["vol_ma_20"]), 0) if not pd.isna(row["vol_ma_20"]) else None,
            "vol_ratio":  row["vol_ratio"]               if not pd.isna(row["vol_ratio"])  else None,
            "high_volume": bool(row["high_volume"]),
            "close":      round(float(row["Close"]), 2),
        })

    return clean_nan({"symbol": symbol, "days": days, "volume_data": records})


# ──────────────────────────────────────────────
# ENDPOINT 8: Market-wide overview / heatmap data
# ──────────────────────────────────────────────
@app.get("/market/overview", summary="Market-wide snapshot: 30d return, volatility, RSI, sector")
def market_overview():
    overview = []
    for item in get_all_symbols():
        sym = item["symbol"]
        df  = get_stock_data(sym)
        if df is None or len(df) < 30:
            continue

        df30    = df.tail(30)
        open_0  = float(df30["Close"].iloc[0])
        ret_30d = round(
            ((float(df30["Close"].iloc[-1]) - open_0) / open_0) * 100, 2
        ) if open_0 != 0 else 0.0

        vol     = round(float(df30["Close"].pct_change(fill_method=None).std() * 100), 3)
        rsi_val = compute_rsi(df["Close"]).iloc[-1]

        overview.append({
            "symbol":        sym,
            "name":          item["name"],
            "sector":        item.get("sector", ""),
            "current_price": round(float(df["Close"].iloc[-1]), 2),
            "return_30d_pct": ret_30d,
            "volatility_30d": vol,
            "rsi":           round(float(rsi_val), 2) if not math.isnan(float(rsi_val)) else None,
        })

    overview.sort(key=lambda x: x["return_30d_pct"], reverse=True)
    return clean_nan({"companies": overview, "count": len(overview)})

# ──────────────────────────────────────────────
# RUN SERVER (Required for Deployment)
# ──────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",   # filename:variable
        host="0.0.0.0",
        port=10000,
        reload=False
    )
