import os
import pytest
from fastapi.testclient import TestClient
from src.api import app

# Test client
client = TestClient(app)

# Test token for authentication
UI_ADMIN_TOKEN = os.getenv("UI_ADMIN_TOKEN", "test_token")

def test_unauthorized_access():
    """Test that unauthorized access to protected pages redirects to login."""
    # Test root path
    response = client.get("/", allow_redirects=False)
    assert response.status_code == 307  # Should redirect to /login
    assert "/login" in response.headers["Location"]
    
    # Test form page
    response = client.get("/form", allow_redirects=False)
    assert response.status_code == 307  # Should redirect to /login
    assert "/login" in response.headers["Location"]

def test_login_page():
    """Test that login page is accessible without authentication."""
    response = client.get("/login")
    assert response.status_code == 200
    assert "Вход в панель управления" in response.text

def test_successful_login():
    """Test successful login with valid token."""
    # First, ensure we're logged out
    client.cookies.clear()
    
    # Submit login form with valid token
    response = client.post(
        "/login",
        data={"token": UI_ADMIN_TOKEN},
        allow_redirects=False
    )
    
    # Should redirect to root with a cookie set
    assert response.status_code == 303
    assert response.headers["Location"] == "/"
    assert "ui_token" in response.cookies
    
    # Now we should be able to access protected pages
    response = client.get("/", allow_redirects=False)
    assert response.status_code == 200
    assert "Генератор откликов" in response.text

def test_invalid_login():
    """Test login with invalid token."""
    response = client.post(
        "/login",
        data={"token": "invalid_token"},
        allow_redirects=False
    )
    
    # Should stay on login page with error
    assert response.status_code == 401
    assert "Неверный токен доступа" in response.text

def test_logout():
    """Test logout functionality."""
    # First login
    client.post("/login", data={"token": UI_ADMIN_TOKEN})
    
    # Now logout
    response = client.get("/logout", allow_redirects=False)
    
    # Should redirect to login page and clear cookie
    assert response.status_code == 307
    assert response.headers["Location"] == "/login"
    assert "ui_token" not in client.cookies
    
    # Should not be able to access protected pages
    response = client.get("/", allow_redirects=False)
    assert response.status_code == 307
    assert "/login" in response.headers["Location"]

# Run the tests
if __name__ == "__main__":
    pytest.main(["-v", __file__])
