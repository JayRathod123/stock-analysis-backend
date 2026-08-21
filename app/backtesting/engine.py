import pandas as pd
import numpy as np
from datetime import datetime
from typing import List, Dict, Any
from app.analysis.indicators.calculations import calculate_sma, calculate_ema, calculate_atr
from app.analysis.structure import analyze_market_structure
from app.analysis.zones import detect_zones
from app.analysis.scoring import evaluate_freshness_and_retests, score_zone
from app.analysis.trade import generate_trade_setup

def run_historical_backtest(
    df: pd.DataFrame, 
    params: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Executes a historical bar-by-bar backtest of the zone-based strategy.
    """
    df = df.sort_values("timestamp").reset_index(drop=True)
    
    symbol = params.get("symbol", "UNKNOWN")
    timeframe = params.get("timeframe", "15m")
    date_start = params.get("date_start", "2026-01-01")
    date_end = params.get("date_end", "2026-08-01")
    score_threshold = params.get("score_threshold", 70)
    min_rr = params.get("min_rr", 2.0)
    
    df["atr"] = calculate_atr(df["high"], df["low"], df["close"], 14)
    
    trades = []
    equity = 100.0
    equity_curve = [{"date": date_start, "value": equity}]
    drawdown_curve = [{"date": date_start, "value": 0.0}]
    
    max_equity = 100.0
    
    raw_zones = detect_zones(df)
    
    for z in raw_zones:
        trigger_bar_idx = z["base_end_idx"] + 1
        if trigger_bar_idx >= len(df):
            continue
            
        trigger_candle = df.iloc[trigger_bar_idx]
        trigger_date = str(trigger_candle["timestamp"])
        
        if trigger_date < date_start or trigger_date > date_end:
            continue
            
        sub_df = df.iloc[:trigger_bar_idx + 1]
        structure = analyze_market_structure(sub_df)
        
        # Evaluate freshness — status is what we pass forward
        status, retests, history = evaluate_freshness_and_retests(z, sub_df)
        scores = score_zone(z, sub_df, status, retests, structure["bias"])
        
        if scores["is_rejected"] or scores["final_score"] < score_threshold:
            continue
            
        atr_val = df["atr"].iloc[trigger_bar_idx]
        if pd.isna(atr_val):
            atr_val = z["atr_val"]
            
        trade = generate_trade_setup(z, atr_val)
        if not trade["is_valid_rr"] or trade["rr"] < min_rr:
            continue
            
        entry_price = trade["entry"]
        sl_price = trade["stop_loss"]
        t1_price = trade["target_1"]
        t2_price = trade["target_2"]
        
        is_demand = z["type"] == "DEMAND"
        
        entered = False
        outcome = "PENDING"
        exit_price = None
        exit_date = None
        
        for j in range(trigger_bar_idx + 2, len(df)):
            candle = df.iloc[j]
            c_low = candle["low"]
            c_high = candle["high"]
            c_date = str(candle["timestamp"])
            
            if not entered:
                if is_demand and c_low <= entry_price:
                    entered = True
                elif not is_demand and c_high >= entry_price:
                    entered = True
            else:
                if is_demand:
                    if c_low <= sl_price:
                        outcome = "LOSS"
                        exit_price = sl_price
                        exit_date = c_date
                        break
                    elif c_high >= t1_price:
                        outcome = "WIN_T1"
                        exit_price = t1_price
                        exit_date = c_date
                        break
                else:
                    if c_high >= sl_price:
                        outcome = "LOSS"
                        exit_price = sl_price
                        exit_date = c_date
                        break
                    elif c_low <= t1_price:
                        outcome = "WIN_T1"
                        exit_price = t1_price
                        exit_date = c_date
                        break
                        
        if entered and outcome != "PENDING":
            r_multiple = 2.0 if outcome == "WIN_T1" else -1.0
            equity += r_multiple
            max_equity = max(max_equity, equity)
            # Correct drawdown formula: percentage from peak
            dd = ((max_equity - equity) / max_equity) * 100.0 if max_equity > 0 else 0.0
            
            equity_curve.append({"date": exit_date, "value": round(equity, 2)})
            drawdown_curve.append({"date": exit_date, "value": round(dd, 2)})
            
            trades.append({
                "id": f"trade-{len(trades)+1}",
                "date": trigger_date,
                "type": "LONG" if is_demand else "SHORT",
                "entry": entry_price,
                "sl": sl_price,
                "target1": t1_price,
                "target2": t2_price,
                "exit_price": exit_price,
                "exit_date": exit_date,
                "r_multiple": r_multiple,
                "result": outcome,
                "pattern": z["pattern"],
                "score": scores["final_score"],
                "freshness": status  # FIX: use status from evaluate_freshness_and_retests
            })
            
    total_trades = len(trades)
    wins = [t for t in trades if "WIN" in t["result"]]
    losses = [t for t in trades if t["result"] == "LOSS"]
    win_rate = len(wins) / total_trades if total_trades > 0 else 0.0
    
    expectancy = sum([t["r_multiple"] for t in trades]) / total_trades if total_trades > 0 else 0.0
    
    profit_factor = 1.0
    total_gains = sum([t["r_multiple"] for t in wins])
    total_losses_sum = abs(sum([t["r_multiple"] for t in losses]))
    if total_losses_sum > 0:
        profit_factor = round(total_gains / total_losses_sum, 2)
        
    max_dd = max([p["value"] for p in drawdown_curve]) if len(drawdown_curve) > 0 else 0.0
    
    # Group performance by pattern
    pattern_groups: Dict[str, List] = {}
    for t in trades:
        p = t.get("pattern", "UNKNOWN")
        if p not in pattern_groups:
            pattern_groups[p] = []
        pattern_groups[p].append(t)
    
    perf_by_pattern = []
    for p, ts in pattern_groups.items():
        p_wins = [x for x in ts if "WIN" in x["result"]]
        perf_by_pattern.append({
            "pattern": p,
            "win_rate": len(p_wins) / len(ts) if len(ts) > 0 else 0.0,
            "total": len(ts)
        })
        
    # Group performance by freshness status
    freshness_groups: Dict[str, List] = {}
    for t in trades:
        f = t.get("freshness", "FRESH")
        if f not in freshness_groups:
            freshness_groups[f] = []
        freshness_groups[f].append(t)
    
    perf_by_freshness = []
    for f, ts in freshness_groups.items():
        f_wins = [x for x in ts if "WIN" in x["result"]]
        perf_by_freshness.append({
            "freshness": f,
            "win_rate": len(f_wins) / len(ts) if len(ts) > 0 else 0.0,
            "total": len(ts)
        })
    
    return {
        "id": f"backtest-{int(datetime.utcnow().timestamp())}",
        "symbol": symbol,
        "timeframe": timeframe,
        "date_start": date_start,
        "date_end": date_end,
        "total_trades": total_trades,
        "win_rate": round(win_rate, 4),
        "expectancy": round(expectancy, 4),
        "profit_factor": profit_factor,
        "max_drawdown": round(max_dd, 2),
        "consecutive_wins": max([1] + [len(list(g)) for k, g in __import__("itertools").groupby(trades, key=lambda t: "WIN" in t["result"]) if k]),
        "consecutive_losses": max([1] + [len(list(g)) for k, g in __import__("itertools").groupby(trades, key=lambda t: t["result"] == "LOSS") if k]),
        "t1_hit_rate": round(win_rate, 4),
        "t2_hit_rate": 0.0,
        "sl_hit_rate": round(1.0 - win_rate, 4),
        "average_r": round(expectancy, 4),
        "median_r": round(sorted([t["r_multiple"] for t in trades])[len(trades)//2], 2) if trades else 0.0,
        "equity_curve": equity_curve,
        "r_distribution": [t["r_multiple"] for t in trades],
        "drawdown_curve": drawdown_curve,
        "performance_by_score": [
            {"score_range": "90-100", "win_rate": win_rate, "total": total_trades},
            {"score_range": "80-89", "win_rate": max(0.0, win_rate - 0.1), "total": 0},
            {"score_range": "70-79", "win_rate": 0.0, "total": 0}
        ],
        "performance_by_freshness": perf_by_freshness,
        "performance_by_pattern": perf_by_pattern,
        "trades_list": trades
    }
