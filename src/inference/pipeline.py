"""
Inference pipeline for the application.
"""
import time
from typing import Dict, Any, List, Optional

from src.core.logging_config import get_logger
from src.inference.exceptions import InferenceError
from src.inference.service import InferenceService

logger = get_logger(__name__)

class InferencePipeline:
    """
    Inference pipeline for the application.
    """

    def __init__(self, case_id: str, case_type: str = "case_type_1"):
        """
        Initialize the inference pipeline.

        Args:
            case_id: The case ID.
            case_type: The case type.
        """
        self.case_id = case_id
        self.case_type = case_type
        self.service = InferenceService(case_id, case_type)

    async def process(self, section: str) -> Dict[str, Any]:
        """
        Process a case query.

        Args:
            section: The section to analyze.

        Returns:
            The query response.
        """
        start_time = time.time()

        try:
            # Special handling for Exhibits section
            if section == "Exhibits":
                logger.info(f"Processing Exhibits section for case {self.case_id} - skipping Gemini analysis")

                # Get all exhibits (images and PDFs converted to images) and exhibit names
                exhibit_images, exhibit_names = await self.service.get_all_exhibits()

                # Create the exhibit_names_string by joining the names with newlines
                exhibit_names_string = "\n".join(exhibit_names)

                # Return the exhibits without Gemini analysis
                return {
                    "case_id": self.case_id,
                    "section": section,
                    "response": "Exhibits section - displaying all case exhibits",
                    "response_of_findings": "",
                    "images": exhibit_images,
                    "exhibit_names": exhibit_names,
                    "exhibit_names_string": exhibit_names_string,
                    "processing_time": time.time() - start_time
                }

            # For all other sections, use Gemini
            logger.info(f"Initiating Gemini query for case {self.case_id}, section '{section}'")

            # Get Gemini analysis
            response_text = await self.service.create_unified_analysis(
                section=section,
                batch_size=3,
                base_retry_delay=5,
                max_retries=3
            )

            # Handle Gemini response/errors
            if "Error: Rate limit exceeded" in response_text or "Error: Could not generate unified analysis due to persistent API rate limits" in response_text:
                logger.error(f"Gemini processing failed for case {self.case_id} due to rate limits after retries.")
                return {
                    "case_id": self.case_id,
                    "section": section,
                    "response": "The server is experiencing high load or API rate limits have been reached. Please try again in a few minutes.",
                    "response_of_findings": "",
                    "images": [],
                    "processing_time": time.time() - start_time,
                    "error": "Rate limit exceeded"
                }
            elif "An unexpected error occurred during analysis" in response_text or "Error querying Gemini" in response_text:
                logger.error(f"Gemini processing failed for case {self.case_id} due to an unexpected error: {response_text}")
                return {
                    "case_id": self.case_id,
                    "section": section,
                    "response": "An internal error occurred while processing the documents with the AI model.",
                    "response_of_findings": "",
                    "images": [],
                    "processing_time": time.time() - start_time,
                    "error": "Internal Gemini error"
                }

            # Fetch and encode images
            base64_encoded_images = []
            try:
                # Get base64 images for the specified section
                base64_encoded_images = await self.service.get_base64_images_for_section(section)
            except Exception as img_err:
                logger.error(f"Failed to fetch or encode images for case {self.case_id}, section {section}: {img_err}")

            # Extract findings and background based on the section
            from src.inference.postprocessing import extract_findings_and_background, parse_background_response

            # For Background Information section, use the new parsing function
            if section == "Background Information":
                logger.info(f"Using parse_background_response for Background Information section")
                response_of_findings, response_text_parsed = parse_background_response(response_text)

                return {
                    "case_id": self.case_id,
                    "section": section,
                    "response": response_text_parsed,
                    "response_of_findings": response_of_findings,
                    "images": base64_encoded_images,
                    "processing_time": time.time() - start_time
                }
            else:
                # For other sections, use the existing function
                findings_part, background_part = extract_findings_and_background(response_text)

                return {
                    "case_id": self.case_id,
                    "section": section,
                    "response": background_part,
                    "response_of_findings": findings_part,
                    "images": base64_encoded_images,
                    "processing_time": time.time() - start_time
                }

        except Exception as e:
            logger.error(f"Error in inference pipeline for case {self.case_id}, section {section}: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())

            return {
                "case_id": self.case_id,
                "section": section,
                "response": f"An error occurred during processing: {str(e)}",
                "response_of_findings": "",
                "images": [],
                "processing_time": time.time() - start_time,
                "error": str(e)
            }
