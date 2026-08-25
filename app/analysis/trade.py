from typing import Dict, Any, Tuple

def generate_trade_setup(
    zone: Dict[str, Any], 
    atr_val: float
) -> Dict[str, Any]:
    """
    Calculates Entry, Stop Loss (SL), Target 1 (T1), Target 2 (T2) and R:R ratios.
    """
    is_demand = zone["type"] == "DEMAND"
    p_min = zone["price_min"]
    p_max = zone["price_max"]
        
    buffer = atr_val * 0.1
    if is_demand:
        entry = p_max + buffer # Just above proximal line
        sl = p_min - buffer # Just below distal line
        risk = entry - sl
            
        # Target 1 (1:2 R:R), Target 2 (1:3 R:R)
        t1 = entry + 2.0 * risk
        t2 = entry + 3.0 * risk
        reward = t1 - entry
    else:
        entry = p_min - buffer # Just below proximal line
        sl = p_max + buffer # Just above distal line
        risk = sl - entry
            
        t1 = entry - 2.0 * risk
        t2 = entry - 3.0 * risk
        reward = entry - t1
        
    rr = reward / risk if risk > 0 else 0
    
    # Validation checks
    is_valid = rr >= 1.9 # Check for min 1:2 R:R
    
    return {
        "entry": entry,
        "stop_loss": sl,
        "target_1": t1,
        "target_2": t2,
        "risk": risk,
        "reward": reward,
        "rr": rr,
        "is_valid_rr": is_valid,
        "status": "WAITING FOR PRICE" if is_valid else "REJECTED_RR"
    }
