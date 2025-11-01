import json
import shutil
import tempfile
from pathlib import Path
from fastapi import APIRouter, HTTPException, status, UploadFile, File, Form, Request
from typing import List, Optional
from pydantic import BaseModel
from datetime import date, datetime
import uuid
from pymongo.errors import PyMongoError
from utils.CRUD_utils import CRUDUtils, ReadWrite  # Import CRUD Utility class
from src.controller.gemini_case_handler import GeminiHandler
import requests
from utils.Mongodbcnnection import MongoDBConnection
import base64
import logging
import os
from pdf2image import convert_from_path, convert_from_bytes
from PIL import Image
import io

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize MongoDB connection
mongo_connection = MongoDBConnection()
database = mongo_connection.get_database()
CASE_COLLECTION = "case_add"
case_collection = database[CASE_COLLECTION]

# Environment variables
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DATABASE_NAME = os.getenv("DATABASE_NAME", "your_db_name")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "case_add")  # Adjust collection name if needed

# Define the case-related models
class MetaData(BaseModel):
    description: str
    file_path: str  # Assuming the file path is saved after upload

class Case(BaseModel):
    case_id: str
    case_name: str
    location: str
    date: str
    time: str
    description: str
    images: List[MetaData]
    pdf: List[MetaData]
    embedding: Optional[str] = ""  # Made optional as embeddings are no longer used
    exhibits: Optional[dict] = None

class QueryRequest(BaseModel):
    case_id: str
    case_type: Optional[str] = None
    section: str

# Initialize Router
case_router = APIRouter()

# Initialize Azure storage client
azure_storage = ReadWrite("original-data")

# Initialize CRUD Utility for the 'cases' collection
case_crud = CRUDUtils("case_add")

# Define upload directories
UPLOAD_DIR = "uploads"
REPORTS_DIR = os.path.join(UPLOAD_DIR, "reports")
IMAGES_DIR = os.path.join(UPLOAD_DIR, "images")
EXHIBITS_DIR = os.path.join(UPLOAD_DIR, "exhibits")

# Create directories if they don't exist
os.makedirs(REPORTS_DIR, exist_ok=True)
os.makedirs(IMAGES_DIR, exist_ok=True)
os.makedirs(EXHIBITS_DIR, exist_ok=True)

# Helper functions
def is_valid_image_file(filename: str) -> bool:
    """Check if a filename has a valid image extension."""
    if not filename:
        return False
    valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp']
    return any(filename.lower().endswith(ext) for ext in valid_extensions)


async def convert_pdf_to_images(pdf_url: str, description: str) -> List[dict]:
    """
    Convert a PDF to a list of base64-encoded images, one per page.

    Args:
        pdf_url: The URL of the PDF file
        description: A description of the PDF

    Returns:
        A list of dictionaries, each containing a base64-encoded image
    """
    logger.info(f"Converting PDF to images: {description} from {pdf_url}")
    images = []

    try:
        # Create a temporary directory to store the PDF
        with tempfile.TemporaryDirectory() as temp_dir:
            # Download the PDF
            response = requests.get(pdf_url, stream=True, timeout=30)
            response.raise_for_status()

            # Save the PDF to a temporary file
            pdf_path = os.path.join(temp_dir, "temp.pdf")
            with open(pdf_path, "wb") as f:
                f.write(response.content)

            try:
                # Try to convert the PDF to images using pdf2image
                # Note: This requires poppler to be installed
                pdf_images = convert_from_path(pdf_path, dpi=200)

                # Process each page
                for i, img in enumerate(pdf_images):
                    # Save the image to a bytes buffer
                    img_buffer = io.BytesIO()
                    img.save(img_buffer, format="PNG")
                    img_buffer.seek(0)

                    # Encode the image to base64
                    base64_encoded = base64.b64encode(img_buffer.getvalue()).decode('utf-8')

                    # Create the data URI
                    base64_data_uri = f"data:image/png;base64,{base64_encoded}"

                    # Add the image to the list
                    # Get the exhibit number from the image metadata if available
                    exhibit_num = i+1

                    # Check if description already contains "Exhibit" to avoid duplication
                    if "Exhibit" in description:
                        # Just add the page number
                        image_description = f"{description} - Page {i+1}"
                    else:
                        # Add "Exhibit" prefix
                        image_description = f"Exhibit {exhibit_num}: {description} - Page {i+1}"

                    images.append({
                        "description": image_description,
                        "file_path": f"page_{i+1}.png",
                        "section": "Exhibits",
                        "base64_content": base64_data_uri,
                        "page_number": i+1
                    })

                logger.info(f"Successfully converted PDF to {len(images)} images: {description}")
            except Exception as pdf_err:
                # If pdf2image fails (e.g., poppler not installed), create a placeholder image
                logger.warning(f"Failed to convert PDF to images using pdf2image: {pdf_err}. Creating placeholder image.")

                # Create a placeholder image with the PDF description
                # Get the exhibit number (default to 1)
                exhibit_num = 1

                # Check if description already contains "Exhibit" to avoid duplication
                if "Exhibit" in description:
                    # Just add the PDF indicator
                    image_description = f"{description} (PDF - view in browser)"
                else:
                    # Add "Exhibit" prefix
                    image_description = f"Exhibit {exhibit_num}: {description} (PDF - view in browser)"

                placeholder_image = {
                    "description": image_description,
                    "file_path": "pdf_placeholder.png",
                    "section": "Exhibits",
                    "base64_content": f"data:application/pdf;base64,{base64.b64encode(response.content).decode('utf-8')}",
                    "page_number": 1,
                    "is_pdf": True,
                    "pdf_url": pdf_url
                }

                images.append(placeholder_image)

    except Exception as e:
        logger.error(f"Error converting PDF to images: {description} from {pdf_url}: {e}")
        import traceback
        logger.error(traceback.format_exc())

    return images

async def get_all_exhibits(case_id: str) -> List[dict]:
    """
    Fetches all exhibits (images and PDFs) for a given case_id,
    downloads them from their Azure URL, and returns them as base64 encoded strings.
    For PDFs, each page is converted to an image.

    Args:
        case_id: The case ID

    Returns:
        A list of dictionaries, each containing a base64-encoded image
        Note: The InferenceService version returns a tuple with (images, exhibit_names),
        but this version only returns the images for backward compatibility.
    """
    logger.info(f"Fetching all exhibits for case '{case_id}'")
    base64_images = []

    try:
        # Use the existing CRUD utility to fetch the case data
        cases = case_crud.read({"case_id": case_id})
        if "error" in cases or not cases:
            logger.error(f"Case '{case_id}' not found or error fetching: {cases.get('error', 'Not found')}")
            return [] # Return empty list if case not found or error

        case_data = cases[0]

        # Check if exhibits exist
        if "exhibits" not in case_data or not case_data["exhibits"]:
            logger.info(f"No exhibits found for case '{case_id}'")
            return []

        exhibits = case_data["exhibits"]
        exhibit_count = 1  # Counter for exhibit numbering

        # Process exhibit images
        exhibit_images = exhibits.get("images", [])
        for image_meta in exhibit_images:
            azure_url = image_meta.get("azure_url")
            description = image_meta.get("description", f"Exhibit {exhibit_count}")
            file_path = image_meta.get("file_path", "No path")

            if not azure_url:
                logger.warning(f"Skipping exhibit image (no azure_url): {description} in case '{case_id}'")
                continue

            try:
                # Fetch the image from Azure URL
                response = requests.get(azure_url, stream=True, timeout=20)
                response.raise_for_status()

                # Read image content
                image_bytes = response.content

                if not image_bytes:
                    logger.warning(f"Skipping exhibit image (empty content): {description} from {azure_url}")
                    continue

                # Encode image bytes to base64
                base64_encoded_image = base64.b64encode(image_bytes).decode('utf-8')

                # Determine content type
                file_extension = os.path.splitext(file_path)[1].lower()
                content_type = f"image/{file_extension.replace('.', '')}"
                if 'png' in file_extension:
                    content_type = 'image/png'
                elif 'jpg' in file_extension or 'jpeg' in file_extension:
                    content_type = 'image/jpeg'
                elif 'gif' in file_extension:
                    content_type = 'image/gif'

                # Prepend the data URI scheme header
                base64_data_uri = f"data:{content_type};base64,{base64_encoded_image}"

                # Add to the list with exhibit number
                # Check if description already contains "Exhibit" to avoid duplication
                if "Exhibit" in description:
                    # Use the description as is
                    image_description = description
                else:
                    # Add "Exhibit" prefix
                    image_description = f"Exhibit {exhibit_count}: {description}"

                base64_images.append({
                    "description": image_description,
                    "file_path": file_path,
                    "section": "Exhibits",
                    "base64_content": base64_data_uri,
                    "exhibit_number": exhibit_count
                })

                logger.info(f"Successfully fetched and encoded exhibit image: {description} from {azure_url}")
                exhibit_count += 1

            except Exception as e:
                logger.error(f"Error processing exhibit image {description} from {azure_url}: {e}")

        # Process exhibit PDFs
        exhibit_pdfs = exhibits.get("pdfs", [])
        for pdf_meta in exhibit_pdfs:
            azure_url = pdf_meta.get("azure_url")
            description = pdf_meta.get("description", f"Exhibit {exhibit_count}")

            if not azure_url:
                logger.warning(f"Skipping exhibit PDF (no azure_url): {description} in case '{case_id}'")
                continue

            try:
                # Convert PDF to images
                pdf_images = await convert_pdf_to_images(azure_url, description)

                # Add exhibit number to each page
                for img in pdf_images:
                    img["exhibit_number"] = exhibit_count

                # Add all pages to the result
                base64_images.extend(pdf_images)

                # Increment exhibit counter only once per PDF
                if pdf_images:
                    exhibit_count += 1

            except Exception as e:
                logger.error(f"Error processing exhibit PDF {description} from {azure_url}: {e}")

        # Sort by exhibit number
        base64_images.sort(key=lambda x: (x.get("exhibit_number", 999), x.get("page_number", 0)))

    except Exception as e:
        logger.error(f"Error retrieving or processing exhibits for case '{case_id}': {e}")
        import traceback
        logger.error(traceback.format_exc())

    logger.info(f"Finished fetching exhibits for case '{case_id}'. Found {len(base64_images)} exhibit images.")
    return base64_images

async def get_base64_images_for_section(case_id: str, section: str) -> List[dict]:
    """
    Fetches images for a given case_id and section from MongoDB,
    downloads them from their Azure URL, and returns them as base64 encoded strings.
    """
    logger.info(f"Fetching images for case '{case_id}', section '{section}'")
    base64_images = []

    try:
        # Use the existing CRUD utility to fetch the case data
        cases = case_crud.read({"case_id": case_id})
        if "error" in cases or not cases:
            logger.error(f"Case '{case_id}' not found or error fetching: {cases.get('error', 'Not found')}")
            return [] # Return empty list if case not found or error

        case_data = cases[0]
        all_images = case_data.get("images", [])

        # Filter images by the requested section
        section_images = [img for img in all_images if img.get("section") == section]

        if not section_images:
            logger.info(f"No images found for case '{case_id}', section '{section}'")
            return []

        for image_meta in section_images:
            azure_url = image_meta.get("azure_url")
            description = image_meta.get("description", "No description")
            file_path = image_meta.get("file_path", "No path") # Useful for identification

            if not azure_url:
                logger.warning(f"Skipping image (no azure_url): {description} in case '{case_id}'")
                continue

            try:
                # Fetch the image from Azure URL
                # Add a timeout to prevent hanging indefinitely
                response = requests.get(azure_url, stream=True, timeout=20) # Timeout in seconds
                response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)

                # Read image content
                image_bytes = response.content

                if not image_bytes:
                    logger.warning(f"Skipping image (empty content): {description} from {azure_url}")
                    continue

                # Encode image bytes to base64
                base64_encoded_image = base64.b64encode(image_bytes).decode('utf-8')

                # Determine content type (simple check based on extension)
                file_extension = os.path.splitext(file_path)[1].lower()
                content_type = f"image/{file_extension.replace('.', '')}"
                if 'png' in file_extension:
                    content_type = 'image/png'
                elif 'jpg' in file_extension or 'jpeg' in file_extension:
                    content_type = 'image/jpeg'
                elif 'gif' in file_extension:
                    content_type = 'image/gif'
                # Add more types if needed

                # Prepend the data URI scheme header
                base64_data_uri = f"data:{content_type};base64,{base64_encoded_image}"


                base64_images.append({
                    "description": description,
                    "file_path": file_path,
                    "section": section,
                    "base64_content": base64_data_uri # Send the full data URI
                })
                logger.info(f"Successfully fetched and encoded image: {description} from {azure_url}")

            except requests.exceptions.RequestException as req_err:
                logger.error(f"Error fetching image {description} from {azure_url}: {req_err}")
            except Exception as enc_err:
                logger.error(f"Error encoding image {description} from {azure_url}: {enc_err}")

    except Exception as e:
        logger.error(f"Error retrieving or processing images for case '{case_id}', section '{section}': {e}")
        import traceback
        logger.error(traceback.format_exc())
        # Depending on desired behavior, you might want to return [] or raise an error

    logger.info(f"Finished fetching images for case '{case_id}', section '{section}'. Found {len(base64_images)} images.")
    return base64_images

async def save_uploaded_file(file: UploadFile, file_path: str) -> bool:
    """
    Save an uploaded file to the specified path.
    Returns True if successful, False otherwise.
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
    Returns the Azure URL if successful, empty string otherwise.

    Note: The ReadWrite.upload_file method expects a Path object, not a string path.
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

        # Upload the file to Azure
        azure_url = azure_storage.upload_file(azure_case_id, file_path_obj)
        if azure_url:
            logger.info(f"File uploaded to Azure: {azure_url}")
            return azure_url
        else:
            logger.warning(f"Azure upload returned None for {file_path}")
            return ""
    except Exception as e:
        logger.error(f"Error uploading to Azure: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return ""

async def process_file_upload(file: UploadFile, case_id: str, file_idx: int, category: str,
                        local_dir: str, description: str = "", section: str = "") -> dict:
    """
    Process a single file upload (image or PDF).
    Returns metadata dict if successful, empty dict otherwise.
    """
    if not file or not hasattr(file, 'filename') or not file.filename:
        return {}

    try:
        # Generate unique filename
        file_ext = os.path.splitext(file.filename)[1]
        if category == "pdfs" and file_ext.lower() != '.pdf':
            file_ext = '.pdf'

        unique_filename = f"{case_id}_{category[:-1]}_{file_idx}{file_ext}"
        file_path = os.path.join(local_dir, unique_filename)

        # Save file locally
        if not await save_uploaded_file(file, file_path):
            return {}

        # For case_id folder structure (mirroring the upload folder structure)
        case_dir_path = os.path.join(UPLOAD_DIR, case_id, category)
        os.makedirs(case_dir_path, exist_ok=True)
        case_file_path = os.path.join(case_dir_path, unique_filename)

        # Copy the file to the case directory structure
        try:
            shutil.copy2(file_path, case_file_path)
            logger.info(f"Copied file to case directory: {case_file_path}")
        except Exception as e:
            logger.error(f"Error copying file to case directory: {str(e)}")

        # Create standardized path format and metadata
        rel_path = f"{case_id}/{category}/{unique_filename}"

        file_metadata = {
            "description": description or f"{category[:-1].capitalize()} {file_idx+1}: {file.filename}",
            "file_path": rel_path
        }

        if section:
            file_metadata["section"] = section

        # Upload to Azure - both from the file in the processing directory
        # Pass an empty string for file_category since the case_id parameter will now include the category
        azure_url = upload_to_azure(f"{case_id}/{category}", "", file_path)
        if azure_url:
            file_metadata["azure_url"] = azure_url

        # Also upload the file from the case directory structure
        if os.path.exists(case_file_path):
            case_azure_url = upload_to_azure(f"{case_id}/{category}", "", case_file_path)
            if case_azure_url and not azure_url:
                file_metadata["azure_url"] = case_azure_url

        return file_metadata

    except Exception as e:
        logger.error(f"Error processing {category} file {file_idx}: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {}

# The generate_embeddings function has been removed as it's no longer needed with the Gemini approach

async def process_exhibit_file(file: UploadFile, case_id: str, file_idx: int, file_type: str,
                        local_dir: str, file_name: str = "", section: str = "Exhibits") -> dict:
    """
    Process a single exhibit file (image or PDF).
    Returns metadata dict if successful, empty dict otherwise.

    Args:
        file: The uploaded file
        case_id: The case ID
        file_idx: The index of the file
        file_type: The type of file ("images" or "pdfs")
        local_dir: The local directory to save the file
        file_name: The name to use for the file (if provided)
        section: The section the file belongs to (default: "Exhibits")
    """
    if not file or not hasattr(file, 'filename') or not file.filename:
        return {}

    try:
        # Generate unique filename
        file_ext = os.path.splitext(file.filename)[1]
        if file_type == "pdfs" and file_ext.lower() != '.pdf':
            file_ext = '.pdf'

        # Use provided file_name if available, otherwise use original filename
        base_name = file_name if file_name else os.path.splitext(file.filename)[0]
        unique_filename = f"{case_id}_exhibit_{file_type[:-1]}_{file_idx}{file_ext}"
        file_path = os.path.join(local_dir, unique_filename)

        # Save file locally
        if not await save_uploaded_file(file, file_path):
            return {}

        # For case_id folder structure (mirroring the upload folder structure)
        case_dir_path = os.path.join(UPLOAD_DIR, case_id, "exhibits", file_type)
        os.makedirs(case_dir_path, exist_ok=True)
        case_file_path = os.path.join(case_dir_path, unique_filename)

        # Copy the file to the case directory structure
        try:
            shutil.copy2(file_path, case_file_path)
            logger.info(f"Copied exhibit file to case directory: {case_file_path}")
        except Exception as e:
            logger.error(f"Error copying exhibit file to case directory: {str(e)}")

        # Create standardized path format and metadata
        rel_path = f"{case_id}/exhibits/{file_type}/{unique_filename}"

        file_metadata = {
            "description": base_name,
            "file_path": rel_path,
            "file_name": base_name + file_ext,
            "section": section,
            "exhibit_number": file_idx+1
        }

        # Upload to Azure
        azure_url = upload_to_azure(f"{case_id}/exhibits/{file_type}", "", file_path)
        if azure_url:
            file_metadata["azure_url"] = azure_url

        # Also upload the file from the case directory structure
        if os.path.exists(case_file_path):
            case_azure_url = upload_to_azure(f"{case_id}/exhibits/{file_type}", "", case_file_path)
            if case_azure_url and not azure_url:
                file_metadata["azure_url"] = case_azure_url

        return file_metadata

    except Exception as e:
        logger.error(f"Error processing exhibit {file_type} file {file_idx}: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {}

async def ensure_directory_in_azure(case_id: str) -> bool:
    """
    Ensure the case directory structure exists in Azure by uploading a marker file.
    Returns True if successful, False otherwise.
    """
    try:
        # Create a simple marker file to ensure directory structure
        marker_path = os.path.join(UPLOAD_DIR, f"{case_id}_marker.txt")
        with open(marker_path, 'w') as f:
            f.write(f"Case directory marker for {case_id}")

        # The ReadWrite.upload_file expects a Path object, not a string
        marker_path_obj = Path(marker_path)

        # Upload marker to case_id root
        # We don't need the return value, just need to ensure the upload happens
        _ = azure_storage.upload_file(case_id, marker_path_obj)

        # Create and upload markers for subdirectories
        for subdir in ["images", "pdfs", "exhibits"]:
            subdir_marker = os.path.join(UPLOAD_DIR, f"{case_id}_{subdir}_marker.txt")
            with open(subdir_marker, 'w') as f:
                f.write(f"Case {subdir} directory marker for {case_id}")

            # Upload to subdirectory
            subdir_path = f"{case_id}/{subdir}"
            subdir_marker_obj = Path(subdir_marker)
            _ = azure_storage.upload_file(subdir_path, subdir_marker_obj)

        # Create and upload markers for exhibit subdirectories
        for exhibit_subdir in ["images", "pdfs"]:
            exhibit_marker = os.path.join(UPLOAD_DIR, f"{case_id}_exhibits_{exhibit_subdir}_marker.txt")
            with open(exhibit_marker, 'w') as f:
                f.write(f"Case exhibits {exhibit_subdir} directory marker for {case_id}")

            # Upload to subdirectory
            exhibit_path = f"{case_id}/exhibits/{exhibit_subdir}"
            exhibit_marker_obj = Path(exhibit_marker)
            _ = azure_storage.upload_file(exhibit_path, exhibit_marker_obj)

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

@case_router.post("/case-add", status_code=status.HTTP_201_CREATED)
async def add_case(
    request: Request,
    case_id: str = Form(...),
    case_name: str = Form(...),
    location: str = Form(...),
    date: str = Form(...),
    time: str = Form(...),
    description: Optional[str] = Form(None),
    image_count: int = Form(0),
    case_type: str = Form("Slip/Fall on Ice"),
    inspection_date: Optional[str] = Form(None),
    inspector_name: Optional[str] = Form(None),
    hub_file_number: Optional[str] = Form(None),
    injured_party_name: Optional[str] = Form(None),
    property_name: Optional[str] = Form(None),
    property_address: Optional[str] = Form(None),
    incident_date: Optional[str] = Form(None),
    incident_time: Optional[str] = Form(None),
    injured_party_present: Optional[str] = Form(None),
    voice_record_allowed: Optional[str] = Form(None),
    voice_record_link: Optional[str] = Form(None),
    dcof_test: Optional[str] = Form(None),
    dcof_explanation: Optional[str] = Form(None),
    handwritten_note: Optional[str] = Form(None),
    note_text: Optional[str] = Form(None),
    # exhibit_count is provided for backward compatibility but not used directly
    # as we use exhibit_image_count and exhibit_pdf_count instead
    exhibit_count: Optional[int] = Form(0),
    exhibit_image_count: Optional[int] = Form(0),
    exhibit_pdf_count: Optional[int] = Form(0),
):
    """
    Add a new case with file uploads handling.
    """
    try:
        # Log the total number of exhibits for debugging purposes
        total_exhibits = exhibit_count
        logger.info(f"Processing case with {total_exhibits} total exhibits, {exhibit_image_count} images and {exhibit_pdf_count} PDFs")

        # Check if case ID already exists
        existing_case = case_collection.find_one({"case_id": case_id})
        if existing_case:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"A case with ID '{case_id}' already exists. Please use a unique case ID."
            )

        # Get form data
        form = await request.form()

        # Log the form data for debugging
        logger.info(f"Case ID: {case_id}, Case Name: {case_name}")
        logger.info(f"Description from form parameter: {description}")

        # Log all form keys and values for debugging
        logger.info("All form data keys:")
        for key in form.keys():
            if key.startswith("image_description_"):
                # Log image descriptions separately to avoid cluttering the log
                logger.info(f"  {key}: (image description, length: {len(str(form[key]))})")
            else:
                # Log other form values
                logger.info(f"  {key}: {form[key]}")

        # Create case directory structure - both for processing and for storage
        case_dir = os.path.join(UPLOAD_DIR, case_id)
        case_image_dir = os.path.join(case_dir, "images")
        case_report_dir = os.path.join(case_dir, "pdfs")
        case_exhibit_dir = os.path.join(case_dir, "exhibits")
        case_exhibit_image_dir = os.path.join(case_exhibit_dir, "images")
        case_exhibit_pdf_dir = os.path.join(case_exhibit_dir, "pdfs")

        # Create directories if they don't exist
        os.makedirs(case_image_dir, exist_ok=True)
        os.makedirs(case_report_dir, exist_ok=True)
        os.makedirs(case_exhibit_image_dir, exist_ok=True)
        os.makedirs(case_exhibit_pdf_dir, exist_ok=True)

        logger.info(f"Created directories for case {case_id}")

        # Ensure the directory structure exists in Azure
        await ensure_directory_in_azure(case_id)

        # Process images
        images_data = []

        for i in range(image_count):
            image_file_key = f"image_file_{i}"

            if image_file_key in form:
                image_file = form[image_file_key]
                image_description = form.get(f"image_description_{i}", "")
                section = form.get(f"image_section_{i}", "background")

                # Log the image description for debugging
                logger.info(f"Processing image {i}, description: {image_description[:50]}...")

                image_metadata = await process_file_upload(
                    file=image_file,
                    case_id=case_id,
                    file_idx=i,
                    category="images",
                    local_dir=case_image_dir,
                    description=image_description,
                    section=section
                )

                if image_metadata:
                    images_data.append(image_metadata)

        # Process PDFs
        pdf_data = []
        pdf_report_count = int(form.get("pdf_report_count", "0"))

        for i in range(pdf_report_count):
            pdf_file_key = f"pdf_report_{i}"

            if pdf_file_key in form:
                pdf_file = form[pdf_file_key]

                pdf_metadata = await process_file_upload(
                    file=pdf_file,
                    case_id=case_id,
                    file_idx=i,
                    category="pdfs",
                    local_dir=case_report_dir
                )

                if pdf_metadata:
                    pdf_data.append(pdf_metadata)

        # Process exhibit images
        exhibit_images_data = []
        exhibit_image_count = int(form.get("exhibit_image_count", "0"))

        for i in range(exhibit_image_count):
            exhibit_image_key = f"exhibit_image_{i}"

            if exhibit_image_key in form:
                exhibit_image = form[exhibit_image_key]
                exhibit_image_name = form.get(f"exhibit_image_name_{i}", "")
                exhibit_image_section = form.get(f"exhibit_image_section_{i}", "Exhibits")

                exhibit_image_metadata = await process_exhibit_file(
                    file=exhibit_image,
                    case_id=case_id,
                    file_idx=i,
                    file_type="images",
                    local_dir=case_exhibit_image_dir,
                    file_name=exhibit_image_name,
                    section=exhibit_image_section
                )

                if exhibit_image_metadata:
                    exhibit_images_data.append(exhibit_image_metadata)

        # Process exhibit PDFs
        exhibit_pdfs_data = []
        exhibit_pdf_count = int(form.get("exhibit_pdf_count", "0"))

        for i in range(exhibit_pdf_count):
            exhibit_pdf_key = f"exhibit_pdf_{i}"

            if exhibit_pdf_key in form:
                exhibit_pdf = form[exhibit_pdf_key]
                exhibit_pdf_name = form.get(f"exhibit_pdf_name_{i}", "")

                exhibit_pdf_metadata = await process_exhibit_file(
                    file=exhibit_pdf,
                    case_id=case_id,
                    file_idx=i,
                    file_type="pdfs",
                    local_dir=case_exhibit_pdf_dir,
                    file_name=exhibit_pdf_name
                )

                if exhibit_pdf_metadata:
                    exhibit_pdfs_data.append(exhibit_pdf_metadata)

        # Get current timestamp
        timestamp = datetime.now().isoformat()

        # Log the case description before creating the case data
        logger.info(f"Case description before creating case data: {description}")

        # Check if description is being incorrectly assigned from an image description
        # This is to handle the case where the image description is being incorrectly assigned to the case description
        case_description = description

        # First check: if description is not empty and there are images
        if description and image_count > 0:
            # Check if the description matches any image description
            for i in range(image_count):
                image_desc_key = f"image_description_{i}"
                if image_desc_key in form:
                    image_desc = form.get(image_desc_key, "")
                    # If the description matches an image description, set it to empty
                    if description == image_desc:
                        logger.warning(f"Case description matches image description {i}, setting to empty")
                        case_description = ""
                        break

        # Second check: if the description is very long (likely an image description)
        if description and len(description) > 500:  # Arbitrary threshold for a very long description
            logger.warning(f"Case description is very long ({len(description)} chars), likely an image description. Setting to empty.")
            case_description = ""

        # Prepare case data for database
        case_data = {
            "case_id": case_id,
            "case_name": case_name,
            "location": location,
            "date": date,
            "time": time,
            "description": case_description or "",
            "images": images_data,
            "pdf": pdf_data,
            "case_type": case_type,
            "inspection_date": inspection_date,
            "inspector_name": inspector_name,
            "hub_file_number": hub_file_number,
            "injured_party_name": injured_party_name,
            "property_name": property_name,
            "property_address": property_address,
            "incident_date": incident_date,
            "incident_time": incident_time,
            "injured_party_present": injured_party_present,
            "voice_record_allowed": voice_record_allowed,
            "voice_record_link": voice_record_link,
            "dcof_test": dcof_test,
            "dcof_explanation": dcof_explanation,
            "handwritten_note": handwritten_note,
            "note_text": note_text,
            "created_at": timestamp,
            "embedding": "",
            "exhibits": {
                "images": exhibit_images_data,
                "pdfs": exhibit_pdfs_data
            }
        }

        # Log the case description after creating the case data
        logger.info(f"Case description in case_data: {case_data['description']}")

        # No embeddings are generated with the Gemini approach
        # Set embedding field to empty string for backward compatibility
        case_data["embedding"] = ""

        # Save to database
        insert_result = case_crud.create(case_data)
        if "error" in insert_result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=insert_result["error"]
            )

        # Add MongoDB ID to response
        case_data["_id"] = str(insert_result["inserted_id"])

        # Add pdf_paths for frontend compatibility
        case_data["pdf_paths"] = [pdf["file_path"] for pdf in case_data["pdf"]]

        # Return the completed case data
        return case_data

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Server error: {str(e)}"
        )


# The embedding-formation endpoint has been removed as it's no longer needed with the Gemini approach


@case_router.get("/cases")
async def get_cases():
    """
    API to fetch all cases from the database without any field transformations.
    """
    try:
        cases = case_crud.read({})
        if "error" in cases:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=cases["error"])

        # Only convert ObjectId to string for JSON serialization
        for case in cases:
            case["_id"] = str(case["_id"])

        # Sort cases by created_at or date
        cases.sort(key=lambda x: (
            x.get("created_at", ""),
            x.get("date", "")
        ), reverse=True)

        # Return raw data without model validation or field transformations
        return cases
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to fetch cases: {str(e)}")


@case_router.delete("/case-delete/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_case(case_id: str):
    """
    API to delete a case by case_id.
    """
    try:
        delete_result = case_crud.delete({"case_id": case_id})
        if delete_result["deleted_count"] == 0:
            raise HTTPException(status_code=404, detail="Case not found")

        return {"message": "Case deleted successfully"}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete case: {str(e)}")

@case_router.post("/query-case/")
async def query_case(request: QueryRequest):
    """
    Query a case using Gemini's document processing capabilities.
    Also fetches and returns base64 encoded images for the specified section.
    For the "Exhibits" section, returns all exhibits (images and PDFs) without using Gemini.
    Implements reactive rate limiting protection using extracted delays and backoff.
    """
    try:
        # Special handling for Exhibits section
        if request.section == "Exhibits":
            logger.info(f"Processing Exhibits section for case {request.case_id} - skipping Gemini analysis")

            # Get all exhibits (images and PDFs converted to images)
            exhibit_images = await get_all_exhibits(case_id=request.case_id)

            # Extract exhibit names from the images
            exhibit_names = []
            for img in exhibit_images:
                description = img.get("description", "")
                if description:
                    # Extract the base name without page numbers or other indicators
                    base_name = description
                    if " (" in base_name and ")" in base_name:
                        base_name = base_name.split(" (")[0]

                    # Only add if not already in the list and not a page indicator
                    if "Page" not in base_name and base_name not in exhibit_names:
                        exhibit_names.append(base_name)

            # Create a newline-separated string of exhibit names
            exhibit_names_string = "\n".join(exhibit_names)

            # Return the exhibits without Gemini analysis
            return {
                "case_id": request.case_id,
                "section": request.section,
                "response": "Exhibits section - displaying all case exhibits",
                "response_of_findings": "",
                "images": exhibit_images,
                "exhibit_names": exhibit_names,
                "exhibit_names_string": exhibit_names_string
            }

        # For all other sections, use Gemini as before
        # --- Get Gemini Analysis ---
        handler = GeminiHandler(case_id=request.case_id, case_type=request.case_type or "case_type_1")
        BASE_RETRY_DELAY_SECONDS = 5
        MAX_RETRIES = 3

        logger.info(f"Initiating Gemini query for case {request.case_id}, section '{request.section}' "
                    f"with base_retry_delay={BASE_RETRY_DELAY_SECONDS}, max_retries={MAX_RETRIES}")

        response_text = handler.create_unified_analysis(
            section=request.section,
            batch_size=3,
            base_retry_delay=BASE_RETRY_DELAY_SECONDS,
            max_retries=MAX_RETRIES
        )

        # --- Handle Gemini Response/Errors ---
        gemini_error = None
        if "Error: Rate limit exceeded" in response_text or "Error: Could not generate unified analysis due to persistent API rate limits" in response_text:
            logger.error(f"Gemini processing failed for case {request.case_id} due to rate limits after retries.")
            gemini_error = "Rate limit exceeded"
            # Don't raise HTTPException yet, try to get images first
        elif "An unexpected error occurred during analysis" in response_text or "Error querying Gemini" in response_text:
             logger.error(f"Gemini processing failed for case {request.case_id} due to an unexpected error: {response_text}")
             gemini_error = "Internal Gemini error"
             # Don't raise HTTPException yet
        elif "No documents found or processed" in response_text:
             logger.warning(f"No documents processed by Gemini for case {request.case_id}, section {request.section}.")
             # Proceed normally, response_text contains the message


        # --- Fetch and Encode Images ---
        base64_encoded_images = []
        try:
            # Call the helper function to get base64 images for the specified section
            base64_encoded_images = await get_base64_images_for_section(
                case_id=request.case_id,
                section=request.section
            )
        except Exception as img_err:
            # Log the error but don't necessarily fail the whole request
            # The Gemini response might still be valuable
            logger.error(f"Failed to fetch or encode images for case {request.case_id}, section {request.section}: {img_err}")


        # --- Handle Final Response and Potential Gemini Errors ---
        # If there was a critical Gemini error earlier, handle it appropriately
        if gemini_error == "Rate limit exceeded":
            # For Background Information section, return empty strings instead of raising an exception
            if request.section == "Background Information":
                logger.info(f"Returning empty strings for Background Information section due to rate limit error")
                return {
                    "case_id": request.case_id,
                    "section": request.section,
                    "response": "",
                    "response_of_findings": "",
                    "images": base64_encoded_images
                }
            else:
                # For other sections, raise the exception as before
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="The server is experiencing high load or API rate limits have been reached. Please try again in a few minutes."
                )
        elif gemini_error == "Internal Gemini error":
            # For Background Information section, return empty strings instead of raising an exception
            if request.section == "Background Information":
                logger.info(f"Returning empty strings for Background Information section due to internal Gemini error")
                return {
                    "case_id": request.case_id,
                    "section": request.section,
                    "response": "",
                    "response_of_findings": "",
                    "images": base64_encoded_images
                }
            else:
                # For other sections, raise the exception as before
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="An internal error occurred while processing the documents with the AI model."
                )

        # --- Return Successful Analysis and Images ---
        # Use the improved extract_findings_and_background function that handles both "**Findings**" and "**1.4 Findings**" formats
        from src.inference.postprocessing import extract_findings_and_background, parse_background_response

        # For Background Information section, use the new parsing function
        if request.section == "Background Information":
            logger.info(f"Using parse_background_response for Background Information section")

            # Check if response_text is empty or contains an error
            if not response_text or response_text.startswith("Error:"):
                logger.warning(f"Empty or error response from Gemini for Background Information section: {response_text}")
                # Even with empty/error response, return empty strings for both fields
                return {
                    "case_id": request.case_id,
                    "section": request.section,
                    "response": "",  # Empty background information
                    "response_of_findings": "",  # Empty findings
                    "images": base64_encoded_images
                }
            else:
                # Normal processing for valid responses
                response_of_findings, response_text_parsed = parse_background_response(response_text)
                return {
                    "case_id": request.case_id,
                    "section": request.section,
                    "response": response_text_parsed,
                    "response_of_findings": response_of_findings,
                    "images": base64_encoded_images
                }
        else:
            # For other sections, use the existing function
            findings_part, background_part = extract_findings_and_background(response_text)

            return {
                "case_id": request.case_id,
                "section": request.section,
                "response": background_part,
                "response_of_findings": findings_part,
                "images": base64_encoded_images  # Add the list of images here
            }

    except ValueError as e:
        # Catch config errors like missing API key or case not found (if GeminiHandler raises it)
        logger.error(f"Value error during query for case {request.case_id}: {str(e)}")

        # For Background Information section, return empty strings instead of raising an exception
        if request.section == "Background Information":
            logger.info(f"Returning empty strings for Background Information section due to ValueError: {str(e)}")
            return {
                "case_id": request.case_id,
                "section": request.section,
                "response": "",
                "response_of_findings": "",
                "images": base64_encoded_images
            }
        # For other sections, raise appropriate exceptions
        elif "Case not found" in str(e):
             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        else:
             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException as e:
        # Re-raise HTTPExceptions (like the 429 or 500 raised above)
        raise e
    except Exception as e:
        # Catch any other unexpected exceptions
        logger.error(f"Unexpected error processing query for case {request.case_id}: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())

        error_str = str(e)

        # For Background Information section, return empty strings instead of raising an exception
        if request.section == "Background Information":
            logger.info(f"Returning empty strings for Background Information section due to error: {error_str}")
            return {
                "case_id": request.case_id,
                "section": request.section,
                "response": "",
                "response_of_findings": "",
                "images": base64_encoded_images
            }
        # For other sections, raise appropriate exceptions
        elif "429" in error_str or "rate limit" in error_str.lower() or "quota" in error_str.lower():
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="API quota or rate limit possibly exceeded. Please try again later."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="An unexpected server error occurred while processing the query."
            )

@case_router.get("/case/{case_id}")
async def get_case(case_id: str):
    """
    API to fetch a specific case by case_id with all fields from the database.
    """
    try:
        # Use CRUD utility to retrieve the case
        cases = case_crud.read({"case_id": case_id})

        if "error" in cases:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=cases["error"])

        if not cases or len(cases) == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

        case = cases[0]  # Get the first (and should be only) result

        # Convert ObjectId to string
        case["_id"] = str(case["_id"])

        # Ensure required fields exist, but don't limit other fields
        if "pdf" not in case or case["pdf"] is None:
            case["pdf"] = []
        elif not isinstance(case["pdf"], list):
            case["pdf"] = [{"description": "PDF document", "file_path": str(case["pdf"])}]

        if "images" not in case or case["images"] is None:
            case["images"] = []

        if "embedding" not in case or case["embedding"] is None:
            case["embedding"] = ""

        if "exhibits" not in case or case["exhibits"] is None:
            case["exhibits"] = {"images": [], "pdfs": []}

        # Return the complete case data without using a response model
        return case
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to fetch case: {str(e)}")

@case_router.post("/image-query")
async def image_query(data: dict):
    """
    Endpoint for passing a base64-encoded image to Gemini, returning an image description.
    Expects JSON body:
    {
        "caseId": str,
        "sectionName": str,
        "imageName": str,
        "Image": str (base64-encoded image)
    }
    """
    from src.controller.gemini_case_handler import GeminiHandler
    case_id = data.get("caseId")
    image_b64 = data.get("Image")

    # These fields are available but not currently used in the processing
    # section_name = data.get("sectionName")
    # image_name = data.get("imageName")

    if not case_id or not image_b64:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required fields: caseId or Image"
        )

    case_type = data.get("caseType", "case_type_1")
    handler = GeminiHandler(case_id=case_id, case_type=case_type)
    desc = handler.Image_processing(image_b64)
    return {"Image_description": desc}
    # try:
    #     # Use CRUD utility to retrieve the case
    #     cases = case_crud.read({"case_id": case_id})

    #     if "error" in cases:
    #         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=cases["error"])

    #     if not cases or len(cases) == 0:
    #         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    #     case = cases[0]  # Get the first (and should be only) result

    #     # Convert ObjectId to string
    #     case["_id"] = str(case["_id"])

    #     # Ensure required fields for Case model exist, but don't limit other fields
    #     if "pdf" not in case or case["pdf"] is None:
    #         case["pdf"] = []
    #     elif not isinstance(case["pdf"], list):
    #         case["pdf"] = [{"description": "PDF document", "file_path": str(case["pdf"])}]

    #     if "images" not in case or case["images"] is None:
    #         case["images"] = []

    #     if "embedding" not in case or case["embedding"] is None:
    #         case["embedding"] = ""

    #     # Return the complete case data without using a response model
    #     return case
    # except HTTPException as e:
    #     raise e
    # except Exception as e:
    #     raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to fetch case: {str(e)}")
