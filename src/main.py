"""
Main application entry point.
"""
import os
import socketio
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import make_wsgi_app
from wsgiref.simple_server import make_server
import threading
import uvicorn

from src.api.endpoints import health, predictions, cases, admin, case_add, reports, login, prompts
from src.core.config import PROJECT_NAME, VERSION, API_V1_STR, CORS_ORIGINS, CORS_METHODS, CORS_HEADERS, CORS_CREDENTIALS
from src.core.logging_config import get_logger
from src.core.openapi import custom_openapi
from src.monitoring.logging_middleware import LoggingMiddleware
from src.monitoring.metrics import MetricsMiddleware, get_metrics
from src.socket.socket_manager import socket_app, sio

# Import socket event handlers
from src.socket.handlers import *

logger = get_logger(__name__)

# Create FastAPI app
app = FastAPI(
    title=PROJECT_NAME,
    version=VERSION,
    description="API for forensic report generation using AI",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=CORS_CREDENTIALS,
    allow_methods=CORS_METHODS,
    allow_headers=CORS_HEADERS
)

# Add logging middleware
app.add_middleware(LoggingMiddleware)

# Add metrics middleware
app.add_middleware(MetricsMiddleware)

# Include routers
app.include_router(health.router, prefix=API_V1_STR)
app.include_router(predictions.router, prefix=API_V1_STR)
app.include_router(cases.router, prefix=API_V1_STR)
app.include_router(case_add.router, prefix=API_V1_STR)
app.include_router(reports.router, prefix=API_V1_STR)
app.include_router(login.router, prefix=API_V1_STR)
app.include_router(prompts.router, prefix=API_V1_STR)
app.include_router(admin.router)

# Use custom OpenAPI schema generator
app.openapi = lambda: custom_openapi(app)

# Add metrics endpoint
@app.get("/metrics")
async def metrics():
    """
    Get application metrics in Prometheus format.
    """
    return Response(content=get_metrics(), media_type="text/plain")

# Add exception handler
@app.exception_handler(Exception)
async def global_exception_handler(_: Request, exc: Exception):
    """
    Global exception handler.
    """
    logger.error(f"Unhandled exception: {str(exc)}")
    import traceback
    logger.error(traceback.format_exc())

    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again later."}
    )

# Startup event
@app.on_event("startup")
async def startup_event():
    """
    Startup event handler.
    """
    logger.info(f"Starting {PROJECT_NAME} {VERSION}")

    # Create upload directories
    from src.core.config import UPLOAD_DIR, REPORTS_DIR, IMAGES_DIR, EXHIBITS_DIR
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    os.makedirs(REPORTS_DIR, exist_ok=True)
    os.makedirs(IMAGES_DIR, exist_ok=True)
    os.makedirs(EXHIBITS_DIR, exist_ok=True)

    logger.info("Application startup complete")

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """
    Shutdown event handler.
    """
    logger.info(f"Shutting down {PROJECT_NAME} {VERSION}")

    # Unload all models
    from src.inference.loader import model_loader
    model_loader.unload_all_models()

    logger.info("Application shutdown complete")

# Mount the Socket.IO app
# The socket_app will handle all WebSocket connections
# IMPORTANT: This must be done AFTER adding all middleware and routes to the FastAPI app
app = socketio.ASGIApp(sio, app)

# TODO: Update to use lifespan when upgrading FastAPI
# The current version doesn't fully support the lifespan feature
# @app.lifespan
# async def lifespan(app: FastAPI):
#     """
#     Lifespan context manager for startup and shutdown events.
#     """
#     # Startup event
#     logger.info(f"Starting {PROJECT_NAME} {VERSION}")
#
#     # Create upload directories
#     from src.core.config import UPLOAD_DIR, REPORTS_DIR, IMAGES_DIR, EXHIBITS_DIR
#     os.makedirs(UPLOAD_DIR, exist_ok=True)
#     os.makedirs(REPORTS_DIR, exist_ok=True)
#     os.makedirs(IMAGES_DIR, exist_ok=True)
#     os.makedirs(EXHIBITS_DIR, exist_ok=True)
#
#     logger.info("Application startup complete")
#
#     yield  # This is where the application runs
#
#     # Shutdown event
#     logger.info(f"Shutting down {PROJECT_NAME} {VERSION}")
#
#     # Unload all models
#     from src.inference.loader import model_loader
#     model_loader.unload_all_models()
#
#     logger.info("Application shutdown complete")

if __name__ == "__main__":
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
