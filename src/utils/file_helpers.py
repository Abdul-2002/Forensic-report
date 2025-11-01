"""
File handling utilities.
"""
import os
import shutil
import base64
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, List
import uuid

from fastapi import UploadFile
from azure.storage.blob import BlobServiceClient, BlobSasPermissions, generate_blob_sas
from datetime import datetime, timedelta

from src.core.config import AZURE_CONNECTION_STRING, AZURE_CONTAINER_NAME, AZURE_ACCOUNT_NAME, AZURE_ACCOUNT_KEY, UPLOAD_DIR
from src.core.logging_config import get_logger

logger = get_logger(__name__)

async def save_uploaded_file(file: UploadFile, file_path: str) -> bool:
    """
    Save an uploaded file to the specified path.

    Args:
        file: The uploaded file.
        file_path: The path to save the file to.

    Returns:
        True if the file was saved successfully, False otherwise.
    """
    try:
        content = await file.read()
        if len(content) == 0:
            logger.warning(f"File {file.filename} is empty")
            return False

        with open(file_path, "wb") as f:
            f.write(content)

        logger.info(f"Saved file to {file_path}")

        # Verify the file exists and has content
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            return True
        else:
            logger.error(f"Failed to save file or file is empty: {file_path}")
            return False
    except Exception as e:
        logger.error(f"Error saving file {file.filename}: {str(e)}")
        return False

def upload_to_azure(case_id: str, file_category: str, file_path: str) -> str:
    """
    Upload a file to Azure Blob Storage.

    Args:
        case_id: The case ID.
        file_category: The file category.
        file_path: The path to the file to upload.

    Returns:
        The Azure URL if successful, empty string otherwise.
    """
    try:
        # Ensure file exists before upload
        if not os.path.exists(file_path):
            logger.error(f"File does not exist for Azure upload: {file_path}")
            return ""

        # Create Azure upload path - combine the case_id with file_category
        azure_case_id = f"{case_id}/{file_category}" if file_category else case_id

        # Convert string path to Path object as expected by upload_file
        file_path_obj = Path(file_path)

        # Create blob service client
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
        container_client = blob_service_client.get_container_client(AZURE_CONTAINER_NAME)

        # Create blob name
        blob_name = f"{azure_case_id}/{file_path_obj.name}"

        # Upload the file to Azure
        blob_client = container_client.get_blob_client(blob_name)

        with open(file_path, "rb") as data:
            blob_client.upload_blob(data, overwrite=True)

        # Generate URL
        azure_url = f"https://{AZURE_ACCOUNT_NAME}.blob.core.windows.net/{AZURE_CONTAINER_NAME}/{blob_name}"
        logger.info(f"File uploaded to Azure: {azure_url}")
        return azure_url
    except Exception as e:
        logger.error(f"Error uploading to Azure: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return ""

def create_sas_link(case_id: str, file_name: str) -> Optional[str]:
    """
    Create a SAS link for a file in Azure Blob Storage.

    Args:
        case_id: The case ID.
        file_name: The file name.

    Returns:
        The SAS link if successful, None otherwise.
    """
    try:
        # Azure expects forward slashes in paths
        blob_name = f"{case_id}/reports/{file_name}"

        # Log the full blob path for debugging
        logger.info(f"Creating SAS link for blob: {blob_name}")

        # Generate SAS token without checking existence first
        # because sometimes exists() method fails even when the blob is there
        sas_token = generate_blob_sas(
            account_name=AZURE_ACCOUNT_NAME,
            container_name=AZURE_CONTAINER_NAME,
            blob_name=blob_name,
            account_key=AZURE_ACCOUNT_KEY,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.utcnow() + timedelta(minutes=15),
        )

        file_url = f"https://{AZURE_ACCOUNT_NAME}.blob.core.windows.net/{AZURE_CONTAINER_NAME}/{blob_name}?{sas_token}"
        logger.info(f"Successfully generated SAS link: {file_url[:50]}...")
        return file_url
    except Exception as e:
        logger.error(f"Error generating SAS link: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None

async def ensure_directory_in_azure(case_id: str) -> bool:
    """
    Ensure the case directory structure exists in Azure by uploading a marker file.

    Args:
        case_id: The case ID.

    Returns:
        True if successful, False otherwise.
    """
    try:
        # Create a simple marker file to ensure directory structure
        marker_path = os.path.join(UPLOAD_DIR, f"{case_id}_marker.txt")
        with open(marker_path, 'w') as f:
            f.write(f"Case directory marker for {case_id}")

        # Upload marker to case_id root
        # We don't need the return value, just need to ensure the upload happens
        _ = upload_to_azure(case_id, "", marker_path)

        # Create and upload markers for subdirectories
        for subdir in ["images", "pdfs", "exhibits"]:
            subdir_marker = os.path.join(UPLOAD_DIR, f"{case_id}_{subdir}_marker.txt")
            with open(subdir_marker, 'w') as f:
                f.write(f"Case {subdir} directory marker for {case_id}")

            # Upload to subdirectory
            subdir_path = f"{case_id}/{subdir}"
            _ = upload_to_azure(subdir_path, "", subdir_marker)

        # Create and upload markers for exhibit subdirectories
        for exhibit_subdir in ["images", "pdfs"]:
            exhibit_marker = os.path.join(UPLOAD_DIR, f"{case_id}_exhibits_{exhibit_subdir}_marker.txt")
            with open(exhibit_marker, 'w') as f:
                f.write(f"Case exhibits {exhibit_subdir} directory marker for {case_id}")

            # Upload to subdirectory
            exhibit_path = f"{case_id}/exhibits/{exhibit_subdir}"
            _ = upload_to_azure(exhibit_path, "", exhibit_marker)

        # Clean up marker files
        try:
            os.remove(marker_path)
            for subdir in ["images", "pdfs", "exhibits"]:
                os.remove(os.path.join(UPLOAD_DIR, f"{case_id}_{subdir}_marker.txt"))
            for exhibit_subdir in ["images", "pdfs"]:
                os.remove(os.path.join(UPLOAD_DIR, f"{case_id}_exhibits_{exhibit_subdir}_marker.txt"))
        except:
            pass

        return True
    except Exception as e:
        logger.error(f"Error ensuring Azure directory structure: {str(e)}")
        return False

def upload_base64_image_to_azure(case_id: str, section: str, base64_content: str, description: str = "") -> Dict[str, Any]:
    """
    Upload a base64 encoded image to Azure Blob Storage.

    Args:
        case_id: The case ID.
        section: The section name (e.g., "Discussion").
        base64_content: The base64 encoded image content.
        description: Optional description of the image.

    Returns:
        A dictionary with image metadata including azure_url, or error information.
    """
    temp_file_path = None
    try:
        # Check if base64_content is too large (log size for debugging)
        content_size_mb = len(base64_content) / (1024 * 1024)
        logger.info(f"Processing base64 image for {case_id}, section {section}, size: {content_size_mb:.2f} MB")

        # Skip extremely large images (over 20MB base64 size)
        if content_size_mb > 20:
            logger.warning(f"Image too large ({content_size_mb:.2f} MB) for {case_id}, section {section}. Skipping.")
            return {
                "description": description,
                "file_path": f"{case_id}_{section}_skipped.jpg",
                "section": section,
                "azure_url": "",
                "skipped": "Image too large"
            }

        # Extract the actual base64 content if it's a data URI
        if "base64," in base64_content:
            # Format is typically: data:image/jpeg;base64,/9j/4AAQSkZJRg...
            base64_data = base64_content.split("base64,")[1]
        else:
            base64_data = base64_content

        # Decode base64 to binary
        try:
            image_data = base64.b64decode(base64_data)
        except Exception as decode_err:
            logger.error(f"Failed to decode base64 data: {str(decode_err)}")
            return {
                "description": description,
                "file_path": f"{case_id}_{section}_invalid.jpg",
                "section": section,
                "azure_url": "",
                "error": "Invalid base64 data"
            }

        # Create a unique filename
        unique_id = uuid.uuid4().hex
        file_extension = "jpg"  # Default to jpg

        # Try to determine the file type from the data URI
        if "image/png" in base64_content:
            file_extension = "png"
        elif "image/jpeg" in base64_content or "image/jpg" in base64_content:
            file_extension = "jpg"
        elif "image/gif" in base64_content:
            file_extension = "gif"

        filename = f"{case_id}_{section}_{unique_id}.{file_extension}"
        logger.info(f"Created filename for image: {filename}")

        # Create a temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{file_extension}") as temp_file:
            temp_file.write(image_data)
            temp_file_path = temp_file.name

        try:
            # Upload to Azure
            logger.info(f"Uploading image to Azure: {temp_file_path}")
            azure_url = upload_to_azure(case_id, f"images", temp_file_path)

            if not azure_url:
                logger.error(f"Failed to get Azure URL for {filename}")
                return {
                    "description": description,
                    "file_path": filename,
                    "section": section,
                    "azure_url": "",
                    "error": "Failed to upload to Azure"
                }

            # Create metadata
            image_metadata = {
                "description": description,
                "file_path": filename,
                "section": section,
                "azure_url": azure_url,
                # Don't include the base64_content here to save space
            }

            logger.info(f"Successfully uploaded image to Azure: {azure_url}")

            # Clean up the temporary file
            if temp_file_path and os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
                temp_file_path = None

            return image_metadata

        except Exception as upload_err:
            logger.error(f"Error uploading base64 image to Azure: {str(upload_err)}")
            import traceback
            logger.error(traceback.format_exc())

            # Clean up the temporary file
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                    temp_file_path = None
                except Exception as cleanup_err:
                    logger.error(f"Error cleaning up temp file: {str(cleanup_err)}")

            return {
                "description": description,
                "file_path": filename,
                "section": section,
                "azure_url": "",
                "error": str(upload_err)
            }

    except Exception as e:
        logger.error(f"Error processing base64 image: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())

        # Clean up the temporary file if it exists
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except:
                pass

        return {
            "description": description,
            "file_path": f"{case_id}_{section}_error.jpg",
            "section": section,
            "azure_url": "",
            "error": str(e)
        }