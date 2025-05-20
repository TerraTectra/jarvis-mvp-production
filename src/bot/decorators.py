"""
Декораторы для обработчиков бота.
"""
import traceback
from functools import wraps
from typing import Callable, Any, Coroutine, TypeVar, Optional

from telegram import Update
from telegram.ext import ContextTypes
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from src.database.session import async_session_factory
from src.bot.telegram_bot import send_notification
import logging

logger = logging.getLogger(__name__)

# Type variables for better type hints
T = TypeVar('T')
HandlerFunc = Callable[..., Coroutine[Any, Any, T]]
DecoratedHandler = Callable[..., Coroutine[Any, Any, T]]

def with_session(handler: HandlerFunc) -> DecoratedHandler:
    """
    Декоратор, предоставляющий сессию базы данных обработчику.
    Управляет жизненным циклом сессии и обработкой ошибок.
    
    Args:
        handler: Асинхронная функция-обработчик
        
    Returns:
        Обернутый обработчик с управлением сессией
    """
    @wraps(handler)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs) -> Any:
        session = None
        try:
            async with async_session_factory() as session:
                # Передаем сессию как именованный аргумент, если она не передана
                if 'session' not in kwargs:
                    kwargs['session'] = session
                
                result = await handler(update, context, *args, **kwargs)
                await session.commit()
                return result
                
        except SQLAlchemyError as e:
            error_msg = f"Database error in {handler.__name__}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            if session:
                await session.rollback()
            await _notify_error(update, context, error_msg, traceback.format_exc())
            
        except Exception as e:
            error_msg = f"Unexpected error in {handler.__name__}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            await _notify_error(update, context, error_msg, traceback.format_exc())
            
        finally:
            if session:
                await session.close()
    
    return wrapper

async def _notify_error(
    update: Update, 
    context: ContextTypes.DEFAULT_TYPE, 
    error_msg: str, 
    trace: str
) -> None:
    """Отправляет уведомление об ошибке администратору с трассировкой."""
    try:
        chat_id = update.effective_chat.id if update.effective_chat else None
        user_id = update.effective_user.id if update.effective_user else None
        
        error_details = (
            f"🚨 *Ошибка в боте*\n"
            f"• Ошибка: `{error_msg}`\n"
            f"• Чат: `{chat_id}`\n"
            f"• Пользователь: `{user_id}`"
        )
        
        # Отправляем краткое сообщение об ошибке пользователю
        if update.effective_message:
            await update.effective_message.reply_text(
                "❌ Произошла ошибка. Администратор уведомлен."
            )
        
        # Отправляем полную ошибку администратору
        admin_id = context.bot_data.get('admin_id')
        if admin_id:
            # Сначала отправляем основную информацию об ошибке
            await send_notification(admin_id, error_details, parse_mode='Markdown')
            # Затем отправляем трассировку, если она не слишком длинная
            if len(trace) < 4000:
                await send_notification(admin_id, f'```\n{trace}\n```', parse_mode='Markdown')
                
    except Exception as e:
        logger.error(f"Error in _notify_error: {e}", exc_info=True)

def admin_required(handler: HandlerFunc) -> DecoratedHandler:
    """
    Декоратор для проверки прав администратора.
    
    Args:
        handler: Обработчик команды бота
        
    Returns:
        Обернутый обработчик с проверкой прав
    """
    @wraps(handler)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs) -> Any:
        # Проверяем, что сообщение пришло от пользователя
        if not update.effective_user:
            logger.warning("Message has no effective user")
            return
            
        user_id = update.effective_user.id
        admin_ids = context.bot_data.get('admin_ids', set())
        
        # Проверяем, что пользователь является администратором
        if user_id not in admin_ids:
            logger.warning(f"Unauthorized access attempt from user {user_id}")
            
            # Отправляем сообщение об ошибке, если это сообщение в личном чате
            if update.effective_chat and update.effective_chat.type == 'private':
                await update.message.reply_text("❌ У вас нет прав для выполнения этой команды.")
            return
            
        # Если пользователь администратор, вызываем обработчик
        return await handler(update, context, *args, **kwargs)
    
    return wrapper
