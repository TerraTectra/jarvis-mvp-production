"""
CRUD-операции для работы с базой данных.
"""
from datetime import datetime
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any

from . import models

def log_system_event(
    db: Session,
    level: str,
    message: str,
    source: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
) -> models.SystemLog:
    """Логирует системное событие."""
    log = models.SystemLog(
        level=level.upper(),
        message=message,
        source=source,
        details=str(details) if details else None
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log

def get_order(db: Session, order_id: str) -> Optional[models.Order]:
    """Получает заказ по ID."""
    return db.query(models.Order).filter(models.Order.id == order_id).first()

def create_or_update_order(db: Session, order_data: Dict[str, Any]) -> models.Order:
    """Создает или обновляет заказ."""
    order = get_order(db, order_data["id"])
    
    if order:
        # Обновляем существующий заказ
        for key, value in order_data.items():
            setattr(order, key, value)
        order.updated_at = datetime.utcnow()
    else:
        # Создаем новый заказ
        order = models.Order(**order_data)
        db.add(order)
    
    db.commit()
    db.refresh(order)
    return order

def create_reply(
    db: Session,
    order_id: str,
    message: str,
    sent: bool = False,
    status: str = "pending",
    error_message: Optional[str] = None
) -> models.Reply:
    """Создает запись об отклике."""
    reply = models.Reply(
        order_id=order_id,
        message=message,
        sent=sent,
        status=status,
        error_message=error_message
    )
    db.add(reply)
    db.commit()
    db.refresh(reply)
    return reply

def get_recent_orders(
    db: Session,
    limit: int = 10,
    source: Optional[str] = None
) -> List[models.Order]:
    """Получает последние заказы."""
    query = db.query(models.Order).order_by(models.Order.created_at.desc())
    
    if source:
        query = query.filter(models.Order.source == source)
    
    return query.limit(limit).all()

def get_order_replies(
    db: Session,
    order_id: str,
    limit: int = 10
) -> List[models.Reply]:
    """Получает историю откликов по заказу."""
    return (
        db.query(models.Reply)
        .filter(models.Reply.order_id == order_id)
        .order_by(models.Reply.created_at.desc())
        .limit(limit)
        .all()
    )

def get_stats(
    db: Session,
    days: int = 7
) -> Dict[str, Any]:
    """Получает статистику за указанный период."""
    from sqlalchemy import func, and_
    from datetime import datetime, timedelta
    
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Общее количество заказов
    total_orders = db.query(func.count(models.Order.id)).scalar()
    
    # Количество заказов за период
    recent_orders = (
        db.query(func.count(models.Order.id))
        .filter(models.Order.created_at >= start_date)
        .scalar()
    )
    
    # Количество отправленных откликов
    sent_replies = (
        db.query(func.count(models.Reply.id))
        .filter(models.Reply.sent == True)  # noqa
        .scalar()
    )
    
    # Количество ошибок
    errors = (
        db.query(func.count(models.SystemLog.id))
        .filter(models.SystemLog.level == "ERROR")
        .filter(models.SystemLog.created_at >= start_date)
        .scalar()
    )
    
    return {
        "total_orders": total_orders or 0,
        "recent_orders": recent_orders or 0,
        "sent_replies": sent_replies or 0,
        "errors_last_days": errors or 0,
        "period_days": days
    }
