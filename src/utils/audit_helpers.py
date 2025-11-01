"""
Audit logging utilities.
"""
import json
import os
import time
from datetime import datetime
from typing import Dict, Any, Optional

from src.core.logging_config import get_logger

logger = get_logger(__name__)

class AuditLogger:
    """
    Audit logger for the application.
    """
    
    def __init__(self, log_dir: str = "logs"):
        """
        Initialize the audit logger.
        
        Args:
            log_dir: The directory to store audit logs.
        """
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
    
    def log_api_request(
        self,
        endpoint: str,
        method: str,
        user_id: Optional[str] = None,
        request_data: Optional[Dict[str, Any]] = None,
        client_ip: Optional[str] = None
    ) -> str:
        """
        Log an API request.
        
        Args:
            endpoint: The API endpoint.
            method: The HTTP method.
            user_id: The user ID.
            request_data: The request data.
            client_ip: The client IP address.
            
        Returns:
            The request ID.
        """
        request_id = f"{int(time.time())}_{os.urandom(4).hex()}"
        
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "request_id": request_id,
            "endpoint": endpoint,
            "method": method,
            "user_id": user_id,
            "client_ip": client_ip,
            "request_data": request_data
        }
        
        self._write_log("api_requests.log", log_entry)
        
        return request_id
    
    def log_api_response(
        self,
        request_id: str,
        status_code: int,
        response_data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        processing_time: Optional[float] = None
    ):
        """
        Log an API response.
        
        Args:
            request_id: The request ID.
            status_code: The HTTP status code.
            response_data: The response data.
            error: The error message.
            processing_time: The processing time in seconds.
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "request_id": request_id,
            "status_code": status_code,
            "processing_time": processing_time,
            "error": error
        }
        
        # Don't log the full response data, it could be very large
        if response_data:
            # Log only metadata about the response
            log_entry["response_size"] = len(json.dumps(response_data))
            
            # If it's a case response, log some basic info
            if isinstance(response_data, dict):
                if "case_id" in response_data:
                    log_entry["case_id"] = response_data["case_id"]
                if "section" in response_data:
                    log_entry["section"] = response_data["section"]
        
        self._write_log("api_responses.log", log_entry)
    
    def log_inference(
        self,
        case_id: str,
        section: str,
        model_name: str,
        processing_time: float,
        status: str,
        error: Optional[str] = None
    ):
        """
        Log an inference operation.
        
        Args:
            case_id: The case ID.
            section: The section.
            model_name: The model name.
            processing_time: The processing time in seconds.
            status: The status.
            error: The error message.
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "case_id": case_id,
            "section": section,
            "model_name": model_name,
            "processing_time": processing_time,
            "status": status
        }
        
        if error:
            log_entry["error"] = error
        
        self._write_log("inference.log", log_entry)
    
    def log_file_upload(
        self,
        case_id: str,
        file_name: str,
        file_size: int,
        file_type: str,
        upload_status: str,
        azure_url: Optional[str] = None,
        error: Optional[str] = None
    ):
        """
        Log a file upload.
        
        Args:
            case_id: The case ID.
            file_name: The file name.
            file_size: The file size in bytes.
            file_type: The file type.
            upload_status: The upload status.
            azure_url: The Azure URL.
            error: The error message.
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "case_id": case_id,
            "file_name": file_name,
            "file_size": file_size,
            "file_type": file_type,
            "upload_status": upload_status
        }
        
        if azure_url:
            # Don't log the full URL, just a truncated version
            log_entry["azure_url"] = azure_url[:50] + "..." if len(azure_url) > 50 else azure_url
        
        if error:
            log_entry["error"] = error
        
        self._write_log("file_uploads.log", log_entry)
    
    def _write_log(self, log_file: str, log_entry: Dict[str, Any]):
        """
        Write a log entry to a log file.
        
        Args:
            log_file: The log file name.
            log_entry: The log entry.
        """
        try:
            log_path = os.path.join(self.log_dir, log_file)
            
            with open(log_path, "a") as f:
                f.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            logger.error(f"Error writing to audit log {log_file}: {str(e)}")

# Create a global instance of the audit logger
audit_logger = AuditLogger()
