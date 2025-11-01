from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Dict, Any, Optional
import logging
from pydantic import BaseModel
from bson.objectid import ObjectId
from bson.errors import InvalidId
from datetime import datetime
from utils.CRUD_utils import CRUDUtils  # Import CRUD Utility class

# Set up logging for debugging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define the User model
class User(BaseModel):
    username: str
    password: str

class SecurityKey(BaseModel):
    object_id: str

class UserUpdateRequest(BaseModel):
    security_key: dict
    user: User

# Initialize the FastAPI Router
login_cred = APIRouter()

# Initialize CRUD Utility for the 'login_data' collection
login_crud = CRUDUtils("login_data")

# Security dependency
async def verify_object_id(security_key: SecurityKey):
    try:
        # Validate the ObjectId format
        if not ObjectId.is_valid(security_key.object_id):
            logger.warning(f"Invalid ObjectId format: {security_key.object_id}")
            raise HTTPException(status_code=401, detail="Invalid security key format")
        
        # Check if this ObjectId exists in the database
        users = login_crud.read({"_id": ObjectId(security_key.object_id)})
        if "error" in users or not users or len(users) == 0:
            logger.warning(f"ObjectId not found in database: {security_key.object_id}")
            raise HTTPException(status_code=401, detail="Invalid security key")
        
        return security_key.object_id
    except InvalidId:
        raise HTTPException(status_code=401, detail="Invalid security key format")
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise HTTPException(status_code=500, detail=f"Authentication error: {e}")

@login_cred.get("/Login-user", response_model=List[Dict[str, str]])
async def fetch_all_data():
    """
    API to fetch all user records from the database.
    """
    try:
        records = login_crud.read({})
        if "error" in records:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=records["error"])
        
        # Convert _id to string for each user
        result = []
        for record in records:
            result.append({
                "id": str(record["_id"]),
                "username": record.get("username", ""),
                # Password is deliberately omitted for security
            })
        
        if not result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No records found")
        
        logger.info(f"Fetched {len(result)} records from login_data collection (limited info).")
        return result
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to fetch user data: {str(e)}")

@login_cred.post("/get-user-details", response_model=Dict[str, Any])
async def get_user_details(security_key: SecurityKey):
    """
    API to get full user details with security key authentication.
    """
    try:
        verified_id = await verify_object_id(security_key)
        users = login_crud.read({"_id": ObjectId(verified_id)})
        
        if "error" in users:
            raise HTTPException(status_code=500, detail=users["error"])
            
        if not users or len(users) == 0:
            raise HTTPException(status_code=404, detail="User not found")
        
        user = users[0]
        
        # Convert datetime objects to ISO format strings
        created_at = user.get("created_at")
        updated_at = user.get("updated_at")
        
        return {
            "id": str(user["_id"]),
            "username": user.get("username", ""),
            "password": user.get("password", ""),
            "created_at": created_at.isoformat() if created_at and hasattr(created_at, 'isoformat') else created_at,
            "updated_at": updated_at.isoformat() if updated_at and hasattr(updated_at, 'isoformat') else updated_at
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error retrieving user details: {e}")
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")

@login_cred.post("/add-user-id", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def add_user(user: User):
    """
    API to add a new user to the database.
    """
    try:
        current_time = datetime.now()
        
        new_user = {
            "username": user.username,
            "password": user.password,
            "created_at": current_time,
            "updated_at": current_time
        }
        
        insert_result = login_crud.create(new_user)
        
        if "error" in insert_result:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=insert_result["error"])
        
        return {
            "id": insert_result["inserted_id"],
            "username": user.username,
            "password": user.password,
            "created_at": current_time.isoformat(),
            "updated_at": current_time.isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to add user: {str(e)}")


@login_cred.put("/update-user-cred/{user_id}", response_model=Dict[str, Any])
async def update_user(user_id: str, update_data: UserUpdateRequest):
    """
    API to update an existing user's credentials with security key.
    """
    try:
        # Extract the security key and user data
        security_key = SecurityKey(object_id=update_data.security_key.get("object_id"))
        user = update_data.user
        
        # Verify the security key matches the user being updated
        if security_key.object_id != user_id:
            raise HTTPException(status_code=401, detail="Security key doesn't match user ID")
        
        # Verify the security key
        await verify_object_id(security_key)
        
        # Validate if user_id is a valid ObjectId
        try:
            object_id = ObjectId(user_id)
        except InvalidId:
            raise HTTPException(status_code=400, detail=f"Invalid ObjectId: {user_id}")
        
        current_time = datetime.now()
        
        update_result = login_crud.update(
            {"_id": object_id},
            {
                "username": user.username,
                "password": user.password,
                "updated_at": current_time
            }
        )
        
        if "error" in update_result:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=update_result["error"])
        
        if update_result["modified_count"] == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with ID {user_id} not found")
        
        return {
            "id": user_id,
            "username": user.username,
            "password": user.password,
            "updated_at": current_time.isoformat()
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                           detail=f"An error occurred while updating: {str(e)}")

@login_cred.delete("/delete-user/{user_id}", response_model=Dict[str, str])
async def delete_user(user_id: str, security_key: SecurityKey):
    """
    API to delete a user by user_id.
    """
    try:
        # Verify the security key
        verified_id = await verify_object_id(security_key)
        
        # Verify the security key matches the user being deleted
        if verified_id != user_id:
            raise HTTPException(status_code=401, detail="Security key doesn't match user ID")
        
        # Validate if user_id is a valid ObjectId
        try:
            object_id = ObjectId(user_id)
        except InvalidId:
            raise HTTPException(status_code=400, detail=f"Invalid ObjectId: {user_id}")
        
        delete_result = login_crud.delete({"_id": object_id})
        
        if "error" in delete_result:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=delete_result["error"])
        
        if delete_result["deleted_count"] == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with ID {user_id} not found")
        
        return {"id": user_id, "status": "deleted"}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                           detail=f"Failed to delete user: {str(e)}")

@login_cred.post("/login", response_model=Dict[str, Any])
async def login(user: User):
    """
    API for user authentication.
    """
    try:
        # Find user by username and password
        users = login_crud.read({
            "username": user.username,
            "password": user.password
        })
        
        if "error" in users:
            raise HTTPException(status_code=500, detail=users["error"])
        
        if not users or len(users) == 0:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password"
            )
        
        user_data = users[0]
        
        # Convert datetime objects to ISO format strings
        created_at = user_data.get("created_at")
        updated_at = user_data.get("updated_at")
        
        return {
            "id": str(user_data["_id"]),
            "username": user_data.get("username", ""),
            "created_at": created_at.isoformat() if created_at and hasattr(created_at, 'isoformat') else created_at,
            "updated_at": updated_at.isoformat() if updated_at and hasattr(updated_at, 'isoformat') else updated_at,
            "status": "success"
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=500, detail=f"An error occurred during login: {str(e)}")