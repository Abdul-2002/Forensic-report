"""
Model loader for inference models.
"""
import os
import tempfile
from typing import Dict, Any, List, Optional, Type

from src.core.logging_config import get_logger
from src.inference.exceptions import ModelNotFoundError, ModelLoadingError
from src.inference.models.base_model import BaseModel
from src.inference.models.gemini_model import GeminiModel

logger = get_logger(__name__)

class ModelLoader:
    """
    Model loader for inference models.
    """
    
    def __init__(self):
        """
        Initialize the model loader.
        """
        self.models = {}
        self.model_classes = {
            "gemini": GeminiModel
        }
    
    def get_model(self, model_type: str, model_name: str, **kwargs) -> BaseModel:
        """
        Get a model instance.
        
        Args:
            model_type: The type of model (e.g., "gemini").
            model_name: The name of the model.
            **kwargs: Additional model parameters.
            
        Returns:
            A model instance.
            
        Raises:
            ModelNotFoundError: If the model type is not found.
            ModelLoadingError: If the model fails to load.
        """
        model_key = f"{model_type}_{model_name}"
        
        # Return cached model if available
        if model_key in self.models:
            return self.models[model_key]
        
        # Get model class
        if model_type not in self.model_classes:
            raise ModelNotFoundError(f"Model type '{model_type}' not found.")
        
        model_class = self.model_classes[model_type]
        
        # Create model instance
        try:
            model = model_class(model_name=model_name, **kwargs)
            model.load()
            self.models[model_key] = model
            return model
        except Exception as e:
            logger.error(f"Failed to load model '{model_key}': {str(e)}")
            raise ModelLoadingError(f"Failed to load model '{model_key}': {str(e)}")
    
    def unload_model(self, model_type: str, model_name: str) -> bool:
        """
        Unload a model.
        
        Args:
            model_type: The type of model (e.g., "gemini").
            model_name: The name of the model.
            
        Returns:
            True if the model was unloaded successfully, False otherwise.
        """
        model_key = f"{model_type}_{model_name}"
        
        if model_key in self.models:
            try:
                self.models[model_key].unload()
                del self.models[model_key]
                return True
            except Exception as e:
                logger.error(f"Failed to unload model '{model_key}': {str(e)}")
                return False
        
        return True
    
    def unload_all_models(self) -> bool:
        """
        Unload all models.
        
        Returns:
            True if all models were unloaded successfully, False otherwise.
        """
        success = True
        
        for model_key, model in list(self.models.items()):
            try:
                model.unload()
                del self.models[model_key]
            except Exception as e:
                logger.error(f"Failed to unload model '{model_key}': {str(e)}")
                success = False
        
        return success

# Create a global instance of the model loader
model_loader = ModelLoader()
