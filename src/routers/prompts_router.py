from fastapi import APIRouter, HTTPException, Body, Query, Path, File, UploadFile
from typing import Dict, List, Optional, Any
import logging
import json  # Add this import
from bson import ObjectId
from pydantic import BaseModel, Field

# Import MongoDB connection
from utils.Mongodbcnnection import MongoDBConnection
from src.db.models.base import format_object_id

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/prompts",
    tags=["System Prompts Management"],
    responses={404: {"description": "Not found"}},
)

# Pydantic models for request and response validation
class PromptBase(BaseModel):
    """Base model for system prompts"""
    case_type: str = Field(..., description="The case type this prompt belongs to (e.g., 'Slip/Fall on Ice')")
    Background_Information: Optional[str] = Field(None, description="Prompt for Background Information section")
    Site_Inspection: Optional[str] = Field(None, description="Prompt for Site Inspection section")
    Discussion: Optional[str] = Field(None, description="Prompt for Discussion section")
    Summary_of_Opinions: Optional[str] = Field(None, description="Prompt for Summary of Opinions section")
    Conclusion: Optional[str] = Field(None, description="Prompt for Conclusion section")
    Exhibits: Optional[str] = Field(None, description="Prompt for Exhibits section")
    description: Optional[str] = Field(None, description="Optional description of the prompt's purpose")

class PromptCreate(PromptBase):
    """Model for creating a new prompt"""
    pass

class PromptUpdate(BaseModel):
    """Model for updating an existing prompt"""
    case_type: Optional[str] = Field(None, description="The case type this prompt belongs to")
    Background_Information: Optional[str] = Field(None, description="Prompt for Background Information section")
    Site_Inspection: Optional[str] = Field(None, description="Prompt for Site Inspection section")
    Discussion: Optional[str] = Field(None, description="Prompt for Discussion section")
    Summary_of_Opinions: Optional[str] = Field(None, description="Prompt for Summary of Opinions section")
    Conclusion: Optional[str] = Field(None, description="Prompt for Conclusion section")
    Exhibits: Optional[str] = Field(None, description="Prompt for Exhibits section")
    description: Optional[str] = Field(None, description="Optional description of the prompt's purpose")

class PromptResponse(PromptBase):
    """Model for prompt responses"""
    id: str = Field(..., description="The unique identifier for the prompt")

    class Config:
        json_encoders = {
            ObjectId: str
        }

# Initialize MongoDB connection
try:
    mongo_connection = MongoDBConnection()
    db = mongo_connection.get_database()
    prompts_collection = db["system_prompts"]
    logger.info("MongoDB connection established for prompts router")
except Exception as e:
    logger.error(f"Failed to initialize MongoDB connection: {e}")
    raise RuntimeError(f"Failed to initialize MongoDB connection: {e}")

# Create a new prompt
@router.post("/", response_model=PromptResponse, status_code=201)
async def create_prompt(prompt: PromptCreate = Body(...)):
    """
    Create a new system prompt in the database.
    """
    try:
        prompt_dict = prompt.dict()
        result = prompts_collection.insert_one(prompt_dict)
        
        if not result.inserted_id:
            raise HTTPException(status_code=500, detail="Failed to create prompt")
        
        # Get the created document
        created_prompt = prompts_collection.find_one({"_id": result.inserted_id})
        if not created_prompt:
            raise HTTPException(status_code=404, detail="Created prompt not found")
        
        # Format the response
        created_prompt["id"] = str(created_prompt.pop("_id"))
        return created_prompt
    
    except Exception as e:
        logger.error(f"Error creating prompt: {e}")
        raise HTTPException(status_code=500, detail=f"Error creating prompt: {str(e)}")

# Get all prompts
# Get all prompts
@router.get("/", response_model=List[PromptResponse])
async def get_all_prompts(
    case_type: Optional[str] = Query(None, description="Filter by case type")
):
    """
    Get all system prompts, with optional filtering by case type.
    """
    try:
        # Build query filter
        query = {}
        if case_type:
            query["case_type"] = case_type
        
        # Execute query
        prompts = list(prompts_collection.find(query))
        
        # Format response
        for prompt in prompts:
            # Add prompt_id field which is the same as _id
            prompt["prompt_id"] = str(prompt["_id"])
            prompt["id"] = str(prompt.pop("_id"))
        
        return prompts
    
    except Exception as e:
        logger.error(f"Error retrieving prompts: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving prompts: {str(e)}")

# Get a specific prompt by ID
@router.get("/{prompt_id}", response_model=PromptResponse)
async def get_prompt(prompt_id: str = Path(..., description="The ID of the prompt to retrieve")):
    """
    Get a specific system prompt by its ID.
    """
    try:
        prompt = prompts_collection.find_one({"_id": ObjectId(prompt_id)})
        if not prompt:
            raise HTTPException(status_code=404, detail=f"Prompt with ID {prompt_id} not found")
        
        # Format response
        prompt["id"] = str(prompt.pop("_id"))
        return prompt
    
    except Exception as e:
        logger.error(f"Error retrieving prompt {prompt_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving prompt: {str(e)}")

# Update a prompt
@router.put("/{prompt_id}", response_model=PromptResponse)
async def update_prompt(
    prompt_id: str = Path(..., description="The ID of the prompt to update"),
    prompt_update: PromptUpdate = Body(...)
):
    """
    Update an existing system prompt.
    """
    try:
        # Filter out None values
        update_data = {k: v for k, v in prompt_update.dict().items() if v is not None}
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No valid update data provided")
        
        result = prompts_collection.update_one(
            {"_id": ObjectId(prompt_id)},
            {"$set": update_data}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail=f"Prompt with ID {prompt_id} not found")
        
        # Get updated document
        updated_prompt = prompts_collection.find_one({"_id": ObjectId(prompt_id)})
        if not updated_prompt:
            raise HTTPException(status_code=404, detail="Updated prompt not found")
        
        # Format response
        updated_prompt["id"] = str(updated_prompt.pop("_id"))
        return updated_prompt
    
    except Exception as e:
        logger.error(f"Error updating prompt {prompt_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error updating prompt: {str(e)}")

# Delete a prompt
@router.delete("/{prompt_id}", status_code=204)
async def delete_prompt(prompt_id: str = Path(..., description="The ID of the prompt to delete")):
    """
    Delete a system prompt.
    """
    try:
        result = prompts_collection.delete_one({"_id": ObjectId(prompt_id)})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail=f"Prompt with ID {prompt_id} not found")
        
        return None
    
    except Exception as e:
        logger.error(f"Error deleting prompt {prompt_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Error deleting prompt: {str(e)}")

# Get prompts by section
@router.get("/by-section/{section}", response_model=Dict[str, Any])
async def get_prompts_by_section(
    section: str = Path(..., description="The section to get prompts for"),
    case_type: Optional[str] = Query(None, description="Optional case type filter")
):
    """
    Get prompts for a specific section, optionally filtered by case type.
    """
    try:
        # Build query filter
        query = {}
        if case_type:
            query["case_type"] = case_type
        
        # Execute query
        prompts = list(prompts_collection.find(query))
        
        if not prompts:
            return {}
        
        # Format as a dictionary with case type as key and section content as value
        result = {}
        for prompt in prompts:
            case_type_key = prompt.get("case_type", "Unknown")
            section_content = prompt.get(section)
            if section_content:
                result[case_type_key] = section_content
        
        return result
    
    except Exception as e:
        logger.error(f"Error retrieving prompts for section {section}: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving prompts: {str(e)}")

# Get all prompts organized by section
@router.get("/all-prompts/by-section", response_model=Dict[str, Any])
async def get_all_prompts_by_section(
    case_type: Optional[str] = Query(None, description="Optional case type filter")
):
    """
    Get all prompts organized by section, optionally filtered by case type.
    """
    try:
        # Build query filter
        query = {}
        if case_type:
            query["case_type"] = case_type
        
        # Execute query
        prompts = list(prompts_collection.find(query))
        
        if not prompts:
            return {}
        
        # Format as a dictionary with section as key and content as value
        result = {}
        for prompt in prompts:
            case_type_key = prompt.get("case_type", "Unknown")
            
            # Extract all section fields (excluding _id, case_type, description, etc.)
            for key, value in prompt.items():
                if key not in ["_id", "id", "case_type", "description"] and value:
                    section_key = key
                    if case_type:
                        section_key = f"{key}_{case_type}"
                    result[section_key] = value
        
        return result
    
    except Exception as e:
        logger.error(f"Error retrieving all prompts: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving prompts: {str(e)}")

# Import prompts from JSON file
@router.post("/import-from-json", status_code=201)
async def import_prompts_from_json(file: UploadFile = File(...)):
    """
    Import prompts from an uploaded JSON file.
    """
    try:
        # Read the uploaded file content
        file_content = await file.read()
        
        try:
            # Parse the JSON content
            prompt_data = json.loads(file_content.decode('utf-8'))
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON format in uploaded file")
        
        if not prompt_data:
            raise HTTPException(status_code=400, detail="No prompts found in the uploaded file")
        
        # Convert the JSON structure to our database structure
        prompts_to_insert = []
        
        # Iterate through top-level keys (case types)
        for case_type, sections in prompt_data.items():
            # Create a document with the flattened structure
            prompt_doc = {
                "case_type": case_type,
                "description": f"Imported from uploaded file: {file.filename}"
            }
            
            # Add each section directly to the document
            if isinstance(sections, dict):
                for section_name, section_content in sections.items():
                    # Replace spaces with underscores for field names
                    field_name = section_name.replace(" ", "_")
                    prompt_doc[field_name] = section_content
            
            prompts_to_insert.append(prompt_doc)
        
        if prompts_to_insert:
            # First, clear existing prompts to avoid duplicates
            prompts_collection.delete_many({})
            
            # Insert the new prompts
            result = prompts_collection.insert_many(prompts_to_insert)
            return {"message": f"Successfully imported {len(result.inserted_ids)} prompts from file '{file.filename}'"}
        else:
            raise HTTPException(status_code=400, detail="No valid prompts to import")
    
    except Exception as e:
        logger.error(f"Error importing prompts from file: {e}")
        raise HTTPException(status_code=500, detail=f"Error importing prompts: {str(e)}")