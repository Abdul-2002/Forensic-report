"""
User model for the application.
"""
from datetime import datetime
from typing import Dict, Any, Optional

from src.db.models.base import BaseModel

class User(BaseModel):
    """
    User model for the application.
    """
    
    def __init__(self, **kwargs):
        """
        Initialize the user model with the given attributes.
        
        Args:
            **kwargs: The user attributes.
        """
        super().__init__(**kwargs)
        self.username: str = kwargs.get("username", "")
        self.email: str = kwargs.get("email", "")
        self.hashed_password: str = kwargs.get("hashed_password", "")
        self.is_active: bool = kwargs.get("is_active", True)
        self.is_superuser: bool = kwargs.get("is_superuser", False)
        self.last_login: Optional[datetime] = kwargs.get("last_login")
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the user model to a dictionary.
        
        Returns:
            A dictionary representation of the user model.
        """
        result = super().to_dict()
        result.update({
            "username": self.username,
            "email": self.email,
            "is_active": self.is_active,
            "is_superuser": self.is_superuser,
            "last_login": self.last_login
        })
        
        # Don't include the hashed password in the dictionary
        
        return result
