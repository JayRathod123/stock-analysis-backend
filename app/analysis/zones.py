import pandas as pd
import numpy as np
from typing import List, Dict, Any, Tuple
from app.analysis.indicators.calculations import calculate_atr

def is_base_candle(row_high, row_low, row_open, row_close, atr_value: float = 0.0) -> bool:
    """
    GTF Definition (Pages 4-5):
    - Exciting Candle: Body > 50% of total candle range (High - Low).
    - Base Candle (Boring Candle): Body < 50% of total candle range (High - Low).
    """
    hl_range = row_high - row_low
    if hl_range == 0:
        return True
    body_range = abs(row_close - row_open)
    return (body_range / hl_range) < 0.5

def detect_zones(df: pd.DataFrame, max_base_candles: int = 5) -> List[Dict[str, Any]]:
    """
    GTF Zone Detection (Pages 9-24):
    - Patterns: DBR, RBR (Demand) / RBD, DBD (Supply)
    - Base: 1-5 boring candles
    - Closing Concept (Page 24):
        - Demand: Green exciting legout closes above legin
        - Supply: Red exciting legout closes below legin
    - Normal & Exceptional Marking (Pages 11-14, 18-21):
        - Demand Proximal: Highest body of all base candles
        - Demand Distal (DBR): Lowest wick of base, legin, and legout
        - Demand Distal (RBR): Lowest wick of base and legout
        - Supply Proximal: Lowest body of all base candles
        - Supply Distal (RBD): Highest wick of base, legin, and legout
        - Supply Distal (DBD): Highest wick of base and legout
    """
    zones = []
    if len(df) < 10:
        return zones
        
    closes = df["close"].values
    opens = df["open"].values
    highs = df["high"].values
    lows = df["low"].values
    
    for i in range(1, len(df) - 2):
        for base_len in range(1, max_base_candles + 1):
            if i + base_len >= len(df) - 1:
                break
                
            base_rows = [(highs[i+k], lows[i+k], opens[i+k], closes[i+k]) for k in range(base_len)]
            
            # Check all base candles (body < 50% range)
            all_bases = True
            for br in base_rows:
                if not is_base_candle(br[0], br[1], br[2], br[3]):
                    all_bases = False
                    break
                    
            if not all_bases:
                continue
                
            legin_idx = i - 1
            legout_idx = i + base_len
            
            legin = (highs[legin_idx], lows[legin_idx], opens[legin_idx], closes[legin_idx])
            legout = (highs[legout_idx], lows[legout_idx], opens[legout_idx], closes[legout_idx])
            
            # Legin and Legout must be EXCITING candles (body > 50% range)
            if is_base_candle(legin[0], legin[1], legin[2], legin[3]) or is_base_candle(legout[0], legout[1], legout[2], legout[3]):
                continue
                
            legin_dir = "GREEN" if legin[3] > legin[2] else "RED"
            legout_dir = "GREEN" if legout[3] > legout[2] else "RED"
            
            # Important point (Page 15):
            # Demand legout MUST be green. Supply legout MUST be red.
            is_demand = legout_dir == "GREEN"
            is_supply = legout_dir == "RED"
            
            # Closing Concepts (Page 24):
            # DZ: Legout candle should be closed above legin
            # SZ: Legout candle should be closed below legin
            if is_demand and legout[3] <= legin[3]:
                continue
            if is_supply and legout[3] >= legin[3]:
                continue
                
            # Base bodies and wicks
            base_high_bodies = [max(r[2], r[3]) for r in base_rows]
            base_low_bodies = [min(r[2], r[3]) for r in base_rows]
            base_high_wicks = [r[0] for r in base_rows]
            base_low_wicks = [r[1] for r in base_rows]
            
            if is_demand:
                # Proximal: Highest body of all base (Pages 11, 13)
                price_max = max(base_high_bodies)
                pattern = "RBR" if legin_dir == "GREEN" else "DBR"
                
                # Distal with Exceptional Marking (Pages 18, 19):
                # DBR: Lowest wick of base, legin, and legout
                # RBR: Lowest wick of base and legout
                if pattern == "DBR":
                    price_min = min(min(base_low_wicks), legin[1], legout[1])
                else:
                    price_min = min(min(base_low_wicks), legout[1])
            else:
                # Proximal: Lowest body of all base (Pages 12, 14)
                price_min = min(base_low_bodies)
                pattern = "DBD" if legin_dir == "RED" else "RBD"
                
                # Distal with Exceptional Marking (Pages 20, 21):
                # RBD: Highest wick of base, legin, and legout
                # DBD: Highest wick of base and legout
                if pattern == "RBD":
                    price_max = max(max(base_high_wicks), legin[0], legout[0])
                else:
                    price_max = max(max(base_high_wicks), legout[0])
                
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

def deduplicate_zones(zones: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    GTF Level Over The Level (LOTL) (Pages 58-60):
    - Case 1 (Page 58): DBR + RBR formed consecutively on top of each other.
    - Case 2 (Page 59): RBR + RBR formed consecutively on top of each other.
    - Case 3 (Page 60): Zones formed at different times / separated are DIFFERENT ZONES.
    - Merged Demand (Pages 58-59): Entry = Proximal of upper zone, Stoploss = Distal of lower zone.
    - Merged Supply: Entry = Proximal of lower zone, Stoploss = Distal of upper zone.
    """
    if not zones:
        return []
        
    # Sort chronologically by formation time
    sorted_zones = sorted(zones, key=lambda x: x["base_end_idx"])
    merged = []
    
    i = 0
    while i < len(sorted_zones):
        curr = dict(sorted_zones[i])
        # Check if next zone is formed immediately after (consecutive in time, within 6 candles)
        if i + 1 < len(sorted_zones):
            nxt = sorted_zones[i + 1]
            time_diff = nxt["base_end_idx"] - curr["base_end_idx"]
            
            if curr["type"] == nxt["type"] and 1 <= time_diff <= 6:
                if curr["type"] == "DEMAND":
                    # Upper zone proximal, lower zone distal (Page 58)
                    price_max = max(curr["price_max"], nxt["price_max"]) # Upper proximal
                    price_min = min(curr["price_min"], nxt["price_min"]) # Lower distal
                    curr["price_max"] = price_max
                    curr["price_min"] = price_min
                    curr["pattern"] = f"{curr['pattern']} / {nxt['pattern']}"
                    curr["is_lotl"] = True
                    curr["base_end_idx"] = nxt["base_end_idx"]
                    i += 1
                else:
                    # Supply: Lower zone proximal, upper zone distal
                    price_min = min(curr["price_min"], nxt["price_min"]) # Lower proximal
                    price_max = max(curr["price_max"], nxt["price_max"]) # Upper distal
                    curr["price_min"] = price_min
                    curr["price_max"] = price_max
                    curr["pattern"] = f"{curr['pattern']} / {nxt['pattern']}"
                    curr["is_lotl"] = True
                    curr["base_end_idx"] = nxt["base_end_idx"]
                    i += 1
                    
        merged.append(curr)
        i += 1
        
    return merged

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
