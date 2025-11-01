"""
Prediction log model for the application.
"""
from datetime import datetime
from typing import Dict, Any, List, Optional

from src.db.models.base import BaseModel

class PredictionLog(BaseModel):
    """
    Prediction log model for the application.
    """
    
    def __init__(self, **kwargs):
        """
        Initialize the prediction log model with the given attributes.
        
        Args:
            **kwargs: The prediction log attributes.
        """
        super().__init__(**kwargs)
        self.case_id: str = kwargs.get("case_id", "")
        self.section: str = kwargs.get("section", "")
        self.response: str = kwargs.get("response", "")
        self.response_of_findings: str = kwargs.get("response_of_findings", "")
        self.images: List[Dict[str, Any]] = kwargs.get("images", [])
        self.processing_time: float = kwargs.get("processing_time", 0.0)
        self.status: str = kwargs.get("status", "success")
        self.error_message: Optional[str] = kwargs.get("error_message")
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the prediction log model to a dictionary.
        
        Returns:
            A dictionary representation of the prediction log model.
        """
        result = super().to_dict()
        result.update({
            "case_id": self.case_id,
            "section": self.section,
            "response": self.response,
            "response_of_findings": self.response_of_findings,
            "images": self.images,
            "processing_time": self.processing_time,
            "status": self.status
        })
        
        if self.error_message:
            result["error_message"] = self.error_message
            
        return result
