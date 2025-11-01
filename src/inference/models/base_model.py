"""
Base model class for inference models.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional

class BaseModel(ABC):
    """
    Base model class for inference models.
    """
    
    @abstractmethod
    def __init__(self, model_name: str, **kwargs):
        """
        Initialize the model.
        
        Args:
            model_name: The name of the model.
            **kwargs: Additional model parameters.
        """
        self.model_name = model_name
    
    @abstractmethod
    def predict(self, inputs: Any) -> Any:
        """
        Make a prediction with the model.
        
        Args:
            inputs: The inputs to the model.
            
        Returns:
            The model predictions.
        """
        pass
    
    @abstractmethod
    def load(self) -> bool:
        """
        Load the model.
        
        Returns:
            True if the model was loaded successfully, False otherwise.
        """
        pass
    
    @abstractmethod
    def unload(self) -> bool:
        """
        Unload the model.
        
        Returns:
            True if the model was unloaded successfully, False otherwise.
        """
        pass
