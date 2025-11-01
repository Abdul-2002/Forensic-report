"""
Metrics collection for the application.
"""
import time
from typing import Dict, Any, Optional, Callable

from fastapi import Request, Response
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, generate_latest

from src.core.logging_config import get_logger

logger = get_logger(__name__)

# Create a registry for metrics
registry = CollectorRegistry()

# Define metrics
http_requests_total = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "status"],
    registry=registry
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    registry=registry
)

active_requests = Gauge(
    "active_requests",
    "Number of active requests",
    registry=registry
)

inference_requests_total = Counter(
    "inference_requests_total",
    "Total number of inference requests",
    ["model", "section", "status"],
    registry=registry
)

inference_request_duration_seconds = Histogram(
    "inference_request_duration_seconds",
    "Inference request duration in seconds",
    ["model", "section"],
    registry=registry
)

file_uploads_total = Counter(
    "file_uploads_total",
    "Total number of file uploads",
    ["file_type", "status"],
    registry=registry
)

file_upload_size_bytes = Histogram(
    "file_upload_size_bytes",
    "File upload size in bytes",
    ["file_type"],
    buckets=[1024, 10240, 102400, 1048576, 10485760, 104857600],
    registry=registry
)

class MetricsMiddleware:
    """
    Middleware for collecting metrics.
    """

    def __init__(self, app):
        """
        Initialize the metrics middleware.

        Args:
            app: The FastAPI application.
        """
        self.app = app

    async def __call__(self, scope, receive, send):
        """
        Process a request and collect metrics.

        Args:
            scope: The ASGI scope.
            receive: The ASGI receive function.
            send: The ASGI send function.

        Returns:
            The response.
        """
        if scope["type"] != "http":
            # If it's not an HTTP request, just pass it through
            await self.app(scope, receive, send)
            return

        active_requests.inc()
        start_time = time.time()

        # Create a wrapper for the send function to capture the status code
        response_status = {}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                response_status["status"] = message["status"]
            await send(message)

        try:
            # Process the request
            await self.app(scope, receive, send_wrapper)

            # Record metrics if we have a status code
            if "status" in response_status:
                method = scope.get("method", "UNKNOWN")
                endpoint = scope.get("path", "UNKNOWN")
                status = response_status["status"]

                http_requests_total.labels(method=method, endpoint=endpoint, status=status).inc()
                http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(time.time() - start_time)
        except Exception as e:
            logger.error(f"Error in metrics middleware: {str(e)}")
            raise
        finally:
            active_requests.dec()

def get_metrics() -> bytes:
    """
    Get the current metrics.

    Returns:
        The metrics in Prometheus format.
    """
    return generate_latest(registry)

def record_inference_metrics(
    model: str,
    section: str,
    duration: float,
    status: str = "success"
):
    """
    Record inference metrics.

    Args:
        model: The model name.
        section: The section.
        duration: The duration in seconds.
        status: The status.
    """
    inference_requests_total.labels(model=model, section=section, status=status).inc()
    inference_request_duration_seconds.labels(model=model, section=section).observe(duration)

def record_file_upload_metrics(
    file_type: str,
    size: int,
    status: str = "success"
):
    """
    Record file upload metrics.

    Args:
        file_type: The file type.
        size: The file size in bytes.
        status: The status.
    """
    file_uploads_total.labels(file_type=file_type, status=status).inc()
    file_upload_size_bytes.labels(file_type=file_type).observe(size)
