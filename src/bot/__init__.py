"""
Модуль для работы с Telegram-ботом.
"""
import logging
import sys
from typing import Optional, List, Dict, Any, Callable, Awaitable, Union

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Add console handler if no handlers are present
if not logger.handlers:
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console.setFormatter(formatter)
    logger.addHandler(console)

logger.debug("Initializing Telegram bot module...")

try:
    from aiogram import Dispatcher
    from . import handlers
    from .telegram_bot import (
        run_bot as _run_bot,
        start,
        get_status,
        get_orders,
        get_logs,
        send_notification as _send_notification,
        setup_handlers as _setup_telegram_handlers,
        error_handler
    )
    
    # Re-export the functions
    run_bot = _run_bot
    send_notification = _send_notification
    
    def setup_handlers(dp: Dispatcher) -> None:
        """Set up all bot handlers."""
        # Register command handlers from handlers.py
        handlers.register_handlers(dp)
        
        # Setup any additional handlers from telegram_bot.py
        _setup_telegram_handlers(dp)
    
    TELEGRAM_AVAILABLE = True
    
    __all__ = [
        'run_bot',
        'start',
        'get_status',
        'get_orders',
        'get_logs',
        'send_notification',
        'setup_handlers',
        'error_handler',
        'TELEGRAM_AVAILABLE'
    ]
    
except ImportError as e:
    logger.warning(f"Telegram bot is not available: {e}")
    
    # Create dummy functions for when Telegram is not available
    async def dummy_async(*args, **kwargs):
        logger.warning("Telegram bot is not available. This is a dummy function.")
        return False
        
    def dummy_sync(*args, **kwargs):
        logger.warning("Telegram bot is not available. This is a dummy function.")
        return False
    
    # Assign dummy functions
    run_bot = dummy_async
    start = dummy_async
    get_status = dummy_async
    get_orders = dummy_async
    get_logs = dummy_async
    send_notification = dummy_async
    error_handler = dummy_sync
    
    def setup_handlers(*args, **kwargs):
        return dummy_sync(*args, **kwargs)
    
    TELEGRAM_AVAILABLE = False
    
    __all__ = [
        'run_bot',
        'start',
        'get_status',
        'get_orders',
        'get_logs',
        'send_notification',
        'setup_handlers',
        'error_handler',
        'TELEGRAM_AVAILABLE'
    ]
