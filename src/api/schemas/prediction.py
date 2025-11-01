"""
Prediction schemas for the API.
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict

from src.api.schemas.base import BaseSchema, MetaDataSchema

class QueryRequest(BaseModel):
    """
    Schema for case query request.
    """
    case_id: str
    case_type: Optional[str] = None
    section: str
    model: Optional[str] = None

class QueryResponse(BaseModel):
    """
    Schema for case query response.
    """
    case_id: str
    section: str
    response: str
    response_of_findings: str = ""
    images: List[Dict[str, Any]] = []
    exhibit_names: List[str] = []
    exhibit_names_string: str = ""

class CaseSchema(BaseSchema):
    """
    Schema for case data.
    """
    case_id: str
    case_name: str
    location: str
    date: str
    time: str
    description: str = ""
    images: List[MetaDataSchema] = []
    pdf: List[MetaDataSchema] = []
    embedding: str = ""
    case_type: str = ""

    # Optional fields
    inspection_date: Optional[str] = None
    inspector_name: Optional[str] = None
    hub_file_number: Optional[str] = None
    injured_party_name: Optional[str] = None
    property_name: Optional[str] = None
    property_address: Optional[str] = None
    incident_date: Optional[str] = None
    incident_time: Optional[str] = None
    injured_party_present: Optional[str] = None
    voice_record_allowed: Optional[str] = None
    voice_record_link: Optional[str] = None
    dcof_test: Optional[str] = None
    dcof_explanation: Optional[str] = None
    handwritten_note: Optional[str] = None
    note_text: Optional[str] = None
    client_location: Optional[str] = None

    # Exhibits
    exhibits: Dict[str, List[MetaDataSchema]] = Field(default_factory=lambda: {"images": [], "pdfs": []})

    model_config = ConfigDict(populate_by_name=True)

class CaseCreate(BaseModel):
    """
    Schema for creating a case.
    """
    case_id: str
    case_name: str
    location: str
    date: str
    time: str
    description: Optional[str] = None
    case_type: str = "Slip/Fall on Ice"

    # Optional fields
    inspection_date: Optional[str] = None
    inspector_name: Optional[str] = None
    hub_file_number: Optional[str] = None
    injured_party_name: Optional[str] = None
    property_name: Optional[str] = None
    property_address: Optional[str] = None
    incident_date: Optional[str] = None
    incident_time: Optional[str] = None
    injured_party_present: Optional[str] = None
    voice_record_allowed: Optional[str] = None
    voice_record_link: Optional[str] = None
    dcof_test: Optional[str] = None
    dcof_explanation: Optional[str] = None
    handwritten_note: Optional[str] = None
    note_text: Optional[str] = None
    client_location: Optional[str] = None