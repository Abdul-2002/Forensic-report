"""
Pytest configuration file.
"""
import os
import pytest
from fastapi.testclient import TestClient
from pymongo import MongoClient
from pymongo.database import Database

from src.main import app
from src.core.config import MONGO_URI, DATABASE_NAME

@pytest.fixture
def client():
    """
    Test client for the FastAPI application.
    """
    with TestClient(app) as test_client:
        yield test_client

@pytest.fixture
def test_db():
    """
    Test database for MongoDB.
    """
    # Use a test database
    test_db_name = f"{DATABASE_NAME}_test"
    
    # Connect to MongoDB
    client = MongoClient(MONGO_URI)
    db = client[test_db_name]
    
    yield db
    
    # Clean up
    client.drop_database(test_db_name)
    client.close()
