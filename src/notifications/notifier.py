"""
Модуль для работы с уведомлениями.
"""
import os
import logging
from enum import Enum
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from src.notifications.telegram import Bot

# Настройка логирования
logger = logging.getLogger(__name__)

class NotificationLevel(str, Enum):
    """Уровни важности уведомлений."""
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

@dataclass
class Notification:
    """Класс уведомления."""
    message: str
    level: NotificationLevel = NotificationLevel.INFO
    title: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    
    @property
    def formatted_message(self) -> str:
        """Возвращает отформатированное сообщение с префиксом уровня."""
        level_emojis = {
            NotificationLevel.INFO: "ℹ️",
            NotificationLevel.SUCCESS: "✅",
            NotificationLevel.WARNING: "⚠️",
            NotificationLevel.ERROR: "❌",
            NotificationLevel.CRITICAL: "🔥"
        }
        
        emoji = level_emojis.get(self.level, "")
        title = f"*{self.title}*\n\n" if self.title else ""
        return f"{emoji} {title}{self.message}"

class BaseNotifier:
    """Базовый класс для отправки уведомлений."""
    
    async def send(self, notification: Notification) -> bool:
        """Отправляет уведомление."""
        raise NotImplementedError
    
    async def send_message(
        self,
        message: str,
        level: NotificationLevel = NotificationLevel.INFO,
        title: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Отправляет текстовое уведомление."""
        notification = Notification(
            message=message,
            level=level,
            title=title,
            data=data or {}
        )
        return await self.send(notification)

class LoggingNotifier(BaseNotifier):
    """Отправляет уведомления в лог."""
    
    def __init__(self):
        self.logger = logging.getLogger("notifications")
    
    async def send(self, notification: Notification) -> bool:
        """Логирует уведомление."""
        log_level = {
            NotificationLevel.INFO: self.logger.info,
            NotificationLevel.SUCCESS: self.logger.info,
            NotificationLevel.WARNING: self.logger.warning,
            NotificationLevel.ERROR: self.logger.error,
            NotificationLevel.CRITICAL: self.logger.critical
        }.get(notification.level, self.logger.info)
        
        log_level(f"{notification.title or 'Notification'}: {notification.message}")
        return True

class TelegramNotifier(BaseNotifier):
    """Отправляет уведомления в Telegram."""
    
    def __init__(self, token: str, chat_ids: List[int]):
        self.bot = Bot(token=token)
        self.chat_ids = chat_ids
    
    async def send(self, notification: Notification) -> bool:
        """Отправляет уведомление в Telegram."""
        if not self.chat_ids:
            logger.warning("Не указаны chat_ids для отправки уведомлений")
            return False
        
        success = True
        message = notification.formatted_message
        
        for chat_id in self.chat_ids:
            try:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode="Markdown",
                    disable_web_page_preview=True
                )
            except Exception as e:
                logger.error(f"Ошибка при отправке уведомления в чат {chat_id}: {e}")
                success = False
        
        return success

class NotificationManager:
    """Менеджер уведомлений."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._initialized = True
        self.notifiers: List[BaseNotifier] = []
        self.enabled = os.getenv("NOTIFICATIONS_ENABLED", "true").lower() == "true"
        
        if not self.enabled:
            logger.info("Уведомления отключены в настройках")
            return
        
        # Инициализируем нотификаторы в зависимости от настроек
        notification_mode = os.getenv("NOTIFICATION_MODE", "telegram").lower()
        
        # Всегда добавляем логирование
        self.notifiers.append(LoggingNotifier())
        
        # Добавляем Telegram, если включен
        if notification_mode == "telegram" and os.getenv("TELEGRAM_NOTIFICATIONS_ENABLED", "true").lower() == "true":
            token = os.getenv("TELEGRAM_TOKEN")
            admin_ids = [int(id_str) for id_str in os.getenv("TELEGRAM_ADMIN_ID", "").split(",") if id_str.strip().isdigit()]
            
            if token and admin_ids:
                self.notifiers.append(TelegramNotifier(token, admin_ids))
                logger.info("Telegram нотификатор инициализирован")
            else:
                logger.warning("Не удалось инициализировать Telegram нотификатор: отсутствует токен или chat_ids")
    
    async def notify(self, notification: Notification) -> bool:
        """Отправляет уведомление через все активные нотификаторы."""
        if not self.enabled:
            return False
        
        results = []
        for notifier in self.notifiers:
            try:
                result = await notifier.send(notification)
                results.append(result)
            except Exception as e:
                logger.error(f"Ошибка при отправке уведомления через {notifier.__class__.__name__}: {e}")
                results.append(False)
        
        return any(results)
    
    async def send_message(
        self,
        message: str,
        level: NotificationLevel = NotificationLevel.INFO,
        title: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Отправляет текстовое уведомление."""
        notification = Notification(
            message=message,
            level=level,
            title=title,
            data=data or {}
        )
        return await self.notify(notification)

# Глобальный экземпляр менеджера
_notification_manager = None

async def get_notifier() -> NotificationManager:
    """Возвращает экземпляр менеджера уведомлений."""
    global _notification_manager
    if _notification_manager is None:
        _notification_manager = NotificationManager()
    return _notification_manager
