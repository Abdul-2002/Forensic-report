"""
Health check endpoints for the API.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.database import Database

from src.api.schemas.health import HealthCheck, DetailedHealthCheck
from src.core.config import VERSION
from src.core.logging_config import get_logger
from src.db.session import get_db

logger = get_logger(__name__)

router = APIRouter()

@router.get("/health", response_model=HealthCheck)
async def health_check():
    """
    Basic health check endpoint.
    """
    return {
        "status": "ok",
        "version": VERSION
    }

@router.get("/health/detailed", response_model=DetailedHealthCheck)
async def detailed_health_check(db: Database = Depends(get_db)):
    """
    Detailed health check endpoint.
    
    Checks the status of the database, storage, and AI services.
    """
    # Check database connection
    db_status = {"status": "ok", "details": {}}
    try:
        # Ping the database
        db.command("ping")
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = {"status": "error", "details": {"error": str(e)}}
    
    # Check storage connection
    storage_status = {"status": "ok", "details": {}}
    try:
        # In a real application, you would check the storage connection
        # For now, we'll just return ok
        pass
    except Exception as e:
        logger.error(f"Storage health check failed: {e}")
        storage_status = {"status": "error", "details": {"error": str(e)}}
    
    # Check AI services
    ai_status = {"status": "ok", "details": {}}
    try:
        # In a real application, you would check the AI services
        # For now, we'll just return ok
        pass
    except Exception as e:
        logger.error(f"AI services health check failed: {e}")
        ai_status = {"status": "error", "details": {"error": str(e)}}
    
    # Overall status
    overall_status = "ok"
    if db_status["status"] == "error" or storage_status["status"] == "error" or ai_status["status"] == "error":
        overall_status = "error"
    
    return {
        "status": overall_status,
        "version": VERSION,
        "database": db_status,
        "storage": storage_status,
        "ai_services": ai_status
    }
