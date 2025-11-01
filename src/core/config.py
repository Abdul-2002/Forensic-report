"""
Configuration settings for the application.
"""
import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# API settings
API_V1_STR: str = "/app/v1"
PROJECT_NAME: str = "Forensic Report Generation API"
VERSION: str = "v1"

# MongoDB settings
MONGO_URI: str = os.getenv("MONGO_URI")
DATABASE_NAME: str = os.getenv("DATABASE_NAME")
CASE_COLLECTION: str = os.getenv("CASE_COLLECTION")
PROMPTS_COLLECTION: str = os.getenv("PROMPTS_COLLECTION")

# Azure Blob Storage settings
AZURE_CONNECTION_STRING: str = os.getenv("AZURE_CONNECTION_STRING")
AZURE_CONTAINER_NAME: str = os.getenv("AZURE_CONTAINER_NAME")
AZURE_ACCOUNT_NAME: str = os.getenv("ACCOUNT_NAME")
AZURE_ACCOUNT_KEY: str = os.getenv("ACCOUNT_KEY")

# AI settings are now only for Gemini

# Google Gemini settings
GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL")
GEMINI_IMAGE_MODEL: str = os.getenv("GEMINI_IMAGE_MODEL")

# File upload settings
UPLOAD_DIR: str = "uploads"
REPORTS_DIR: str = os.path.join(UPLOAD_DIR, "reports")
IMAGES_DIR: str = os.path.join(UPLOAD_DIR, "images")
EXHIBITS_DIR: str = os.path.join(UPLOAD_DIR, "exhibits")

# CORS settings
# In production, specify the exact frontend domain
# For local development, allow localhost
CORS_ORIGINS: list = [
    "*",  # Allow all origins (remove in production)
    "http://localhost:3000",
    "https://forensic-be-gemini.gentleisland-62854069.centralindia.azurecontainerapps.io",
    # Add your production frontend domain here
]
CORS_CREDENTIALS: bool = True
CORS_METHODS: list = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
CORS_HEADERS: list = [
    "Content-Type",
    "Authorization",
    "X-Requested-With",
    "X-Client-Version",
    "X-Client-Keep-Alive",
    "Origin",
    "Accept"
]

# Create directories if they don't exist
os.makedirs(REPORTS_DIR, exist_ok=True)
os.makedirs(IMAGES_DIR, exist_ok=True)
os.makedirs(EXHIBITS_DIR, exist_ok=True)
