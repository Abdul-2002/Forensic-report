"""
Script to test the /app/v1/Prompts/prompts/import-from-json endpoint.
This script reads a JSON file and sends it to the endpoint.
"""
import requests
import json
import os
import sys
from pathlib import Path

# Configuration
API_URL = "http://localhost:8000/app/v1/Prompts/prompts/import-from-json"
JSON_FILE_PATH = r"C:\Users\avina\Downloads\system_prompts.json"

def test_import_prompts():
    """
    Test the import-from-json endpoint by sending a JSON file.
    """
    print(f"Testing endpoint: {API_URL}")
    print(f"Using JSON file: {JSON_FILE_PATH}")
    
    # Check if file exists
    if not os.path.exists(JSON_FILE_PATH):
        print(f"Error: File not found at {JSON_FILE_PATH}")
        return False
    
    try:
        # Open the file in binary mode for multipart/form-data
        with open(JSON_FILE_PATH, 'rb') as file:
            # Create the files dictionary for the request
            files = {'file': (os.path.basename(JSON_FILE_PATH), file, 'application/json')}
            
            # Make the POST request
            print("Sending request to the endpoint...")
            response = requests.post(API_URL, files=files)
            
            # Check the response
            if response.status_code == 201:
                print("Success! Prompts imported successfully.")
                print(f"Response: {response.json()}")
                return True
            else:
                print(f"Error: Received status code {response.status_code}")
                print(f"Response: {response.text}")
                return False
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return False

def print_file_preview():
    """
    Print a preview of the JSON file to verify its structure.
    """
    try:
        with open(JSON_FILE_PATH, 'r', encoding='utf-8') as file:
            data = json.load(file)
            
            # Get the number of case types
            case_types = list(data.keys())
            num_case_types = len(case_types)
            
            print(f"\nJSON File Preview:")
            print(f"Number of case types: {num_case_types}")
            
            if num_case_types > 0:
                # Print the first case type as an example
                first_case_type = case_types[0]
                print(f"\nFirst case type: '{first_case_type}'")
                
                # Print the sections for the first case type
                sections = data[first_case_type]
                print(f"Sections for '{first_case_type}':")
                for section_name, section_content in sections.items():
                    # Truncate content if too long
                    content_preview = section_content[:100] + "..." if len(section_content) > 100 else section_content
                    print(f"  - {section_name}: {content_preview}")
    
    except Exception as e:
        print(f"Error reading JSON file: {str(e)}")

if __name__ == "__main__":
    print("=== Testing Import Prompts Endpoint ===")
    
    # Print a preview of the file
    print_file_preview()
    
    # Test the endpoint
    print("\n=== Sending Request ===")
    success = test_import_prompts()
    
    # Exit with appropriate code
    sys.exit(0 if success else 1)
