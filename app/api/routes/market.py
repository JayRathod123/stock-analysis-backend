from fastapi import APIRouter, Depends
from typing import List, Dict, Any
from datetime import datetime
from sqlmodel import Session, select

from app.database.connection import get_session
from app.database.models.models import DailyScan

router = APIRouter()

@router.get("/scan")
def scan_market(session: Session = Depends(get_session)):
    """
    Returns ALL perfect 14/14 trades found in today's daily database scan.
    """
    today = datetime.utcnow().date()
    
    # Query all trades scanned today
    scans = session.exec(select(DailyScan)).all()
    # Filter in python to ensure we only get today's (SQLite/Postgres date issues bypass)
    today_scans = [s for s in scans if s.scan_date.date() == today]
    
    results = []
    
    # Group by symbol so the UI can still show Intraday and Swing side-by-side
    grouped = {}
    for s in today_scans:
        if s.symbol not in grouped:
            grouped[s.symbol] = {
                "symbol": s.symbol,
                "name": s.name,
                "current_price": s.entry_price, # rough proxy, not fully accurate but enough for display
                "intraday": {"trade_decision": "NO TRADE", "setup": None, "ai_summary": None},
                "swing": {"trade_decision": "NO TRADE", "setup": None, "ai_summary": None}
            }
            
        setup_obj = {
            "entry": s.entry_price,
            "stop_loss": s.stop_loss,
            "target_1": s.target_price,
            "final_score": s.score
        }
        
        if s.setup_type == "INTRADAY":
            grouped[s.symbol]["intraday"] = {
                "trade_decision": "TRADE",
                "setup": setup_obj,
                "ai_summary": s.ai_summary
            }
        elif s.setup_type == "SWING":
            grouped[s.symbol]["swing"] = {
                "trade_decision": "TRADE",
                "setup": setup_obj,
                "ai_summary": s.ai_summary
            }

    for symbol, data in grouped.items():
        results.append(data)
        
    # Sort alphabetically
    results = sorted(results, key=lambda x: x["symbol"])

    return {
        "page": 1,
        "limit": 5000,
        "total_stocks": len(results),
        "total_pages": 1,
        "results": results
    }
