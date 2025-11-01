"""
Database session management.
"""
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import ConnectionFailure, ConfigurationError

from src.core.config import MONGO_URI, DATABASE_NAME
from src.core.logging_config import get_logger

logger = get_logger(__name__)

class DatabaseSession:
    """
    Database session manager for MongoDB.
    """
    _instance = None
    
    def __new__(cls):
        """
        Singleton pattern to ensure only one database connection is created.
        """
        if cls._instance is None:
            cls._instance = super(DatabaseSession, cls).__new__(cls)
            cls._instance.client = None
            cls._instance.db = None
            cls._instance.connect()
        return cls._instance
    
    def connect(self):
        """
        Connect to the MongoDB database.
        
        Raises:
            Exception: If the connection fails.
        """
        try:
            self.client = MongoClient(
                MONGO_URI,
                tls=True  # Ensure TLS/SSL is enabled
            )
            self.db = self.client[DATABASE_NAME]
            self.client.admin.command("ping")
            logger.info("MongoDB connection successful.")
        except (ConnectionFailure, ConfigurationError) as e:
            logger.error(f"Error connecting to MongoDB: {e}")
            raise Exception(f"MongoDB connection error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise Exception(f"Unexpected error during MongoDB initialization: {e}")
    
    def get_database(self) -> Database:
        """
        Get the database instance.
        
        Returns:
            The MongoDB database instance.
        """
        return self.db
    
    def close(self):
        """
        Close the database connection.
        """
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed.")

# Create a global instance of the database session
db_session = DatabaseSession()

def get_db() -> Database:
    """
    Get the database instance.
    
    Returns:
        The MongoDB database instance.
    """
    return db_session.get_database()
