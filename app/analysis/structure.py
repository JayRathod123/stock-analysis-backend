import pandas as pd
import numpy as np
from typing import List, Dict, Any, Tuple
from app.analysis.zones import detect_zones

def detect_swings(high: pd.Series, low: pd.Series, window: int = 2) -> Tuple[pd.Series, pd.Series]:
    """
    Detects swing highs and swing lows.
    A candle is a swing high if its high is higher than N surrounding candles.
    """
    swing_highs = pd.Series(index=high.index, dtype=float)
    swing_lows = pd.Series(index=low.index, dtype=float)
    
    high_vals = high.values
    low_vals = low.values
    
    for i in range(window, len(high) - window):
        # Swing High
        is_high = True
        for w in range(1, window + 1):
            if high_vals[i] <= high_vals[i - w] or high_vals[i] <= high_vals[i + w]:
                is_high = False
                break
        if is_high:
            swing_highs.iloc[i] = high_vals[i]
            
        # Swing Low
        is_low = True
        for w in range(1, window + 1):
            if low_vals[i] >= low_vals[i - w] or low_vals[i] >= low_vals[i + w]:
                is_low = False
                break
        if is_low:
            swing_lows.iloc[i] = low_vals[i]
            
    return swing_highs, swing_lows

def analyze_market_structure(df: pd.DataFrame, window: int = 2) -> Dict[str, Any]:
    """
    Calculates trend bias using GTF Advanced Trend Analysis (Zone breaches).
    """
    if len(df) < 10:
        return {
            "bias": "NEUTRAL",
            "structure": "CONSOLIDATION"
        }
        
    zones = detect_zones(df)
    zones = sorted(zones, key=lambda z: z["base_end_idx"])
    
    supply_breaches = 0
    demand_breaches = 0
    
    close_vals = df["close"].values
    
    for z in zones:
        end_idx = z["base_end_idx"]
        breached = False
        for i in range(end_idx + 1, len(df)):
            if z["type"] == "DEMAND" and close_vals[i] < z["price_min"]:
                breached = True
                break
            elif z["type"] == "SUPPLY" and close_vals[i] > z["price_max"]:
                breached = True
                break
                
        if breached:
            if z["type"] == "DEMAND":
                demand_breaches += 1
                supply_breaches = 0 # reset opposite
            else:
                supply_breaches += 1
                demand_breaches = 0
                
    bias = "NEUTRAL"
    if supply_breaches >= 2:
        bias = "UPTREND"
    elif demand_breaches >= 2:
        bias = "DOWNTREND"
    elif supply_breaches == 1 or demand_breaches == 1:
        bias = "SIDEWAYS"
        
    return {
        "bias": bias,
        "structure": bias
    }

def evaluate_curve(df_htf: pd.DataFrame, current_price: float) -> str:
    zones = detect_zones(df_htf)
    
    htf_supplies = [z for z in zones if z["type"] == "SUPPLY" and z["price_min"] > current_price]
    htf_demands = [z for z in zones if z["type"] == "DEMAND" and z["price_max"] < current_price]
    
    closest_supply = min(htf_supplies, key=lambda x: x["price_min"])["price_min"] if htf_supplies else None
    closest_demand = max(htf_demands, key=lambda x: x["price_max"])["price_max"] if htf_demands else None
    
    if not closest_supply or not closest_demand:
        return "EQUILIBRIUM" # Cannot determine full curve
        
    curve_range = closest_supply - closest_demand
    price_position = current_price - closest_demand
    
    position_pct = price_position / curve_range
    
    if position_pct > 0.66:
        return "HIGH"
    elif position_pct < 0.33:
        return "LOW"
    else:
        return "EQUILIBRIUM"

def detect_market_traps(df: pd.DataFrame, zones: List[Dict[str, Any]], window: int = 5) -> List[Dict[str, Any]]:
    """
    Identifies Bull Traps (resistance just below supply) and Bear Traps (support just above demand).
    """
    highs = df["high"]
    lows = df["low"]
    swing_highs, swing_lows = detect_swings(highs, lows, window)
    
    sh_vals = swing_highs.dropna().values
    sl_vals = swing_lows.dropna().values
    
    for z in zones:
        z["trap_type"] = "NONE"
        if z["type"] == "SUPPLY":
            # Check if there is a swing high just below the supply zone (within 1%)
            for sh in sh_vals:
                if sh < z["price_min"] and (z["price_min"] - sh) / z["price_min"] < 0.01:
                    z["trap_type"] = "BULL_TRAP"
                    break
        else:
            # Check if there is a swing low just above the demand zone (within 1%)
            for sl in sl_vals:
                if sl > z["price_max"] and (sl - z["price_max"]) / z["price_max"] < 0.01:
                    z["trap_type"] = "BEAR_TRAP"
                    break
    return zones
