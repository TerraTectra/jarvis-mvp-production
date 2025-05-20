"""Tests for the authentication system."""
import pytest
from datetime import timedelta
from fastapi import HTTPException, status

from ci.auth import (
    User,
    Token,
    TokenData,
    authenticate_user,
    create_access_token,
    get_current_user,
    get_current_active_user,
    RoleChecker,
    get_token
)

# Test data
TEST_USER = {
    "username": "testuser",
    "hashed_password": "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW",  # 'secret'
    "scopes": ["read:items", "write:items"],
    "disabled": False
}

class TestAuthentication:
    """Test authentication functions."""
    
    def test_authenticate_user_success(self, monkeypatch):
        """Test successful user authentication."""
        def mock_get_user(db, username):
            if username == "testuser":
                return TEST_USER
            return None
        
        monkeypatch.setattr("ci.auth.get_user", mock_get_user)
        
        user = authenticate_user({}, "testuser", "secret")
        assert user is not None
        assert user.username == "testuser"
        assert "read:items" in user.scopes
        
    def test_authenticate_user_invalid_password(self, monkeypatch):
        """Test authentication with invalid password."""
        def mock_get_user(db, username):
            if username == "testuser":
                return TEST_USER
            return None
            
        monkeypatch.setattr("ci.auth.get_user", mock_get_user)
        
        user = authenticate_user({}, "testuser", "wrongpassword")
        assert user is None
        
    def test_authenticate_user_nonexistent(self, monkeypatch):
        """Test authentication with non-existent user."""
        def mock_get_user(db, username):
            return None
            
        monkeypatch.setattr("ci.auth.get_user", mock_get_user)
        
        user = authenticate_user({}, "nonexistent", "password")
        assert user is None
        
    def test_create_access_token(self):
        """Test creating an access token."""
        token_data = {"sub": "testuser", "scopes": ["read:items"]}
        token = create_access_token(token_data)
        assert isinstance(token, str)
        assert len(token) > 0
        
    def test_get_token_success(self, monkeypatch):
        """Test getting a token with valid credentials."""
        def mock_authenticate_user(db, username, password):
            if username == "testuser" and password == "secret":
                return User(**TEST_USER)
            return None
            
        monkeypatch.setattr("ci.auth.authenticate_user", mock_authenticate_user)
        
        token = get_token("testuser", "secret")
        assert token is not None
        assert hasattr(token, "access_token")
        assert token.token_type == "bearer"
        
    def test_get_token_invalid_credentials(self, monkeypatch):
        """Test getting a token with invalid credentials."""
        def mock_authenticate_user(db, username, password):
            return None
            
        monkeypatch.setattr("ci.auth.authenticate_user", mock_authenticate_user)
        
        token = get_token("testuser", "wrongpassword")
        assert token is None

class TestCurrentUser:
    """Test current user dependency."""
    
    def test_get_current_user_success(self, monkeypatch):
        """Test getting current user with valid token."""
        # Create a valid token
        token_data = {"sub": "testuser", "scopes": ["read:items"]}
        token = create_access_token(token_data)
        
        # Mock the token validation
        def mock_oauth2_scheme(token: str = None):
            return token
            
        monkeypatch.setattr("ci.auth.oauth2_scheme", mock_oauth2_scheme)
        
        # Mock the user lookup
        def mock_get_user(db, username):
            if username == "testuser":
                return TEST_USER
            return None
            
        monkeypatch.setattr("ci.auth.get_user", mock_get_user)
        
        user = get_current_user(token)
        assert user is not None
        assert user.username == "testuser"
        
    def test_get_current_user_invalid_token(self, monkeypatch):
        """Test getting current user with invalid token."""
        with pytest.raises(HTTPException) as exc_info:
            get_current_user("invalid.token.here")
            
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        
    def test_get_current_active_user(self, monkeypatch):
        """Test getting current active user."""
        # Create an active user
        active_user = User(
            username="active",
            scopes=["read:items"],
            disabled=False
        )
        
        # Should return the user
        assert get_current_active_user(active_user) == active_user
        
        # Create a disabled user
        disabled_user = User(
            username="disabled",
            scopes=["read:items"],
            disabled=True
        )
        
        # Should raise an exception
        with pytest.raises(HTTPException) as exc_info:
            get_current_active_user(disabled_user)
            
        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

class TestRoleChecker:
    """Test role-based access control."""
    
    def test_role_checker_success(self):
        """Test role checker with user having required scope."""
        user = User(
            username="testuser",
            scopes=["read:items", "write:items"],
            disabled=False
        )
        
        # User has required scope
        checker = RoleChecker(["read:items"])
        assert checker(user) is True
        
    def test_role_checker_missing_scope(self):
        """Test role checker with user missing required scope."""
        user = User(
            username="testuser",
            scopes=["read:items"],
            disabled=False
        )
        
        # User is missing required scope
        checker = RoleChecker(["write:items"])
        with pytest.raises(HTTPException) as exc_info:
            checker(user)
            
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Missing required scope" in str(exc_info.value.detail)
