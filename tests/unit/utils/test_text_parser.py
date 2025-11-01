"""
Tests for the text_parser module.
"""
import pytest
from src.utils.text_parser import parse_text_to_json

def test_parse_text_to_json_with_both_sections():
    """
    Test parsing text with both findings and background sections.
    """
    # Test text with both sections
    text = """
    **1.4 Findings**
    1. Finding one
    2. Finding two
    3. Finding three

    **2. Background Information**
    More detailed background information.
    Additional context about the case.
    """

    # Parse the text
    result = parse_text_to_json(text)

    # Check the results
    assert "**1.4 Findings**" in result["response_of_findings"]
    assert "1. Finding one" in result["response_of_findings"]
    assert "2. Finding two" in result["response_of_findings"]
    assert "3. Finding three" in result["response_of_findings"]
    assert "**2. Background Information**" in result["response"]
    assert "More detailed background information" in result["response"]
    assert "Additional context about the case" in result["response"]

def test_parse_text_to_json_with_findings_only():
    """
    Test parsing text with only findings section.
    """
    # Test text with only findings
    text = """
    **1.4 Findings**
    1. Finding one
    2. Finding two
    3. Finding three
    """

    # Parse the text
    result = parse_text_to_json(text)

    # Check the results
    assert "**1.4 Findings**" in result["response_of_findings"]
    assert "1. Finding one" in result["response_of_findings"]
    assert "2. Finding two" in result["response_of_findings"]
    assert "3. Finding three" in result["response_of_findings"]
    assert result["response"] == ""

def test_parse_text_to_json_with_background_only():
    """
    Test parsing text with only background section.
    """
    # Test text with only background
    text = """
    **Background Information**
    More detailed background information.
    Additional context about the case.
    """

    # Parse the text
    result = parse_text_to_json(text)

    # Check the results
    assert result["response_of_findings"] == ""
    assert "**Background Information**" in result["response"]
    assert "More detailed background information" in result["response"]
    assert "Additional context about the case" in result["response"]

def test_parse_text_to_json_with_content_before_sections():
    """
    Test parsing text with content before any section headers.
    """
    # Test text with content before sections
    text = """
    This is some initial content without a header.
    It should be treated as findings.

    **2. Background Information**
    More detailed background information.
    """

    # Parse the text
    result = parse_text_to_json(text)

    # Check the results
    assert "**1.4 Findings**" in result["response_of_findings"]
    # The content should be in the findings section, but after the header
    content = result["response_of_findings"].replace("**1.4 Findings**", "").strip()
    assert "This is some initial content without a header" in content or "This is some initial content without a header" in result["response_of_findings"]
    assert "It should be treated as findings" in content or "It should be treated as findings" in result["response_of_findings"]
    assert "**2. Background Information**" in result["response"]
    assert "More detailed background information" in result["response"]

def test_parse_text_to_json_with_no_sections():
    """
    Test parsing text with no section headers.
    """
    # Test text with no section headers
    text = """
    This is some content without any section headers.
    It should be treated as response.
    """

    # Parse the text
    result = parse_text_to_json(text)

    # Check the results
    assert result["response_of_findings"] == ""
    assert "This is some content without any section headers" in result["response"]
    assert "It should be treated as response" in result["response"]

def test_parse_text_to_json_with_findings_keyword():
    """
    Test parsing text with 'finding' keyword but no proper header.
    """
    # Test text with 'finding' keyword
    text = """
    The investigation found several findings related to the incident.
    These findings indicate negligence.
    """

    # Parse the text
    result = parse_text_to_json(text)

    # Check the results
    assert "**1.4 Findings**" in result["response_of_findings"]
    # The content should be in the findings section, but after the header
    content = result["response_of_findings"].replace("**1.4 Findings**", "").strip()
    assert "findings related to the incident" in content or "findings related to the incident" in result["response_of_findings"]
    assert "These findings indicate negligence" in content or "These findings indicate negligence" in result["response_of_findings"]
    assert result["response"] == ""

def test_parse_text_to_json_with_mixed_case_headers():
    """
    Test parsing text with mixed case headers.
    """
    # Test text with mixed case headers
    text = """
    **FINDINGS**
    1. Finding one
    2. Finding two

    **background information**
    More detailed background information.
    """

    # Parse the text
    result = parse_text_to_json(text)

    # Check the results
    assert "**1.4 Findings**" in result["response_of_findings"]
    assert "1. Finding one" in result["response_of_findings"]
    assert "2. Finding two" in result["response_of_findings"]
    assert "**background information**" in result["response"]
    assert "More detailed background information" in result["response"]

def test_parse_text_to_json_with_empty_text():
    """
    Test parsing empty text.
    """
    # Test with empty text
    text = ""

    # Parse the text
    result = parse_text_to_json(text)

    # Check the results
    assert result["response_of_findings"] == ""
    assert result["response"] == ""

def test_parse_text_to_json_with_problematic_format():
    """
    Test parsing text with the problematic format from the example.
    """
    # Test with the problematic format
    text = """**1.4 Findings**
The incident was caused by the following, individually or in combina......................slope of the concrete public sidewalk surface measuring 7.1% at the incident location.

2. Background Information
2.1 Basic Data Received and Reviewed
The following basic data was received and reviewed by the author of this report:

*   Complaint Filed ....................mulated and formed ice at the incident location more than 20 hours prior to the incident on January 31, 2021."""

    # Parse the text
    result = parse_text_to_json(text)

    # Check the results
    assert "**1.4 Findings**" in result["response_of_findings"]
    assert "The incident was caused by the following" in result["response_of_findings"]
    assert "2. Background Information" in result["response"]
    assert "2.1 Basic Data Received and Reviewed" in result["response"]
    assert "The following basic data was received" in result["response"]
    assert "Complaint Filed" in result["response"]
