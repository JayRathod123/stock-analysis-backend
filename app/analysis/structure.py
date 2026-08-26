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

def calculate_50_sma_trend(df: pd.DataFrame) -> str:
    """
    GTF 50 SMA Trend Rule (Pages 27-28):
    1. Calculate 50 SMA on price chart.
    2. Starting from current candle, count 7 candles backwards.
    3. Determine slope between 50 SMA at 7 candles ago and current 50 SMA.
       - 12 to 3 on clock (Positive slope > 0.05%) -> Trend is UP.
       - 3 to 6 on clock (Negative slope < -0.05%) -> Trend is DOWN.
       - Close to 3 (Flat / horizontal) -> Trend is SIDEWAYS.
    """
    if len(df) < 57:
        return "SIDEWAYS"
        
    sma50 = df["close"].rolling(50).mean()
    curr_sma = sma50.iloc[-1]
    sma_7_ago = sma50.iloc[-8]
    
    if pd.isna(curr_sma) or pd.isna(sma_7_ago) or sma_7_ago == 0:
        return "SIDEWAYS"
        
    change_pct = (curr_sma - sma_7_ago) / sma_7_ago * 100
    
    if change_pct > 0.1:
        return "UPTREND"
    elif change_pct < -0.1:
        return "DOWNTREND"
    else:
        return "SIDEWAYS"

def analyze_market_structure(df: pd.DataFrame) -> Dict[str, Any]:
    """
    GTF Combined Trend Analysis (Pages 27-28 & Page 42):
    - 50 SMA Slope (7-candles back)
    - Advanced Zone Breaches:
        - 2 supply breached -> Trend UP
        - 2 demand breached -> Trend DOWN
        - 1 breached -> Trend SIDEWAYS
    """
    if len(df) < 10:
        return {
            "bias": "NEUTRAL",
            "structure": "CONSOLIDATION"
        }
        
    sma_bias = calculate_50_sma_trend(df)
    
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
                supply_breaches = 0
            else:
                supply_breaches += 1
                demand_breaches = 0
                
    if supply_breaches >= 2:
        breach_bias = "UPTREND"
    elif demand_breaches >= 2:
        breach_bias = "DOWNTREND"
    elif supply_breaches == 1 or demand_breaches == 1:
        breach_bias = "SIDEWAYS"
    else:
        breach_bias = "NEUTRAL"
        
    # Prefer explicit breach bias if established; otherwise fallback to 50 SMA slope
    final_bias = breach_bias if breach_bias != "NEUTRAL" else sma_bias
    
    return {
        "bias": final_bias,
        "structure": final_bias,
        "sma_bias": sma_bias,
        "breach_bias": breach_bias
    }

def evaluate_curve(df_htf: pd.DataFrame, current_price: float) -> str:
    """
    GTF Curve Analysis / Location Analysis (Pages 30-33):
    1. Mark nearest fresh supply & demand on HTF.
    2. Divide area between proximal supply and proximal demand into 3 parts (Retracement Tool):
       - Top 1/3 (66.6% - 100%): VERY HIGH / HIGH on curve
       - Middle 1/3 (33.3% - 66.6%): EQUILIBRIUM
       - Bottom 1/3 (0% - 33.3%): LOW / VERY LOW on curve
    Note (Page 33): If one side is missing, assume EQUILIBRIUM.
    """
    zones = detect_zones(df_htf)
    
    # Nearest fresh HTF Supply above current price
    htf_supplies = [z for z in zones if z["type"] == "SUPPLY" and z["price_min"] > current_price]
    # Nearest fresh HTF Demand below current price
    htf_demands = [z for z in zones if z["type"] == "DEMAND" and z["price_max"] < current_price]
    
    closest_supply = min(htf_supplies, key=lambda x: x["price_min"])["price_min"] if htf_supplies else None
    closest_demand = max(htf_demands, key=lambda x: x["price_max"])["price_max"] if htf_demands else None
    
    if not closest_supply or not closest_demand:
        # Note on Page 33: If there is no fresh supply or no fresh demand, assume EQUILIBRIUM
        return "EQUILIBRIUM"
        
    curve_range = closest_supply - closest_demand
    if curve_range <= 0:
        return "EQUILIBRIUM"
        
    price_position = current_price - closest_demand
    position_pct = price_position / curve_range
    
    if position_pct > 0.666:
        return "HIGH"
    elif position_pct < 0.333:
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
