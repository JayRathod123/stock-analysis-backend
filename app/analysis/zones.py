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
    zones = []
    if len(df) < 10:
        return zones
        
    closes = df["close"]
    opens = df["open"]
    highs = df["high"]
    lows = df["low"]
    
    from app.analysis.indicators.calculations import calculate_atr
    atr = calculate_atr(highs, lows, closes, 14)
    
    for i in range(1, len(df) - 2):
        atr_val = atr.iloc[i] if not pd.isna(atr.iloc[i]) else (highs.iloc[i] - lows.iloc[i])
        if atr_val == 0:
            atr_val = 1.0
            
        for base_len in range(1, max_base_candles + 1):
            if i + base_len >= len(df) - 1:
                break
                
            base_rows = [df.iloc[i + k] for k in range(base_len)]
            
            all_bases = True
            for br in base_rows:
                if not is_base_candle(br, atr_val):
                    all_bases = False
                    break
                    
            if not all_bases:
                continue
                
            legin_idx = i - 1
            legout_idx = i + base_len
            
            legin = df.iloc[legin_idx]
            legout = df.iloc[legout_idx]
            
            if is_base_candle(legin, atr_val) or is_base_candle(legout, atr_val):
                continue
                
            legin_range = legin["high"] - legin["low"]
            legout_range = legout["high"] - legout["low"]
            
            legin_dir = "GREEN" if legin["close"] > legin["open"] else "RED"
            legout_dir = "GREEN" if legout["close"] > legout["open"] else "RED"
            
            # GTF Closing Concepts (Page 24)
            # Demand: Legout MUST close above legin. Supply: Legout MUST close below legin.
            
            is_demand = legout_dir == "GREEN"
            is_supply = legout_dir == "RED"
            
            if is_demand and legout["close"] <= legin["close"]:
                continue # Fails closing concept
            if is_supply and legout["close"] >= legin["close"]:
                continue # Fails closing concept
                
            # Zone Marking (Page 11-12)
            # Demand Proximal: Highest body of all base. Distal: Lowest wick of all base.
            # Supply Proximal: Lowest body of all base. Distal: Highest wick of all base.
            base_high_bodies = [max(r["open"], r["close"]) for r in base_rows]
            base_low_bodies = [min(r["open"], r["close"]) for r in base_rows]
            base_high_wicks = [r["high"] for r in base_rows]
            base_low_wicks = [r["low"] for r in base_rows]
            
            if is_demand:
                price_max = max(base_high_bodies) # Proximal
                price_min = min(base_low_wicks) # Distal
                pattern = "RBR" if legin_dir == "GREEN" else "DBR"
            else:
                price_min = min(base_low_bodies) # Proximal
                price_max = max(base_high_wicks) # Distal
                pattern = "DBD" if legin_dir == "RED" else "RBD"
                
            zones.append({
                "type": "DEMAND" if is_demand else "SUPPLY",
                "pattern": pattern,
                "price_min": price_min,
                "price_max": price_max,
                "base_candles": base_len,
                "departure_strength": "STRONG",
                "base_end_idx": legout_idx - 1,
            })
            
    return zones

def deduplicate_zones(zones: List[Dict[str, Any]], threshold_pct: float = 0.02) -> List[Dict[str, Any]]:
    if not zones:
        return []
    demands = sorted([z for z in zones if z["type"] == "DEMAND"], key=lambda x: x["price_max"])
    supplies = sorted([z for z in zones if z["type"] == "SUPPLY"], key=lambda x: x["price_min"])
    
    def merge_group(group: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not group:
            return []
        merged = []
        current = group[0]
        for next_zone in group[1:]:
            price_ref = current["price_max"] if current["type"] == "DEMAND" else current["price_min"]
            price_next = next_zone["price_max"] if next_zone["type"] == "DEMAND" else next_zone["price_min"]
            diff_pct = abs(price_ref - price_next) / price_ref if price_ref > 0 else 0
            if diff_pct <= threshold_pct:
                if current["type"] == "DEMAND":
                    current["price_min"] = min(current["price_min"], next_zone["price_min"])
                    current["price_max"] = max(current["price_max"], next_zone["price_max"])
                else:
                    current["price_min"] = min(current["price_min"], next_zone["price_min"])
                    current["price_max"] = max(current["price_max"], next_zone["price_max"])
                if next_zone['pattern'] not in current['pattern']:
                    current["pattern"] = f"{current['pattern']} / {next_zone['pattern']}"
            else:
                merged.append(current)
                current = next_zone
        merged.append(current)
        return merged

    return merge_group(demands) + merge_group(supplies)
