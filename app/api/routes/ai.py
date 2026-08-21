from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.api.routes.zones import ZONES_BY_ID
from app.ai.ollama import explain_setup_with_ollama

router = APIRouter()

class AiExplainRequest(BaseModel):
    analysis_id: str
    zone_id: str

@router.post("")
def explain_endpoint(req: AiExplainRequest):
    """Generates natural language narrative from deterministic setups using Ollama."""
    zone_id = req.zone_id
    if zone_id not in ZONES_BY_ID:
        raise HTTPException(status_code=404, detail="Zone setup details not cached. Perform an analysis first.")
        
    zone_details = ZONES_BY_ID[zone_id]
    try:
        explanation = explain_setup_with_ollama(zone_details)
        return {"explanation": explanation}
    except Exception as e:
        # Fallback: return a 503 error representing unavailable service
        raise HTTPException(
            status_code=503, 
            detail="Local AI is currently unavailable. The deterministic analysis is still available."
        ) from e
