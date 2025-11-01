"""
Prediction endpoints for the API.
"""
import time
from typing import List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.dependencies import get_case_repository, get_prediction_repository
from src.api.schemas.prediction import QueryRequest, QueryResponse
from src.core.logging_config import get_logger
from src.db.repositories.case_repository import CaseRepository
from src.db.repositories.prediction_repository import PredictionRepository
from src.inference.service import InferenceService
from src.controller.gemini_case_handler import GeminiHandler

logger = get_logger(__name__)

router = APIRouter()

@router.post("/query", response_model=QueryResponse)
async def query_case(
    request: QueryRequest,
    case_repo: CaseRepository = Depends(get_case_repository),
    prediction_repo: PredictionRepository = Depends(get_prediction_repository)
):
    """
    Query a case using Gemini's document processing capabilities.
    Also fetches and returns base64 encoded images for the specified section.
    For the "Exhibits" section, returns all exhibits (images and PDFs) without using Gemini.
    Implements reactive rate limiting protection using extracted delays and backoff.
    """
    start_time = time.time()

    # Initialize base64_encoded_images at the beginning to avoid reference errors
    base64_encoded_images = []

    try:
        # Check if case exists
        case = case_repo.get_by_case_id(request.case_id)
        if not case:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Case '{request.case_id}' not found"
            )

        # Create inference service
        inference_service = InferenceService(request.case_id, request.case_type or "case_type_1")

        # Special handling for Exhibits section
        if request.section == "Exhibits":
            logger.info(f"Processing Exhibits section for case {request.case_id} - skipping Gemini analysis")

            # Get all exhibits (images and PDFs converted to images) and exhibit names
            exhibit_images, exhibit_names = await inference_service.get_all_exhibits()

            # Create a newline-separated string of exhibit names
            exhibit_names_string = "\n".join(exhibit_names)

            # Return the exhibits without Gemini analysis
            response = {
                "case_id": request.case_id,
                "section": request.section,
                "response": "Exhibits section - displaying all case exhibits",
                "response_of_findings": "",
                "images": exhibit_images,
                "exhibit_names": exhibit_names,
                "exhibit_names_string": exhibit_names_string
            }

            # Log the prediction using the method that handles large images
            prediction_repo.create_with_large_images({
                "case_id": request.case_id,
                "section": request.section,
                "response": response["response"],
                "response_of_findings": response["response_of_findings"],
                "images": response["images"],
                "processing_time": time.time() - start_time,
                "status": "success"
            })

            return response

        # For all other sections, use Gemini
        logger.info(f"Initiating Gemini query for case {request.case_id}, section '{request.section}'")

        # Special handling for 14_findings_and_background section
        if request.section == "14_findings_and_background":
            logger.info(f"Using GeminiHandler for 14_findings_and_background section")

            # Create GeminiHandler instance
            handler = GeminiHandler(case_id=request.case_id, case_type=request.case_type or "case_type_1")

            # Set model if specified
            if request.model:
                handler.set_model(request.model)

            # Get findings and background
            out14 = handler.create_unified_analysis(
                section="1.4 Findings",
                batch_size=3,
                base_retry_delay=5,
                max_retries=3
            )

            outBackground = handler.create_unified_analysis(
                section="Background Information",
                batch_size=3,
                base_retry_delay=5,
                max_retries=3
            )

            response_text = f"=== 1.4 FINDINGS ===\n{out14}\n\n=== BACKGROUND INFORMATION ===\n{outBackground}"
        else:
            # Get Gemini analysis using InferenceService
            response_text = await inference_service.create_unified_analysis(
                section=request.section,
                batch_size=3,
                base_retry_delay=5,
                max_retries=3
            )

        # Handle Gemini response/errors
        gemini_error = None
        if "Error: Rate limit exceeded" in response_text or "Error: Could not generate unified analysis due to persistent API rate limits" in response_text:
            logger.error(f"Gemini processing failed for case {request.case_id} due to rate limits after retries.")
            gemini_error = "Rate limit exceeded"
        elif "An unexpected error occurred during analysis" in response_text or "Error querying Gemini" in response_text:
            logger.error(f"Gemini processing failed for case {request.case_id} due to an unexpected error: {response_text}")
            gemini_error = "Internal Gemini error"

        # Fetch and encode images
        base64_encoded_images = []
        try:
            # Get base64 images for the specified section
            base64_encoded_images = await inference_service.get_base64_images_for_section(request.section)
        except Exception as img_err:
            logger.error(f"Failed to fetch or encode images for case {request.case_id}, section {request.section}: {img_err}")

        # Handle final response and potential Gemini errors
        if gemini_error == "Rate limit exceeded":
            # For Background Information section, always return default values for both fields
            if request.section == "Background Information":
                error_response = {
                    "case_id": request.case_id,
                    "section": request.section,
                    "response": "Background Information",
                    "response_of_findings": "Findings",
                    "images": base64_encoded_images
                }
            else:
                error_response = {
                    "case_id": request.case_id,
                    "section": request.section,
                    "response": "The server is experiencing high load or API rate limits have been reached. Please try again in a few minutes.",
                    "response_of_findings": "",
                    "images": base64_encoded_images
                }

            # Log the error using the method that handles large images
            prediction_repo.create_with_large_images({
                "case_id": request.case_id,
                "section": request.section,
                "response": error_response["response"],
                "response_of_findings": error_response["response_of_findings"],
                "images": error_response["images"],
                "processing_time": time.time() - start_time,
                "status": "error",
                "error_message": "Rate limit exceeded"
            })

            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=error_response["response"]
            )
        elif gemini_error == "Internal Gemini error":
            # For Background Information section, always return default values for both fields
            if request.section == "Background Information":
                error_response = {
                    "case_id": request.case_id,
                    "section": request.section,
                    "response": "Background Information",
                    "response_of_findings": "Findings",
                    "images": base64_encoded_images
                }
            else:
                error_response = {
                    "case_id": request.case_id,
                    "section": request.section,
                    "response": "An internal error occurred while processing the documents with the AI model.",
                    "response_of_findings": "",
                    "images": base64_encoded_images
                }

            # Log the error using the method that handles large images
            prediction_repo.create_with_large_images({
                "case_id": request.case_id,
                "section": request.section,
                "response": error_response["response"],
                "response_of_findings": error_response["response_of_findings"],
                "images": error_response["images"],
                "processing_time": time.time() - start_time,
                "status": "error",
                "error_message": "Internal Gemini error"
            })

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_response["response"]
            )

        # Return successful analysis and images
        # Use the appropriate function based on the section
        from src.inference.postprocessing import extract_findings_and_background, parse_background_response

        # For Background Information section, use the new parsing function
        if request.section == "Background Information":
            logger.info(f"Using parse_background_response for Background Information section")

            # Check if response_text is empty or contains an error
            if not response_text or response_text.startswith("Error:"):
                logger.warning(f"Empty or error response from Gemini for Background Information section: {response_text}. Returning default values.")
                # Even with empty/error response, return default values for both fields
                response = {
                    "case_id": request.case_id,
                    "section": request.section,
                    "response": "Background Information",  # Default background information
                    "response_of_findings": "Findings",  # Default findings
                    "images": base64_encoded_images
                }
            else:
                # Normal processing for valid responses
                response_of_findings, response_text_parsed = parse_background_response(response_text)
                response = {
                    "case_id": request.case_id,
                    "section": request.section,
                    "response": response_text_parsed,
                    "response_of_findings": response_of_findings,
                    "images": base64_encoded_images
                }
        else:
            # For other sections, use the existing function
            findings_part, background_part = extract_findings_and_background(response_text)

            response = {
                "case_id": request.case_id,
                "section": request.section,
                "response": background_part,
                "response_of_findings": findings_part,
                "images": base64_encoded_images
            }

        # Log the prediction using the method that handles large images
        prediction_repo.create_with_large_images({
            "case_id": request.case_id,
            "section": request.section,
            "response": response["response"],
            "response_of_findings": response["response_of_findings"],
            "images": response["images"],
            "processing_time": time.time() - start_time,
            "status": "success"
        })

        return response

    except ValueError as e:
        # Catch config errors like missing API key or case not found
        logger.error(f"Value error during query for case {request.case_id}: {str(e)}")

        # Check if it's a case not found error
        if "Case not found" in str(e):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    except HTTPException:
        # Re-raise HTTPExceptions
        raise

    except Exception as e:
        # Catch any other unexpected exceptions
        logger.error(f"Unexpected error processing query for case {request.case_id}: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())

        error_str = str(e)
        # For Background Information section, return default values instead of raising an exception
        if request.section == "Background Information":
            logger.info(f"Returning default values for Background Information section due to error: {error_str}")
            return {
                "case_id": request.case_id,
                "section": request.section,
                "response": "Background Information",
                "response_of_findings": "Findings",
                "images": base64_encoded_images
            }
        # For other sections, raise appropriate exceptions
        elif "429" in error_str or "rate limit" in error_str.lower() or "quota" in error_str.lower():
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="API quota or rate limit possibly exceeded. Please try again later."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected server error occurred while processing the query."
            )
