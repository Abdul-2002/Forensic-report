"""
Gemini model for text generation.
"""
import time
from typing import Dict, Any, List, Optional, Union
import base64

import google.generativeai as genai

from src.core.config import GOOGLE_API_KEY, GEMINI_MODEL, GEMINI_IMAGE_MODEL
from src.core.logging_config import get_logger
from src.inference.exceptions import ModelLoadingError, APIRateLimitError, APIError
from src.inference.models.base_model import BaseModel

logger = get_logger(__name__)

def extract_retry_delay(error_message: str, default_delay: int = 5) -> int:
    """
    Extract the retry delay from a Gemini API rate limit error message (429).

    Args:
        error_message: The error message string from the Gemini API.
        default_delay: Default delay in seconds to use if extraction fails or not a 429 error.

    Returns:
        The number of seconds to delay before retrying.
    """
    try:
        # Only attempt extraction for 429 errors
        if "429" not in error_message:
            logger.debug("Error is not 429, returning default delay for backoff.")
            return default_delay  # Use default for non-429 errors triggering backoff

        # Look for the retry_delay section in the error message
        if "retry_delay" in error_message:
            # Extract the seconds value using string manipulation
            retry_delay_section = error_message.split("retry_delay {")[1].split("}")[0]
            seconds_str = retry_delay_section.split("seconds:")[1].strip()

            # Convert to integer, handling any trailing characters
            seconds = int(''.join(filter(str.isdigit, seconds_str)))

            # Add a small buffer (e.g., 1-2 seconds or 10%) to the suggested retry time
            # This helps avoid hitting the limit immediately again.
            buffered_delay = seconds + 2  # Add 2 seconds buffer

            logger.info(f"Extracted retry delay from 429 error: {seconds} seconds, using buffered delay: {buffered_delay}s")
            return buffered_delay
        else:
            logger.warning(f"429 error message did not contain 'retry_delay' details. Using default delay: {default_delay}s")
            return default_delay

    except Exception as e:
        logger.warning(f"Failed to parse retry delay from error message: {str(e)}. Using default delay: {default_delay}s")
        return default_delay

class GeminiModel(BaseModel):
    """
    Gemini model for text generation.
    """

    def __init__(self, model_name: str = GEMINI_MODEL, **kwargs):
        """
        Initialize the Gemini model.

        Args:
            model_name: The name of the Gemini model.
            **kwargs: Additional model parameters.
        """
        super().__init__(model_name, **kwargs)
        self.api_key = kwargs.get("api_key", GOOGLE_API_KEY)
        self.model = None
        self.temperature = kwargs.get("temperature", 0.2)
        self.max_output_tokens = kwargs.get("max_output_tokens", 8192)
        self.timeout = kwargs.get("timeout", 300)

    def load(self) -> bool:
        """
        Load the Gemini model.

        Returns:
            True if the model was loaded successfully, False otherwise.
        """
        try:
            if not self.api_key:
                raise ModelLoadingError("Missing Google API key. Set GOOGLE_API_KEY in the environment variables.")

            # Configure Gemini API
            genai.configure(api_key=self.api_key)

            # Create the model
            self.model = genai.GenerativeModel(self.model_name)

            logger.info(f"Loaded Gemini model: {self.model_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to load Gemini model: {str(e)}")
            raise ModelLoadingError(f"Failed to load Gemini model: {str(e)}")

    def unload(self) -> bool:
        """
        Unload the Gemini model.

        Returns:
            True if the model was unloaded successfully, False otherwise.
        """
        self.model = None
        return True

    def predict(self, inputs: Union[str, List[Dict[str, str]]], max_retries: int = 3, base_retry_delay: int = 5) -> str:
        """
        Generate text with the Gemini model.

        Args:
            inputs: The inputs to the model. Can be a string or a list of dictionaries with text.
            max_retries: The maximum number of retries for rate-limited requests.
            base_retry_delay: The base delay in seconds for retries.

        Returns:
            The generated text.

        Raises:
            ModelLoadingError: If the model is not loaded.
            APIRateLimitError: If the API rate limit is reached.
            APIError: If the API call fails.
        """
        if not self.model:
            self.load()

        retry_count = 0
        while retry_count <= max_retries:
            try:
                response = self.model.generate_content(
                    inputs,
                    generation_config=genai.GenerationConfig(
                        temperature=self.temperature,
                        max_output_tokens=self.max_output_tokens
                    ),
                    request_options={"timeout": self.timeout}
                )

                if hasattr(response, "prompt_feedback") and response.prompt_feedback and response.prompt_feedback.block_reason:
                    raise APIError(f"Content generation blocked ({response.prompt_feedback.block_reason})")

                if not hasattr(response, "text") or not response.text:
                    finish_reason = response.candidates[0].finish_reason if response.candidates else "UNKNOWN"
                    raise APIError(f"No text returned (Reason: {finish_reason}).")

                return response.text

            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "rate limit" in error_str.lower() or "quota" in error_str.lower():
                    retry_delay = extract_retry_delay(error_str, default_delay=base_retry_delay * (2 ** retry_count))
                    logger.warning(f"Rate limit in Gemini API. Sleeping {retry_delay}s.")
                    time.sleep(retry_delay)
                    retry_count += 1
                else:
                    logger.error(f"Gemini API error: {error_str}")
                    raise APIError(f"Gemini API error: {error_str}")

        raise APIRateLimitError("Rate limit exceeded after maximum retries.")

    def predict_with_image(self, image_b64: str, prompt: str, max_retries: int = 3, base_retry_delay: int = 5) -> str:
        """
        Generate text with the Gemini model using an image as input.

        Args:
            image_b64: The base64-encoded image.
            prompt: The text prompt to accompany the image.
            max_retries: The maximum number of retries for rate-limited requests.
            base_retry_delay: The base delay in seconds for retries.

        Returns:
            The generated text description of the image.

        Raises:
            ModelLoadingError: If the model is not loaded.
            APIRateLimitError: If the API rate limit is reached.
            APIError: If the API call fails.
        """
        # Use the image-capable model
        image_model_name = GEMINI_IMAGE_MODEL or "gemini-2.0-pro-vision"

        # Configure the Gemini API
        genai.configure(api_key=self.api_key)

        retry_count = 0
        while retry_count <= max_retries:
            try:
                # Decode the image from base64
                try:
                    image_bytes = base64.b64decode(image_b64)
                except Exception as e:
                    raise APIError(f"Failed to decode base64 image: {e}")

                # Create the model
                model = genai.GenerativeModel(image_model_name)

                # Generate content with the image
                response = model.generate_content([
                    {"mime_type": "image/jpeg", "data": image_bytes},
                    prompt
                ])

                # Check for safety ratings/blocks
                if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                    if hasattr(response.prompt_feedback, 'safety_ratings'):
                        for rating in response.prompt_feedback.safety_ratings:
                            if rating.blocked:
                                raise APIError(f"Image description blocked: {rating.category}")

                # Get the response text
                if hasattr(response, "text"):
                    return response.text
                elif hasattr(response, "parts"):
                    return "".join(part.text for part in response.parts if hasattr(part, "text"))
                else:
                    raise APIError("No description generated.")

            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "rate limit" in error_str.lower() or "quota" in error_str.lower():
                    retry_delay = extract_retry_delay(error_str, default_delay=base_retry_delay * (2 ** retry_count))
                    logger.warning(f"Rate limit in Gemini API. Sleeping {retry_delay}s.")
                    time.sleep(retry_delay)
                    retry_count += 1
                else:
                    logger.error(f"Error describing image: {error_str}")
                    raise APIError(f"Error generating image description: {error_str}")

        raise APIRateLimitError("Rate limit exceeded after maximum retries for image processing.")
