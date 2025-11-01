"""
Main application entry point.
This file is kept for backward compatibility.
The actual application is now in src/main.py.
"""
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)
logger.info("Starting application from main.py (compatibility mode)")

# Import the application from the new location
from src.main import app as application

# Export the application for ASGI servers
app = application

# If this file is run directly, start the server
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
