"""
Admin routes for the application.
"""
from typing import Dict, Any, List

from fastapi import APIRouter, Depends, HTTPException, status, Query

from src.admin.dashboard_service import get_system_stats, get_case_stats, get_prediction_stats
from src.api.dependencies import get_case_repository, get_prediction_repository
from src.core.logging_config import get_logger
from src.db.repositories.case_repository import CaseRepository
from src.db.repositories.prediction_repository import PredictionRepository
from src.monitoring.health_checks import run_all_health_checks

logger = get_logger(__name__)

router = APIRouter()

@router.get("/dashboard/stats")
async def get_dashboard_stats(
    case_repo: CaseRepository = Depends(get_case_repository),
    prediction_repo: PredictionRepository = Depends(get_prediction_repository)
):
    """
    Get dashboard statistics.
    """
    try:
        system_stats = await get_system_stats()
        case_stats = await get_case_stats(case_repo)
        prediction_stats = await get_prediction_stats(prediction_repo)
        
        return {
            "system": system_stats,
            "cases": case_stats,
            "predictions": prediction_stats
        }
    except Exception as e:
        logger.error(f"Error getting dashboard stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting dashboard stats: {str(e)}"
        )

@router.get("/dashboard/health")
async def get_health_dashboard():
    """
    Get health dashboard.
    """
    try:
        health_checks = await run_all_health_checks()
        return health_checks
    except Exception as e:
        logger.error(f"Error getting health dashboard: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting health dashboard: {str(e)}"
        )

@router.get("/system-prompts")
async def get_system_prompts(
    case_repo: CaseRepository = Depends(get_case_repository)
):
    """
    Get system prompts.
    """
    try:
        prompts_collection = case_repo.db["system_prompts"]
        prompts = list(prompts_collection.find({}, {"_id": 0}))
        return prompts
    except Exception as e:
        logger.error(f"Error getting system prompts: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting system prompts: {str(e)}"
        )

@router.post("/system-prompts")
async def create_system_prompt(
    prompt: Dict[str, Any],
    case_repo: CaseRepository = Depends(get_case_repository)
):
    """
    Create a system prompt.
    """
    try:
        # Validate required fields
        if "section" not in prompt or "prompt_text" not in prompt:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing required fields: section, prompt_text"
            )
        
        prompts_collection = case_repo.db["system_prompts"]
        
        # Check if prompt already exists
        existing_prompt = prompts_collection.find_one({
            "section": prompt["section"],
            "case_type": prompt.get("case_type")
        })
        
        if existing_prompt:
            # Update existing prompt
            prompts_collection.update_one(
                {
                    "section": prompt["section"],
                    "case_type": prompt.get("case_type")
                },
                {"$set": prompt}
            )
            return {"message": "Prompt updated successfully"}
        else:
            # Create new prompt
            prompts_collection.insert_one(prompt)
            return {"message": "Prompt created successfully"}
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error creating system prompt: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating system prompt: {str(e)}"
        )

@router.delete("/system-prompts/{section}")
async def delete_system_prompt(
    section: str,
    case_type: str = Query(None),
    case_repo: CaseRepository = Depends(get_case_repository)
):
    """
    Delete a system prompt.
    """
    try:
        prompts_collection = case_repo.db["system_prompts"]
        
        # Create query
        query = {"section": section}
        if case_type:
            query["case_type"] = case_type
        
        # Delete prompt
        result = prompts_collection.delete_one(query)
        
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Prompt not found for section '{section}'"
            )
        
        return {"message": "Prompt deleted successfully"}
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error deleting system prompt: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting system prompt: {str(e)}"
        )
