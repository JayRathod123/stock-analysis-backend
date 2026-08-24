import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
from datetime import datetime
from sqlmodel import Session, select
from app.database.connection import engine
from app.database.models.models import DailyScan
from app.api.routes.stocks import get_stock_cache
from app.api.routes.analysis import run_analysis_endpoint, RunAnalysisParams
from app.ai.ollama import explain_setup_with_ollama

def main():
    print(f"[{datetime.now()}] Starting Daily Market Scan...")
    stocks = get_stock_cache()
    # For testing/demo, we scan top 50, otherwise Yahoo finance blocks us
    nse_stocks = [s for s in stocks if s.get("exchange") == "NSE"][:50]
    
    with Session(engine) as session:
        # Clear today's old scans to prevent duplicates if run twice
        today = datetime.utcnow().date()
        old_scans = session.exec(select(DailyScan)).all()
        for s in old_scans:
            if s.scan_date.date() == today:
                session.delete(s)
        session.commit()

        count = 0
        for i, s in enumerate(nse_stocks):
            symbol = s["symbol"]
            name = s.get("name", "")
            print(f"Scanning {i+1}/{len(nse_stocks)}: {symbol}...")
            
            for mode, timeframe in [("intraday", "15m"), ("swing", "1d")]:
                try:
                    params = RunAnalysisParams(symbol=symbol, timeframe=timeframe, mode=mode)
                    res = run_analysis_endpoint(params)
                    
                    if res["trade_decision"] == "TRADE":
                        setup = res["best_intraday_setup"] if mode == "intraday" else res["best_swing_setup"]
                        
                        ai_summary = "AI analysis skipped."
                        try:
                            ai_summary = explain_setup_with_ollama(setup)
                        except Exception:
                            pass
                            
                        scan = DailyScan(
                            symbol=symbol,
                            name=name,
                            setup_type=mode.upper(),
                            entry_price=setup["entry"],
                            stop_loss=setup["stop_loss"],
                            target_price=setup["target_1"],
                            score=str(setup["final_score"]),
                            ai_summary=ai_summary
                        )
                        session.add(scan)
                        session.commit()
                        count += 1
                        print(f"  -> FOUND PERFECT {mode.upper()} TRADE: {symbol}")
                except Exception as e:
                    # skip on errors (like missing data)
                    pass
            time.sleep(0.5)
            
    print(f"[{datetime.now()}] Daily Scan Complete. Found {count} perfect setups.")

if __name__ == "__main__":
    main()
