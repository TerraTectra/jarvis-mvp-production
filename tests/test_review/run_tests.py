"""Test runner for the code review tests."""
import os
import sys
import pytest
from pathlib import Path

def run_tests():
    """Run the tests with the correct configuration."""
    # Add the project root to the Python path
    project_root = str(Path(__file__).parent.parent.parent)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    # Set up test environment variables
    os.environ["ENV"] = "test"
    os.environ["DATABASE_URL"] = "sqlite:///:memory:"
    os.environ["JWT_SECRET_KEY"] = "test-secret-key"
    os.environ["JWT_ALGORITHM"] = "HS256"
    os.environ["JWT_ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"
    
    # Run pytest programmatically
    test_dir = str(Path(__file__).parent)
    return pytest.main([
        test_dir,
        "-v",
        "--tb=short",
        "--disable-warnings",
        "-p", "no:warnings",
    ])

if __name__ == "__main__":
    sys.exit(run_tests())
