"""
Example script to demonstrate how to use the text_parser module.
"""
import json
import sys
import os

# Add the src directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.text_parser import parse_text_to_json

def main():
    """
    Demonstrate how to use the text_parser module.
    """
    # Example text with both findings and background sections
    example_text = """
    **1.4 Findings**
    The incident was caused by the following, individually or in combination:
    1. The property owner failed to properly maintain the sidewalk.
    2. The slope of the concrete public sidewalk surface measuring 7.1% at the incident location.

    2. Background Information
    2.1 Basic Data Received and Reviewed
    The following basic data was received and reviewed by the author of this report:

    *   Complaint Filed on February 15, 2021
    *   Police Report dated January 31, 2021
    *   Weather data showing that snow accumulated and formed ice at the incident location more than 20 hours prior to the incident on January 31, 2021.
    """

    # Parse the text
    result = parse_text_to_json(example_text)

    # Print the result
    print("Parsed JSON:")
    print(json.dumps(result, indent=2))

    # Example text with problematic format
    problematic_text = """**1.4 Findings**
    The incident was caused by the following, individually or in combina......................slope of the concrete public sidewalk surface measuring 7.1% at the incident location.

    2. Background Information
    2.1 Basic Data Received and Reviewed
    The following basic data was received and reviewed by the author of this report:

    *   Complaint Filed ....................mulated and formed ice at the incident location more than 20 hours prior to the incident on January 31, 2021."""

    # Parse the problematic text
    problematic_result = parse_text_to_json(problematic_text)

    # Print the result
    print("\nParsed JSON for problematic text:")
    print(json.dumps(problematic_result, indent=2))

if __name__ == "__main__":
    main()
