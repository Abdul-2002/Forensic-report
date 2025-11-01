"""
Tests for the dashboard service.
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from src.admin.dashboard_service import get_case_stats, get_prediction_stats, get_system_stats

@pytest.mark.asyncio
async def test_get_system_stats():
    """
    Test getting system statistics.
    """
    with patch("src.admin.dashboard_service.psutil") as mock_psutil:
        # Mock psutil.cpu_percent
        mock_psutil.cpu_percent.return_value = 25.0

        # Mock psutil.virtual_memory
        mock_memory = MagicMock()
        mock_memory.percent = 50.0
        mock_memory.used = 4000000000
        mock_memory.total = 8000000000
        mock_psutil.virtual_memory.return_value = mock_memory

        # Mock psutil.disk_usage
        mock_disk = MagicMock()
        mock_disk.percent = 75.0
        mock_disk.used = 750000000000
        mock_disk.total = 1000000000000
        mock_psutil.disk_usage.return_value = mock_disk

        # Mock psutil.Process
        mock_process = MagicMock()
        mock_process.memory_info.return_value.rss = 200000000
        mock_process.cpu_percent.return_value = 10.0
        mock_process.num_threads.return_value = 4
        mock_process.create_time.return_value = 1609459200  # 2021-01-01 00:00:00
        mock_psutil.Process.return_value = mock_process

        # Get system stats
        stats = await get_system_stats()

        # Check the result
        assert stats["cpu"]["percent"] == 25.0
        assert stats["memory"]["percent"] == 50.0
        assert stats["memory"]["used"] == 4000000000
        assert stats["memory"]["total"] == 8000000000
        assert stats["disk"]["percent"] == 75.0
        assert stats["disk"]["used"] == 750000000000
        assert stats["disk"]["total"] == 1000000000000
        assert stats["process"]["memory"] == 200000000
        assert stats["process"]["cpu"] == 10.0
        assert stats["process"]["threads"] == 4
        assert "uptime" in stats["process"]

@pytest.mark.asyncio
async def test_get_case_stats():
    """
    Test getting case statistics.
    """
    # Mock the case repository
    mock_case_repo = MagicMock()
    mock_case_repo.get_all_cases.return_value = [
        {
            "_id": "test_id_1",
            "case_id": "test_case_123",
            "case_name": "Test Case 1",
            "location": "Test Location 1",
            "date": "2023-01-01",
            "time": "12:00",
            "description": "Test description 1",
            "case_type": "Slip/Fall on Ice",
            "created_at": "2023-01-01T12:00:00",
            "images": ["image1.jpg", "image2.jpg"],
            "pdf": ["doc1.pdf"],
            "exhibits": {"images": ["exhibit1.jpg"], "pdfs": ["exhibit1.pdf"]}
        },
        {
            "_id": "test_id_2",
            "case_id": "test_case_456",
            "case_name": "Test Case 2",
            "location": "Test Location 2",
            "date": "2023-02-01",
            "time": "13:00",
            "description": "Test description 2",
            "case_type": "Slip/Fall on Wet Surface",
            "created_at": "2023-02-01T13:00:00",
            "images": ["image3.jpg"],
            "pdf": [],
            "exhibits": {"images": [], "pdfs": []}
        }
    ]

    # Get case stats
    stats = await get_case_stats(mock_case_repo)

    # Check the result
    assert stats["total_cases"] == 2
    assert stats["cases_by_type"]["Slip/Fall on Ice"] == 1
    assert stats["cases_by_type"]["Slip/Fall on Wet Surface"] == 1
    assert stats["total_images"] == 4  # 3 images + 1 exhibit image
    assert stats["total_pdfs"] == 2  # 1 pdf + 1 exhibit pdf
    assert len(stats["recent_cases"]) == 2
    assert stats["recent_cases"][0]["case_id"] == "test_case_456"  # Most recent first
    assert stats["recent_cases"][1]["case_id"] == "test_case_123"

@pytest.mark.asyncio
async def test_get_prediction_stats():
    """
    Test getting prediction statistics.
    """
    # Mock the prediction repository
    mock_prediction_repo = MagicMock()
    mock_prediction_repo.get_successful_predictions.return_value = [
        {
            "_id": "pred_id_1",
            "case_id": "test_case_123",
            "section": "Background Information",
            "status": "success",
            "processing_time": 5.2,
            "created_at": "2023-01-01T12:30:00"
        },
        {
            "_id": "pred_id_2",
            "case_id": "test_case_123",
            "section": "Exhibits",
            "status": "success",
            "processing_time": 3.8,
            "created_at": "2023-01-01T12:35:00"
        }
    ]
    mock_prediction_repo.get_failed_predictions.return_value = [
        {
            "_id": "pred_id_3",
            "case_id": "test_case_456",
            "section": "Background Information",
            "status": "error",
            "error": "Test error",
            "created_at": "2023-02-01T13:30:00"
        }
    ]

    # Get prediction stats
    stats = await get_prediction_stats(mock_prediction_repo)

    # Check the result
    assert stats["total_predictions"] == 3
    assert stats["successful_predictions"] == 2
    assert stats["failed_predictions"] == 1
    assert stats["success_rate"] == (2/3) * 100
    assert stats["predictions_by_section"]["Background Information"]["total"] == 2
    assert stats["predictions_by_section"]["Background Information"]["success"] == 1
    assert stats["predictions_by_section"]["Background Information"]["failure"] == 1
    assert stats["predictions_by_section"]["Exhibits"]["total"] == 1
    assert stats["predictions_by_section"]["Exhibits"]["success"] == 1
    assert stats["predictions_by_section"]["Exhibits"]["failure"] == 0
    assert stats["average_processing_time"] == (5.2 + 3.8) / 2
    assert len(stats["recent_predictions"]) == 3
    assert stats["recent_predictions"][0]["case_id"] == "test_case_456"  # Most recent first
