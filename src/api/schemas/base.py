"""
Base schemas for the API.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel as PydanticBaseModel, Field, ConfigDict

class BaseSchema(PydanticBaseModel):
    """
    Base schema for all API schemas.
    """
    id: Optional[str] = Field(None, alias="_id")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "json_encoders": {
                datetime: lambda dt: dt.isoformat()
            }
        }
    )

class MetaDataSchema(PydanticBaseModel):
    """
    Schema for file metadata.
    """
    description: str
    file_path: str
    azure_url: Optional[str] = None
    section: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True)
