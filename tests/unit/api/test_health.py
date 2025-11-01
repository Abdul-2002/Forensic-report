"""
Tests for the health check endpoints.
"""
import pytest
from fastapi.testclient import TestClient

from src.core.config import VERSION

def test_health_check(client: TestClient):
    """
    Test the basic health check endpoint.
    """
    response = client.get("/app/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == VERSION
