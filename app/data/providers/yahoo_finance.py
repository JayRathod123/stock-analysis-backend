"""
Yahoo Finance data provider for Indian stocks (NSE/BSE).
Supports real OHLCV candle history and live price quotes.
NSE symbol format: RELIANCE.NS
BSE symbol format: RELIANCE.BO
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import pandas as pd

logger = logging.getLogger(__name__)

# ── Timeframe → (yf_interval, yf_period, max_candles) ──────────────────────
# yfinance intraday data:
#   1m  → max 7 days
#   5m  → max 60 days
#   15m → max 60 days
#   30m → max 60 days
#   60m → max 730 days
#   1d  → max (years of history)
#   1wk → max

_TIMEFRAME_MAP: Dict[str, Dict[str, Any]] = {
    "1m":     {"interval": "1m",  "period": "5d",   "resample": None},
    "5m":     {"interval": "5m",  "period": "60d",  "resample": None},
    "15m":    {"interval": "15m", "period": "60d",  "resample": None},
    "30m":    {"interval": "30m", "period": "60d",  "resample": None},
    "1H":     {"interval": "60m", "period": "180d", "resample": None},
    "1h":     {"interval": "60m", "period": "180d", "resample": None},
    "2H":     {"interval": "60m", "period": "365d", "resample": "2H"},
    "4H":     {"interval": "60m", "period": "730d", "resample": "4H"},
    "4h":     {"interval": "60m", "period": "730d", "resample": "4H"},
    "Daily":  {"interval": "1d",  "period": "2y",   "resample": None},
    "daily":  {"interval": "1d",  "period": "2y",   "resample": None},
    "1D":     {"interval": "1d",  "period": "2y",   "resample": None},
    "Weekly": {"interval": "1wk", "period": "5y",   "resample": None},
    "weekly": {"interval": "1wk", "period": "5y",   "resample": None},
    "1W":     {"interval": "1wk", "period": "5y",   "resample": None},
}


def _to_yf_symbol(symbol: str, exchange: str = "NSE") -> str:
    """Convert NSE/BSE symbol to Yahoo Finance ticker format."""
    sym = symbol.upper().strip()
    # Already has exchange suffix
    if sym.endswith(".NS") or sym.endswith(".BO"):
        return sym
    suffix = ".BO" if exchange.upper() == "BSE" else ".NS"
    return f"{sym}{suffix}"


def fetch_candles(
    symbol: str,
    timeframe: str,
    exchange: str = "NSE",
) -> List[Dict[str, Any]]:
    """
    Fetch real OHLCV candles from Yahoo Finance for an Indian stock.
    Returns a list of dicts: {time, open, high, low, close, volume}
    """
    import yfinance as yf  # import here so module loads even without yfinance installed

    tf_config = _TIMEFRAME_MAP.get(timeframe, _TIMEFRAME_MAP["Daily"])
    interval = tf_config["interval"]
    period = tf_config["period"]
    resample_rule = tf_config.get("resample")

    yf_symbol = _to_yf_symbol(symbol, exchange)
    logger.info(f"Fetching {yf_symbol} | interval={interval} | period={period}")

    ticker = yf.Ticker(yf_symbol)
    df = ticker.history(
        period=period,
        interval=interval,
        auto_adjust=True,
        prepost=False,
    )

    if df is None or df.empty:
        raise ValueError(f"No data returned for {yf_symbol} ({interval}/{period})")

    # Drop rows with NaN OHLCV
    df = df.dropna(subset=["Open", "High", "Low", "Close"])

    # Resample for 4H etc.
    if resample_rule:
        df = df.resample(resample_rule).agg({
            "Open": "first",
            "High": "max",
            "Low": "min",
            "Close": "last",
            "Volume": "sum",
        }).dropna()

    candles = []
    for ts, row in df.iterrows():
        # Normalize timezone to UTC
        if hasattr(ts, "tzinfo") and ts.tzinfo is not None:
            ts_utc = ts.tz_convert("UTC")
        else:
            ts_utc = ts

        candles.append({
            "time": ts_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "open":   round(float(row["Open"]),   2),
            "high":   round(float(row["High"]),   2),
            "low":    round(float(row["Low"]),    2),
            "close":  round(float(row["Close"]),  2),
            "volume": round(float(row["Volume"]), 2),
        })

    return candles


def fetch_quote(symbol: str, exchange: str = "NSE") -> Dict[str, Any]:
    """
    Fetch the latest quote (current price, day change, market cap, etc.)
    for a single Indian stock from Yahoo Finance.
    """
    import yfinance as yf

    yf_symbol = _to_yf_symbol(symbol, exchange)
    ticker = yf.Ticker(yf_symbol)

    try:
        info = ticker.fast_info
        current_price = getattr(info, "last_price", None) or getattr(info, "regularMarketPrice", None)
        prev_close    = getattr(info, "previous_close", None)
        market_cap    = getattr(info, "market_cap", None)
        volume        = getattr(info, "three_month_average_volume", None)
    except Exception:
        current_price = prev_close = market_cap = volume = None

    change = None
    change_pct = None
    if current_price is not None and prev_close and prev_close > 0:
        change = round(current_price - prev_close, 2)
        change_pct = round((change / prev_close) * 100, 2)

    return {
        "symbol": symbol.upper(),
        "current_price": round(current_price, 2) if current_price else None,
        "prev_close":    round(prev_close, 2)    if prev_close    else None,
        "change":        change,
        "change_pct":    change_pct,
        "market_cap":    market_cap,
        "volume":        volume,
        "last_update":   datetime.utcnow().isoformat() + "Z",
    }
