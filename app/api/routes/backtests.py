from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import pandas as pd

from app.backtesting.engine import run_historical_backtest

router = APIRouter()

class BacktestRequest(BaseModel):
    symbol: str
    timeframe: str
    date_start: str
    date_end: str
    mode: str
    score_threshold: int
    min_rr: float
    entry_mode: str

BACKTEST_CACHE = {}
BACKTEST_TRADES = {}

def _get_candles(symbol: str, timeframe: str) -> List[dict]:
    """Fetch candles from Yahoo Finance; fall back to synthetic data."""
    try:
        from app.data.providers.yahoo_finance import fetch_candles
        candles = fetch_candles(symbol, timeframe)
        if candles:
            return candles
    except Exception:
        pass
    from app.api.routes.candles import _synthetic_fallback
    return _synthetic_fallback(symbol, timeframe, count=250)

@router.post("")
def run_backtest_endpoint(req: BacktestRequest):
    """Triggers a historical simulation run using Yahoo Finance data."""
    symbol = req.symbol.upper()
    timeframe = req.timeframe

    # Get candles (real or synthetic fallback)
    candles_raw = _get_candles(symbol, timeframe)
    df = pd.DataFrame(candles_raw)
    df["timestamp"] = pd.to_datetime(df["time"])

    params = {
        "symbol": symbol,
        "timeframe": timeframe,
        "date_start": req.date_start,
        "date_end": req.date_end,
        "score_threshold": req.score_threshold,
        "min_rr": req.min_rr,
        "entry_mode": req.entry_mode,
    }

    result = run_historical_backtest(df, params)
    backtest_id = result["id"]
    BACKTEST_CACHE[backtest_id] = result
    BACKTEST_TRADES[backtest_id] = result.get("trades_list", [])
    return result

@router.get("/{id}")
def get_backtest_by_id(id: str):
    if id in BACKTEST_CACHE:
        return BACKTEST_CACHE[id]
    raise HTTPException(status_code=404, detail="Backtest run not found")

@router.get("/{id}/trades")
def get_backtest_trades(id: str):
    if id in BACKTEST_TRADES:
        return BACKTEST_TRADES[id]
    raise HTTPException(status_code=404, detail="Backtest trades not found")
