from fastapi import APIRouter
from typing import List, Dict, Any
import asyncio
from concurrent.futures import ThreadPoolExecutor

from app.api.routes.analysis import run_analysis_endpoint, RunAnalysisParams

router = APIRouter()

# Top 50 highly liquid Nifty stocks
NIFTY_50 = [
    "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY", 
    "ITC", "SBIN", "BHARTIARTL", "BAJFINANCE", "LART", 
    "HINDUNILVR", "AXISBANK", "KOTAKBANK", "MARUTI", "SUNPHARMA", 
    "TATAMOTORS", "ASIANPAINT", "NTPC", "TITAN", "ULTRACEMCO",
    "TATASTEEL", "POWERGRID", "M&M", "WIPRO", "HCLTECH",
    "BAJAJFINSV", "NESTLEIND", "ONGC", "JSWSTEEL", "ADANIENT",
    "ADANIPORTS", "HDFCLIFE", "COALINDIA", "GRASIM", "TECHM",
    "SBILIFE", "BAJAJ-AUTO", "HINDALCO", "DRREDDY", "TATACONSUM",
    "INDUSINDBK", "CIPLA", "APOLLOHOSP", "BRITANNIA", "EICHERMOT",
    "BPCL", "HEROMOTOCO", "DIVISLAB", "LTIM"
]

def process_stock(symbol: str, mode: str) -> Dict[str, Any]:
    try:
        # Default timeframes (handled inside run_analysis_endpoint correctly now)
        if mode == "intraday": timeframe = "15m"
        elif mode == "swing": timeframe = "125m"
        elif mode == "scalping": timeframe = "5m"
        else: timeframe = "15m"
        params = RunAnalysisParams(symbol=symbol, timeframe=timeframe, mode=mode)
        analysis = run_analysis_endpoint(params)
        
        valid_setups = []
        # Filter setups from analysis
        if mode == "intraday":
            zones = analysis.get("intraday_zones", [])
        elif mode == "swing":
            zones = analysis.get("swing_zones", [])
        elif mode == "scalping":
            zones = analysis.get("scalping_zones", [])
        else:
            zones = []
        for z in zones:
            # 1.5% proximity filter
            entry_price = z.get("entry", 0)
            current_price = analysis["current_price"]
            if entry_price > 0:
                proximity = abs(entry_price - current_price) / current_price * 100
                if z.get("final_score", 0) >= 6 and proximity <= 1.5:
                    z["proximity_pct"] = proximity
                    valid_setups.append(z)
                    
        if valid_setups:
            return {
                "symbol": symbol,
                "current_price": analysis["current_price"],
                "setups": valid_setups
            }
    except Exception as e:
        print(f"Error scanning {symbol}: {e}")
        pass
    return None

@router.get("/todays-trades")
async def screen_todays_trades(mode: str = "intraday"):
    '''
    Scans Nifty 50 stocks in parallel for 6/7 or 7/7 GTF setups within 1.5% proximity.
    '''
    loop = asyncio.get_event_loop()
    
    # Process up to 10 stocks concurrently to avoid massive rate limits from YFinance
    with ThreadPoolExecutor(max_workers=5) as executor:
        tasks = [
            loop.run_in_executor(executor, process_stock, symbol, mode)
            for symbol in NIFTY_50
        ]
        results = await asyncio.gather(*tasks)
        
    trades = [r for r in results if r is not None]
    
    return {
        "count": len(trades),
        "mode": mode,
        "scanned": len(NIFTY_50),
        "trades": trades
    }

