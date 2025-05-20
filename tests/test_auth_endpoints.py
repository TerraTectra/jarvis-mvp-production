"""
Test cases for authentication endpoints including negative test scenarios.
"""
import os
import sys
import time
import pytest
from fastapi.testclient import TestClient
from jose import jwt
from datetime import datetime, timedelta

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the FastAPI app and config
from src.api import app
from src.config import Settings

# Test configuration
TEST_SETTINGS = Settings()

# Test credentials
TEST_USERNAME = "testuser"
TEST_PASSWORD = "testpass"
INVALID_USERNAME = "nonexistent"
INVALID_PASSWORD = "wrongpassword"

# Test user data
TEST_USER = {
    "username": TEST_USERNAME,
    "password": TEST_PASSWORD,
    "email": "test@example.com"
}

# Test tokens
TEST_TOKENS = {}

@pytest.fixture(scope="module")
def test_user():
    """Create a test user and return user data."""
    return TEST_USER

@pytest.fixture(scope="module")
def auth_tokens(test_client, test_user):
    """Get authentication tokens for the test user."""
    # Register test user
    response = test_client.post(
        "/api/auth/register",
        json=test_user
    )
    
    # Get tokens
    response = test_client.post(
        "/api/auth/token",
        data={
            "username": test_user["username"],
            "password": test_user["password"],
            "grant_type": "password"
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    
    assert response.status_code == 200
    tokens = response.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens
    assert tokens["token_type"] == "bearer"
    
    return tokens

def test_register_user(test_client, test_user):
    """Test user registration."""
    # Test successful registration
    response = test_client.post(
        "/api/auth/register",
        json=test_user
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert data["username"] == test_user["username"]
    assert data["email"] == test_user["email"]
    assert "hashed_password" not in data  # Password should not be returned

def test_login_success(test_client, test_user, auth_tokens):
    """Test successful login with valid credentials."""
    # Test login with valid credentials
    response = test_client.post(
        "/api/auth/token",
        data={
            "username": test_user["username"],
            "password": test_user["password"],
            "grant_type": "password"
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    
    # Save tokens for other tests
    TEST_TOKENS["access"] = data["access_token"]
    TEST_TOKENS["refresh"] = data["refresh_token"]

def test_login_invalid_username(test_client):
    """Test login with non-existent username."""
    response = test_client.post(
        "/api/auth/token",
        data={
            "username": INVALID_USERNAME,
            "password": "anypassword",
            "grant_type": "password"
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    
    assert response.status_code == 401
    assert "Incorrect username or password" in response.json()["detail"]

def test_login_invalid_password(test_client, test_user):
    """Test login with incorrect password."""
    response = test_client.post(
        "/api/auth/token",
        data={
            "username": test_user["username"],
            "password": INVALID_PASSWORD,
            "grant_type": "password"
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    
    assert response.status_code == 401
    assert "Incorrect username or password" in response.json()["detail"]

def test_protected_endpoint_without_token(test_client):
    """Test accessing a protected endpoint without a token."""
    response = test_client.get("/api/orders")
    assert response.status_code == 401
    assert "Not authenticated" in response.json()["detail"]

def test_protected_endpoint_with_invalid_token(test_client):
    """Test accessing a protected endpoint with an invalid token."""
    response = test_client.get(
        "/api/orders",
        headers={"Authorization": "Bearer invalid_token_here"}
    )
    assert response.status_code == 401
    assert "Could not validate credentials" in response.json()["detail"]

def test_refresh_token_success(test_client, auth_tokens):
    """Test refreshing an access token with a valid refresh token."""
    refresh_token = auth_tokens["refresh_token"]
    
    response = test_client.post(
        "/api/auth/refresh",
        json={"refresh_token": refresh_token}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    
    # Verify the new access token works
    access_token = data["access_token"]
    response = test_client.get(
        "/api/users/me",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200

def test_refresh_token_invalid(test_client):
    """Test refreshing an access token with an invalid refresh token."""
    response = test_client.post(
        "/api/auth/refresh",
        json={"refresh_token": "invalid_refresh_token"}
    )
    
    assert response.status_code == 401
    assert "Invalid refresh token" in response.json()["detail"]

def test_expired_token(test_client, test_user):
    """Test accessing a protected endpoint with an expired token."""
    # Create an expired token
    expired_token = jwt.encode(
        {
            "sub": test_user["username"],
            "exp": datetime.utcnow() - timedelta(minutes=5),
            "type": "access"
        },
        TEST_SETTINGS.SECRET_KEY,
        algorithm=TEST_SETTINGS.ALGORITHM
    )
    
    response = test_client.get(
        "/api/orders",
        headers={"Authorization": f"Bearer {expired_token}"}
    )
    
    assert response.status_code == 401
    assert "Token has expired" in response.json()["detail"]

def test_invalid_token_signature(test_client, test_user):
    """Test accessing a protected endpoint with a token with an invalid signature."""
    # Create a token with a different secret key
    invalid_token = jwt.encode(
        {"sub": test_user["username"], "type": "access"},
        "wrong_secret_key",
        algorithm=TEST_SETTINGS.ALGORITHM
    )
    
    response = test_client.get(
        "/api/orders",
        headers={"Authorization": f"Bearer {invalid_token}"}
    )
    
    assert response.status_code == 401
    assert "Signature verification failed" in response.json()["detail"]

# Run the tests with: pytest tests/test_auth_endpoints.py -v
