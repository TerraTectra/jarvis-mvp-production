"""Database models for the code review system."""
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field
from uuid import uuid4, UUID

class ReviewStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

class IssueSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class IssueType(str, Enum):
    STYLE = "style"
    TYPE = "type"
    SECURITY = "security"
    BUG = "bug"
    PERFORMANCE = "performance"

class ReviewIssue(BaseModel):
    """Model representing a single issue found during code review."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    file_path: str
    line: int
    column: int = 0
    message: str
    severity: IssueSeverity = IssueSeverity.INFO
    type: IssueType
    tool: str  # flake8, mypy, bandit, etc.
    code: Optional[str] = None  # Error code (e.g., E501)
    context: Optional[Dict[str, Any]] = None

class ReviewSummary(BaseModel):
    """Summary of a code review."""
    total_issues: int = 0
    issues_by_severity: Dict[IssueSeverity, int] = Field(
        default_factory=lambda: {s: 0 for s in IssueSeverity}
    )
    issues_by_type: Dict[IssueType, int] = Field(
        default_factory=lambda: {t: 0 for t in IssueType}
    )

class PipelineContext(BaseModel):
    """Context for the CI/CD pipeline."""
    pipeline_id: str = Field(default_factory=lambda: str(uuid4()))
    pipeline_name: str
    trigger: str  # push, pr, manual, etc.
    trigger_user: Optional[str] = None
    branch: str
    commit_hash: str
    commit_message: Optional[str] = None
    commit_author: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    environment: str = "development"
    variables: Dict[str, str] = Field(default_factory=dict)
    artifacts: List[str] = Field(default_factory=list)

class ReviewTask(BaseModel):
    """Model representing a code review task."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    repository_path: str
    branch: Optional[str] = None
    commit_hash: Optional[str] = None
    status: ReviewStatus = ReviewStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    summary: ReviewSummary = Field(default_factory=ReviewSummary)
    issues: List[ReviewIssue] = Field(default_factory=list)
    pipeline_context: Optional[PipelineContext] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
