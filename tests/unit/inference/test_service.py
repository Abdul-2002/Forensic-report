"""
Tests for the inference service.
"""
import os
import pytest
from unittest.mock import patch, MagicMock

from src.inference.service import InferenceService

@pytest.fixture
def inference_service():
    """
    Fixture for the inference service.
    """
    return InferenceService(case_id="test_case_123", case_type="test_case_type")

@patch("src.inference.service.model_loader")
def test_inference_service_initialization(mock_model_loader, inference_service):
    """
    Test the initialization of the inference service.
    """
    assert inference_service.case_id == "test_case_123"
    assert inference_service.case_type == "test_case_type"
    assert inference_service.temp_dir is None

@patch("src.inference.service.model_loader")
@patch("src.inference.service.InferenceService.load_system_prompts")
def test_load_system_prompts(mock_load_prompts, mock_model_loader, inference_service):
    """
    Test loading system prompts.
    """
    mock_load_prompts.return_value = {
        "Background Information": "Test prompt for background",
        "Exhibits": "Test prompt for exhibits"
    }
    
    prompts = inference_service.load_system_prompts()
    assert "Background Information" in prompts
    assert "Exhibits" in prompts
