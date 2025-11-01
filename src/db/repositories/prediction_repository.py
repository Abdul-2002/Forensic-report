"""
Prediction repository for database operations.
"""
from typing import Dict, Any, List, Optional
import copy

from src.core.logging_config import get_logger
from src.db.models.prediction_log import PredictionLog
from src.db.repositories.base_repository import BaseRepository
from src.utils.file_helpers import upload_base64_image_to_azure

logger = get_logger(__name__)

class PredictionRepository(BaseRepository[PredictionLog]):
    """
    Prediction repository for database operations.
    """

    def __init__(self):
        """
        Initialize the prediction repository.
        """
        super().__init__("prediction_logs", PredictionLog)

    def get_by_case_id(self, case_id: str) -> List[Dict[str, Any]]:
        """
        Get predictions by case ID.

        Args:
            case_id: The case ID to search for.

        Returns:
            A list of prediction documents.
        """
        return self.read({"case_id": case_id})

    def get_by_case_id_and_section(self, case_id: str, section: str) -> Optional[Dict[str, Any]]:
        """
        Get a prediction by case ID and section.

        Args:
            case_id: The case ID to search for.
            section: The section to search for.

        Returns:
            The prediction document or None if not found.
        """
        return self.read_one({"case_id": case_id, "section": section})

    def get_successful_predictions(self) -> List[Dict[str, Any]]:
        """
        Get all successful predictions.

        Returns:
            A list of successful prediction documents.
        """
        return self.read({"status": "success"})

    def get_failed_predictions(self) -> List[Dict[str, Any]]:
        """
        Get all failed predictions.

        Returns:
            A list of failed prediction documents.
        """
        return self.read({"status": {"$ne": "success"}})

    def create_with_large_images(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new prediction document, handling large images by storing them in Azure Blob Storage.
        Also handles cases where there are too many images by batching them.

        Args:
            data: The prediction data including potentially large base64 images.

        Returns:
            A dictionary with the inserted ID or an error message.
        """
        try:
            # Make a deep copy of the data to avoid modifying the original
            processed_data = copy.deepcopy(data)

            # Check if there are images to process
            if "images" in processed_data and processed_data["images"]:
                case_id = processed_data.get("case_id", "unknown")
                section = processed_data.get("section", "unknown")

                # Log the number of images to process
                image_count = len(processed_data["images"])
                logger.info(f"Processing {image_count} images for case {case_id}, section {section}")

                # Process each image
                processed_images = []
                for i, img in enumerate(processed_data["images"]):
                    # Skip if no base64_content
                    if "base64_content" not in img:
                        processed_images.append(img)
                        continue

                    # Get the description and base64 content
                    description = img.get("description", "")
                    base64_content = img["base64_content"]

                    # Log progress for large image sets
                    if image_count > 10 and i % 5 == 0:
                        logger.info(f"Processing image {i+1}/{image_count} for {case_id}, section {section}")

                    # Upload to Azure and get metadata
                    image_metadata = upload_base64_image_to_azure(
                        case_id=case_id,
                        section=section,
                        base64_content=base64_content,
                        description=description
                    )

                    # If there was an error, log it but continue
                    if "error" in image_metadata:
                        logger.error(f"Error uploading image {i+1}/{image_count} for {case_id}, {section}: {image_metadata['error']}")
                        # Add a placeholder without the base64 content
                        processed_images.append({
                            "description": description,
                            "file_path": img.get("file_path", "unknown"),
                            "section": section,
                            "error": image_metadata["error"]
                        })
                    elif "skipped" in image_metadata:
                        logger.warning(f"Skipped large image {i+1}/{image_count} for {case_id}, {section}: {image_metadata['skipped']}")
                        processed_images.append(image_metadata)
                    else:
                        # Add the processed image metadata (without base64_content)
                        processed_images.append(image_metadata)

                # Replace the images array with processed images
                processed_data["images"] = processed_images

                # Check if we have too many images for a single document (MongoDB has a 16MB limit)
                # If we have more than 50 images, we'll split them into batches
                if len(processed_images) > 50:
                    logger.warning(f"Large number of images ({len(processed_images)}) for {case_id}, {section}. Splitting into batches.")
                    return self._create_with_batched_images(processed_data)

            # Now create the document with processed data
            return super().create(processed_data)

        except Exception as e:
            logger.error(f"Error creating prediction with large images: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {"error": str(e)}

    def _create_with_batched_images(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create multiple prediction documents when there are too many images for a single document.

        Args:
            data: The prediction data with processed images.

        Returns:
            A dictionary with the inserted ID of the main document or an error message.
        """
        try:
            # Make a copy of the data
            main_data = copy.deepcopy(data)
            case_id = main_data.get("case_id", "unknown")
            section = main_data.get("section", "unknown")

            # Get all images
            all_images = main_data.get("images", [])
            image_count = len(all_images)

            # If we have a reasonable number of images, just create a single document
            if image_count <= 50:
                return super().create(main_data)

            # Split images into batches of 50
            batch_size = 50
            image_batches = []
            for i in range(0, image_count, batch_size):
                image_batches.append(all_images[i:i+batch_size])

            logger.info(f"Split {image_count} images into {len(image_batches)} batches for {case_id}, {section}")

            # Keep the first batch in the main document
            main_data["images"] = image_batches[0]
            main_data["image_batch"] = 1
            main_data["total_batches"] = len(image_batches)
            main_data["total_images"] = image_count

            # Create the main document
            main_result = super().create(main_data)

            if "error" in main_result:
                logger.error(f"Error creating main batch document: {main_result['error']}")
                return main_result

            main_id = main_result["inserted_id"]
            logger.info(f"Created main batch document with ID: {main_id}")

            # Create additional documents for the remaining batches
            for i, batch in enumerate(image_batches[1:], start=2):
                batch_data = {
                    "case_id": case_id,
                    "section": section,
                    "response": f"Batch {i} of {len(image_batches)} for {section}",
                    "response_of_findings": "",
                    "images": batch,
                    "processing_time": main_data.get("processing_time", 0),
                    "status": "success",
                    "image_batch": i,
                    "total_batches": len(image_batches),
                    "main_batch_id": str(main_id),
                    "total_images": image_count
                }

                batch_result = super().create(batch_data)
                if "error" in batch_result:
                    logger.error(f"Error creating batch {i} document: {batch_result['error']}")
                    # Continue with other batches even if one fails

            return main_result

        except Exception as e:
            logger.error(f"Error creating batched prediction documents: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {"error": str(e)}
