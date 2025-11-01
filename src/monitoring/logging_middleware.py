"""
Logging middleware for the application.
"""
import time
import uuid
from typing import Callable, Dict, Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from src.core.logging_config import get_logger
from src.utils.audit_helpers import audit_logger

logger = get_logger(__name__)

class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for logging requests and responses.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process a request and log it.
        
        Args:
            request: The request.
            call_next: The next middleware.
            
        Returns:
            The response.
        """
        request_id = str(uuid.uuid4())
        start_time = time.time()
        
        # Extract client IP
        client_ip = request.client.host if request.client else None
        
        # Log request
        logger.info(f"Request {request_id}: {request.method} {request.url.path}")
        
        # Extract request data for audit log
        request_data = None
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                # For multipart/form-data, don't try to read the body
                content_type = request.headers.get("content-type", "")
                if "multipart/form-data" not in content_type:
                    # Clone the request to read the body
                    body = await request.body()
                    request_data = {"body_size": len(body)}
                else:
                    request_data = {"content_type": "multipart/form-data"}
            except Exception as e:
                logger.warning(f"Could not read request body for audit log: {str(e)}")
        
        # Log to audit trail
        audit_logger.log_api_request(
            endpoint=request.url.path,
            method=request.method,
            client_ip=client_ip,
            request_data=request_data
        )
        
        try:
            # Process the request
            response = await call_next(request)
            
            # Calculate processing time
            processing_time = time.time() - start_time
            
            # Log response
            logger.info(f"Response {request_id}: {response.status_code} ({processing_time:.3f}s)")
            
            # Log to audit trail
            audit_logger.log_api_response(
                request_id=request_id,
                status_code=response.status_code,
                processing_time=processing_time
            )
            
            # Add custom headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = str(processing_time)
            
            return response
        except Exception as e:
            # Log error
            logger.error(f"Error processing request {request_id}: {str(e)}")
            
            # Log to audit trail
            audit_logger.log_api_response(
                request_id=request_id,
                status_code=500,
                error=str(e),
                processing_time=time.time() - start_time
            )
            
            # Re-raise the exception
            raise
