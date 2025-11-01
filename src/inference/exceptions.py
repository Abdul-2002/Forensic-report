"""
Custom exceptions for the inference module.
"""

class InferenceError(Exception):
    """Base exception for inference errors."""
    pass

class ModelNotFoundError(InferenceError):
    """Exception raised when a model is not found."""
    pass

class ModelLoadingError(InferenceError):
    """Exception raised when a model fails to load."""
    pass

class PreprocessingError(InferenceError):
    """Exception raised when preprocessing fails."""
    pass

class PostprocessingError(InferenceError):
    """Exception raised when postprocessing fails."""
    pass

class APIRateLimitError(InferenceError):
    """Exception raised when an API rate limit is reached."""
    def __init__(self, message: str, retry_after: int = None):
        self.retry_after = retry_after
        super().__init__(message)

class APIError(InferenceError):
    """Exception raised when an API call fails."""
    pass
