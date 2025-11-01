"""
Base model for database models.
"""
from datetime import datetime
from typing import Dict, Any, Optional
from bson import ObjectId

class BaseModel:
    """
    Base model for database models.
    """
    
    def __init__(self, **kwargs):
        """
        Initialize the model with the given attributes.
        
        Args:
            **kwargs: The model attributes.
        """
        self._id: Optional[ObjectId] = kwargs.get("_id")
        self.created_at: datetime = kwargs.get("created_at", datetime.now())
        self.updated_at: datetime = kwargs.get("updated_at", datetime.now())
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the model to a dictionary.
        
        Returns:
            A dictionary representation of the model.
        """
        result = {
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
        
        if self._id:
            result["_id"] = str(self._id)
            
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BaseModel":
        """
        Create a model instance from a dictionary.
        
        Args:
            data: The dictionary containing the model data.
            
        Returns:
            A model instance.
        """
        return cls(**data)

def format_object_id(obj: Any) -> Any:
    """
    Recursively formats MongoDB ObjectId to string in dictionaries and lists.
    
    Args:
        obj: The object to format (dict, list, or other)
        
    Returns:
        The formatted object with ObjectId converted to strings
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, ObjectId):
                obj[k] = str(v)
            elif isinstance(v, (dict, list)):
                obj[k] = format_object_id(v)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            if isinstance(v, ObjectId):
                obj[i] = str(v)
            elif isinstance(v, (dict, list)):
                obj[i] = format_object_id(v)
    return obj
