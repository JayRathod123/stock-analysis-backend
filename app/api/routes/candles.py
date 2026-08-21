"""
Candles API route — fetches real OHLCV data from Yahoo Finance.
Supports all NSE/BSE listed stocks and all standard timeframes.
Falls back to deterministic synthetic data if Yahoo Finance is unreachable.
"""
import logging
from fastapi import APIRouter, Query, HTTPException
from typing import List, Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()

class CandleSchema(BaseModel):
    time: str
    open: float
    high: float
    low: float
    close: float
    volume: float


# ── Helpers ─────────────────────────────────────────────────────────────────

def _yf_fetch(symbol: str, timeframe: str) -> List[dict]:
    """Delegate to the Yahoo Finance provider module."""
    from app.data.providers.yahoo_finance import fetch_candles
    return fetch_candles(symbol, timeframe, exchange="NSE")


def _synthetic_fallback(symbol: str, timeframe: str, count: int = 150) -> List[dict]:
    """
    Deterministic synthetic OHLCV with 3 injected Supply/Demand patterns.
    Used ONLY when Yahoo Finance is unavailable.
    """
    from datetime import datetime, timedelta
    import random

    base_prices = {
        "TCS": 3400.0, "INFY": 1450.0, "HDFCBANK": 1600.0, "ICICIBANK": 950.0
    }
    price = base_prices.get(symbol.upper(), 2400.0)

    delta_map = {
        "1m": timedelta(minutes=1), "5m": timedelta(minutes=5),
        "15m": timedelta(minutes=15), "30m": timedelta(minutes=30),
        "1H": timedelta(hours=1), "1h": timedelta(hours=1),
        "4H": timedelta(hours=4), "4h": timedelta(hours=4),
        "Daily": timedelta(days=1), "daily": timedelta(days=1),
        "Weekly": timedelta(days=7),
    }
    delta = delta_map.get(timeframe, timedelta(minutes=15))
    now = datetime.utcnow()
    random.seed(42)
    atr = price * 0.004

    candles = []
    for i in range(count):
        ch = random.normalvariate(0.05, atr * 0.4)
        o, c = price, price + ch
        h = max(o, c) + abs(random.normalvariate(atr * 0.3, atr * 0.1))
        l = min(o, c) - abs(random.normalvariate(atr * 0.3, atr * 0.1))
        vol = abs(random.normalvariate(12000, 3000))
        # Inject DBR Demand at 29-31
        if i == 29:   o, c, h, l, vol = price+atr*3, price-atr*2.5, price+atr*3.3, price-atr*2.8, 30000
        elif i == 30: o, c, h, l, vol = price-atr*2.5, price-atr*2.3, price-atr*1.8, price-atr*2.8, 8000
        elif i == 31: o, c, h, l, vol = price-atr*2.3, price+atr*4, price+atr*4.3, price-atr*2.4, 50000
        # Inject RBD Supply at 69-71
        elif i == 69: o, c, h, l, vol = price-atr*2, price+atr*3, price+atr*3.3, price-atr*2.2, 28000
        elif i == 70: o, c, h, l, vol = price+atr*3, price+atr*2.8, price+atr*3.4, price+atr*2.4, 7500
        elif i == 71: o, c, h, l, vol = price+atr*2.8, price-atr*3.5, price+atr*3, price-atr*3.8, 48000
        # Inject RBR Demand at 109-111
        elif i == 109: o, c, h, l, vol = price-atr, price+atr*3, price+atr*3.3, price-atr*1.2, 26000
        elif i == 110: o, c, h, l, vol = price+atr*3, price+atr*2.8, price+atr*3.3, price+atr*2.4, 8500
        elif i == 111: o, c, h, l, vol = price+atr*2.8, price+atr*5.5, price+atr*5.8, price+atr*2.6, 55000

        ts = now - (count - i) * delta
        candles.append({
            "time": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "open": round(o, 2), "high": round(h, 2),
            "low": round(l, 2), "close": round(c, 2),
            "volume": round(vol, 2),
        })
        price = c

    return candles


# ── Endpoint ─────────────────────────────────────────────────────────────────

@router.get("", response_model=List[CandleSchema])
def get_candles(
    symbol: str = Query(..., description="NSE stock symbol e.g. RELIANCE"),
    timeframe: str = Query("15m", description="Candle interval: 1m/5m/15m/30m/1H/4H/Daily/Weekly"),
    exchange: str = Query("NSE", description="Exchange: NSE or BSE"),
):
    """
    Fetch real OHLCV candle data for an Indian stock from Yahoo Finance.
    Automatically falls back to synthetic demo data if the live fetch fails.
    """
    sym = symbol.upper().strip()
    tf = timeframe.strip()

    # 1. Attempt live Yahoo Finance fetch
    try:
        candles = _yf_fetch(sym, tf)
        if candles:
            logger.info(f"Yahoo Finance: {len(candles)} candles returned for {sym}/{tf}")
            return candles
        logger.warning(f"Yahoo Finance returned empty data for {sym}/{tf}, using fallback")
    except Exception as exc:
        logger.warning(f"Yahoo Finance fetch failed for {sym}/{tf}: {exc} — using synthetic fallback")

    # 2. Synthetic fallback
    return _synthetic_fallback(sym, tf)
