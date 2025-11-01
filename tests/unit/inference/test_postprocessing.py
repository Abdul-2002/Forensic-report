"""
Tests for the postprocessing module.
"""
import os
import pytest
from unittest.mock import patch, MagicMock, mock_open

from src.inference.postprocessing import extract_findings_and_background, convert_pdf_to_images, parse_background_response

def test_extract_findings_and_background_with_findings():
    """
    Test extracting findings and background from a response with findings.
    """
    # Test response with findings
    response = """
    Here is the background information:
    This is some background text.

    **1.4 Findings**
    1. Finding one
    2. Finding two
    3. Finding three

    **2. Background Information**
    More detailed background information.
    """

    # Extract findings and background
    findings, background = extract_findings_and_background(response)

    # Check the results
    assert "**1.4 Findings**" in findings
    assert "1. Finding one" in findings
    assert "2. Finding two" in findings
    assert "3. Finding three" in findings
    assert "**2. Background Information**" in background
    assert "More detailed background information" in background

def test_extract_findings_and_background_without_findings():
    """
    Test extracting findings and background from a response without findings.
    """
    # Test response without findings
    response = """
    Here is the background information:
    This is some background text.

    More text but no findings section.
    """

    # Extract findings and background
    findings, background = extract_findings_and_background(response)

    # Check the results
    assert findings == ""
    assert background == response

def test_extract_findings_and_background_with_alternate_format():
    """
    Test extracting findings and background with an alternate format.
    """
    # Test response with findings in a different format
    response = """
    **1.4 Findings**
    * Finding one
    * Finding two
    * Finding three

    **2. Background Information**
    This is some background text.
    More text after findings.
    """

    # Extract findings and background
    findings, background = extract_findings_and_background(response)

    # Check the results
    assert "**1.4 Findings**" in findings
    assert "* Finding one" in findings
    assert "* Finding two" in findings
    assert "* Finding three" in findings
    assert "**2. Background Information**" in background
    assert "This is some background text." in background

def test_extract_findings_without_header():
    """
    Test extracting findings when they appear before background but without a header.
    """
    # Test response with findings content but no header
    response = """
    A pedestrian slip and fall incident occurred on an icy surface.
    The incident took place in a parking lot.

    **2.0 Background Information**
    The incident occurred on January 15, 2023, at approximately 9:30 AM.
    """

    # Extract findings and background
    findings, background = extract_findings_and_background(response)

    # Check the results
    assert "**1.4 Findings**" in findings
    assert "A pedestrian slip and fall incident" in findings
    assert "**2.0 Background Information**" in background
    assert "The incident occurred on January 15, 2023" in background

def test_extract_findings_with_different_header_format():
    """
    Test extracting findings with different header formats.
    """
    # Test response with findings in a different header format
    response = """
    **FINDINGS**
    * A pedestrian slip and fall incident occurred on an icy surface.
    * The incident took place in a parking lot.

    **2.0 BACKGROUND INFORMATION**
    The incident occurred on January 15, 2023, at approximately 9:30 AM.
    """

    # Extract findings and background
    findings, background = extract_findings_and_background(response)

    # Check the results
    assert "**1.4 Findings**" in findings
    assert "**FINDINGS**" not in findings
    assert "* A pedestrian slip and fall incident" in findings
    assert "**2.0 BACKGROUND INFORMATION**" in background
    assert "The incident occurred on January 15, 2023" in background



@pytest.mark.asyncio
@patch("src.inference.postprocessing.requests.get")
@patch("src.inference.postprocessing.tempfile.TemporaryDirectory")
@patch("pdf2image.convert_from_path")
@patch("src.inference.postprocessing.os.path.exists")
async def test_convert_pdf_to_images(mock_exists, mock_convert, mock_temp_dir, mock_requests_get):
    """
    Test converting a PDF to images.
    """
    # Mock os.path.exists to return True
    mock_exists.return_value = True

    # Mock the temporary directory
    mock_temp_dir.return_value.__enter__.return_value = "/tmp/test"

    # Mock the requests.get response
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.content = b"test pdf content"
    mock_requests_get.return_value = mock_response

    # Mock convert_from_path to return a list of images
    mock_image1 = MagicMock()
    mock_image2 = MagicMock()
    mock_convert.return_value = [mock_image1, mock_image2]

    # Mock the save method
    mock_image1.save = MagicMock()
    mock_image2.save = MagicMock()

    # Mock open to avoid writing to disk
    with patch("builtins.open", mock_open()) as mock_file:
        # Convert the PDF to images
        result = await convert_pdf_to_images("https://example.com/test.pdf", "Test PDF")

    # Check the result
    assert len(result) == 2
    assert all("description" in img for img in result)
    assert all("base64_content" in img for img in result)

    # Check that convert_from_path was called with the correct path
    mock_convert.assert_called_once()

    # Check that save was called for each image
    mock_image1.save.assert_called_once()
    mock_image2.save.assert_called_once()


def test_parse_background_response_with_marker():
    """
    Test parsing a response with the '**Background Information**' marker.
    """
    # Test response with the marker
    response = """
    This is the findings section content.
    It contains important observations about the case.

    **Background Information**
    This is the background information section.
    It provides context for the case.
    """

    # Parse the response
    findings, background = parse_background_response(response)

    # Check the results
    assert "This is the findings section content." in findings
    assert "It contains important observations about the case." in findings
    assert "**Background Information**" in background
    assert "This is the background information section." in background
    assert "It provides context for the case." in background


def test_parse_background_response_without_marker():
    """
    Test parsing a response without the '**Background Information**' marker.
    Should fall back to extract_findings_and_background.
    """
    # Test response without the marker but with standard headers
    response = """
    **1.4 Findings**
    This is the findings section content.
    It contains important observations about the case.

    **2.0 Background Information**
    This is the background information section.
    It provides context for the case.
    """

    # Parse the response
    findings, background = parse_background_response(response)

    # Check the results
    assert "**1.4 Findings**" in findings
    assert "This is the findings section content." in findings
    assert "**2.0 Background Information**" in background
    assert "This is the background information section." in background


def test_parse_background_response_empty_input():
    """
    Test parsing an empty response.
    """
    # Test with empty response
    response = ""

    # Parse the response
    findings, background = parse_background_response(response)

    # Check the results
    assert findings == ""
    assert background == ""


def test_parse_background_response_only_findings():
    """
    Test parsing a response with only findings content (no marker or background header).
    """
    # Test with only findings content
    response = "This is only findings content without any markers or headers."

    # Parse the response
    findings, background = parse_background_response(response)

    # Check the results - should treat all as background since there's no marker
    assert findings == ""
    assert background == response
