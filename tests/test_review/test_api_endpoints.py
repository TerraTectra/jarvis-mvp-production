"""Tests for the code review API endpoints."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import json

from ci.review_api import app, router
from ci.models import ReviewStatus, ReviewTask, ReviewSummary
from ci.auth import create_access_token, User

# Test client
client = TestClient(app)

# Test data
TEST_USER = User(
    username="testuser",
    scopes=["reviews:read", "reviews:write"],
    disabled=False
)

def get_test_token():
    """Generate a test JWT token."""
    token_data = {
        "sub": TEST_USER.username,
        "scopes": TEST_USER.scopes
    }
    return create_access_token(token_data)

@pytest.fixture
def authenticated_client():
    """Return a test client with authentication."""
    token = get_test_token()
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client

class TestReviewEndpoints:
    """Test the review API endpoints."""
    
    @patch("ci.review_api.storage")
    def test_trigger_review(self, mock_storage, authenticated_client):
        """Test triggering a new code review."""
        # Mock the storage
        mock_task = ReviewTask(
            id="test-id",
            repository_path="/path/to/repo",
            branch="main",
            status=ReviewStatus.PENDING,
            created_at=datetime.utcnow(),
            summary=ReviewSummary(total_issues=0)
        )
        mock_storage.create_review_task.return_value = mock_task
        
        # Make the request
        response = authenticated_client.post(
            "/ci/api/review/trigger",
            json={"path": "/path/to/repo", "branch": "main"}
        )
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "test-id"
        assert data["status"] == "started"
        
        # Verify the task was created
        mock_storage.create_review_task.assert_called_once_with(
            repository_path="/path/to/repo",
            branch="main",
            commit_hash=None,
            metadata={"triggered_by": "testuser"}
        )
    
    @patch("ci.review_api.storage")
    def test_get_review_status(self, mock_storage, authenticated_client):
        """Test getting the status of a review."""
        # Mock the storage
        mock_task = ReviewTask(
            id="test-id",
            repository_path="/path/to/repo",
            status=ReviewStatus.COMPLETED,
            created_at=datetime.utcnow(),
            summary=ReviewSummary(total_issues=3)
        )
        mock_storage.get_review_task.return_value = mock_task
        
        # Make the request
        response = authenticated_client.get("/ci/api/review/test-id")
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "test-id"
        assert data["status"] == "completed"
        assert data["summary"]["total_issues"] == 3
        
        # Verify the task was retrieved
        mock_storage.get_review_task.assert_called_once_with("test-id")
    
    @patch("ci.review_api.storage")
    def test_get_review_status_not_found(self, mock_storage, authenticated_client):
        """Test getting status of a non-existent review."""
        # Mock the storage to return None
        mock_storage.get_review_task.return_value = None
        
        # Make the request
        response = authenticated_client.get("/ci/api/review/nonexistent")
        
        # Assertions
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    @patch("ci.review_api.storage")
    def test_get_review_report(self, mock_storage, authenticated_client):
        """Test getting a full review report."""
        # Mock the storage
        mock_task = ReviewTask(
            id="test-id",
            repository_path="/path/to/repo",
            status=ReviewStatus.COMPLETED,
            created_at=datetime.utcnow(),
            summary=ReviewSummary(total_issues=3),
            issues=[
                {
                    "id": "issue-1",
                    "file_path": "src/main.py",
                    "line": 10,
                    "message": "Test issue",
                    "severity": "error",
                    "type": "bug"
                }
            ]
        )
        mock_storage.get_review_task.return_value = mock_task
        
        # Make the request
        response = authenticated_client.get("/ci/api/review/test-id/report")
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "test-id"
        assert data["status"] == "completed"
        assert len(data["issues"]) == 1
        assert data["issues"][0]["id"] == "issue-1"
    
    @patch("ci.review_api.storage")
    @patch("ci.review_api.send_telegram_notification")
    def test_send_telegram_notification(self, mock_send, mock_storage, authenticated_client):
        """Test sending a Telegram notification for a review."""
        # Mock the storage
        mock_task = ReviewTask(
            id="test-id",
            repository_path="/path/to/repo",
            branch="main",
            commit_hash="abc123",
            status=ReviewStatus.COMPLETED,
            created_at=datetime.utcnow(),
            summary=ReviewSummary(total_issues=3),
            issues=[
                {"severity": "error", "type": "bug"},
                {"severity": "warning", "type": "style"},
                {"severity": "info", "type": "style"}
            ]
        )
        mock_storage.get_review_task.return_value = mock_task
        
        # Mock the Telegram sender
        mock_send.return_value = {"status": "success"}
        
        # Make the request
        response = authenticated_client.get("/ci/api/review/test-id/telegram")
        
        # Assertions
        assert response.status_code == 200
        assert response.json()["notification_sent"] is True
        
        # Verify the notification was sent
        mock_send.assert_called_once()
        
        # Check the notification content
        args, _ = mock_send.call_args
        assert "🔍 Code Review Completed" in args[0]  # Notification title
        assert "3 issues found" in args[1]  # Notification message

class TestAuthentication:
    """Test authentication and authorization."""
    
    def test_unauthenticated_access(self):
        """Test accessing protected endpoints without authentication."""
        # Create a client without authentication
        client = TestClient(app)
        
        # Try to access a protected endpoint
        response = client.get("/ci/api/review/test-id")
        
        # Should return 401 Unauthorized
        assert response.status_code == 401
        assert "Not authenticated" in response.json()["detail"]
    
    def test_insufficient_permissions(self, authenticated_client):
        """Test accessing an endpoint without the required permissions."""
        # Mock the RoleChecker to require admin scope
        with patch("ci.review_api.RoleChecker") as mock_checker:
            # Configure the mock to raise an exception
            mock_checker.return_value = MagicMock(side_effect=HTTPException(
                status_code=403,
                detail="Insufficient permissions"
            ))
            
            # Try to access the endpoint
            response = authenticated_client.get("/ci/api/review/test-id")
            
            # Should return 403 Forbidden
            assert response.status_code == 403
            assert "Insufficient permissions" in response.json()["detail"]
    
    def test_token_validation(self):
        """Test token validation."""
        # Create a client with an invalid token
        client = TestClient(app)
        client.headers.update({"Authorization": "Bearer invalid.token.here"})
        
        # Try to access a protected endpoint
        response = client.get("/ci/api/review/test-id")
        
        # Should return 401 Unauthorized
        assert response.status_code == 401
        assert "Invalid token" in response.json()["detail"]
