"""
Модели базы данных для системы мониторинга.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from .session import Base

class Order(Base):
    """Модель заказа."""
    __tablename__ = "orders"

    id = Column(String, primary_key=True, index=True)
    title = Column(String, nullable=False)
    category = Column(String, nullable=True)
    budget = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    source = Column(String, nullable=False, default="kwork")
    url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Связи
    replies = relationship("Reply", back_populates="order", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Order(id='{self.id}', title='{self.title}')>"


class Reply(Base):
    """Модель отклика на заказ."""
    __tablename__ = "replies"
    
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    message = Column(Text, nullable=False)
    sent = Column(Boolean, default=False, nullable=False)
    status = Column(String(50), default="pending", nullable=False)  # pending, sent, error
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Связи
    order = relationship("Order", back_populates="replies")
    
    def __repr__(self):
        status = f"{self.status.upper()}"
        if self.error_message:
            status += f" ({self.error_message[:20]}...)"
        return f"<Reply(order_id='{self.order_id}', status='{status}')>"


class SystemLog(Base):
    """Модель для системных логов."""
    __tablename__ = "system_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    level = Column(String(20), nullable=False)  # INFO, WARNING, ERROR, CRITICAL
    message = Column(Text, nullable=False)
    source = Column(String(50), nullable=True)  # Модуль-источник
    details = Column(Text, nullable=True)  # Дополнительные данные в JSON
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<SystemLog({self.level}): {self.message[:50]}>"
