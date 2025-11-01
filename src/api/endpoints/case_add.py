"""
Case-add endpoints for the API.
This module provides compatibility for frontend requests to /app/v1/Case-add/cases,
/app/v1/Case-add/case-add, and /app/v1/Case-add/query-case/.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status, Form
from typing import List, Dict, Any, Optional

from src.api.dependencies import get_case_repository, get_prediction_repository
from src.api.endpoints.cases import add_case as original_add_case
from src.api.endpoints.predictions import query_case as original_query_case
from src.api.schemas.prediction import CaseSchema, QueryRequest, QueryResponse
from src.db.repositories.case_repository import CaseRepository
from src.db.repositories.prediction_repository import PredictionRepository
from src.core.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/Case-add", tags=["case-add"])

@router.get("/cases", response_model=List[Dict[str, Any]])
async def get_cases_compat(
    case_repo: CaseRepository = Depends(get_case_repository)
):
    """
    API to fetch all cases from the database.
    This is a compatibility endpoint for frontend requests to /app/v1/Case-add/cases.

    Returns:
        List[Dict[str, Any]]: A list of all cases.
    """
    logger.info("Handling request to compatibility endpoint /app/v1/Case-add/cases")
    try:
        cases = case_repo.get_all_cases()
        return cases
    except Exception as e:
        logger.error(f"Failed to fetch cases: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch cases: {str(e)}"
        )

@router.delete("/case-delete/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_case_compat(
    case_id: str,
    case_repo: CaseRepository = Depends(get_case_repository)
):
    """
    API to delete a case by case_id.
    This is a compatibility endpoint for frontend requests to /app/v1/Case-add/case-delete/{case_id}.
    """
    logger.info(f"Handling request to compatibility endpoint /app/v1/Case-add/case-delete/{case_id}")

    from src.api.endpoints.cases import delete_case as original_delete_case
    return await original_delete_case(case_id=case_id, case_repo=case_repo)

@router.get("/case/{case_id}", response_model=Dict[str, Any])
async def get_case_compat(
    case_id: str,
    case_repo: CaseRepository = Depends(get_case_repository)
):
    """
    API to fetch a specific case by case_id with all fields from the database.
    This is a compatibility endpoint for frontend requests to /app/v1/Case-add/case/{case_id}.
    """
    logger.info(f"Handling request to compatibility endpoint /app/v1/Case-add/case/{case_id}")

    from src.api.endpoints.cases import get_case as original_get_case
    return await original_get_case(case_id=case_id, case_repo=case_repo)

@router.post("/case-add", response_model=CaseSchema, status_code=status.HTTP_201_CREATED)
async def add_case_compat(
    request: Request,
    case_id: str = Form(...),
    case_name: str = Form(...),
    location: str = Form(...),
    date: str = Form(...),
    time: str = Form(...),
    description: Optional[str] = Form(None),
    image_count: int = Form(0),
    case_type: str = Form("Slip/Fall on Ice"),
    inspection_date: Optional[str] = Form(None),
    inspector_name: Optional[str] = Form(None),
    hub_file_number: Optional[str] = Form(None),
    injured_party_name: Optional[str] = Form(None),
    property_name: Optional[str] = Form(None),
    property_address: Optional[str] = Form(None),
    incident_date: Optional[str] = Form(None),
    incident_time: Optional[str] = Form(None),
    injured_party_present: Optional[str] = Form(None),
    voice_record_allowed: Optional[str] = Form(None),
    voice_record_link: Optional[str] = Form(None),
    dcof_test: Optional[str] = Form(None),
    dcof_explanation: Optional[str] = Form(None),
    handwritten_note: Optional[str] = Form(None),
    note_text: Optional[str] = Form(None),
    client_location: Optional[str] = Form(None),
    exhibit_count: Optional[int] = Form(0),
    exhibit_image_count: Optional[int] = Form(0),
    exhibit_pdf_count: Optional[int] = Form(0),
    case_repo: CaseRepository = Depends(get_case_repository)
):
    """
    Add a new case with file uploads handling.
    This is a compatibility endpoint for frontend requests to /app/v1/Case-add/case-add.

    This endpoint forwards the request to the original case-add endpoint.
    """
    logger.info("Handling request to compatibility endpoint /app/v1/Case-add/case-add")

    # Forward the request to the original add_case function
    return await original_add_case(
        request=request,
        case_id=case_id,
        case_name=case_name,
        location=location,
        date=date,
        time=time,
        description=description,
        image_count=image_count,
        case_type=case_type,
        inspection_date=inspection_date,
        inspector_name=inspector_name,
        hub_file_number=hub_file_number,
        injured_party_name=injured_party_name,
        property_name=property_name,
        property_address=property_address,
        incident_date=incident_date,
        incident_time=incident_time,
        injured_party_present=injured_party_present,
        voice_record_allowed=voice_record_allowed,
        voice_record_link=voice_record_link,
        dcof_test=dcof_test,
        dcof_explanation=dcof_explanation,
        handwritten_note=handwritten_note,
        note_text=note_text,
        client_location=client_location,
        exhibit_count=exhibit_count,
        exhibit_image_count=exhibit_image_count,
        exhibit_pdf_count=exhibit_pdf_count,
        case_repo=case_repo
    )

@router.post("/query-case/", response_model=QueryResponse)
async def query_case_compat(
    request: QueryRequest,
    case_repo: CaseRepository = Depends(get_case_repository),
    prediction_repo: PredictionRepository = Depends(get_prediction_repository)
):
    """
    Query a case using Gemini's document processing capabilities.
    This is a compatibility endpoint for frontend requests to /app/v1/Case-add/query-case/.

    This endpoint forwards the request to the original query-case endpoint.
    """
    logger.info("Handling request to compatibility endpoint /app/v1/Case-add/query-case/")

    # Forward the request to the original query_case function with all required dependencies
    return await original_query_case(
        request=request,
        case_repo=case_repo,
        prediction_repo=prediction_repo
    )

@router.post("/image-query")
async def image_query_compat(data: dict):
    """
    Endpoint for passing a base64-encoded image to Gemini, returning an image description.
    This is a compatibility endpoint for frontend requests to /app/v1/Case-add/image-query.

    Expects JSON body:
    {
        "caseId": str,
        "sectionName": str,
        "imageName": str,
        "Image": str (base64-encoded image)
    }
    """
    logger.info("Handling request to compatibility endpoint /app/v1/Case-add/image-query")

    case_id = data.get("caseId")
    image_b64 = data.get("Image")

    # These fields are available but not currently used in the processing
    # section_name = data.get("sectionName")
    # image_name = data.get("imageName")

    if not case_id or not image_b64:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required fields: caseId or Image"
        )

    case_type = data.get("caseType", "case_type_1")

    # Process image using GeminiHandler
    try:
        from src.controller.gemini_case_handler import GeminiHandler

        # Create GeminiHandler instance
        handler = GeminiHandler(case_id=case_id, case_type=case_type)

        # Process the image
        desc = handler.Image_processing(image_b64)
        return {"Image_description": desc}
    except Exception as e:
        logger.error(f"Error processing image: {str(e)}")
        return {"Image_description": f"Error generating image description: {str(e)}"}
