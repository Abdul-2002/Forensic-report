from fastapi import APIRouter, HTTPException, status, UploadFile, File, Form, Depends, Response
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
import os
import shutil
from utils.Mongodbcnnection import MongoDBConnection
from fastapi.staticfiles import StaticFiles
from bson import ObjectId
from pathlib import Path
from utils.CRUD_utils import ReadWrite  # Import ReadWrite for Azure operations
import tempfile
from src.core.config import AZURE_ACCOUNT_NAME  # Import account name from config

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Create router
report_router = APIRouter()

# Mount static files for serving uploads (still useful for local development)
report_router.mount("/reports", StaticFiles(directory="uploads/reports"), name="reports")

# MongoDB connection
mongo_connection = MongoDBConnection()
database = mongo_connection.get_database()
REPORT_COLLECTION = "case_reports"
report_collection = database[REPORT_COLLECTION]

# Initialize Azure storage client for reports - using the same container as case_router
azure_storage = ReadWrite("original-data")  # Match container name with case_router

# Ensure upload directories exist (still useful for local temp files)
UPLOAD_DIR = "uploads"
REPORTS_DIR = os.path.join(UPLOAD_DIR, "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

# Helper function to save uploaded file - synchronized with case_router implementation
async def save_uploaded_file(file: UploadFile, file_path: str) -> bool:
    """
    Save an uploaded file to the specified path.
    Returns True if successful, False otherwise.
    """
    try:
        content = await file.read()
        if len(content) == 0:
            logger.warning(f"File {file.filename} is empty")
            return False

        with open(file_path, "wb") as f:
            f.write(content)

        logger.info(f"Saved file to {file_path}")

        # Verify the file exists and has content
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            return True
        else:
            logger.error(f"Failed to save file or file is empty: {file_path}")
            return False
    except Exception as e:
        logger.error(f"Error saving file {file.filename}: {str(e)}")
        return False

# Upload to Azure function - following the pattern from case_router
def upload_to_azure(case_id: str, file_path: str) -> str:
    """
    Upload a file to Azure Blob Storage.
    Returns the Azure URL if successful, empty string otherwise.
    """
    try:
        # Ensure file exists before upload
        if not os.path.exists(file_path):
            logger.error(f"File does not exist for Azure upload: {file_path}")
            return ""

        # Construct path: case_id/reports/filename
        file_name = os.path.basename(file_path)
        azure_path = f"{case_id}/reports"

        # Convert string path to Path object as expected by upload_file
        file_path_obj = Path(file_path)

        # Upload the file to Azure
        azure_url = azure_storage.upload_file(azure_path, file_path_obj)
        if azure_url:
            logger.info(f"File uploaded to Azure: {azure_url}")
            return azure_url
        else:
            logger.warning(f"Azure upload returned None for {file_path}")
            return ""
    except Exception as e:
        logger.error(f"Error uploading to Azure: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return ""

# Helper function to convert MongoDB document to dict with string IDs
def convert_mongo_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    if doc is None:
        return None

    result = {}
    for key, value in doc.items():
        if key == "_id":
            result["id"] = str(value)
        elif isinstance(value, ObjectId):
            result[key] = str(value)
        else:
            result[key] = value

    return result

# Save generated report to Azure
@report_router.post("/save-report", status_code=status.HTTP_201_CREATED)
async def save_report(
    case_id: str = Form(...),
    case_name: str = Form(...),
    report_content: str = Form(...),
    report_file: UploadFile = File(...)
):
    try:
        # Create a timestamp for unique filenames
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"{case_id}_{timestamp}.docx"

        # Create a local directory path for the case reports
        case_report_dir = os.path.join(UPLOAD_DIR, case_id, "reports")
        os.makedirs(case_report_dir, exist_ok=True)

        # Local file path
        local_file_path = os.path.join(case_report_dir, filename)

        # Save the file locally first
        if not await save_uploaded_file(report_file, local_file_path):
            raise HTTPException(
                status_code=500,
                detail="Failed to save report file locally"
            )

        # Upload to Azure Blob Storage
        azure_url = upload_to_azure(case_id, local_file_path)

        if not azure_url:
            raise HTTPException(
                status_code=500,
                detail="Failed to upload file to Azure storage"
            )

        # Create report data for MongoDB
        report_data = {
            "case_id": case_id,
            "case_name": case_name,
            "generated_date": datetime.now().strftime("%Y-%m-%d"),
            "report_url": azure_url,  # Store Azure URL
            "report_content": report_content,
            "filename": filename,  # Store original filename
            "local_path": os.path.join(case_id, "reports", filename).replace("\\", "/"),  # Store relative local path with forward slashes
            "final_report_url": None
        }

        # Insert into database
        result = report_collection.insert_one(report_data)

        # Create a plain dictionary for response
        response = {
            "id": str(result.inserted_id),
            "case_id": case_id,
            "case_name": case_name,
            "generated_date": report_data["generated_date"],
            "report_url": report_data["report_url"],
            "filename": report_data["filename"],
            "final_report_url": None
        }

        return response
    except HTTPException as e:
        logger.error(f"HTTP Exception: {str(e)}")
        raise e
    except Exception as e:
        logger.error(f"Failed to save report: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to save report: {str(e)}")

# Get all reports
@report_router.get("/reports")
async def get_reports():
    try:
        reports = list(report_collection.find())
        # Convert MongoDB documents to serializable dictionaries
        serialized_reports = [convert_mongo_doc(report) for report in reports]
        return serialized_reports
    except Exception as e:
        logger.error(f"Failed to fetch reports: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch reports: {str(e)}")

# Upload final report to Azure
@report_router.post("/upload-final-report/{report_id}", status_code=status.HTTP_200_OK)
async def upload_final_report(
    report_id: str,
    final_report: UploadFile = File(...)
):
    try:
        # Verify report exists
        report = report_collection.find_one({"_id": ObjectId(report_id)})
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")

        # Create a timestamp for unique filenames
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"final_{report['case_id']}_{timestamp}.pdf"

        # Create a local directory path for the case reports
        case_id = report['case_id']
        case_report_dir = os.path.join(UPLOAD_DIR, case_id, "reports")
        os.makedirs(case_report_dir, exist_ok=True)

        # Local file path
        local_file_path = os.path.join(case_report_dir, filename)

        # Save the file locally first
        if not await save_uploaded_file(final_report, local_file_path):
            raise HTTPException(
                status_code=500,
                detail="Failed to save final report file locally"
            )

        # Upload to Azure Blob Storage
        azure_url = upload_to_azure(case_id, local_file_path)

        if not azure_url:
            raise HTTPException(
                status_code=500,
                detail="Failed to upload final report to Azure storage"
            )

        # Update report record
        report_collection.update_one(
            {"_id": ObjectId(report_id)},
            {"$set": {
                "final_report_url": azure_url,
                "final_filename": filename,
                "final_local_path": os.path.join(case_id, "reports", filename).replace("\\", "/")
            }}
        )

        return {
            "message": "Final report uploaded successfully",
            "final_report_url": azure_url
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Failed to upload final report: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to upload final report: {str(e)}")

# Get reports for a specific case
@report_router.get("/reports/{case_id}")
async def get_case_reports(case_id: str):
    try:
        # Find all reports for this case
        reports = list(report_collection.find({"case_id": case_id}))

        # If no reports found, return empty list (not an error)
        if not reports:
            return []

        # Convert MongoDB documents to serializable dictionaries
        serialized_reports = [convert_mongo_doc(report) for report in reports]
        return serialized_reports
    except Exception as e:
        logger.error(f"Failed to fetch reports for case {case_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch reports for case {case_id}: {str(e)}"
        )

# Delete a report
@report_router.delete("/reports/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_report(report_id: str):
    try:
        # Find the report to get file information before deletion
        report = report_collection.find_one({"_id": ObjectId(report_id)})
        if not report:
            raise HTTPException(status_code=404, detail="Report not found")

        case_id = report.get("case_id")
        filename = report.get("filename")
        final_filename = report.get("final_filename")

        # Delete the report from Azure if possible
        # Note: We're intentionally continuing even if Azure deletion fails
        try:
            if case_id and filename:
                # Due to how the paths are constructed in upload_to_azure,
                # we need to ensure we use the exact path format
                azure_storage.delete_file(case_id, filename)

            if case_id and final_filename:
                azure_storage.delete_file(case_id, final_filename)
        except Exception as e:
            logger.error(f"Error deleting files from Azure: {str(e)}")
            # Continue with database deletion even if Azure deletion fails

        # Delete local files if they exist
        try:
            if "local_path" in report and report["local_path"]:
                local_path = os.path.join(UPLOAD_DIR, report["local_path"])
                if os.path.exists(local_path):
                    os.remove(local_path)

            if "final_local_path" in report and report["final_local_path"]:
                final_path = os.path.join(UPLOAD_DIR, report["final_local_path"])
                if os.path.exists(final_path):
                    os.remove(final_path)
        except Exception as e:
            logger.error(f"Error deleting local files: {str(e)}")
            # Continue with database deletion even if local deletion fails

        # Delete the report from the database
        result = report_collection.delete_one({"_id": ObjectId(report_id)})

        if result.deleted_count == 0:
            # This shouldn't happen since we already checked existence
            raise HTTPException(status_code=404, detail="Report not found")

        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Failed to delete report {report_id}: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete report {report_id}: {str(e)}"
        )

# Download a report - create a temporary SAS link for downloading
@report_router.get("/download-report/{case_id}")
async def download_report(case_id: str):
    try:
        logger.info(f"Download request for case_id: {case_id}")

        # Find all reports for this case without sorting
        reports = list(report_collection.find({"case_id": case_id}))

        logger.info(f"Found {len(reports)} reports for case_id: {case_id}")

        if not reports:
            logger.error(f"No reports found for case_id: {case_id}")
            raise HTTPException(status_code=404, detail=f"No reports found for case {case_id}")

        # Get the most recent report
        if len(reports) > 1:
            # Manual sorting by date (handles string dates)
            reports.sort(key=lambda x: x.get("generated_date", ""), reverse=True)

        report = reports[0]

        # Log all fields in the report for debugging
        logger.info(f"Report keys: {list(report.keys())}")

        # Check if report_url exists and use it directly
        report_url = report.get("report_url")
        logger.info(f"Report URL from document: {report_url}")

        if report_url and isinstance(report_url, str) and report_url.startswith("https://"):
            logger.info(f"Found valid direct Azure URL: {report_url}")
            # Return both the download URL and the document data
            return {
                "download_url": report_url,
                "report_data": {
                    "case_id": report.get("case_id"),
                    "case_name": report.get("case_name"),
                    "generated_date": report.get("generated_date"),
                    "report_url": report.get("report_url")
                }
            }

        # If report_url is missing, construct it based on case_id pattern
        constructed_url = f"https://{AZURE_ACCOUNT_NAME}.blob.core.windows.net/original-data/{case_id}/reports/{case_id}_"
        logger.info(f"No direct URL found, using constructed base: {constructed_url}")

        # Return both the constructed URL and document data
        return {
            "download_url": report.get("report_url", constructed_url),
            "report_data": {
                "case_id": report.get("case_id"),
                "case_name": report.get("case_name"),
                "generated_date": report.get("generated_date")
            }
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Failed to create download link for case {case_id}: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create download link: {str(e)}"
        )


# Download a final report
@report_router.get("/download-final-report/{case_id}")
async def download_final_report(case_id: str):
    try:
        # Find all reports for this case without sorting in the query
        reports = list(report_collection.find({"case_id": case_id}))

        if not reports:
            raise HTTPException(status_code=404, detail=f"No reports found for case {case_id}")

        # Manually sort reports by generated_date if needed
        if len(reports) > 1:
            reports.sort(key=lambda x: x.get("generated_date", ""), reverse=True)

        # Get the most recent report
        report = reports[0]

        # Check if final report exists
        final_report_url = report.get("final_report_url")
        if not final_report_url:
            raise HTTPException(status_code=404, detail="Final report not found")

        # If we have a direct URL to Azure blob, return it
        if final_report_url.startswith("https://"):
            return {"download_url": final_report_url}

        # Get the filename
        final_filename = report.get("final_filename")

        if not final_filename:
            raise HTTPException(status_code=404, detail="Final report file information not found")

        # Create a temporary SAS link for download
        try:
            download_url = azure_storage.create_link(case_id, final_filename)

            if not download_url:
                raise HTTPException(status_code=500, detail="Failed to create download link")

            # Return the download URL
            return {"download_url": download_url}
        except Exception as e:
            logger.error(f"Error creating download link: {str(e)}")

            # Fallback: try to serve the local file if it exists
            local_path = os.path.join(UPLOAD_DIR, case_id, "reports", final_filename)
            if os.path.exists(local_path):
                return {"local_file_path": f"/uploads/{case_id}/reports/{final_filename}"}
            else:
                raise HTTPException(status_code=500, detail="Failed to create download link and local file not found")
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Failed to create download link for final report for case {case_id}: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create download link: {str(e)}"
        )