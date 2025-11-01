"""
Preprocessing utilities for inference.
"""
import os
import shutil
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional

from fastapi import UploadFile

from src.core.config import UPLOAD_DIR
from src.core.logging_config import get_logger
from src.inference.exceptions import PreprocessingError
from src.utils.file_helpers import save_uploaded_file, upload_to_azure

logger = get_logger(__name__)

async def process_file_upload(
    file: UploadFile,
    case_id: str,
    file_idx: int,
    category: str,
    local_dir: str,
    description: str = "",
    section: str = ""
) -> Dict[str, Any]:
    """
    Process a single file upload (image or PDF).

    Args:
        file: The uploaded file.
        case_id: The case ID.
        file_idx: The index of the file.
        category: The category of the file (images or pdfs).
        local_dir: The local directory to save the file.
        description: The description of the file.
        section: The section the file belongs to.

    Returns:
        The file metadata.
    """
    # Log the incoming parameters for debugging
    logger.info(f"Processing file upload: case_id={case_id}, file_idx={file_idx}, category={category}")
    logger.info(f"File description: {description[:50]}..." if description and len(description) > 50 else f"File description: {description}")

    if not file or not hasattr(file, 'filename') or not file.filename:
        logger.warning(f"Invalid file object for case_id={case_id}, file_idx={file_idx}")
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

        # Use the provided description or generate a default one
        file_description = description or f"{category[:-1].capitalize()} {file_idx+1}: {file.filename}"
        logger.info(f"Setting file metadata description: {file_description[:50]}..." if len(file_description) > 50 else file_description)

        file_metadata = {
            "description": file_description,
            "file_path": rel_path
        }

        if section:
            file_metadata["section"] = section
            logger.info(f"Setting file section: {section}")

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

async def process_exhibit_file(
    file: UploadFile,
    case_id: str,
    file_idx: int,
    file_type: str,
    local_dir: str,
    file_name: str = "",
    section: str = "Exhibits"
) -> Dict[str, Any]:
    """
    Process a single exhibit file (image or PDF).

    Args:
        file: The uploaded file.
        case_id: The case ID.
        file_idx: The index of the file.
        file_type: The type of file (images or pdfs).
        local_dir: The local directory to save the file.
        file_name: The name to use for the file.
        section: The section the file belongs to.

    Returns:
        The file metadata.
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

def process_pdf_for_gemini(pdf_path: str) -> Optional[Dict[str, str]]:
    """
    Convert PDF to text for Gemini processing.

    Args:
        pdf_path: The path to the PDF file.

    Returns:
        A dictionary with the extracted text.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.error("PyMuPDF (fitz) is not installed. Cannot process PDF files. Run 'pip install PyMuPDF'")
        return None

    if not pdf_path or not os.path.exists(pdf_path):
        logger.error(f"PDF file not found or path invalid: {pdf_path}")
        return None

    try:
        doc = fitz.open(pdf_path)
        text_content = ""
        for page_num, page in enumerate(doc):
            try:
                page_text = page.get_text()
                if page_text:
                    text_content += page_text
            except Exception as page_e:
                logger.warning(f"Error extracting text from page {page_num + 1} of {pdf_path}: {page_e}")
                text_content += f"\n[Error extracting page {page_num + 1}]\n"
        doc.close()

        processed_text = text_content.strip()
        if not processed_text:
            logger.warning(f"No text extracted from PDF: {pdf_path}")
            return None

        logger.info(f"Successfully extracted text from PDF: {os.path.basename(pdf_path)}")
        # Only include the 'text' key for Gemini API compatibility
        return {"text": processed_text}

    except Exception as e:
        logger.error(f"Error processing PDF {pdf_path}: {str(e)}")
        return None

def process_docx(docx_path: str) -> Optional[Dict[str, str]]:
    """
    Convert DOCX to text for Gemini processing.

    Args:
        docx_path: The path to the DOCX file.

    Returns:
        A dictionary with the extracted text.
    """
    try:
        import docx
    except ImportError:
        logger.error("python-docx is not installed. Cannot process DOCX files. Run 'pip install python-docx'")
        return None

    if not docx_path or not os.path.exists(docx_path):
        logger.error(f"DOCX file not found or path invalid: {docx_path}")
        return None

    try:
        doc = docx.Document(docx_path)
        full_text = [para.text for para in doc.paragraphs]
        text_content = "\n\n".join(p for p in full_text if p.strip())
        processed_text = text_content.strip()
        if not processed_text:
            logger.warning(f"No text extracted from DOCX: {docx_path}")
            return None

        logger.info(f"Successfully processed DOCX: {os.path.basename(docx_path)}")
        # Only include the 'text' key for Gemini API compatibility
        return {"text": processed_text}
    except Exception as e:
        logger.error(f"Error processing DOCX {docx_path}: {str(e)}")
        return None

def process_txt(txt_path: str) -> Optional[Dict[str, str]]:
    """
    Convert a TXT file to text for Gemini processing.

    Args:
        txt_path: The path to the TXT file.

    Returns:
        A dictionary with the extracted text.
    """
    if not txt_path or not os.path.exists(txt_path):
        logger.error(f"TXT file not found or path invalid: {txt_path}")
        return None

    try:
        with open(txt_path, 'r', encoding='utf-8', errors='ignore') as f:
            text_content = f.read()

        processed_text = text_content.strip()
        if not processed_text:
            logger.warning(f"No text extracted from TXT: {txt_path}")
            return None

        logger.info(f"Successfully processed TXT: {os.path.basename(txt_path)}")
        # Only include the 'text' key for Gemini API compatibility
        return {"text": processed_text}
    except Exception as e:
        logger.error(f"Error processing TXT {txt_path}: {str(e)}")
        return None
