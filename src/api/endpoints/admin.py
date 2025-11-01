"""
Admin endpoints for the API.
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any

from src.db.repositories.case_repository import get_case_repository, CaseRepository

router = APIRouter(prefix="/app/v1/admin", tags=["admin"])

@router.get("/cases", response_model=List[Dict[str, Any]])
async def get_all_cases(
    case_repo: CaseRepository = Depends(get_case_repository)
):
    """
    Get all cases.
    
    Returns:
        List[Dict[str, Any]]: A list of all cases.
    """
    cases = case_repo.find_all()
    return cases

@router.delete("/case/{case_id}", response_model=Dict[str, str])
async def delete_case(
    case_id: str,
    case_repo: CaseRepository = Depends(get_case_repository)
):
    """
    Delete a case.
    
    Args:
        case_id: The ID of the case to delete.
        
    Returns:
        Dict[str, str]: A message indicating success.
        
    Raises:
        HTTPException: If the case is not found.
    """
    result = case_repo.delete_one({"case_id": case_id})
    
    if not result:
        raise HTTPException(status_code=404, detail="Case not found")
    
    return {"message": "Case deleted successfully"}
