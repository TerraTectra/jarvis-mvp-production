"""Tests for the code review models and storage layer."""
import os
import pytest
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Generator, Dict, Any, List, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session as DBSession

from ci.models import (
    ReviewTask,
    ReviewIssue,
    ReviewStatus,
    IssueSeverity,
    IssueType,
    PipelineContext,
    ReviewSummary
)
from ci.review_storage import (
    DBReviewTask, 
    DBReviewIssue, 
    DBPipelineContext, 
    ReviewStorage,
    Base,
    storage
)

@pytest.fixture
def sample_issue():
    """Create a sample review issue."""
    return ReviewIssue(
        file_path="src/main.py",
        line=10,
        column=5,
        message="Line too long",
        severity=IssueSeverity.WARNING,
        type=IssueType.STYLE,
        tool="flake8",
        code="E501",
        context={"snippet": "print('This is a very long line that exceeds the maximum allowed line length')"}
    )

@pytest.fixture
def sample_task():
    """Create a sample review task."""
    return ReviewTask(
        repository_path="/path/to/repo",
        branch="main",
        commit_hash="abc123",
        status=ReviewStatus.PENDING,
        created_at=datetime.utcnow(),
        summary=ReviewSummary(total_issues=1),
        issues=[]
    )

@pytest.fixture
def sample_pipeline_context():
    """Create a sample pipeline context."""
    return PipelineContext(
        pipeline_name="test-pipeline",
        trigger="push",
        branch="main",
        commit_hash="abc123",
        commit_message="Initial commit",
        commit_author="test@example.com",
        environment="test",
        variables={"ENV": "test"},
        artifacts=["build/report.html"]
    )

@pytest_asyncio.fixture(scope="module")
async def db_engine():
    """Create a SQLite in-memory database for testing."""
    from sqlalchemy.ext.asyncio import create_async_engine
    
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    try:
        yield engine
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()

@pytest.fixture
def db_session(db_engine):
    """Create a new database session for a test."""
    connection = db_engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()
    
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()

@pytest.fixture
def temp_db(db_session):
    """Create a ReviewStorage instance with a test database session."""
    # Clear any existing data
    for table in reversed(Base.metadata.sorted_tables):
        db_session.execute(table.delete())
    db_session.commit()
    
    # Create a new storage instance
    storage = ReviewStorage("sqlite:///:memory:")
    
    # Replace the session with our test session
    storage.SessionLocal = lambda: db_session
    
    # Make sure the tables exist
    Base.metadata.create_all(bind=db_session.bind)
    
    return storage

class TestModels:
    """Test the Pydantic models."""
    
    def test_review_issue_creation(self, sample_issue):
        """Test creating a review issue."""
        assert sample_issue.file_path == "src/main.py"
        assert sample_issue.line == 10
        assert sample_issue.severity == IssueSeverity.WARNING
        assert sample_issue.type == IssueType.STYLE
        assert sample_issue.code == "E501"
        
    def test_review_task_creation(self, sample_task):
        """Test creating a review task."""
        assert sample_task.repository_path == "/path/to/repo"
        assert sample_task.branch == "main"
        assert sample_task.status == ReviewStatus.PENDING
        assert isinstance(sample_task.created_at, datetime)
        
    def test_pipeline_context_creation(self, sample_pipeline_context):
        """Test creating a pipeline context."""
        assert sample_pipeline_context.pipeline_name == "test-pipeline"
        assert sample_pipeline_context.trigger == "push"
        assert sample_pipeline_context.environment == "test"
        assert "ENV" in sample_pipeline_context.variables

class TestReviewStorage:
    """Test the review storage layer."""
    
    def test_create_and_get_review_task(self, temp_db):
        """Test creating and retrieving a review task."""
        # Create a task with required fields
        task = temp_db.create_review_task(
            repository_path="/path/to/repo",
            branch="main",
            commit_hash="abc123",
            metadata={"test": "data"}
        )
        
        assert task is not None
        assert task.id is not None
        assert task.status == ReviewStatus.PENDING
        
        # Retrieve the task
        retrieved = temp_db.get_review_task(task.id)
        assert retrieved is not None
        assert retrieved.id == task.id
        assert retrieved.repository_path == "/path/to/repo"
        assert retrieved.branch == "main"
        
        # Verify the task exists in the database
        db = temp_db.SessionLocal()
        try:
            db_task = db.query(DBReviewTask).filter(DBReviewTask.id == task.id).first()
            assert db_task is not None
            assert db_task.repository_path == "/path/to/repo"
            assert db_task.branch == "main"
        finally:
            db.close()
        
    def test_update_review_task(self, temp_db):
        """Test updating a review task."""
        task = temp_db.create_review_task(
            repository_path="/path/to/repo",
            branch="main",
            commit_hash="abc123",
            metadata={"initial": "data"}
        )
        
        # Update the task
        updated = temp_db.update_review_task(
            task.id,
            status=ReviewStatus.COMPLETED,
            metadata={"duration": 42}
        )
        
        assert updated is not None
        assert updated.status == ReviewStatus.COMPLETED
        assert updated.metadata.get("duration") == 42
        # Verify the original metadata is preserved
        assert updated.metadata.get("initial") == "data"
        
    def test_add_issues_to_review(self, temp_db, sample_issue):
        """Test adding issues to a review."""
        task = temp_db.create_review_task(
            repository_path="/path/to/repo",
            branch="main",
            commit_hash="abc123",
            metadata={"test": "data"}
        )
        
        # Add issues
        success = temp_db.add_issues_to_review(task.id, [sample_issue])
        assert success is True
        
        # Retrieve the task with issues
        task_with_issues = temp_db.get_review_task(task.id)
        assert len(task_with_issues.issues) == 1
        assert task_with_issues.issues[0].message == "Line too long"
        
    def test_list_review_tasks(self, temp_db):
        """Test listing review tasks."""
        # Create some tasks with required fields
        for i in range(3):
            temp_db.create_review_task(
                repository_path=f"/path/to/repo/{i}",
                branch=f"branch-{i}",
                commit_hash=f"hash-{i}",
                metadata={"test": f"data-{i}"}
            )
        
        # List all tasks
        tasks = temp_db.list_review_tasks()
        assert len(tasks) == 3
        
        # Filter by status
        completed_task = temp_db.create_review_task(
            repository_path="/path/to/repo/completed",
            branch="main",
            commit_hash="completed-hash",
            metadata={"status": "completed"}
        )
        temp_db.update_review_task(completed_task.id, status=ReviewStatus.COMPLETED)
        
        completed_tasks = temp_db.list_review_tasks(status=ReviewStatus.COMPLETED)
        assert len(completed_tasks) == 1
        assert completed_tasks[0].status == ReviewStatus.COMPLETED
        
    def test_save_pipeline_context(self, temp_db, sample_pipeline_context):
        """Test saving pipeline context."""
        task = temp_db.create_review_task(
            repository_path="/path/to/repo",
            branch="main",
            commit_hash="abc123",
            metadata={"test": "data"}
        )
        
        # Save context
        success = temp_db.save_pipeline_context(task.id, sample_pipeline_context)
        assert success is True
        
        # Retrieve the task with context
        task_with_context = temp_db.get_review_task(task.id)
        assert task_with_context.pipeline_context is not None
        assert task_with_context.pipeline_context.pipeline_name == "test-pipeline"
        assert task_with_context.pipeline_context.trigger == "push"
        
    def test_delete_review_task(self, temp_db):
        """Test deleting a review task."""
        task = temp_db.create_review_task(
            repository_path="/path/to/repo",
            branch="main",
            commit_hash="abc123",
            metadata={"test": "data"}
        )
        
        # Delete the task
        success = temp_db.delete_review_task(task.id)
        assert success is True
        
        # Verify the task is deleted
        assert temp_db.get_review_task(task.id) is None

class TestDatabaseModels:
    """Test the SQLAlchemy database models."""
    
    def test_db_review_task_creation(self, temp_db):
        """Test creating a DBReviewTask."""
        task = DBReviewTask(
            id=str(uuid.uuid4()),
            repository_path="/path/to/repo",
            branch="main",
            status=ReviewStatus.PENDING,
            created_at=datetime.utcnow()
        )
        
        assert task is not None
        assert task.repository_path == "/path/to/repo"
        assert task.status == ReviewStatus.PENDING
        
    def test_db_review_issue_creation(self, temp_db):
        """Test creating a DBReviewIssue."""
        task = DBReviewTask(
            id=str(uuid.uuid4()),
            repository_path="/path/to/repo"
        )
        
        issue = DBReviewIssue(
            id=str(uuid.uuid4()),
            task_id=task.id,
            file_path="src/main.py",
            line=10,
            message="Test issue",
            severity=IssueSeverity.ERROR,
            type=IssueType.BUG,
            tool="pylint"
        )
        
        assert issue is not None
        assert issue.file_path == "src/main.py"
        assert issue.severity == IssueSeverity.ERROR
        
    def test_db_pipeline_context_creation(self, temp_db):
        """Test creating a DBPipelineContext."""
        task = DBReviewTask(
            id=str(uuid.uuid4()),
            repository_path="/path/to/repo"
        )
        
        context = DBPipelineContext(
            id=str(uuid.uuid4()),
            review_task_id=task.id,
            pipeline_name="test-pipeline",
            trigger="push",
            branch="main",
            commit_hash="abc123"
        )
        
        assert context is not None
        assert context.pipeline_name == "test-pipeline"
        assert context.trigger == "push"
