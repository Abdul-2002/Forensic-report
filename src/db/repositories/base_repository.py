"""
Base repository for database operations.
"""
from typing import Dict, Any, List, Optional, TypeVar, Generic, Type
from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from src.core.logging_config import get_logger
from src.db.session import get_db
from src.db.models.base import BaseModel, format_object_id

logger = get_logger(__name__)

T = TypeVar('T', bound=BaseModel)

class BaseRepository(Generic[T]):
    """
    Base repository for database operations.
    """
    
    def __init__(self, collection_name: str, model_class: Type[T]):
        """
        Initialize the repository with the given collection name and model class.
        
        Args:
            collection_name: The name of the collection.
            model_class: The model class.
        """
        self.db = get_db()
        self.collection: Collection = self.db[collection_name]
        self.model_class = model_class
    
    def create(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new document in the collection.
        
        Args:
            data: The document data.
            
        Returns:
            A dictionary with the inserted ID or an error message.
        """
        try:
            result = self.collection.insert_one(data)
            logger.info(f"Document inserted with ID: {result.inserted_id}")
            return {"inserted_id": result.inserted_id}
        except PyMongoError as e:
            logger.error(f"Error inserting document: {e}")
            return {"error": str(e)}
    
    def read(self, query: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Read documents from the collection.
        
        Args:
            query: The query to filter documents.
            
        Returns:
            A list of documents or an error message.
        """
        try:
            documents = list(self.collection.find(query))
            logger.info(f"Found {len(documents)} documents matching query.")
            return format_object_id(documents)
        except PyMongoError as e:
            logger.error(f"Error reading documents: {e}")
            return [{"error": str(e)}]
    
    def read_one(self, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Read a single document from the collection.
        
        Args:
            query: The query to filter documents.
            
        Returns:
            The document or None if not found.
        """
        try:
            document = self.collection.find_one(query)
            if document:
                logger.info(f"Found document matching query.")
                return format_object_id(document)
            else:
                logger.info(f"No document found matching query.")
                return None
        except PyMongoError as e:
            logger.error(f"Error reading document: {e}")
            return None
    
    def update(self, query: Dict[str, Any], update_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update documents in the collection.
        
        Args:
            query: The query to filter documents.
            update_data: The data to update.
            
        Returns:
            A dictionary with the number of modified documents or an error message.
        """
        try:
            result = self.collection.update_many(query, {"$set": update_data})
            logger.info(f"Updated {result.modified_count} document(s).")
            return {"modified_count": result.modified_count}
        except PyMongoError as e:
            logger.error(f"Error updating documents: {e}")
            return {"error": str(e)}
    
    def delete(self, query: Dict[str, Any]) -> Dict[str, Any]:
        """
        Delete documents from the collection.
        
        Args:
            query: The query to filter documents.
            
        Returns:
            A dictionary with the number of deleted documents or an error message.
        """
        try:
            result = self.collection.delete_many(query)
            logger.info(f"Deleted {result.deleted_count} document(s).")
            return {"deleted_count": result.deleted_count}
        except PyMongoError as e:
            logger.error(f"Error deleting documents: {e}")
            return {"error": str(e)}
