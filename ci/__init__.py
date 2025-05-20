"""
Jarvis CI/CD - A comprehensive CI/CD solution with built-in code review and analytics.

This package provides:
- Automated CI/CD pipeline execution
- Code quality analysis and reporting
- Authentication and authorization
- Web-based dashboard for monitoring
- API endpoints for integration
"""

__version__ = "1.0.0"

# Import key components for easier access
from .auth import (
    User,
    UserInDB,
    Token,
    authenticate_user,
    create_access_token,
    create_refresh_token,
    get_current_user,
    get_password_hash,
)
from .review_engine import CodeReviewer
from .review_api import init_review_api
from .review_storage import ReviewStorage
from .models import (
    ReviewTask,
    ReviewIssue,
    ReviewStatus,
    IssueSeverity,
    IssueType,
    PipelineContext,
    ReviewSummary
)

# Version of the package
__version__ = "0.1.0"

__all__ = [
    'CodeReviewer',
    'ReviewStorage',
    'ReviewTask',
    'ReviewIssue',
    'ReviewStatus',
    'IssueSeverity',
    'IssueType',
    'PipelineContext',
    'ReviewSummary',
    'init_review_api'
]
