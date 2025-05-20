"""Database models for Kwork projects."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON, ForeignKey
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import relationship

from .session import Base

class KworkProject(Base):
    """Model for storing Kwork projects."""
    __tablename__ = "kwork_projects"
    
    id = Column(Integer, primary_key=True, index=True)
    kwork_id = Column(String, unique=True, index=True, nullable=False)
    title = Column(String, nullable=False)
    url = Column(String, nullable=False, unique=True)
    category = Column(String, nullable=True)
    price = Column(String, nullable=True)
    date_posted = Column(DateTime, nullable=True)
    description = Column(Text, nullable=True)
    raw_data = Column(JSON, nullable=True)  # Store complete raw data
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_scraped_at = Column(DateTime, nullable=True)
    
    # Status flags
    is_active = Column(Boolean, default=True, nullable=False)
    is_processed = Column(Boolean, default=False, nullable=False)
    
    # Relationships
    snapshots = relationship("ProjectSnapshot", back_populates="project", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<KworkProject(id={self.id}, kwork_id='{self.kwork_id}', title='{self.title}')>"


class ProjectSnapshot(Base):
    """Model for storing historical snapshots of project data."""
    __tablename__ = "project_snapshots"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("kwork_projects.id", ondelete="CASCADE"), nullable=False)
    
    # Snapshot data
    price = Column(String, nullable=True)
    status = Column(String, nullable=True)
    raw_data = Column(JSON, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    project = relationship("KworkProject", back_populates="snapshots")
    
    def __repr__(self):
        return f"<ProjectSnapshot(id={self.id}, project_id={self.project_id}, created_at={self.created_at})>"


class ScrapeSession(Base):
    """Model for tracking scraping sessions."""
    __tablename__ = "scrape_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    start_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    end_time = Column(DateTime, nullable=True)
    status = Column(String(20), default="running", nullable=False)  # running, completed, failed
    pages_scraped = Column(Integer, default=0, nullable=False)
    projects_found = Column(Integer, default=0, nullable=False)
    new_projects = Column(Integer, default=0, nullable=False)
    errors_encountered = Column(Integer, default=0, nullable=False)
    
    # Configuration
    max_pages = Column(Integer, nullable=True)
    filters = Column(JSON, nullable=True)
    
    # Error tracking
    last_error = Column(Text, nullable=True)
    
    def __repr__(self):
        status = f"{self.status.upper()}"
        if self.last_error:
            status += f" (ERROR: {self.last_error[:50]}...)"
        return f"<ScrapeSession(id={self.id}, status='{status}')>"
