import pandas as pd
import numpy as np
from typing import List, Dict, Any, Tuple

def evaluate_freshness_and_retests(
    zone: Dict[str, Any], 
    candles: pd.DataFrame
) -> Tuple[str, int, List[Dict[str, Any]]]:
    """
    Evaluates historical retests for a zone.
    Returns (status, retest_count, test_history).
    """
    status = "FRESH"
    retest_count = 0
    test_history = []
    
    start_idx = zone["base_end_idx"] + 1
    p_min = zone["price_min"]
    p_max = zone["price_max"]
    is_demand = zone["type"] == "DEMAND"
    
    # distal/proximal boundaries
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
        timestamp = candle["timestamp"]
        
        # Check invalidation first
        if is_demand and c_low <= distal:
            status = "INVALIDATED"
            test_history.append({
                "timestamp": timestamp,
                "type": "INVALIDATION",
                "price": c_low
            })
            break
        elif not is_demand and c_high >= distal:
            status = "INVALIDATED"
            test_history.append({
                "timestamp": timestamp,
                "type": "INVALIDATION",
                "price": c_high
            })
            break
            
        # Check touch
        touched = False
        penetration = 0.0
        
        if is_demand and c_low <= proximal:
            touched = True
            penetration = (proximal - c_low) / (proximal - distal)
        elif not is_demand and c_high >= proximal:
            touched = True
            penetration = (c_high - proximal) / (distal - proximal)
            
        if touched:
            retest_count += 1
            if retest_count == 1:
                status = "FIRST_RETEST"
            elif retest_count == 2:
                status = "SECOND_RETEST"
            else:
                status = "CONSUMED"
                
            test_history.append({
                "timestamp": timestamp,
                "type": f"RETEST_{retest_count}",
                "price": c_low if is_demand else c_high,
                "penetration": min(1.0, max(0.0, penetration))
            })
            
    return status, retest_count, test_history

def score_zone(
    zone: Dict[str, Any], 
    df: pd.DataFrame, 
    status: str, 
    retest_count: int,
    market_bias: str = "NEUTRAL"
) -> Dict[str, Any]:
    """
    Scores a zone, builds positive/negative lists, and checks garbage filters.
    """
    positive_reasons = []
    negative_reasons = []
    rejection_reasons = []
    
    # 1. Base Quality (15 pts)
    # Lower base candles are better
    base_count = zone["base_candles"]
    if base_count <= 2:
        base_score = 100
        positive_reasons.append("Tight consolidation base (1-2 candles)")
    elif base_count <= 4:
        base_score = 80
        positive_reasons.append("Standard consolidation base (3-4 candles)")
    else:
        base_score = 50
        negative_reasons.append(f"Wide consolidation base ({base_count} candles)")
        if base_count > 6:
            rejection_reasons.append(f"Excessive base candles ({base_count} count)")
            
    # 2. Departure Strength (15 pts)
    dep_strength = zone["departure_strength"]
    if dep_strength == "STRONG":
        dep_score = 100
        positive_reasons.append("High impulse departure displacement")
    else:
        dep_score = 60
        negative_reasons.append("Weak departure velocity")
        
    # 3. Freshness (15 pts)
    if status == "FRESH":
        fresh_score = 100
        positive_reasons.append("Untested fresh zone")
    elif status == "FIRST_RETEST":
        fresh_score = 75
        positive_reasons.append("Zone tested once (retained strength)")
    elif status == "SECOND_RETEST":
        fresh_score = 40
        negative_reasons.append("Zone tested twice (reduced probability)")
    else:
        fresh_score = 0
        rejection_reasons.append(f"Zone consumed (status: {status})")
        
    # 4. Participation/Liquidity Proxy (10 pts)
    # Estimated based on relative volume and displacement
    vol_series = df["volume"]
    departure_candle = df.iloc[zone["base_end_idx"] + 1]
    
    # Calculate simple relative volume
    recent_vols = vol_series.iloc[max(0, zone["base_end_idx"]-20):zone["base_end_idx"]+1]
    avg_vol = recent_vols.mean() if len(recent_vols) > 0 else 1.0
    rel_vol = departure_candle["volume"] / avg_vol if avg_vol > 0 else 1.0
    
    participation_proxy = min(100, int(rel_vol * 35))
    if participation_proxy > 80:
        positive_reasons.append("Strong institutional volume proxy support")
    else:
        negative_reasons.append("Low volume participation proxy marker")
        
    # 5. Trend Alignment & Bias (18 pts)
    trend_score = 50
    zone_type = zone["type"]
    if (zone_type == "DEMAND" and market_bias == "BULLISH") or (zone_type == "SUPPLY" and market_bias == "BEARISH"):
        trend_score = 100
        positive_reasons.append(f"Zone aligned with {market_bias} market bias")
    elif market_bias != "NEUTRAL":
        trend_score = 30
        negative_reasons.append(f"Zone counter-trend to {market_bias} bias")
        
    # Standard values for remaining categories
    auth_score = int((base_score + dep_score + (100 if participation_proxy > 60 else 50)) / 3)
    
    # Final Weighted score calculation
    final_score = int(
        (base_score * 0.15) +
        (dep_score * 0.15) +
        (fresh_score * 0.15) +
        (auth_score * 0.15) +
        (participation_proxy * 0.10) +
        (trend_score * 0.18) +
        (75 * 0.12) # Static default structure / MA weights
    )
    
    # Hard invalidate rejections
    if status == "INVALIDATED":
        rejection_reasons.append("Zone price boundaries breached (invalidated)")
        
    return {
        "final_score": final_score,
        "authentication_score": auth_score,
        "participation_proxy_score": participation_proxy,
        "positive_reasons": positive_reasons,
        "negative_reasons": negative_reasons,
        "rejection_reasons": rejection_reasons,
        "is_rejected": len(rejection_reasons) > 0,
        "rating_class": "A+" if final_score >= 90 else "Strong" if final_score >= 80 else "Watch" if final_score >= 70 else "Reject"
    }
