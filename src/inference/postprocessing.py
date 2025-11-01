"""
Postprocessing utilities for inference.
"""
import base64
import io
import os
import tempfile
from typing import Dict, Any, List, Optional

import requests
from PIL import Image

from src.core.logging_config import get_logger
from src.inference.exceptions import PostprocessingError

logger = get_logger(__name__)

async def convert_pdf_to_images(pdf_url: str, description: str) -> List[Dict[str, Any]]:
    """
    Convert a PDF to a list of base64-encoded images, one per page.

    Args:
        pdf_url: The URL of the PDF file.
        description: A description of the PDF.

    Returns:
        A list of dictionaries, each containing a base64-encoded image.
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
                import pdf2image

                pdf_images = pdf2image.convert_from_path(pdf_path, dpi=200)

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

def extract_findings_and_background(response_text: str) -> tuple:
    """
    Extract findings and background information from a response text.
    Handles both "**1.4 Findings**" and "**Findings**" formats, standardizing to "**1.4 Findings**".
    Also handles various background information header formats.

    Args:
        response_text: The response text.

    Returns:
        A tuple of (findings_part, background_part).
    """
    # Initialize with defaults
    findings_part = ""
    background_part = response_text

    # Check for various header formats
    findings_headers = [
        "**1.4 Findings**",
        "**Findings**",
        "**1.4. Findings**",
        "**1.4 FINDINGS**",
        "**FINDINGS**"
    ]

    background_headers = [
        "**2. Background Information**",
        "**2.0 Background Information**",
        "**Background Information**",
        "**BACKGROUND INFORMATION**",
        "**2. BACKGROUND INFORMATION**",
        "**2.0 BACKGROUND INFORMATION**"
    ]

    # Find the earliest occurrence of any findings header
    start_findings = -1
    found_findings_header = None

    for header in findings_headers:
        pos = response_text.find(header)
        if pos != -1 and (start_findings == -1 or pos < start_findings):
            start_findings = pos
            found_findings_header = header

    # Find the earliest occurrence of any background header
    start_background = -1
    found_background_header = None

    for header in background_headers:
        pos = response_text.find(header)
        if pos != -1 and (start_background == -1 or pos < start_background):
            start_background = pos
            found_background_header = header

    # Extract findings and background based on what was found
    if start_findings != -1:
        # We found a findings section
        if start_background != -1:
            # Both findings and background sections exist
            findings_part = response_text[start_findings:start_background].strip()
            background_part = response_text[start_background:].strip()
        else:
            # Only findings section exists
            findings_part = response_text[start_findings:].strip()
            background_part = ""

        # Standardize the findings header to "**1.4 Findings**"
        if found_findings_header and found_findings_header != "**1.4 Findings**":
            findings_part = findings_part.replace(found_findings_header, "**1.4 Findings**", 1)

    elif start_background != -1:
        # Only background section exists, check if there's content before it that might be findings
        pre_background = response_text[:start_background].strip()
        if pre_background:
            # If there's content before background but no findings header,
            # treat it as findings and add the header
            findings_part = "**1.4 Findings**\n" + pre_background

        background_part = response_text[start_background:].strip()

    # If we have a background section but no findings were extracted,
    # check if the background section itself contains findings information
    if not findings_part and background_part:
        # Look for findings-related content within the background section
        lower_background = background_part.lower()
        if "finding" in lower_background and start_background != -1:
            # Try to extract findings from the beginning of the response
            if response_text[:start_background].strip():
                findings_part = "**1.4 Findings**\n" + response_text[:start_background].strip()

    # If background part is empty but we have response text, use the whole text as background
    if not background_part and response_text and not findings_part:
        background_part = response_text

    return findings_part, background_part


def parse_background_response(response_text: str) -> tuple:
    """
    Parse a Gemini output string for the "Background Information" section.

    This function specifically looks for the first occurrence of '**Background Information**'
    and splits the response into two parts:
    1. response_of_findings: Everything before '**Background Information**'
    2. response: Everything from '**Background Information**' to the end

    Args:
        response_text: The Gemini output string to parse.

    Returns:
        A tuple of (response_of_findings, response).
    """
    # Initialize with defaults
    response_of_findings = ""
    response = response_text

    # Find the first occurrence of '**Background Information**'
    background_marker = "**Background Information**"
    background_index = response_text.find(background_marker)

    if background_index != -1:
        # Extract the substring from the beginning up to the background marker
        response_of_findings = response_text[:background_index].strip()

        # Extract the substring from the background marker to the end
        response = response_text[background_index:].strip()
    else:
        # If '**Background Information**' is not found, use the existing extract_findings_and_background function
        # as a fallback to maintain compatibility
        logger.info("'**Background Information**' marker not found, falling back to standard extraction")
        findings_part, background_part = extract_findings_and_background(response_text)
        response_of_findings = findings_part
        response = background_part

    return response_of_findings, response
