"""
Database storage layer for the code review system using SQLAlchemy.
"""

import os
import json
import sqlite3
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import logging

from sqlalchemy import create_engine, Column, String, Integer, DateTime, Boolean, JSON, Enum, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session as DBSession

from .models import (
    ReviewTask,
    ReviewIssue,
    ReviewStatus,
    IssueSeverity,
    IssueType,
    PipelineContext,
    ReviewSummary
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# SQLAlchemy setup
Base = declarative_base()

class DBReviewTask(Base):
    """Database model for review tasks."""
    __tablename__ = 'review_tasks'

    id = Column(String(36), primary_key=True, index=True)
    repository_path = Column(String(512), nullable=False)
    branch = Column(String(256))
    commit_hash = Column(String(64))
    status = Column(Enum(ReviewStatus), default=ReviewStatus.PENDING)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    metadata_ = Column('metadata', JSON, default=dict)

    # Relationships
    issues = relationship("DBReviewIssue", back_populates="task", cascade="all, delete-orphan")
    pipeline_context = relationship("DBPipelineContext", back_populates="review_task", uselist=False)

class DBReviewIssue(Base):
    """Database model for review issues."""
    __tablename__ = 'review_issues'

    id = Column(String(36), primary_key=True, index=True)
    task_id = Column(String(36), ForeignKey('review_tasks.id', ondelete='CASCADE'))
    file_path = Column(String(512), nullable=False)
    line = Column(Integer, nullable=False)
    column = Column(Integer, default=0)
    message = Column(Text, nullable=False)
    severity = Column(Enum(IssueSeverity), default=IssueSeverity.INFO)
    type = Column(Enum(IssueType), nullable=False)
    tool = Column(String(50), nullable=False)
    code = Column(String(50), nullable=True)
    context = Column(JSON, default=dict)

    # Relationships
    task = relationship("DBReviewTask", back_populates="issues")

class DBPipelineContext(Base):
    """Database model for pipeline context."""
    __tablename__ = 'pipeline_contexts'

    id = Column(String(36), primary_key=True, index=True)
    review_task_id = Column(String(36), ForeignKey('review_tasks.id', ondelete='CASCADE'))
    pipeline_name = Column(String(256), nullable=False)
    trigger = Column(String(50), nullable=False)
    trigger_user = Column(String(256))
    branch = Column(String(256), nullable=False)
    commit_hash = Column(String(64), nullable=False)
    commit_message = Column(Text)
    commit_author = Column(String(256))
    timestamp = Column(DateTime, default=datetime.utcnow)
    environment = Column(String(50), default="development")
    variables = Column(JSON, default=dict)
    artifacts = Column(JSON, default=list)

    # Relationships
    review_task = relationship("DBReviewTask", back_populates="pipeline_context")

class ReviewStorage:
    """Storage layer for the code review system using SQLite."""

    def __init__(self, db_url: str = None):
        """Initialize the storage with a database URL."""
        if db_url is None:
            # Default to a file in the current working directory
            db_path = Path("reviews.db")
            db_url = f"sqlite:///{db_path.absolute()}"

        self.engine = create_engine(db_url, connect_args={"check_same_thread": False})
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

        # Create tables if they don't exist
        Base.metadata.create_all(bind=self.engine)

    def _to_review_task_model(self, db_task: DBReviewTask) -> ReviewTask:
        """Convert a database model to a Pydantic model."""
        if db_task is None:
            return None

        # Convert pipeline context if it exists
        pipeline_context = None
        if db_task.pipeline_context is not None:
            pipeline_context = PipelineContext(
                id=db_task.pipeline_context.id,
                pipeline_name=db_task.pipeline_context.pipeline_name,
                trigger=db_task.pipeline_context.trigger,
                trigger_user=db_task.pipeline_context.trigger_user,
                branch=db_task.pipeline_context.branch,
                commit_hash=db_task.pipeline_context.commit_hash,
                commit_message=db_task.pipeline_context.commit_message,
                commit_author=db_task.pipeline_context.commit_author,
                timestamp=db_task.pipeline_context.timestamp,
                environment=db_task.pipeline_context.environment,
                variables=db_task.pipeline_context.variables,
                artifacts=db_task.pipeline_context.artifacts
            )

        return ReviewTask(
            id=db_task.id,
            repository_path=db_task.repository_path,
            branch=db_task.branch,
            commit_hash=db_task.commit_hash,
            status=db_task.status,
            created_at=db_task.created_at,
            started_at=db_task.started_at,
            completed_at=db_task.completed_at,
            metadata=db_task.metadata_,
            summary=ReviewSummary(),  # Will be populated from issues
            pipeline_context=pipeline_context,
            issues=[
                ReviewIssue(
                    id=issue.id,
                    file_path=issue.file_path,
                    line=issue.line,
                    column=issue.column,
                    message=issue.message,
                    severity=issue.severity,
                    type=issue.type,
                    tool=issue.tool,
                    code=issue.code,
                    context=issue.context
                ) for issue in db_task.issues
            ]
        )

    def create_review_task(
        self,
        repository_path: str,
        branch: Optional[str] = None,
        commit_hash: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ReviewTask:
        """Create a new review task."""
        db = self.SessionLocal()
        try:
            # Generate a UUID for the task ID
            task_id = str(uuid.uuid4())
            
            db_task = DBReviewTask(
                id=task_id,
                repository_path=repository_path,
                branch=branch,
                commit_hash=commit_hash,
                status=ReviewStatus.PENDING,
                metadata_=metadata or {}
            )
            db.add(db_task)
            db.commit()
            db.refresh(db_task)
            return self._to_review_task_model(db_task)
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create review task: {e}")
            raise
        finally:
            db.close()

    def get_review_task(self, task_id: str) -> Optional[ReviewTask]:
        """Get a review task by ID."""
        db = self.SessionLocal()
        try:
            db_task = db.query(DBReviewTask).filter(DBReviewTask.id == task_id).first()
            return self._to_review_task_model(db_task)
        finally:
            db.close()

    def update_review_task(
        self,
        task_id: str,
        status: Optional[ReviewStatus] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[ReviewTask]:
        """Update a review task."""
        db = self.SessionLocal()
        try:
            db_task = db.query(DBReviewTask).filter(DBReviewTask.id == task_id).first()
            if not db_task:
                return None

            if status is not None:
                db_task.status = status
            if started_at is not None:
                db_task.started_at = started_at
            if completed_at is not None:
                db_task.completed_at = completed_at
            if metadata is not None:
                # Create a new dictionary with the existing metadata and update it with the new metadata
                db_task.metadata_ = {**db_task.metadata_, **metadata}

            db.commit()
            db.refresh(db_task)
            return self._to_review_task_model(db_task)
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to update review task {task_id}: {e}")
            raise
        finally:
            db.close()

    def add_issues_to_review(
        self,
        task_id: str,
        issues: List[ReviewIssue]
    ) -> bool:
        """Add issues to a review task."""
        db = self.SessionLocal()
        try:
            db_task = db.query(DBReviewTask).filter(DBReviewTask.id == task_id).first()
            if not db_task:
                return False

            for issue in issues:
                db_issue = DBReviewIssue(
                    id=issue.id,
                    task_id=task_id,
                    file_path=issue.file_path,
                    line=issue.line,
                    column=issue.column or 0,
                    message=issue.message,
                    severity=issue.severity,
                    type=issue.type,
                    tool=issue.tool,
                    code=issue.code,
                    context=issue.context or {}
                )
                db.add(db_issue)

            db.commit()
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to add issues to review {task_id}: {e}")
            return False
        finally:
            db.close()

    def list_review_tasks(
        self,
        status: Optional[ReviewStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[ReviewTask]:
        """List review tasks with optional filtering."""
        db = self.SessionLocal()
        try:
            query = db.query(DBReviewTask)

            if status is not None:
                query = query.filter(DBReviewTask.status == status)

            query = query.order_by(DBReviewTask.created_at.desc())

            if limit > 0:
                query = query.limit(limit).offset(offset)

            return [self._to_review_task_model(task) for task in query.all()]
        finally:
            db.close()

    def delete_review_task(self, task_id: str) -> bool:
        """Delete a review task and all its issues."""
        db = self.SessionLocal()
        try:
            db_task = db.query(DBReviewTask).filter(DBReviewTask.id == task_id).first()
            if not db_task:
                return False

            db.delete(db_task)
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to delete review task {task_id}: {e}")
            return False
        finally:
            db.close()

    def save_pipeline_context(
        self,
        review_task_id: str,
        context: PipelineContext
    ) -> bool:
        """Save pipeline context for a review task."""
        db = self.SessionLocal()
        try:
            # Delete existing context if it exists
            db.query(DBPipelineContext).filter(
                DBPipelineContext.review_task_id == review_task_id
            ).delete()

            db_context = DBPipelineContext(
                id=context.pipeline_id,  # Use pipeline_id as the ID
                review_task_id=review_task_id,
                pipeline_name=context.pipeline_name,
                trigger=context.trigger,
                trigger_user=context.trigger_user,
                branch=context.branch,
                commit_hash=context.commit_hash,
                commit_message=context.commit_message,
                commit_author=context.commit_author,
                timestamp=context.timestamp,
                environment=context.environment,
                variables=context.variables,
                artifacts=context.artifacts
            )
            db.add(db_context)
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to save pipeline context for task {review_task_id}: {e}")
            return False
        finally:
            db.close()

# Singleton instance
storage = ReviewStorage()
