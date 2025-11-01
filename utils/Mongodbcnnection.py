from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ConfigurationError
import logging
import os
from dotenv import load_dotenv

load_dotenv()


# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MongoDBConnection:
    def __init__(self):
        self.client = None
        self.db = None
        self.connect()

    def connect(self):
        MONGO_URI = os.getenv("MONGO_URI")
        DATABASE_NAME = "forensic_report"
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

    def get_database(self):
        return self.db
