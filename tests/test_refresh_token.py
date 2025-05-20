"""
Tests for JWT refresh token functionality.
"""
import os
import sys
import time
import pytest
from fastapi.testclient import TestClient
from jose import jwt

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the FastAPI app
from src.api import app
from ci.auth import SECRET_KEY, ALGORITHM, TOKEN_TYPE_ACCESS, TOKEN_TYPE_REFRESH

# Test client
client = TestClient(app)

# Test credentials
TEST_USERNAME = "testuser"
TEST_PASSWORD = "testpassword"

# Mock user for testing
mock_user = {
    "username": TEST_USERNAME,
    "hashed_password": "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",  # 'secret'
    "scopes": ["test:read"],
}

@pytest.fixture(scope="module")
def test_user():
    """Fixture to provide a test user."""
    return mock_user

@pytest.fixture(scope="module")
def access_token(test_user):
    """Fixture to provide a valid access token."""
    # Create a test token that expires in 1 minute
    token_data = {
        "sub": test_user["username"],
        "scopes": test_user["scopes"],
        "type": TOKEN_TYPE_ACCESS,
    }
    return jwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)

@pytest.fixture(scope="module")
def refresh_token(test_user):
    """Fixture to provide a valid refresh token."""
    # Create a test refresh token that expires in 7 days
    token_data = {
        "sub": test_user["username"],
        "type": TOKEN_TYPE_REFRESH,
    }
    return jwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)

def test_refresh_token_success(test_user, refresh_token):
    """Test successful token refresh."""
    response = client.post(
        "/api/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    
    # Verify the new access token
    token_data = jwt.decode(
        data["access_token"], 
        SECRET_KEY, 
        algorithms=[ALGORITHM]
    )
    assert token_data["sub"] == test_user["username"]
    assert token_data["type"] == TOKEN_TYPE_ACCESS
    
    # Verify the new refresh token
    refresh_data = jwt.decode(
        data["refresh_token"], 
        SECRET_KEY, 
        algorithms=[ALGORITHM]
    )
    assert refresh_data["sub"] == test_user["username"]
    assert refresh_data["type"] == TOKEN_TYPE_REFRESH

def test_refresh_token_invalid():
    """Test refresh with invalid token."""
    response = client.post(
        "/api/auth/refresh",
        json={"refresh_token": "invalid_token"},
    )
    
    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate credentials"

def test_refresh_token_wrong_type(test_user):
    """Test refresh with access token instead of refresh token."""
    # Create an access token but try to use it as refresh token
    token_data = {
        "sub": test_user["username"],
        "scopes": test_user["scopes"],
        "type": TOKEN_TYPE_ACCESS,  # Wrong type
    }
    wrong_token = jwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)
    
    response = client.post(
        "/api/auth/refresh",
        json={"refresh_token": wrong_token},
    )
    
    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate credentials"

def test_refresh_token_expired():
    """Test refresh with expired token."""
    # Create an expired refresh token
    expired_token = jwt.encode(
        {
            "sub": "testuser",
            "type": TOKEN_TYPE_REFRESH,
            "exp": 1,  # Expired in 1970
        },
        SECRET_KEY,
        algorithm=ALGORITHM
    )
    
    response = client.post(
        "/api/auth/refresh",
        json={"refresh_token": expired_token},
    )
    
    assert response.status_code == 401
    assert "Token expired" in response.json()["detail"]
