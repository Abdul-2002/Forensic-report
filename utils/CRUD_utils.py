import os
import logging
from pymongo.collection import Collection
from pymongo.errors import PyMongoError
from azure.storage.blob import BlobServiceClient, BlobSasPermissions, generate_blob_sas
from datetime import datetime, timedelta
from pathlib import Path
from utils.Mongodbcnnection import MongoDBConnection
from dotenv import load_dotenv
# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()

class CRUDUtils:
    """
    Utility class to perform CRUD operations on MongoDB collections.
    """
    def __init__(self, collection_name: str):
        self.db = MongoDBConnection().get_database()
        self.collection: Collection = self.db[collection_name]

    def create(self, data: dict):
        try:
            result = self.collection.insert_one(data)
            logger.info(f"Document inserted with ID: {result.inserted_id}")
            return {"inserted_id": str(result.inserted_id)}
        except PyMongoError as e:
            logger.error(f"Error inserting document: {e}")
            return {"error": str(e)}

    def read(self, query: dict):
        try:
            documents = list(self.collection.find(query))
            logger.info(f"Found {len(documents)} documents matching query.")
            return documents
        except PyMongoError as e:
            logger.error(f"Error reading documents: {e}")
            return {"error": str(e)}

    def update(self, query: dict, update_data: dict):
        try:
            result = self.collection.update_many(query, {"$set": update_data})
            logger.info(f"Updated {result.modified_count} document(s).")
            return {"modified_count": result.modified_count}
        except PyMongoError as e:
            logger.error(f"Error updating documents: {e}")
            return {"error": str(e)}

    def delete(self, query: dict):
        try:
            result = self.collection.delete_many(query)
            logger.info(f"Deleted {result.deleted_count} document(s).")
            return {"deleted_count": result.deleted_count}
        except PyMongoError as e:
            logger.error(f"Error deleting documents: {e}")
            return {"error": str(e)}

class ReadWrite:
    """
    Utility class for handling Read and Write operations on Azure Blob Storage.
    """
    def __init__(self, container_name: str):
        self.connection_string = os.getenv("AZURE_CONNECTION_STRING")
        self.container_name = container_name
        self.account_name = os.getenv("ACCOUNT_NAME")

        try:
            self.blob_service_client = BlobServiceClient.from_connection_string(self.connection_string)
            self.container_client = self.blob_service_client.get_container_client(self.container_name)
            logger.info(f"Successfully connected to Azure Blob Storage account: {self.account_name}")
        except Exception as e:
            logger.error(f"Error connecting to Azure Blob Storage: {e}")
            raise e

    def upload_file(self, case_id: str, file_path: Path) -> str:
        try:
            blob_name = f"{case_id}/{file_path.name}"
            blob_client = self.container_client.get_blob_client(blob_name)

            with open(file_path, "rb") as data:
                blob_client.upload_blob(data, overwrite=True)

            file_url = f"https://{self.account_name}.blob.core.windows.net/{self.container_name}/{blob_name}"
            logger.info(f"File uploaded successfully: {file_url}")

            return file_url
        except Exception as e:
            logger.error(f"Error uploading file: {e}")
            return None

    def delete_file(self, case_id: str, file_name: str) -> bool:
        try:
            blob_name = f"{case_id}/{file_name}"
            blob_client = self.container_client.get_blob_client(blob_name)

            if blob_client.exists():
                blob_client.delete_blob()
                logger.info(f"File deleted successfully: {blob_name}")
                return True
            else:
                logger.warning(f"File not found: {blob_name}")
                return False
        except Exception as e:
            logger.error(f"Error deleting file: {e}")
            return False

    def create_link(self, case_id: str, file_name: str) -> str:
        try:
            # Azure expects forward slashes in paths
            blob_name = f"{case_id}/reports/{file_name}"

            # Log the full blob path for debugging
            logger.info(f"Creating SAS link for blob: {blob_name}")

            # Generate SAS token without checking existence first
            # because sometimes exists() method fails even when the blob is there
            sas_token = generate_blob_sas(
                account_name=self.account_name,
                container_name=self.container_name,
                blob_name=blob_name,
                account_key=os.getenv("ACCOUNT_KEY"),
                permission=BlobSasPermissions(read=True),
                expiry=datetime.utcnow() + timedelta(minutes=15),
            )

            file_url = f"https://{self.account_name}.blob.core.windows.net/{self.container_name}/{blob_name}?{sas_token}"
            logger.info(f"Successfully generated SAS link: {file_url[:50]}...")
            return file_url
        except Exception as e:
            logger.error(f"Error generating SAS link: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return None


from bson import ObjectId

def format_object_id(obj):
    """
    Recursively formats MongoDB ObjectId to string in dictionaries and lists.

    Args:
        obj: The object to format (dict, list, or other)

    Returns:
        The formatted object with ObjectId converted to strings
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, ObjectId):
                obj[k] = str(v)
            elif isinstance(v, (dict, list)):
                obj[k] = format_object_id(v)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            if isinstance(v, ObjectId):
                obj[i] = str(v)
            elif isinstance(v, (dict, list)):
                obj[i] = format_object_id(v)
    return obj