"""
Login endpoints for the API.
This module provides compatibility for frontend requests to /app/v1/Login/* endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict, Any

from src.core.logging_config import get_logger
from src.routers.login_router import (
    fetch_all_data as original_fetch_all_data,
    get_user_details as original_get_user_details,
    add_user as original_add_user,
    update_user as original_update_user,
    delete_user as original_delete_user,
    login as original_login,
    SecurityKey,
    User,
    UserUpdateRequest
)

logger = get_logger(__name__)

router = APIRouter(prefix="/Login", tags=["login"])

@router.get("/Login-user", response_model=List[Dict[str, str]])
async def fetch_all_data_compat():
    """
    API to fetch all user records from the database.
    This is a compatibility endpoint for frontend requests to /app/v1/Login/Login-user.
    """
    logger.info("Handling request to compatibility endpoint /app/v1/Login/Login-user")
    return await original_fetch_all_data()

@router.post("/get-user-details", response_model=Dict[str, Any])
async def get_user_details_compat(security_key: SecurityKey):
    """
    API to get full user details with security key authentication.
    This is a compatibility endpoint for frontend requests to /app/v1/Login/get-user-details.
    """
    logger.info("Handling request to compatibility endpoint /app/v1/Login/get-user-details")
    return await original_get_user_details(security_key=security_key)

@router.post("/add-user-id", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def add_user_compat(user: User):
    """
    API to add a new user to the database.
    This is a compatibility endpoint for frontend requests to /app/v1/Login/add-user-id.
    """
    logger.info("Handling request to compatibility endpoint /app/v1/Login/add-user-id")
    return await original_add_user(user=user)

@router.put("/update-user-cred/{user_id}", response_model=Dict[str, Any])
async def update_user_compat(user_id: str, update_data: UserUpdateRequest):
    """
    API to update an existing user's credentials with security key.
    This is a compatibility endpoint for frontend requests to /app/v1/Login/update-user-cred/{user_id}.
    """
    logger.info(f"Handling request to compatibility endpoint /app/v1/Login/update-user-cred/{user_id}")
    return await original_update_user(user_id=user_id, update_data=update_data)

@router.delete("/delete-user/{user_id}", response_model=Dict[str, str])
async def delete_user_compat(user_id: str, security_key: SecurityKey):
    """
    API to delete a user by user_id.
    This is a compatibility endpoint for frontend requests to /app/v1/Login/delete-user/{user_id}.
    """
    logger.info(f"Handling request to compatibility endpoint /app/v1/Login/delete-user/{user_id}")
    return await original_delete_user(user_id=user_id, security_key=security_key)

@router.post("/login", response_model=Dict[str, Any])
async def login_compat(user: User):
    """
    API for user authentication.
    This is a compatibility endpoint for frontend requests to /app/v1/Login/login.
    """
    logger.info("Handling request to compatibility endpoint /app/v1/Login/login")
    return await original_login(user=user)
