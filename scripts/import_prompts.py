"""
Script to import system prompts from JSON file to MongoDB.
"""
import json
import os
import sys
from pathlib import Path

# Add the parent directory to the path so we can import from src
sys.path.append(str(Path(__file__).parent.parent))

from src.db.session import get_db
from src.core.logging_config import get_logger

logger = get_logger(__name__)

def import_prompts_from_json(json_file_path: str):
    """
    Import prompts from a JSON file to MongoDB.
    
    Args:
        json_file_path: Path to the JSON file.
    """
    try:
        # Check if file exists
        if not os.path.exists(json_file_path):
            logger.error(f"File not found: {json_file_path}")
            return False
        
        # Read the JSON file
        with open(json_file_path, 'r', encoding='utf-8') as f:
            prompt_data = json.load(f)
        
        if not prompt_data:
            logger.error("No prompts found in the JSON file.")
            return False
        
        # Get the database
        db = get_db()
        prompts_collection = db["system_prompts"]
        
        # Clear existing prompts
        prompts_collection.delete_many({})
        logger.info("Cleared existing prompts from MongoDB.")
        
        # Convert the JSON structure to our database structure
        prompts_to_insert = []
        
        # Iterate through top-level keys (case types)
        for case_type, sections in prompt_data.items():
            # Create a document with the flattened structure
            prompt_doc = {
                "case_type": case_type,
                "description": f"Imported from file: {json_file_path}"
            }
            
            # Add each section directly to the document
            if isinstance(sections, dict):
                for section_name, section_content in sections.items():
                    # Replace spaces with underscores for field names
                    field_name = section_name.replace(" ", "_")
                    prompt_doc[field_name] = section_content
            
            prompts_to_insert.append(prompt_doc)
        
        if prompts_to_insert:
            # Insert the new prompts
            result = prompts_collection.insert_many(prompts_to_insert)
            logger.info(f"Successfully imported {len(result.inserted_ids)} prompts from file '{json_file_path}'")
            
            # Verify the prompts were inserted
            count = prompts_collection.count_documents({})
            logger.info(f"Total prompts in MongoDB: {count}")
            
            # Log the first prompt to verify structure
            first_prompt = prompts_collection.find_one({})
            if first_prompt:
                logger.info(f"First prompt structure: {list(first_prompt.keys())}")
            
            return True
        else:
            logger.error("No valid prompts to import.")
            return False
    
    except Exception as e:
        logger.error(f"Error importing prompts from file: {e}")
        return False

if __name__ == "__main__":
    # Get the JSON file path from command line arguments or use default
    json_file_path = sys.argv[1] if len(sys.argv) > 1 else "src/controller/system_prompts.json"
    
    logger.info(f"Importing prompts from {json_file_path}...")
    success = import_prompts_from_json(json_file_path)
    
    if success:
        logger.info("Import completed successfully.")
    else:
        logger.error("Import failed.")
        sys.exit(1)
