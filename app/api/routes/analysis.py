from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import pandas as pd
import uuid

from app.analysis.structure import analyze_market_structure
from app.analysis.zones import detect_zones
from app.analysis.scoring import evaluate_freshness_and_retests, score_zone
from app.analysis.trade import generate_trade_setup

router = APIRouter()

class RunAnalysisParams(BaseModel):
    symbol: str
    timeframe: str
    mode: str  # intraday or swing

ANALYSIS_CACHE = {}

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
    return _synthetic_fallback(symbol, timeframe)

@router.post("")
def run_analysis_endpoint(params: RunAnalysisParams):
    """Full pipeline: fetch candles -> structure -> zones -> score -> trade."""
    symbol = params.symbol.upper()
    timeframe = params.timeframe

    # 1. Get candles (Yahoo Finance or synthetic)
    candles_raw = _get_candles(symbol, timeframe)
    df = pd.DataFrame(candles_raw)
    df["timestamp"] = pd.to_datetime(df["time"])

    # 2. Market structure
    struct = analyze_market_structure(df)

    # 3. Detect zones
    detected = detect_zones(df)

    best_intraday_setup = None
    best_swing_setup = None
    other_valid_setups = []
    watchlist_zones = []
    rejected_zones = []

    # ATR for SL/target buffers
    from app.analysis.indicators.calculations import calculate_atr
    atr = calculate_atr(df["high"], df["low"], df["close"], 14)
    atr_val = atr.iloc[-1] if not pd.isna(atr.iloc[-1]) else 10.0

    # 4. Score each zone and build trade parameters
    for idx, z in enumerate(detected):
        status, retests, history = evaluate_freshness_and_retests(z, df)
        scores = score_zone(z, df, status, retests, struct["bias"])
        trade = generate_trade_setup(z, atr_val)

        zone_detail = {
            "zone_id": f"zone-{idx}-{uuid.uuid4().hex[:8]}",
            "symbol": symbol,
            "zone_type": z["type"],
            "pattern": z["pattern"],
            "timeframe": timeframe,
            "price_min": z["price_min"],
            "price_max": z["price_max"],
            "freshness": status,
            "retest_count": retests,
            "base_candles": z["base_candles"],
            "departure_strength": z["departure_strength"],
            "participation_proxy_score": scores["participation_proxy_score"],
            "authentication_score": scores["authentication_score"],
            "final_score": scores["final_score"],
            "market_structure": struct["structure"],
            "trend": struct["bias"],
            "ema_context": "Above 50 EMA" if _is_bullish_context(df) else "Below 50 EMA",
            "vwap_context": "Above VWAP" if _is_above_vwap(df) else "Below VWAP",
            "entry": trade["entry"],
            "stop_loss": trade["stop_loss"],
            "target_1": trade["target_1"],
            "target_2": trade["target_2"],
            "risk": trade["risk"],
            "reward": trade["reward"],
            "rr": trade["rr"],
            "status": trade["status"],
            "positive_reasons": scores["positive_reasons"],
            "negative_reasons": scores["negative_reasons"],
            "warnings": [],
        }

        if scores["is_rejected"] or trade["status"] == "REJECTED_RR":
            zone_detail["rejection_reasons"] = scores["rejection_reasons"] or ["Sub-optimal R:R"]
            rejected_zones.append(zone_detail)
        elif scores["final_score"] >= 85 and not best_intraday_setup and params.mode == "intraday":
            best_intraday_setup = zone_detail
        elif scores["final_score"] >= 85 and not best_swing_setup and params.mode == "swing":
            best_swing_setup = zone_detail
        elif scores["final_score"] >= 75:
            other_valid_setups.append(zone_detail)
        else:
            watchlist_zones.append(zone_detail)

    # Promote from other_setups if no best found
    if not best_intraday_setup and other_valid_setups and params.mode == "intraday":
        best_intraday_setup = other_valid_setups.pop(0)
    if not best_swing_setup and other_valid_setups and params.mode == "swing":
        best_swing_setup = other_valid_setups.pop(0)

    response = {
        "id": str(uuid.uuid4()),
        "symbol": symbol,
        "current_price": round(float(df["close"].iloc[-1]), 2),
        "market_bias": struct["bias"],
        "intraday_bias": struct["bias"],
        "swing_bias": struct["bias"],
        "best_intraday_setup": best_intraday_setup,
        "best_swing_setup": best_swing_setup,
        "other_valid_setups": other_valid_setups,
        "watchlist_zones": watchlist_zones,
        "rejected_zones": rejected_zones,
        "created_at": datetime.utcnow().isoformat(),
    }

    ANALYSIS_CACHE[response["id"]] = response
    return response

@router.get("/{id}")
def get_analysis_by_id(id: str):
    if id in ANALYSIS_CACHE:
        return ANALYSIS_CACHE[id]
    raise HTTPException(status_code=404, detail="Analysis run not found")

def _is_bullish_context(df: pd.DataFrame) -> bool:
    try:
        from app.analysis.indicators.calculations import calculate_ema
        ema = calculate_ema(df["close"], 50)
        return float(df["close"].iloc[-1]) > float(ema.iloc[-1])
    except Exception:
        return True

def _is_above_vwap(df: pd.DataFrame) -> bool:
    try:
        from app.analysis.indicators.calculations import calculate_vwap
        vwap = calculate_vwap(df)
        return float(df["close"].iloc[-1]) > float(vwap.iloc[-1])
    except Exception:
        return True
