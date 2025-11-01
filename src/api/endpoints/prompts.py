"""
Prompts endpoints for the API.
This module provides compatibility for frontend requests to /app/v1/Prompts/* endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from typing import List, Dict, Any, Optional

from src.core.logging_config import get_logger
from src.routers.prompts_router import (
    get_all_prompts as original_get_all_prompts,
    get_prompt as original_get_prompt_by_id,
    create_prompt as original_create_prompt,
    update_prompt as original_update_prompt,
    delete_prompt as original_delete_prompt,
    get_prompts_by_section as original_get_prompts_by_section,
    get_all_prompts_by_section as original_get_all_prompts_by_section,
    import_prompts_from_json as original_import_prompts_from_json,
    PromptCreate,
    PromptUpdate
)

logger = get_logger(__name__)

router = APIRouter(prefix="/Prompts", tags=["prompts"])

@router.get("/prompts", response_model=List[Dict[str, Any]])
async def get_all_prompts_compat():
    """
    Get all prompts.
    This is a compatibility endpoint for frontend requests to /app/v1/Prompts/prompts.
    """
    logger.info("Handling request to compatibility endpoint /app/v1/Prompts/prompts")
    return await original_get_all_prompts()

@router.get("/prompts/{prompt_id}", response_model=Dict[str, Any])
async def get_prompt_by_id_compat(prompt_id: str):
    """
    Get a prompt by ID.
    This is a compatibility endpoint for frontend requests to /app/v1/Prompts/prompts/{prompt_id}.
    """
    logger.info(f"Handling request to compatibility endpoint /app/v1/Prompts/prompts/{prompt_id}")
    return await original_get_prompt_by_id(prompt_id=prompt_id)

@router.post("/prompts", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_prompt_compat(prompt: PromptCreate):
    """
    Create a new prompt.
    This is a compatibility endpoint for frontend requests to /app/v1/Prompts/prompts.
    """
    logger.info("Handling request to compatibility endpoint /app/v1/Prompts/prompts (POST)")
    return await original_create_prompt(prompt=prompt)

@router.put("/prompts/{prompt_id}", response_model=Dict[str, Any])
async def update_prompt_compat(prompt_id: str, prompt: PromptUpdate):
    """
    Update a prompt.
    This is a compatibility endpoint for frontend requests to /app/v1/Prompts/prompts/{prompt_id}.
    """
    logger.info(f"Handling request to compatibility endpoint /app/v1/Prompts/prompts/{prompt_id} (PUT)")
    return await original_update_prompt(prompt_id=prompt_id, prompt=prompt)

@router.delete("/prompts/{prompt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_prompt_compat(prompt_id: str):
    """
    Delete a prompt.
    This is a compatibility endpoint for frontend requests to /app/v1/Prompts/prompts/{prompt_id}.
    """
    logger.info(f"Handling request to compatibility endpoint /app/v1/Prompts/prompts/{prompt_id} (DELETE)")
    return await original_delete_prompt(prompt_id=prompt_id)

@router.get("/prompts/by-section/{section}", response_model=Dict[str, Any])
async def get_prompts_by_section_compat(section: str):
    """
    Get prompts by section.
    This is a compatibility endpoint for frontend requests to /app/v1/Prompts/prompts/by-section/{section}.
    """
    logger.info(f"Handling request to compatibility endpoint /app/v1/Prompts/prompts/by-section/{section}")
    return await original_get_prompts_by_section(section=section)

@router.get("/prompts/all-prompts/by-section", response_model=Dict[str, List[Dict[str, Any]]])
async def get_all_prompts_by_section_compat():
    """
    Get all prompts organized by section.
    This is a compatibility endpoint for frontend requests to /app/v1/Prompts/prompts/all-prompts/by-section.
    """
    logger.info("Handling request to compatibility endpoint /app/v1/Prompts/prompts/all-prompts/by-section")
    return await original_get_all_prompts_by_section()

@router.post("/prompts/import-from-json", status_code=status.HTTP_201_CREATED)
async def import_prompts_from_json_compat(file: UploadFile = File(...)):
    """
    Import prompts from a JSON file.
    This is a compatibility endpoint for frontend requests to /app/v1/Prompts/prompts/import-from-json.
    """
    logger.info("Handling request to compatibility endpoint /app/v1/Prompts/prompts/import-from-json")
    return await original_import_prompts_from_json(file=file)
