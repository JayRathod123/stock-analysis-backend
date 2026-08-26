from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import pandas as pd
import uuid

from app.analysis.structure import analyze_market_structure, evaluate_curve
from app.analysis.zones import detect_zones, deduplicate_zones

from app.analysis.scoring import evaluate_freshness_and_retests, score_zone
from app.analysis.trade import generate_trade_setup
from app.analysis.indicators.calculations import calculate_atr
from app.data.providers.yahoo_finance import fetch_candles

router = APIRouter()

class RunAnalysisParams(BaseModel):
    symbol: str
    timeframe: Optional[str] = "15m"
    mode: Optional[str] = "all"  # intraday or swing or all

ANALYSIS_CACHE = {}

def _get_candles(symbol: str, timeframe: str) -> List[dict]:
    try:
        candles = fetch_candles(symbol, timeframe)
        if candles:
            return candles
    except Exception as e:
        print(f"Yahoo Finance fetch error for {symbol}: {e}")
        return []

def _is_bullish_context(df):
    return True

def _is_above_vwap(df):
    return True

def _process_timeframe(
    symbol: str, 
    timeframe: str, 
    df: pd.DataFrame, 
    struct: dict, 
    atr_val: float,
    htf_curve: str,
    itf_trend: str
):
    detected_sd = detect_zones(df)
    
    # GTF only uses core S&D zones
    from app.analysis.zones import flag_reaction_zones
    from app.analysis.structure import detect_market_traps
    detected = deduplicate_zones(detected_sd)
    detected = flag_reaction_zones(detected)
    detected = detect_market_traps(df, detected)
    valid_zones = []
    
    current_price = float(df["close"].iloc[-1])

    from app.analysis.indicators.calculations import calculate_ema
    if "close" in df.columns and len(df) > 50:
        ema_20 = calculate_ema(df["close"], 20).iloc[-1]
        ema_50 = calculate_ema(df["close"], 50).iloc[-1]
    else:
        ema_20 = ema_50 = 0.0

    for idx, z in enumerate(detected):
        status, retests, history = evaluate_freshness_and_retests(z, df)
        ema_context = "Above 50 EMA" if _is_bullish_context(df) else "Below 50 EMA"
        
        # Gap Context
        z["gap_context"] = "NONE"
        base_start = z.get("base_end_idx", 1) - z.get("base_candles", 1)
        base_end = z.get("base_end_idx", 1)
        
        # Check pro gap (departure gap)
        if base_end + 1 < len(df):
            dep_candle = df.iloc[base_end + 1]
            prev_candle = df.iloc[base_end]
            if z["type"] == "DEMAND" and dep_candle["open"] > prev_candle["high"]:
                z["gap_context"] = "PRO_GAP_UP"
            elif z["type"] == "SUPPLY" and dep_candle["open"] < prev_candle["low"]:
                z["gap_context"] = "PRO_GAP_DOWN"
        
        # Check novice gap (entry gap into zone)
        if base_start > 0 and z["gap_context"] == "NONE":
            legin_candle = df.iloc[base_start - 1]
            first_base = df.iloc[base_start]
            if z["type"] == "DEMAND" and first_base["open"] < legin_candle["low"]:
                z["gap_context"] = "NOVICE_GAP_DOWN"
            elif z["type"] == "SUPPLY" and first_base["open"] > legin_candle["high"]:
                z["gap_context"] = "NOVICE_GAP_UP"
        
        # Check if EMA 20 or 50 is trading through the zone
        ema_intersection = False
        if (z["price_min"] <= ema_20 <= z["price_max"]) or (z["price_min"] <= ema_50 <= z["price_max"]):
            ema_intersection = True
        
        # New MTF Scoring
        scores = score_zone(z, df, status, retests, itf_trend=itf_trend, htf_curve=htf_curve, ema_context=ema_context, ema_intersection=ema_intersection, timeframe=timeframe)
        trade = generate_trade_setup(z, atr_val)

        entry_price = trade["entry"]
        proximity_pct = abs(current_price - entry_price) / current_price * 100

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
            "ema_context": ema_context,
            "vwap_context": "Above VWAP" if _is_above_vwap(df) else "Below VWAP",
            "gap_context": z["gap_context"],
            "trap_type": z.get("trap_type", "NONE"),
            "is_reaction": z.get("is_reaction", False),
            "is_lotl": z.get("is_lotl", False),
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
            "warnings": scores["rejection_reasons"],
            "entry_type": scores["entry_type"],
            "proximity_pct": round(proximity_pct, 2)
        }

        # Timeframe-based Actionable Proximity Limits (GTF Nearest Zone Principle)
        # Scalping (5m): within 1.5% of CMP
        # Intraday (15m): within 2.5% of CMP
        # Swing (125m/Daily): within 6.0% of CMP
        if timeframe == "5m":
            max_prox = 1.5
        elif timeframe in ["15m", "10m"]:
            max_prox = 2.5
        else:
            max_prox = 6.0

        if proximity_pct > max_prox:
            scores["is_rejected"] = True
            scores["rejection_reasons"].append(f"REJECTED: Entry too far from CMP ({proximity_pct:.1f}% > {max_prox}%).")

        # Threshold of score >= 5, not rejected, and valid R:R
        if scores["final_score"] >= 5 and not scores["is_rejected"] and trade["status"] != "REJECTED_RR":
            valid_zones.append(zone_detail)
            
    # Calculate proximity to current price
    for z in valid_zones:
        z["proximity"] = abs(z["entry"] - current_price)
        
    # Sort by highest score first (Descending), then by proximity (Ascending)
    valid_zones = sorted(valid_zones, key=lambda x: (-x["final_score"], x["proximity"]))
    return valid_zones

@router.post("")
def run_analysis_endpoint(params: RunAnalysisParams):
    symbol = params.symbol.upper()
    mode = params.mode

    # Initialize empty DFs
    df_1mo = pd.DataFrame()
    df_1w = pd.DataFrame()
    df_1d = pd.DataFrame()
    df_125m = pd.DataFrame()
    df_75m = pd.DataFrame()
    df_15m = pd.DataFrame()
    df_5m = pd.DataFrame()
    
    current_price = 0.0
    
    if mode == "intraday":
        df_1d = pd.DataFrame(_get_candles(symbol, "1d"))
        df_75m = pd.DataFrame(_get_candles(symbol, "75m"))
        df_15m = pd.DataFrame(_get_candles(symbol, "15m"))
        
        for df in [df_1d, df_75m, df_15m]:
            if df.empty: return {"trade_decision": "REJECTED", "reason": "No data"}
            df["timestamp"] = pd.to_datetime(df["time"])
        current_price = float(df_15m["close"].iloc[-1])
        
    elif mode == "swing":
        df_1mo = pd.DataFrame(_get_candles(symbol, "1mo"))
        df_1w = pd.DataFrame(_get_candles(symbol, "1wk"))
        df_1d = pd.DataFrame(_get_candles(symbol, "1d"))
        df_125m = pd.DataFrame(_get_candles(symbol, "125m"))
        
        for df in [df_1mo, df_1w, df_1d, df_125m]:
            if df.empty: return {"trade_decision": "REJECTED", "reason": "No data"}
            df["timestamp"] = pd.to_datetime(df["time"])
        current_price = float(df_125m["close"].iloc[-1])
        
    elif mode == "scalping":
        df_75m = pd.DataFrame(_get_candles(symbol, "75m"))
        df_15m = pd.DataFrame(_get_candles(symbol, "15m"))
        df_5m = pd.DataFrame(_get_candles(symbol, "5m"))
        
        for df in [df_75m, df_15m, df_5m]:
            if df.empty: return {"trade_decision": "REJECTED", "reason": "No data"}
            df["timestamp"] = pd.to_datetime(df["time"])
        current_price = float(df_5m["close"].iloc[-1])
    else:
        # manual mode fetches all
        df_1mo = pd.DataFrame(_get_candles(symbol, "1mo"))
        df_1w = pd.DataFrame(_get_candles(symbol, "1wk"))
        df_1d = pd.DataFrame(_get_candles(symbol, "1d"))
        df_125m = pd.DataFrame(_get_candles(symbol, "125m"))
        df_75m = pd.DataFrame(_get_candles(symbol, "75m"))
        df_15m = pd.DataFrame(_get_candles(symbol, "15m"))
        df_5m = pd.DataFrame(_get_candles(symbol, "5m"))
        for df in [df_1mo, df_1w, df_1d, df_125m, df_75m, df_15m, df_5m]:
            if df.empty: return {"trade_decision": "REJECTED", "reason": "No data"}
            df["timestamp"] = pd.to_datetime(df["time"])
        current_price = float(df_15m["close"].iloc[-1])

    intraday_zones = []
    swing_zones = []
    scalping_zones = []
    
    if mode == "intraday" or mode not in ["intraday", "swing", "scalping"]:
        struct_75m = analyze_market_structure(df_75m)
        struct_15m = analyze_market_structure(df_15m)
        curve_1d = evaluate_curve(df_1d, current_price)
        atr_15m = calculate_atr(df_15m["high"], df_15m["low"], df_15m["close"], 14)
        atr_val_15m = float(atr_15m.iloc[-1])
        
        intraday_zones = _process_timeframe(
            symbol=symbol, 
            timeframe="15m", 
            df=df_15m, 
            struct=struct_15m, 
            atr_val=atr_val_15m,
            htf_curve=curve_1d,
            itf_trend=struct_75m["bias"]
        )
        
    if mode == "swing" or mode not in ["intraday", "swing", "scalping"]:
        struct_1w = analyze_market_structure(df_1w)
        struct_1d = analyze_market_structure(df_1d)
        curve_1mo = evaluate_curve(df_1mo, current_price)
        curve_1w = evaluate_curve(df_1w, current_price)
        atr_125m = calculate_atr(df_125m["high"], df_125m["low"], df_125m["close"], 14)
        atr_val_125m = float(atr_125m.iloc[-1])
        
        swing_zones = _process_timeframe(
            symbol=symbol, 
            timeframe="125m", 
            df=df_125m, 
            struct=struct_1d, 
            atr_val=atr_val_125m,
            htf_curve=curve_1w,
            itf_trend=struct_1d["bias"]
        )
        
    if mode == "scalping" or mode not in ["intraday", "swing", "scalping"]:
        struct_15m = analyze_market_structure(df_15m)
        struct_5m = analyze_market_structure(df_5m)
        curve_75m = evaluate_curve(df_75m, current_price)
        atr_5m = calculate_atr(df_5m["high"], df_5m["low"], df_5m["close"], 14)
        atr_val_5m = float(atr_5m.iloc[-1])
        
        scalping_zones = _process_timeframe(
            symbol=symbol, 
            timeframe="5m", 
            df=df_5m, 
            struct=struct_5m, 
            atr_val=atr_val_5m,
            htf_curve=curve_1d,
            itf_trend=struct_15m["bias"]
        )
        


    best_intraday = intraday_zones[0] if intraday_zones else None
    best_swing = swing_zones[0] if swing_zones else None
    best_scalping = scalping_zones[0] if scalping_zones else None

    # Trade Decision
    trade_decision = "WAIT"
    if (best_intraday and best_intraday["final_score"] >= 5) or \
       (best_swing and best_swing["final_score"] >= 5) or \
       (best_scalping and best_scalping["final_score"] >= 5):
        trade_decision = "TRADE"

    return {
        "analysis_id": f"an-{uuid.uuid4().hex[:8]}",
        "symbol": symbol,
        "current_price": current_price,
        "mode": mode,
        "timestamp": datetime.utcnow().isoformat(),
        "trade_decision": trade_decision,
        "intraday_zones": intraday_zones,
        "swing_zones": swing_zones,
        "scalping_zones": scalping_zones,
        "best_intraday_setup": best_intraday,
        "best_swing_setup": best_swing,
        "best_scalping_setup": best_scalping
    }
