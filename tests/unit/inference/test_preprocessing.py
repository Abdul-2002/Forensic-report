"""
Tests for the preprocessing module.
"""
import os
import pytest
from unittest.mock import patch, MagicMock, mock_open

from src.inference.preprocessing import process_txt, process_docx, process_pdf_for_gemini

@pytest.mark.parametrize("content,expected_text", [
    ("Test content", "Test content"),
    ("", None),  # Empty content should return None
])
def test_process_txt(content, expected_text):
    """
    Test processing a text file.
    """
    # Mock os.path.exists to return True
    with patch("os.path.exists", return_value=True):
        # Mock open to return the test content
        with patch("builtins.open", mock_open(read_data=content)):
            result = process_txt("test.txt")

            if expected_text is None:
                assert result is None
            else:
                assert result is not None
                assert result["text"] == expected_text
                assert result["source"] == "test.txt"

def test_process_docx():
    """
    Test processing a DOCX file.
    """
    # Import docx here to avoid import error in the test
    with patch("os.path.exists", return_value=True):
        with patch("src.inference.preprocessing.docx") as mock_docx:
            # Mock the Document class
            mock_doc = MagicMock()
            mock_doc.paragraphs = [
                MagicMock(text="Paragraph 1"),
                MagicMock(text="Paragraph 2"),
                MagicMock(text="")  # Empty paragraph should be skipped
            ]
            mock_docx.Document.return_value = mock_doc

            # Process the DOCX file
            result = process_docx("test.docx")

            # Check the result
            assert result["text"] == "Paragraph 1\n\nParagraph 2"
            assert result["source"] == "test.docx"

            # Check that Document was called with the correct path
            mock_docx.Document.assert_called_once_with("test.docx")

def test_process_pdf_for_gemini():
    """
    Test processing a PDF file for Gemini.
    """
    # Import fitz here to avoid import error in the test
    with patch("os.path.exists", return_value=True):
        with patch("src.inference.preprocessing.fitz") as mock_fitz:
            # Mock the fitz.open function
            mock_doc = MagicMock()
            mock_page1 = MagicMock()
            mock_page1.get_text.return_value = "Page 1 content"
            mock_page2 = MagicMock()
            mock_page2.get_text.return_value = "Page 2 content"
            mock_doc.__len__.return_value = 2
            mock_doc.__getitem__.side_effect = [mock_page1, mock_page2]
            mock_fitz.open.return_value = mock_doc

            # Process the PDF file
            result = process_pdf_for_gemini("test.pdf")

            # Check the result
            assert result["text"] == "Page 1 content\nPage 2 content"
            assert result["source"] == "test.pdf"

            # Check that fitz.open was called with the correct path
            mock_fitz.open.assert_called_once_with("test.pdf")
