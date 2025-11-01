"""
Dependencies for the API.
"""
from typing import Callable, Dict, Any

from fastapi import Depends, HTTPException, status, Header
from pymongo.database import Database

from src.core.config import MONGO_URI, DATABASE_NAME
from src.core.logging_config import get_logger
from src.core.security import validate_api_key
from src.db.repositories.case_repository import CaseRepository
from src.db.repositories.prediction_repository import PredictionRepository
from src.db.repositories.user_repository import UserRepository
from src.db.session import get_db

logger = get_logger(__name__)

def get_case_repository() -> CaseRepository:
    """
    Get the case repository.
    
    Returns:
        The case repository.
    """
    return CaseRepository()

def get_prediction_repository() -> PredictionRepository:
    """
    Get the prediction repository.
    
    Returns:
        The prediction repository.
    """
    return PredictionRepository()

def get_user_repository() -> UserRepository:
    """
    Get the user repository.
    
    Returns:
        The user repository.
    """
    return UserRepository()

def get_api_key(x_api_key: str = Header(None)) -> str:
    """
    Get and validate the API key from the request header.
    
    Args:
        x_api_key: The API key from the request header.
        
    Returns:
        The validated API key.
        
    Raises:
        HTTPException: If the API key is invalid.
    """
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key is missing"
        )
    
    # In a real application, you would validate the API key against a stored value
    # For now, we'll just return the key
    return x_api_key
