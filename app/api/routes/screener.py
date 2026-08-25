from fastapi import APIRouter
from typing import List, Dict, Any
import asyncio
from concurrent.futures import ThreadPoolExecutor

from app.api.routes.analysis import run_analysis_endpoint, RunAnalysisParams

router = APIRouter()

# Top 50 highly liquid Nifty stocks
NIFTY_50 = [
    "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY", 
    "ITC", "SBIN", "BHARTIARTL", "BAJFINANCE", "LT", 
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
                if mode == "swing": max_prox = 4.0
                elif mode == "scalping": max_prox = 1.0
                else: max_prox = 1.5
                if z.get("final_score", 0) >= 5 and proximity <= max_prox:
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
    
    # Preload all data into the memory cache simultaneously using a thread pool
    from app.data.providers.yahoo_finance import preload_candles
    
    # We always fetch LTF, ITF, HTF depending on the mode. Let's just preload the required ones.
    if mode == "intraday":
        await loop.run_in_executor(None, preload_candles, NIFTY_50, ["15m", "75m", "1d"])
    elif mode == "swing":
        await loop.run_in_executor(None, preload_candles, NIFTY_50, ["125m", "1d", "1W"])
    elif mode == "scalping":
        await loop.run_in_executor(None, preload_candles, NIFTY_50, ["5m", "15m", "75m"])
    else:
        await loop.run_in_executor(None, preload_candles, NIFTY_50, ["5m", "15m", "75m", "125m", "1d", "1W", "1mo"])

    # Process up to 25 stocks concurrently now that data is cached
    with ThreadPoolExecutor(max_workers=25) as executor:
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

