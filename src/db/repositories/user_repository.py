"""
User repository for database operations.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime

from src.core.logging_config import get_logger
from src.db.models.user import User
from src.db.repositories.base_repository import BaseRepository

logger = get_logger(__name__)

class UserRepository(BaseRepository[User]):
    """
    User repository for database operations.
    """
    
    def __init__(self):
        """
        Initialize the user repository.
        """
        super().__init__("users", User)
    
    def get_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Get a user by username.
        
        Args:
            username: The username to search for.
            
        Returns:
            The user document or None if not found.
        """
        return self.read_one({"username": username})
    
    def get_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Get a user by email.
        
        Args:
            email: The email to search for.
            
        Returns:
            The user document or None if not found.
        """
        return self.read_one({"email": email})
    
    def update_last_login(self, user_id: str) -> Dict[str, Any]:
        """
        Update the last login time for a user.
        
        Args:
            user_id: The user ID.
            
        Returns:
            A dictionary with the number of modified documents or an error message.
        """
        return self.update(
            {"_id": user_id},
            {"last_login": datetime.now()}
        )
