"""
Health check schemas for the API.
"""
from typing import Dict, Any, Optional
from pydantic import BaseModel, ConfigDict

class HealthCheck(BaseModel):
    """
    Schema for health check response.
    """
    status: str
    version: str

    model_config = ConfigDict(populate_by_name=True)

class DetailedHealthCheck(HealthCheck):
    """
    Schema for detailed health check response.
    """
    database: Dict[str, Any]
    storage: Dict[str, Any]
    ai_services: Dict[str, Any]

    model_config = ConfigDict(populate_by_name=True)
