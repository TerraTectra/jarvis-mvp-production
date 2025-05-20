"""Pytest configuration and fixtures for review tests."""
import os
import sys
import pytest
import tempfile
import shutil
from pathlib import Path
from typing import Generator, Dict, Any
from unittest.mock import MagicMock, patch

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Test configuration
TEST_DB_URL = "sqlite:///:memory:"

@pytest.fixture(scope="session", autouse=True)
def set_test_environment():
    """Set up test environment variables."""
    os.environ["ENV"] = "test"
    os.environ["DATABASE_URL"] = TEST_DB_URL
    os.environ["JWT_SECRET_KEY"] = "test-secret-key"
    os.environ["JWT_ALGORITHM"] = "HS256"
    os.environ["JWT_ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"

@pytest.fixture(scope="module")
def temp_db() -> Generator[str, None, None]:
    """Create a temporary database for testing."""
    from ci.review_storage import Base, storage
    
    # Create all tables
    Base.metadata.create_all(bind=storage.engine)
    
    try:
        yield storage
    finally:
        # Clean up
        Base.metadata.drop_all(bind=storage.engine)

@pytest.fixture
def test_client():
    """Create a test client for the FastAPI application."""
    from ci.review_api import app
    from fastapi.testclient import TestClient
    
    with TestClient(app) as client:
        yield client

@pytest.fixture
def authenticated_client(test_client):
    """Return an authenticated test client."""
    from ci.auth import create_access_token
    
    token = create_access_token(
        data={"sub": "testuser", "scopes": ["reviews:read", "reviews:write"]}
    )
    test_client.headers.update({"Authorization": f"Bearer {token}"})
    return test_client

@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for testing."""
    temp_dir = tempfile.mkdtemp()
    try:
        yield Path(temp_dir)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

@pytest.fixture
def sample_review_task() -> Dict[str, Any]:
    """Return sample review task data."""
    return {
        "id": "test-task-123",
        "repository_path": "/path/to/repo",
        "branch": "main",
        "commit_hash": "abc123",
        "status": "pending",
        "created_at": "2023-01-01T00:00:00Z"
    }

@pytest.fixture
def mock_telegram():
    """Mock the Telegram notification function."""
    with patch("ci.review_api.send_telegram_notification") as mock:
        mock.return_value = {"status": "success"}
        yield mock

def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers",
        "slow: mark test as slow to run"
    )
    config.addinivalue_line(
        "markers",
        "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers",
        "requires_db: mark test as requiring database access"
    )
