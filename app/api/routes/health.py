from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, text
from app.database.connection import get_session
import logging

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("")
def health_check(session: Session = Depends(get_session)):
    """Health check endpoint to verify API and DB status."""
    try:
        # Check database connectivity
        session.exec(text("SELECT 1")).one()
        return {
            "status": "ok",
            "database": "connected",
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail="Database connection is unavailable",
        )
