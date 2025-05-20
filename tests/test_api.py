import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

# Import the FastAPI app
import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.api import app

# Test client
client = TestClient(app)

def test_health_check():
    """Test the health check endpoint."""
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_root_endpoint():
    """Test the root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "version" in data
    assert "endpoints" in data

def test_get_orders():
    """Test the orders endpoint."""
    # Test with default parameters
    response = client.get("/orders")
    assert response.status_code == 200
    orders = response.json()
    assert isinstance(orders, list)
    
    # Test with limit parameter
    response = client.get("/orders?limit=2")
    assert response.status_code == 200
    assert len(response.json()) <= 2
    
    # Test with source parameter
    response = client.get("/orders?source=local")
    assert response.status_code == 200

@patch('src.api.fetch_kwork_orders')
async def test_get_kwork_orders(mock_fetch_kwork_orders):
    """Test fetching orders from Kwork."""
    # Mock the Kwork API response
    mock_orders = [
        {"id": "kwork1", "title": "Test Kwork Order 1"},
        {"id": "kwork2", "title": "Test Kwork Order 2"},
    ]
    mock_fetch_kwork_orders.return_value = mock_orders
    
    response = client.get("/orders?source=kwork")
    assert response.status_code == 200
    orders = response.json()
    assert len(orders) == 2
    assert orders[0]["source"] == "kwork"

def test_generate_reply():
    """Test the generate reply endpoint."""
    test_order = {
        "id": "test123",
        "title": "Test order for API testing",
        "source": "local",
        "send": False
    }
    
    response = client.post("/generate-reply", json=test_order)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "test123"
    assert "reply" in data
    assert data["source"] == "local"
    assert data["sent"] is False

def test_unauthorized_access():
    """Test unauthorized access to protected endpoints."""
    # This endpoint requires authentication
    response = client.get("/api/docs")
    assert response.status_code == 401  # Unauthorized

# Run the tests with: pytest tests/test_api.py -v
