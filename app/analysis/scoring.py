import pandas as pd
import numpy as np
from typing import List, Dict, Any, Tuple

def evaluate_freshness_and_retests(
    zone: Dict[str, Any], 
    candles: pd.DataFrame
) -> Tuple[str, int, List[Dict[str, Any]]]:
    status = "FRESH"
    retest_count = 0
    test_history = []
    
    start_idx = zone["base_end_idx"] + 1
    p_min = zone["price_min"]
    p_max = zone["price_max"]
    is_demand = zone["type"] == "DEMAND"
    
    if is_demand:
        proximal = p_max
        distal = p_min
    else:
        proximal = p_min
        distal = p_max
        
    for idx in range(start_idx, len(candles)):
        candle = candles.iloc[idx]
        c_low = candle["low"]
        c_high = candle["high"]
        
        if is_demand and c_low <= distal:
            status = "INVALIDATED"
            break
        elif not is_demand and c_high >= distal:
            status = "INVALIDATED"
            break
            
        touched = False
        if is_demand and c_low <= proximal:
            touched = True
        elif not is_demand and c_high >= proximal:
            touched = True
            
        if touched:
            retest_count += 1
            if retest_count == 1:
                status = "FIRST_RETEST"
            elif retest_count == 2:
                status = "SECOND_RETEST"
            else:
                status = "CONSUMED"
                
    return status, retest_count, test_history

def score_zone(
    zone: Dict[str, Any], 
    df: pd.DataFrame, 
    status: str, 
    retest_count: int,
    itf_trend: str = "NEUTRAL",
    htf_curve: str = "EQUILIBRIUM",
    ema_context: str = "N/A",
    ema_intersection: bool = False,
    timeframe: str = "15m"
) -> Dict[str, Any]:
    positive_reasons = []
    negative_reasons = []
    rejection_reasons = []
    points = 0.0
    
    is_demand = zone["type"] == "DEMAND"

    # 1. Freshness (Max 3)
    if status == "FRESH":
        points += 3
        positive_reasons.append("Fresh (Untested) (+3)")
    elif status == "FIRST_RETEST":
        points += 1.5
        positive_reasons.append("Tested Once (+1.5)")
    else:
        negative_reasons.append("Tested Twice or Consumed (0)")

    if status == "INVALIDATED":
        rejection_reasons.append("REJECTED: Zone is Invalidated (Price broke distal line).")
        
    # 2. Strength / Departure (Max 2)
    # Check departure candles for gaps
    departure_idx = zone["base_end_idx"] + 1
    if departure_idx < len(df):
        dep_candle = df.iloc[departure_idx]
        prev_candle = df.iloc[zone["base_end_idx"]]
        
        has_gap = False
        if is_demand and dep_candle["open"] > prev_candle["high"]:
            has_gap = True
        elif not is_demand and dep_candle["open"] < prev_candle["low"]:
            has_gap = True
            
        # For simplicity, if departure_strength is STRONG we assume it's exciting.
        # We also look at the candle after departure to see if it's 2 exciting.
        second_exciting = False
        if departure_idx + 1 < len(df):
            c2 = df.iloc[departure_idx + 1]
            from app.analysis.zones import is_base_candle
            # If not a base candle, it's exciting
            atr_val = (c2["high"] - c2["low"]) # rough approx
            if not is_base_candle(c2["high"], c2["low"], c2["open"], c2["close"], atr_val):
                second_exciting = True

        if second_exciting:
            points += 2
            positive_reasons.append("2 Exciting Candles Departure (+2)")
        elif has_gap:
            points += 2
            positive_reasons.append("1 Exciting Candle with GAP (+2)")
        else:
            points += 1
            positive_reasons.append("1 Exciting Candle no GAP (+1)")
            
    # 3. Time at Base (Max 2) (Page 35)
    base_count = zone["base_candles"]
    if 1 <= base_count <= 3:
        points += 2
        positive_reasons.append(f"1-3 Base Candles ({base_count}) (+2)")
    elif 4 <= base_count <= 5:
        points += 1
        positive_reasons.append(f"4-5 Base Candles ({base_count}) (+1)")
    else:
        negative_reasons.append(f">5 Base Candles ({base_count}) (0)")

    # 4. EMA Intersection (+1) (Page 41, Point 3)
    if ema_intersection:
        points += 1
        positive_reasons.append("20/50 EMA trading through zone (+1)")

    # MTF Curve & Trend Rules (Pages 32-33)
    if is_demand:
        if htf_curve == "HIGH":
            rejection_reasons.append("REJECTED: High on HTF Curve (Sell only on high curve).")
        if itf_trend == "DOWNTREND":
            rejection_reasons.append("REJECTED: Trading against Downtrend (Do not buy).")
    else:
        if htf_curve == "LOW":
            rejection_reasons.append("REJECTED: Low on HTF Curve (Buy only on low curve).")
        if itf_trend == "UPTREND":
            rejection_reasons.append("REJECTED: Trading against Uptrend (Do not sell).")

    # Score below 5 Rule (Page 35: "No trade should be below 5")
    if points < 5.0:
        rejection_reasons.append(f"REJECTED: Trade score ({points}/7) is below minimum 5 points.")

    # Cap maximum score at 7 (Page 34-35)
    final_score = min(points, 7.0)

    # Entry Type (Pages 35-37)
    if final_score >= 7.0:
        entry_type = "TYPE 1: SET & FORGET (Score 7)"
    elif final_score >= 5.0:
        entry_type = "TYPE 2/3: CONFIRM ENTRY (Score 5-6)"
    else:
        entry_type = "NO TRADE (Score < 5)"

    return {
        "final_score": final_score,
        "raw_points": points,
        "entry_type": entry_type,
        "positive_reasons": positive_reasons,
        "negative_reasons": negative_reasons,
        "rejection_reasons": rejection_reasons,
        "participation_proxy_score": final_score * 14.28,
        "authentication_score": final_score * 14.28,
        "is_rejected": len(rejection_reasons) > 0
    }
