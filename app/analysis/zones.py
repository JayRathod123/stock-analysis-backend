import pandas as pd
import numpy as np
from typing import List, Dict, Any, Tuple

def is_base_candle(row: pd.Series, atr_value: float) -> bool:
    """
    Identifies if a candle is a base candle.
    A base candle is defined by its body range being small relative to the high-low range,
    and its overall range being narrow.
    """
    hl_range = row["high"] - row["low"]
    body_range = abs(row["close"] - row["open"])
    
    if hl_range == 0:
        return True
        
    body_pct = body_range / hl_range
    # Body is less than 50% of the high-low range or range is smaller than ATR
    return body_pct < 0.5 or hl_range < (0.8 * atr_value)

def detect_zones(df: pd.DataFrame, max_base_candles: int = 6) -> List[Dict[str, Any]]:
    """
    Scans the candle series and returns a list of detected Supply and Demand zones.
    """
    zones = []
    if len(df) < 10:
        return zones
        
    closes = df["close"]
    opens = df["open"]
    highs = df["high"]
    lows = df["low"]
    
    # Calculate ATR 14
    from app.analysis.indicators.calculations import calculate_atr
    atr = calculate_atr(highs, lows, closes, 14)
    
    for i in range(1, len(df) - 2):
        atr_val = atr.iloc[i] if not pd.isna(atr.iloc[i]) else (highs.iloc[i] - lows.iloc[i])
        if atr_val == 0:
            atr_val = 1.0
            
        # Check potential base candle sequences starting at index i
        for base_len in range(1, max_base_candles + 1):
            if i + base_len >= len(df) - 1:
                break
                
            base_rows = [df.iloc[i + k] for k in range(base_len)]
            
            # Verify all base candles fit the base criteria
            all_base = True
            for r in base_rows:
                if not is_base_candle(r, atr_val):
                    all_base = False
                    break
                    
            if not all_base:
                continue
                
            # Check candles before and after the base zone
            prev_candle = df.iloc[i - 1]
            next_candle = df.iloc[i + base_len]
            
            # Calculations for directional movements
            prev_body = prev_candle["close"] - prev_candle["open"]
            next_body = next_candle["close"] - next_candle["open"]
            
            # Demand Pattern: DBR (Drop-Base-Rally) or RBR (Rally-Base-Rally)
            # Departure must be strong (next body must be positive and substantial)
            if next_body > 1.5 * atr_val:
                is_demand = False
                pattern = ""
                
                if prev_body < -1.0 * atr_val:
                    is_demand = True
                    pattern = "DBR"
                elif prev_body > 1.0 * atr_val:
                    is_demand = True
                    pattern = "RBR"
                    
                if is_demand:
                    # Boundary calculations
                    base_highs = [r["high"] for r in base_rows]
                    base_lows = [r["low"] for r in base_rows]
                    base_bodies_top = [max(r["open"], r["close"]) for r in base_rows]
                    
                    proximal = max(base_bodies_top) # Conservative: top of bodies
                    distal = min(base_lows) # Bottom of wicks
                    
                    zones.append({
                        "type": "DEMAND",
                        "pattern": pattern,
                        "price_min": distal,
                        "price_max": proximal,
                        "base_candles": base_len,
                        "base_start_idx": i,
                        "base_end_idx": i + base_len - 1,
                        "departure_strength": "STRONG" if next_body > 2.5 * atr_val else "WEAK",
                        "atr_val": atr_val
                    })
                    
            # Supply Pattern: RBD (Rally-Base-Drop) or DBD (Drop-Base-Drop)
            # Departure must be strong negative
            elif next_body < -1.5 * atr_val:
                is_supply = False
                pattern = ""
                
                if prev_body > 1.0 * atr_val:
                    is_supply = True
                    pattern = "RBD"
                elif prev_body < -1.0 * atr_val:
                    is_supply = True
                    pattern = "DBD"
                    
                if is_supply:
                    base_highs = [r["high"] for r in base_rows]
                    base_lows = [r["low"] for r in base_rows]
                    base_bodies_bottom = [min(r["open"], r["close"]) for r in base_rows]
                    
                    proximal = min(base_bodies_bottom) # Bottom of bodies
                    distal = max(base_highs) # Top of wicks
                    
                    zones.append({
                        "type": "SUPPLY",
                        "pattern": pattern,
                        "price_min": proximal,
                        "price_max": distal,
                        "base_candles": base_len,
                        "base_start_idx": i,
                        "base_end_idx": i + base_len - 1,
                        "departure_strength": "STRONG" if abs(next_body) > 2.5 * atr_val else "WEAK",
                        "atr_val": atr_val
                    })
                    
    return zones
