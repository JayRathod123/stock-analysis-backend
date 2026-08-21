from fastapi import APIRouter, Query, HTTPException
from typing import List, Optional
from app.api.routes.analysis import run_analysis_endpoint, RunAnalysisParams

router = APIRouter()

# Flat list cache of zones mapped by zone_id
ZONES_BY_ID = {}

def load_zones_for_symbol(symbol: str) -> List[dict]:
    """Helper to trigger an analysis and populate the flat zone cache."""
    params = RunAnalysisParams(symbol=symbol, timeframe="15m", mode="intraday")
    res = run_analysis_endpoint(params)
    
    zones = []
    # Collect all categories
    if res.get("best_intraday_setup"):
        zones.append(res["best_intraday_setup"])
    if res.get("best_swing_setup"):
        zones.append(res["best_swing_setup"])
    for z in res.get("other_valid_setups", []):
        zones.append(z)
    for z in res.get("watchlist_zones", []):
        zones.append(z)
    for z in res.get("rejected_zones", []):
        zones.append(z)
        
    # Cache flat list
    for z in zones:
        ZONES_BY_ID[z["zone_id"]] = z
        
    return zones

@router.get("")
def list_zones(
    symbol: Optional[str] = Query(None),
    timeframe: Optional[str] = Query(None)
):
    """Retrieve supply/demand zones for active stocks."""
    sym = symbol or "RELIANCE"
    zones = load_zones_for_symbol(sym)
    if timeframe:
        zones = [z for z in zones if z["timeframe"] == timeframe]
    return zones

@router.get("/{id}")
def get_zone_by_id(id: str):
    """Retrieve detailed metrics for a specific zone."""
    if id in ZONES_BY_ID:
        return ZONES_BY_ID[id]
        
    # If not loaded, trigger default RELIANCE/TCS/INFY scans
    for s in ["RELIANCE", "TCS", "INFY"]:
        load_zones_for_symbol(s)
        if id in ZONES_BY_ID:
            return ZONES_BY_ID[id]
            
    raise HTTPException(status_code=404, detail=f"Zone '{id}' not found in terminal logs")
