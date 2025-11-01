"""
Tests for the inference pipeline.
"""
import os
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from src.inference.pipeline import InferencePipeline

@pytest.fixture
def inference_pipeline():
    """
    Fixture for the inference pipeline.
    """
    return InferencePipeline(case_id="test_case_123", case_type="test_case_type")

@patch("src.inference.pipeline.InferenceService")
def test_inference_pipeline_initialization(mock_service, inference_pipeline):
    """
    Test the initialization of the inference pipeline.
    """
    assert inference_pipeline.case_id == "test_case_123"
    assert inference_pipeline.case_type == "test_case_type"

@pytest.mark.asyncio
@patch("src.inference.pipeline.InferenceService")
async def test_process_exhibits_section(mock_service, inference_pipeline):
    """
    Test processing a query for the Exhibits section.
    """
    # Mock the service
    mock_service_instance = AsyncMock()
    mock_service_instance.get_all_exhibits.return_value = [
        {"url": "https://example.com/image1.jpg", "description": "Test image 1"},
        {"url": "https://example.com/image2.jpg", "description": "Test image 2"}
    ]
    mock_service.return_value = mock_service_instance

    # Set the service
    inference_pipeline.service = mock_service_instance

    # Process the query
    result = await inference_pipeline.process("Exhibits")

    # Check the result
    assert result["case_id"] == "test_case_123"
    assert result["section"] == "Exhibits"
    assert "response" in result
    assert "images" in result
    assert len(result["images"]) == 2

    # Check that the service was called
    mock_service_instance.get_all_exhibits.assert_called_once()

@pytest.mark.asyncio
@patch("src.inference.postprocessing.extract_findings_and_background")
@patch("src.inference.pipeline.InferenceService")
async def test_process_background_section(mock_service, mock_extract, inference_pipeline):
    """
    Test processing a query for the Background Information section.
    """
    # Mock the service
    mock_service_instance = AsyncMock()
    mock_service_instance.create_unified_analysis.return_value = "Test background information"
    mock_service_instance.get_base64_images_for_section.return_value = [
        {"url": "https://example.com/image1.jpg", "description": "Test image 1"}
    ]
    mock_service.return_value = mock_service_instance

    # Mock the extract_findings_and_background function
    mock_extract.return_value = ("Test findings", "Test background information")

    # Set the service
    inference_pipeline.service = mock_service_instance

    # Process the query
    result = await inference_pipeline.process("Background Information")

    # Check the result
    assert result["case_id"] == "test_case_123"
    assert result["section"] == "Background Information"
    assert result["response"] == "Test background information"
    assert result["response_of_findings"] == "Test findings"
    assert "images" in result
    assert len(result["images"]) == 1

    # Check that the service was called
    mock_service_instance.create_unified_analysis.assert_called_once_with(
        section="Background Information",
        batch_size=3,
        base_retry_delay=5,
        max_retries=3
    )
    mock_service_instance.get_base64_images_for_section.assert_called_once_with("Background Information")
