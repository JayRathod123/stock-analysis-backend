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
        
    if is_demand:
        entry = p_max # Proximal line
        sl = p_min # Distal line
        risk = entry - sl
            
        # Target 1 (1:3 R:R), Target 2 (1:5 R:R)
        t1 = entry + 3.0 * risk
        t2 = entry + 5.0 * risk
        reward = t1 - entry
    else:
        entry = p_min # Proximal line
        sl = p_max # Distal line
        risk = sl - entry
            
        t1 = entry - 3.0 * risk
        t2 = entry - 5.0 * risk
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
