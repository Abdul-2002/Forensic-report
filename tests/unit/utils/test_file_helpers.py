"""
Tests for the file helpers.
"""
import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi import UploadFile

from src.utils.file_helpers import save_uploaded_file

@pytest.mark.asyncio
@patch("builtins.open", new_callable=MagicMock)
async def test_save_uploaded_file(mock_open):
    """
    Test saving an uploaded file.
    """
    # Mock file content
    mock_content = b"test file content"
    
    # Mock UploadFile
    mock_file = MagicMock(spec=UploadFile)
    mock_file.filename = "test.txt"
    mock_file.read.return_value = mock_content
    
    # Mock file path
    file_path = "test/path/test.txt"
    
    # Mock os.path.exists and os.path.getsize
    with patch("os.path.exists", return_value=True), \
         patch("os.path.getsize", return_value=len(mock_content)):
        
        # Call the function
        result = await save_uploaded_file(mock_file, file_path)
        
        # Assertions
        assert result is True
        mock_file.read.assert_called_once()
        mock_open.assert_called_once_with(file_path, "wb")
        mock_open().__enter__().write.assert_called_once_with(mock_content)
