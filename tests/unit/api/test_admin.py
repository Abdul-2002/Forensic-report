"""
Tests for the admin endpoints.
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

@pytest.mark.asyncio
@patch("src.api.endpoints.admin.get_case_repository")
async def test_get_all_cases(mock_repo, client: TestClient):
    """
    Test getting all cases.
    """
    # Mock the case repository
    mock_case_repo = MagicMock()
    mock_case_repo.find_all.return_value = [
        {
            "_id": "test_id_1",
            "case_id": "test_case_123",
            "case_name": "Test Case 1",
            "location": "Test Location 1",
            "date": "2023-01-01",
            "time": "12:00",
            "description": "Test description 1",
            "case_type": "Slip/Fall on Ice",
            "images": [],
            "pdf": [],
            "exhibits": {"images": [], "pdfs": []}
        },
        {
            "_id": "test_id_2",
            "case_id": "test_case_456",
            "case_name": "Test Case 2",
            "location": "Test Location 2",
            "date": "2023-02-01",
            "time": "13:00",
            "description": "Test description 2",
            "case_type": "Slip/Fall on Ice",
            "images": [],
            "pdf": [],
            "exhibits": {"images": [], "pdfs": []}
        }
    ]
    mock_repo.return_value = mock_case_repo
    
    # Make the request
    response = client.get("/app/v1/admin/cases")
    
    # Check the response
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["case_id"] == "test_case_123"
    assert data[1]["case_id"] == "test_case_456"
    
    # Check that the repository was called
    mock_case_repo.find_all.assert_called_once()

@pytest.mark.asyncio
@patch("src.api.endpoints.admin.get_case_repository")
async def test_delete_case(mock_repo, client: TestClient):
    """
    Test deleting a case.
    """
    # Mock the case repository
    mock_case_repo = MagicMock()
    mock_case_repo.delete_one.return_value = True
    mock_repo.return_value = mock_case_repo
    
    # Make the request
    response = client.delete("/app/v1/admin/case/test_case_123")
    
    # Check the response
    assert response.status_code == 200
    data = response.json()
    assert data["message"] == "Case deleted successfully"
    
    # Check that the repository was called
    mock_case_repo.delete_one.assert_called_once_with({"case_id": "test_case_123"})

@pytest.mark.asyncio
@patch("src.api.endpoints.admin.get_case_repository")
async def test_delete_case_not_found(mock_repo, client: TestClient):
    """
    Test deleting a case that doesn't exist.
    """
    # Mock the case repository
    mock_case_repo = MagicMock()
    mock_case_repo.delete_one.return_value = False
    mock_repo.return_value = mock_case_repo
    
    # Make the request
    response = client.delete("/app/v1/admin/case/nonexistent")
    
    # Check the response
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == "Case not found"
    
    # Check that the repository was called
    mock_case_repo.delete_one.assert_called_once_with({"case_id": "nonexistent"})
