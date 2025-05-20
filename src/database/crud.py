"""
CRUD-операции для работы с базой данных.
"""
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

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

async def get_stats(
    db: AsyncSession,
    days: int = 7
) -> Dict[str, Any]:
    """Получает статистику за указанный период."""
    from sqlalchemy import func, select, and_, or_
    from datetime import datetime, timedelta
    
    async def _get_count(q):
        result = await db.execute(select(func.count()).select_from(q.subquery()))
        return result.scalar() or 0
    
    # Рассчитываем дату начала периода
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Получаем общее количество пользователей
    total_users = await _get_count(select(models.User.id))
    
    # Получаем общее количество заказов
    total_orders = await _get_count(select(models.Order.id))
    
    # Получаем количество отправленных откликов
    total_replies = await _get_count(select(models.Reply.id))
    
    # Получаем количество успешных и неудачных откликов
    successful_replies = await _get_count(
        select(models.Reply.id).where(models.Reply.status == 'success')
    )
    
    failed_replies = await _get_count(
        select(models.Reply.id).where(models.Reply.status == 'error')
    )
    
    # Получаем время последней проверки
    last_check_log = await db.execute(
        select(models.SystemLog)
        .where(models.SystemLog.message.like('%проверка завершена%'))
        .order_by(models.SystemLog.created_at.desc())
        .limit(1)
    )
    last_check_log = last_check_log.scalar_one_or_none()
    
    last_check = last_check_log.created_at.strftime('%d.%m.%Y %H:%M:%S') if last_check_log else 'никогда'
    
    return {
        'total_users': total_users,
        'total_orders': total_orders,
        'total_replies': total_replies,
        'successful_replies': successful_replies,
        'failed_replies': failed_replies,
        'last_check': last_check,
        'period_days': days
    }
