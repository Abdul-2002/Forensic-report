"""
Tests for the cases endpoints.
"""
import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import UploadFile

from src.api.endpoints.cases import router

@pytest.mark.asyncio
@patch("src.api.endpoints.cases.save_uploaded_file")
@patch("src.api.endpoints.cases.upload_to_azure")
@patch("src.api.endpoints.cases.ensure_directory_in_azure")
async def test_add_case(mock_ensure_dir, mock_upload, mock_save, client: TestClient):
    """
    Test adding a case.
    """
    # Mock the save_uploaded_file function to return True
    mock_save.return_value = True
    
    # Mock the upload_to_azure function to return a URL
    mock_upload.return_value = "https://example.com/test.jpg"
    
    # Mock the ensure_directory_in_azure function
    mock_ensure_dir.return_value = True
    
    # Create a test case
    with patch("src.api.endpoints.cases.get_case_repository") as mock_repo:
        # Mock the case repository
        mock_case_repo = MagicMock()
        mock_case_repo.create.return_value = {
            "_id": "test_id",
            "case_id": "test_case_123",
            "case_name": "Test Case",
            "location": "Test Location",
            "date": "2023-01-01",
            "time": "12:00",
            "description": "Test description",
            "case_type": "Slip/Fall on Ice",
            "images": [],
            "pdf": [],
            "exhibits": {"images": [], "pdfs": []}
        }
        mock_repo.return_value = mock_case_repo
        
        # Make the request
        response = client.post(
            "/app/v1/case-add",
            data={
                "case_id": "test_case_123",
                "case_name": "Test Case",
                "location": "Test Location",
                "date": "2023-01-01",
                "time": "12:00",
                "description": "Test description",
                "image_count": "0",
                "case_type": "Slip/Fall on Ice"
            }
        )
        
        # Check the response
        assert response.status_code == 201
        data = response.json()
        assert data["case_id"] == "test_case_123"
        assert data["case_name"] == "Test Case"
        
        # Check that the repository was called
        mock_case_repo.create.assert_called_once()

@pytest.mark.asyncio
@patch("src.api.endpoints.cases.get_case_repository")
async def test_get_case(mock_repo, client: TestClient):
    """
    Test getting a case.
    """
    # Mock the case repository
    mock_case_repo = MagicMock()
    mock_case_repo.find_one.return_value = {
        "_id": "test_id",
        "case_id": "test_case_123",
        "case_name": "Test Case",
        "location": "Test Location",
        "date": "2023-01-01",
        "time": "12:00",
        "description": "Test description",
        "case_type": "Slip/Fall on Ice",
        "images": [],
        "pdf": [],
        "exhibits": {"images": [], "pdfs": []}
    }
    mock_repo.return_value = mock_case_repo
    
    # Make the request
    response = client.get("/app/v1/case/test_case_123")
    
    # Check the response
    assert response.status_code == 200
    data = response.json()
    assert data["case_id"] == "test_case_123"
    assert data["case_name"] == "Test Case"
    
    # Check that the repository was called
    mock_case_repo.find_one.assert_called_once_with({"case_id": "test_case_123"})

@pytest.mark.asyncio
@patch("src.api.endpoints.cases.get_case_repository")
async def test_get_case_not_found(mock_repo, client: TestClient):
    """
    Test getting a case that doesn't exist.
    """
    # Mock the case repository
    mock_case_repo = MagicMock()
    mock_case_repo.find_one.return_value = None
    mock_repo.return_value = mock_case_repo
    
    # Make the request
    response = client.get("/app/v1/case/nonexistent")
    
    # Check the response
    assert response.status_code == 404
    
    # Check that the repository was called
    mock_case_repo.find_one.assert_called_once_with({"case_id": "nonexistent"})
