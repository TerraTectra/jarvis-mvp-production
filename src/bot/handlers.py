"""
Telegram bot command handlers."""
import logging
from typing import List, Optional

from telegram import Update
from telegram.ext import CommandHandler, CallbackContext
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import SystemLog
from src.kwork.models import KworkOrder
from .decorators import admin_required, with_session

# Configure logging
logger = logging.getLogger(__name__)

def register_handlers(application):
    """Register all command handlers."""
    # Register admin commands
    application.add_handler(CommandHandler("orders", admin_required(with_session(cmd_orders))))
    application.add_handler(CommandHandler("logs", admin_required(with_session(cmd_logs))))
    
    # Register other commands here
    # application.add_handler(CommandHandler("status", with_session(cmd_status)))

@with_session
@admin_required
async def cmd_orders(update: Update, context: CallbackContext, session: AsyncSession) -> None:
    """
    Обработчик команды /orders.
    Получает и отображает последние заказы.
    
    Args:
        update: Объект обновления Telegram
        context: Контекст бота
        session: Сессия базы данных
    """
    message = update.message
    if not message:
        logger.warning("Empty message in cmd_orders")
        return
    
    logger.info(f"Processing /orders command from user {message.from_user.id}")
    
    # Получаем количество заказов из аргументов или используем значение по умолчанию
    limit = 5
    if context.args and context.args[0].isdigit():
        limit = min(int(context.args[0]), 20)  # Ограничиваем максимальное количество
    
    logger.debug(f"Fetching {limit} latest orders...")
    result = await session.execute(
        select(KworkOrder)
        .order_by(desc(KworkOrder.created_at))
        .limit(limit)
    )
    orders = result.scalars().all()
    
    if not orders:
        logger.info("No orders found in the database")
        await message.reply_text("📭 Заказы не найдены.")
        return
    
    # Формируем ответ
    orders_text = []
    for order in orders:
        order_info = f"• {order.id}"
        if hasattr(order, 'title') and order.title:
            order_info += f" — {order.title}"
        if hasattr(order, 'created_at') and order.created_at:
            order_info += f" ({order.created_at.strftime('%Y-%m-%d %H:%M')})"
        orders_text.append(order_info)
    
    response = "📋 Последние заказы:\n\n" + "\n\n".join(orders_text)
    await message.reply_text(response, parse_mode=None)

@with_session
@admin_required
async def cmd_logs(update: Update, context: CallbackContext, session: AsyncSession) -> None:
    """
    Обработчик команды /logs.
    Получает и отображает последние системные логи.
    
    Args:
        update: Объект обновления Telegram
        context: Контекст бота
        session: Сессия базы данных
    """
    message = update.message
    if not message:
        logger.warning("Empty message in cmd_logs")
        return
    
    logger.info(f"Processing /logs command from user {message.from_user.id}")
    
    # Получаем количество логов из аргументов или используем значение по умолчанию
    limit = 10
    if context.args and context.args[0].isdigit():
        limit = min(int(context.args[0]), 50)  # Ограничиваем максимальное количество
    
    # Получаем уровень логирования, если указан
    log_level = None
    if context.args and len(context.args) > 1:
        log_level = context.args[1].upper()
    
    logger.debug(f"Fetching {limit} recent logs (level: {log_level or 'ALL'})...")
    
    # Строим запрос с фильтрацией по уровню, если указан
    query = select(SystemLog).order_by(desc(SystemLog.created_at)).limit(limit)
    if log_level:
        query = query.where(SystemLog.level == log_level.lower())
    
    result = await session.execute(query)
    logs = result.scalars().all()
    
    if not logs:
        await message.reply_text("📭 Логи не найдены.")
        return
    
    # Формируем ответ
    text_lines = []
    for log in logs:
        timestamp = log.created_at.strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"[{timestamp}] [{log.level.upper()}]"
        
        # Добавляем источник, если он есть
        if hasattr(log, 'source') and log.source:
            log_entry += f" {log.source}:"
        else:
            log_entry += ":"
        
        # Добавляем сообщение
        log_entry += f" {log.message}"
        
        # Добавляем детали, если они есть
        details = getattr(log, 'details', None)
        if details:
            details = str(details)
            log_entry += f"\n  Details: {details}"
        
        text_lines.append(log_entry)
    
    # Формируем ответ с заголовком
    response = "📜 Последние логи:" + (f" (уровень: {log_level})" if log_level else "") + "\n\n"
    response += "\n\n".join(text_lines)
    
    # Ограничиваем длину сообщения
    if len(response) > 4096:
        response = response[:4093] + '...'
    
    await message.reply_text(response, parse_mode=None)
