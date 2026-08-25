import pandas as pd
import numpy as np
from typing import List, Dict, Any, Tuple
from app.analysis.indicators.calculations import calculate_atr

def is_base_candle(row_high, row_low, row_open, row_close, atr_value: float) -> bool:
    """
    Identifies if a candle is a base candle.
    A base candle is defined by its body range being small relative to the high-low range,
    and its overall range being narrow.
    """
    hl_range = row_high - row_low
    body_range = abs(row_close - row_open)
    
    if hl_range == 0:
        return True
        
    body_pct = body_range / hl_range
    # Body is less than 50% of the high-low range or range is smaller than ATR
    return body_pct < 0.5 or hl_range < (0.8 * atr_value)

def detect_zones(df: pd.DataFrame, max_base_candles: int = 6) -> List[Dict[str, Any]]:
    zones = []
    if len(df) < 10:
        return zones
        
    closes = df["close"].values
    opens = df["open"].values
    highs = df["high"].values
    lows = df["low"].values
    atr = calculate_atr(df["high"], df["low"], df["close"], 14)
    
    for i in range(1, len(df) - 2):
        atr_val = atr.iloc[i] if not pd.isna(atr.iloc[i]) else (highs[i] - lows[i])
        if atr_val == 0:
            atr_val = 1.0
            
        for base_len in range(1, max_base_candles + 1):
            if i + base_len >= len(df) - 1:
                break
                
            base_rows = [(highs[i+k], lows[i+k], opens[i+k], closes[i+k]) for k in range(base_len)]
            
            all_bases = True
            for br in base_rows:
                if not is_base_candle(br[0], br[1], br[2], br[3], atr_val):
                    all_bases = False
                    break
                    
            if not all_bases:
                continue
                
            legin_idx = i - 1
            legout_idx = i + base_len
            
            legin = (highs[legin_idx], lows[legin_idx], opens[legin_idx], closes[legin_idx])
            legout = (highs[legout_idx], lows[legout_idx], opens[legout_idx], closes[legout_idx])
            
            if is_base_candle(legin[0], legin[1], legin[2], legin[3], atr_val) or is_base_candle(legout[0], legout[1], legout[2], legout[3], atr_val):
                continue
                
            legin_range = legin[0] - legin[1]
            legout_range = legout[0] - legout[1]
            
            legin_dir = "GREEN" if legin[3] > legin[2] else "RED"
            legout_dir = "GREEN" if legout[3] > legout[2] else "RED"
            
            # GTF Closing Concepts (Page 24)
            # Demand: Legout MUST close above legin. Supply: Legout MUST close below legin.
            
            is_demand = legout_dir == "GREEN"
            is_supply = legout_dir == "RED"
            
            if is_demand and legout[3] <= legin[3]:
                continue # Fails closing concept
            if is_supply and legout[3] >= legin[3]:
                continue # Fails closing concept
                
            # Zone Marking (Page 11-12)
            # Demand Proximal: Highest body of all base. Distal: Lowest wick of all base.
            # Supply Proximal: Lowest body of all base. Distal: Highest wick of all base.
            base_high_bodies = [max(r[2], r[3]) for r in base_rows]
            base_low_bodies = [min(r[2], r[3]) for r in base_rows]
            base_high_wicks = [r[0] for r in base_rows]
            base_low_wicks = [r[1] for r in base_rows]
            
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
                "is_lotl": False,
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
            
            # Calculate what the new width would be if merged
            new_min = min(current["price_min"], next_zone["price_min"])
            new_max = max(current["price_max"], next_zone["price_max"])
            new_width_pct = (new_max - new_min) / new_min if new_min > 0 else 0
            
            # Merge if within threshold AND the resulting zone isn't absurdly massive (> 4% wide)
            if diff_pct <= threshold_pct and new_width_pct <= 0.04:
                current["price_min"] = new_min
                current["price_max"] = new_max
                if next_zone['pattern'] not in current['pattern']:
                    current["pattern"] = f"{current['pattern']} / {next_zone['pattern']}"
                current["is_lotl"] = True
            else:
                merged.append(current)
                current = next_zone
        merged.append(current)
        return merged

    return merge_group(demands) + merge_group(supplies)

def flag_reaction_zones(zones: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    sorted_zones = sorted(zones, key=lambda z: z["base_end_idx"])
    for i in range(len(sorted_zones)):
        sorted_zones[i]["is_reaction"] = False
        z1 = sorted_zones[i]
        for j in range(i):
            z2 = sorted_zones[j]
            if z1["price_min"] >= z2["price_min"] and z1["price_max"] <= z2["price_max"]:
                sorted_zones[i]["is_reaction"] = True
                break
    return sorted_zones
