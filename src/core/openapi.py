"""
Custom OpenAPI schema generator for the application.
"""
from typing import Any, Dict

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi
from pydantic_core._pydantic_core import PydanticSerializationError

from src.core.logging_config import get_logger

logger = get_logger(__name__)

def custom_openapi(app: FastAPI) -> Dict[str, Any]:
    """
    Custom OpenAPI schema generator that handles serialization of class types
    and excludes internal endpoints from the documentation.

    Args:
        app: The FastAPI application.

    Returns:
        The OpenAPI schema.
    """
    if app.openapi_schema:
        return app.openapi_schema

    # Define endpoints to hide from documentation
    hidden_paths = [
        "/openapi.json",
        "/docs",
        "/docs/oauth2-redirect",
        "/redoc"
    ]

    # Filter routes to exclude hidden paths
    filtered_routes = [
        route for route in app.routes
        if not hasattr(route, "path") or route.path not in hidden_paths
    ]

    try:
        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=filtered_routes,
            tags=app.openapi_tags,
            servers=app.servers,
        )

        app.openapi_schema = openapi_schema
        return app.openapi_schema
    except PydanticSerializationError as e:
        logger.error(f"Error generating OpenAPI schema: {str(e)}")

        # Create a simplified schema as fallback
        openapi_schema = {
            "openapi": "3.0.2",
            "info": {
                "title": app.title,
                "version": app.version,
                "description": app.description + "\n\n**Note: Full API schema could not be generated due to serialization issues.**"
            },
            "paths": {},
            "components": {
                "schemas": {}
            }
        }

        # Add basic path information, excluding hidden paths
        for route in filtered_routes:
            if hasattr(route, "path") and hasattr(route, "methods"):
                path = route.path
                for method in route.methods:
                    method = method.lower()
                    if path not in openapi_schema["paths"]:
                        openapi_schema["paths"][path] = {}

                    # Add basic operation info
                    operation = {}
                    if hasattr(route, "name") and route.name:
                        operation["summary"] = route.name

                    # Add operation to path
                    openapi_schema["paths"][path][method] = operation

        app.openapi_schema = openapi_schema
        return app.openapi_schema
