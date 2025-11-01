"""
Security utilities for the application.
"""
import os
import secrets
from typing import Optional, Dict, Any

from src.core.logging_config import get_logger

logger = get_logger(__name__)

def generate_secure_token(length: int = 32) -> str:
    """
    Generate a secure random token.
    
    Args:
        length: The length of the token.
        
    Returns:
        A secure random token.
    """
    return secrets.token_hex(length)

def validate_api_key(api_key: str, expected_key: str) -> bool:
    """
    Validate an API key.
    
    Args:
        api_key: The API key to validate.
        expected_key: The expected API key.
        
    Returns:
        True if the API key is valid, False otherwise.
    """
    if not api_key or not expected_key:
        return False
    return secrets.compare_digest(api_key, expected_key)

def get_api_key_from_header(headers: Dict[str, Any], header_name: str = "X-API-Key") -> Optional[str]:
    """
    Get the API key from the request headers.
    
    Args:
        headers: The request headers.
        header_name: The name of the header containing the API key.
        
    Returns:
        The API key if found, None otherwise.
    """
    return headers.get(header_name)
