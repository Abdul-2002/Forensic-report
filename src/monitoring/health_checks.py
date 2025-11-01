"""
Health check implementations for the application.
"""
import os
import time
from typing import Dict, Any, List

from pymongo.database import Database
from azure.storage.blob import BlobServiceClient

from src.core.config import AZURE_CONNECTION_STRING, AZURE_CONTAINER_NAME, GOOGLE_API_KEY
from src.core.logging_config import get_logger
from src.db.session import get_db

logger = get_logger(__name__)

async def check_database() -> Dict[str, Any]:
    """
    Check the database connection.

    Returns:
        A dictionary with the database status.
    """
    try:
        db = get_db()

        # Ping the database
        start_time = time.time()
        db.command("ping")
        ping_time = time.time() - start_time

        # Get database stats
        stats = db.command("dbStats")

        return {
            "status": "ok",
            "ping_time": ping_time,
            "collections": stats.get("collections", 0),
            "objects": stats.get("objects", 0),
            "storage_size": stats.get("storageSize", 0)
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "error",
            "error": str(e)
        }

async def check_storage() -> Dict[str, Any]:
    """
    Check the Azure Blob Storage connection.

    Returns:
        A dictionary with the storage status.
    """
    try:
        # Create blob service client
        blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
        container_client = blob_service_client.get_container_client(AZURE_CONTAINER_NAME)

        # Check if container exists
        start_time = time.time()
        container_exists = container_client.exists()
        check_time = time.time() - start_time

        if not container_exists:
            return {
                "status": "error",
                "error": f"Container '{AZURE_CONTAINER_NAME}' does not exist"
            }

        # Get container properties
        properties = container_client.get_container_properties()

        return {
            "status": "ok",
            "check_time": check_time,
            "container": AZURE_CONTAINER_NAME,
            "last_modified": properties.last_modified.isoformat() if hasattr(properties, "last_modified") else None
        }
    except Exception as e:
        logger.error(f"Storage health check failed: {e}")
        return {
            "status": "error",
            "error": str(e)
        }

async def check_ai_services() -> Dict[str, Any]:
    """
    Check the AI services.

    Returns:
        A dictionary with the AI services status.
    """
    services = {}

    # Check Google API key
    if GOOGLE_API_KEY:
        services["gemini"] = {
            "status": "ok",
            "api_key_configured": True
        }
    else:
        services["gemini"] = {
            "status": "error",
            "api_key_configured": False,
            "error": "Google API key not configured"
        }

    # Overall status is the same as Gemini status since it's the only AI service now
    overall_status = services["gemini"]["status"]

    return {
        "status": overall_status,
        "services": services
    }

async def check_disk_space() -> Dict[str, Any]:
    """
    Check the disk space.

    Returns:
        A dictionary with the disk space status.
    """
    try:
        # Get disk usage
        total, used, free = os.statvfs("/").f_frsize, os.statvfs("/").f_blocks, os.statvfs("/").f_bfree
        total_size = total * used
        free_size = total * free
        used_size = total_size - free_size
        used_percent = (used_size / total_size) * 100

        # Check if disk space is low
        status = "ok"
        if used_percent > 90:
            status = "warning"
        if used_percent > 95:
            status = "error"

        return {
            "status": status,
            "total_size": total_size,
            "used_size": used_size,
            "free_size": free_size,
            "used_percent": used_percent
        }
    except Exception as e:
        logger.error(f"Disk space health check failed: {e}")
        return {
            "status": "error",
            "error": str(e)
        }

async def check_upload_directories() -> Dict[str, Any]:
    """
    Check the upload directories.

    Returns:
        A dictionary with the upload directories status.
    """
    from src.core.config import UPLOAD_DIR, REPORTS_DIR, IMAGES_DIR, EXHIBITS_DIR

    directories = [
        {"name": "uploads", "path": UPLOAD_DIR},
        {"name": "reports", "path": REPORTS_DIR},
        {"name": "images", "path": IMAGES_DIR},
        {"name": "exhibits", "path": EXHIBITS_DIR}
    ]

    results = {}
    overall_status = "ok"

    for directory in directories:
        name = directory["name"]
        path = directory["path"]

        if not os.path.exists(path):
            results[name] = {
                "status": "error",
                "error": f"Directory '{path}' does not exist"
            }
            overall_status = "error"
        elif not os.path.isdir(path):
            results[name] = {
                "status": "error",
                "error": f"Path '{path}' is not a directory"
            }
            overall_status = "error"
        elif not os.access(path, os.W_OK):
            results[name] = {
                "status": "error",
                "error": f"Directory '{path}' is not writable"
            }
            overall_status = "error"
        else:
            results[name] = {
                "status": "ok",
                "path": path
            }

    return {
        "status": overall_status,
        "directories": results
    }

async def run_all_health_checks() -> Dict[str, Any]:
    """
    Run all health checks.

    Returns:
        A dictionary with all health check results.
    """
    database = await check_database()
    storage = await check_storage()
    ai_services = await check_ai_services()
    disk_space = await check_disk_space()
    upload_directories = await check_upload_directories()

    # Overall status
    overall_status = "ok"
    for check in [database, storage, ai_services, disk_space, upload_directories]:
        if check["status"] == "error":
            overall_status = "error"
            break
        elif check["status"] == "warning" and overall_status != "error":
            overall_status = "warning"

    return {
        "status": overall_status,
        "database": database,
        "storage": storage,
        "ai_services": ai_services,
        "disk_space": disk_space,
        "upload_directories": upload_directories
    }
