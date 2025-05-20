"""
Database models for Kwork integration.
"""
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects import sqlite

# Use JSONB for PostgreSQL, JSON for SQLite
JSON_COLUMN = JSONB().with_variant(JSON(), sqlite.dialect.name)

from src.database.session import Base

class KworkOrder(Base):
    """Model for storing Kwork orders."""
    __tablename__ = "kwork_orders"
    
    id = Column(String, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    price = Column(JSON_COLUMN, nullable=True)  # Store price as JSON: {"amount": 1000, "currency": "RUB"}
    category = Column(String, nullable=True)
    status = Column(String, nullable=True)
    views = Column(Integer, default=0)
    replies_count = Column(Integer, default=0)
    published_at = Column(DateTime, nullable=True)
    
    # Additional fields from Kwork API
    raw_data = Column(JSON_COLUMN, nullable=True)  # Store complete API response
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    replies = relationship("KworkReply", back_populates="order", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<KworkOrder(id='{self.id}', title='{self.title}')>"


class KworkReply(Base):
    """Model for storing our replies to Kwork orders."""
    __tablename__ = "kwork_replies"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String, ForeignKey("kwork_orders.id", ondelete="CASCADE"), nullable=False)
    message = Column(Text, nullable=False)
    price = Column(Float, nullable=True)
    days = Column(Integer, nullable=True)
    status = Column(String, default="pending")  # pending, sent, error
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    order = relationship("KworkOrder", back_populates="replies")
    
    def __repr__(self):
        return f"<KworkReply(order_id='{self.order_id}', status='{self.status}')>"


class KworkFilter(Base):
    """Model for storing Kwork order filters."""
    __tablename__ = "kwork_filters"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    keywords = Column(JSON_COLUMN, nullable=True)  # List of keywords to include/exclude
    categories = Column(JSON_COLUMN, nullable=True)  # List of category IDs
    min_price = Column(Float, nullable=True)
    max_price = Column(Float, nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<KworkFilter(id={self.id}, name='{self.name}')>"
