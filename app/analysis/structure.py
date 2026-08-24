import pandas as pd
import numpy as np
from typing import List, Dict, Any, Tuple

def detect_swings(high: pd.Series, low: pd.Series, window: int = 2) -> Tuple[pd.Series, pd.Series]:
    """
    Detects swing highs and swing lows.
    A candle is a swing high if its high is higher than N surrounding candles.
    """
    swing_highs = pd.Series(index=high.index, dtype=float)
    swing_lows = pd.Series(index=low.index, dtype=float)
    
    for i in range(window, len(high) - window):
        # Swing High
        is_high = True
        for w in range(1, window + 1):
            if high.iloc[i] <= high.iloc[i - w] or high.iloc[i] <= high.iloc[i + w]:
                is_high = False
                break
        if is_high:
            swing_highs.iloc[i] = high.iloc[i]
            
        # Swing Low
        is_low = True
        for w in range(1, window + 1):
            if low.iloc[i] >= low.iloc[i - w] or low.iloc[i] >= low.iloc[i + w]:
                is_low = False
                break
        if is_low:
            swing_lows.iloc[i] = low.iloc[i]
            
    return swing_highs, swing_lows

def analyze_market_structure(df: pd.DataFrame, window: int = 2) -> Dict[str, Any]:
    """
    Calculates swing points, BOS, CHoCH, and trend bias.
    """
    if len(df) < 10:
        return {
            "bias": "NEUTRAL",
            "structure": "CONSOLIDATION",
            "swings_high": [],
            "swings_low": [],
            "bos_count": 0,
            "choch_detected": False
        }
        
    highs = df["high"]
    lows = df["low"]
    closes = df["close"]
    
    swing_highs, swing_lows = detect_swings(highs, lows, window)
    
    sh_indices = swing_highs.dropna().index.tolist()
    sl_indices = swing_lows.dropna().index.tolist()
    
    bias = "NEUTRAL"
    structure = "CONSOLIDATION"
    bos_count = 0
    choch_detected = False
    
    if len(sh_indices) >= 2 and len(sl_indices) >= 2:
        last_sh = swing_highs.loc[sh_indices[-1]]
        prev_sh = swing_highs.loc[sh_indices[-2]]
        
        last_sl = swing_lows.loc[sl_indices[-1]]
        prev_sl = swing_lows.loc[sl_indices[-2]]
        
        if last_sh > prev_sh and last_sl > prev_sl:
            bias = "BULLISH"
            structure = "UPTREND"
        elif last_sh < prev_sh and last_sl < prev_sl:
            bias = "BEARISH"
            structure = "DOWNTREND"
            
        last_close = closes.iloc[-1]
        if last_close > last_sh:
            bos_count += 1
            if bias == "BEARISH":
                choch_detected = True
                bias = "BULLISH"
        elif last_close < last_sl:
            bos_count += 1
            if bias == "BULLISH":
                choch_detected = True
                bias = "BEARISH"
                
    return {
        "bias": bias,
        "structure": structure,
        "swings_high": sh_indices,
        "swings_low": sl_indices,
        "bos_count": bos_count,
        "choch_detected": choch_detected
    }

def evaluate_curve(df_htf: pd.DataFrame, current_price: float) -> str:
    from app.analysis.zones import detect_zones
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
