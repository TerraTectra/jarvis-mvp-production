"""
Telegram-бот для уведомлений и управления Jarvis MVP.
"""
import os
import logging
from datetime import datetime
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackContext,
    CallbackQueryHandler
)
from telegram.constants import ParseMode

from database import SessionLocal
from database.crud import get_stats, get_recent_orders, get_order_replies, log_system_event

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Загрузка конфигурации
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_IDS = [int(id_str) for id_str in os.getenv("TELEGRAM_ADMIN_ID", "").split(",") if id_str.strip().isdigit()]

if not TELEGRAM_TOKEN or not ADMIN_IDS:
    raise ValueError("Не заданы TELEGRAM_TOKEN или TELEGRAM_ADMIN_ID в .env файле")

# Утилиты для форматирования
def format_order(order) -> str:
    """Форматирует заказ для отображения в Telegram."""
    return (
        f"📝 *{order.title}*\n"
        f"🆔 `{order.id}`\n"
        f"💼 {order.category or 'Без категории'}\n"
        f"💰 {order.budget or 'Не указан'}\n"
        f"📅 {order.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        f"🔗 [Открыть заказ]({order.url or '#'})\n"
    )

def format_reply(reply) -> str:
    """Форматирует отклик для отображения в Telegram."""
    status_emoji = "✅" if reply.sent else "❌"
    return (
        f"{status_emoji} *Отклик*\n"
        f"🆔 `{reply.id}`\n"
        f"📅 {reply.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        f"📝 {reply.message[:50]}..."
    )

# Обработчики команд
async def start(update: Update, context: CallbackContext) -> None:
    """Обработчик команды /start."""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Доступ запрещен.")
        return
    
    await update.message.reply_text(
        "🤖 *Jarvis MVP Bot*\n\n"
        "Доступные команды:\n"
        "/start - Показать это сообщение\n"
        "/status - Статус системы\n"
        "/orders - Последние заказы\n"
        "/logs - Последние логи\n"
        "\nБот будет присылать уведомления о новых заказах и результатах отправки откликов.",
        parse_mode=ParseMode.MARKDOWN
    )

async def get_status(update: Update, context: CallbackContext) -> None:
    """Обработчик команды /status."""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Доступ запрещен.")
        return
    
    with SessionLocal() as db:
        stats = get_stats(db)
        
    message = (
        "📊 *Статус системы*\n\n"
        f"📝 Всего заказов: *{stats['total_orders']}*\n"
        f"📨 Отправлено откликов: *{stats['sent_replies']}*\n"
        f"🔥 Новых заказов (за {stats['period_days']} дн.): *{stats['recent_orders']}*\n"
        f"⚠️ Ошибок: *{stats['errors_last_days']}*\n"
        f"\n🔄 Последняя проверка: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )
    
    await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)

async def get_orders(update: Update, context: CallbackContext) -> None:
    """Обработчик команды /orders."""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Доступ запрещен.")
        return
    
    limit = 5
    if context.args and context.args[0].isdigit():
        limit = min(int(context.args[0]), 10)  # Не более 10 заказов
    
    with SessionLocal() as db:
        orders = get_recent_orders(db, limit=limit)
    
    if not orders:
        await update.message.reply_text("📭 Список заказов пуст.")
        return
    
    for order in orders:
        # Получаем последний отклик по заказу
        with SessionLocal() as db:
            replies = get_order_replies(db, order.id, limit=1)
        
        reply_status = ""
        if replies:
            reply_status = "\n\n" + format_reply(replies[0])
        
        await update.message.reply_text(
            format_order(order) + reply_status,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True
        )

async def get_logs(update: Update, context: CallbackContext) -> None:
    """Обработчик команды /logs."""
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ Доступ запрещен.")
        return
    
    limit = 10
    if context.args and context.args[0].isdigit():
        limit = min(int(context.args[0]), 20)  # Не более 20 логов
    
    # В реальном приложении здесь был бы запрос к логам
    # Для примера просто вернем сообщение
    await update.message.reply_text(
        f"📜 Последние {limit} записей лога:\n\n"
        "(Здесь будут логи приложения)",
        parse_mode=ParseMode.MARKDOWN
    )

# Уведомления
async def send_notification(chat_id: int, message: str, parse_mode: Optional[str] = None) -> bool:
    """Отправляет уведомление указанному пользователю."""
    try:
        if chat_id not in ADMIN_IDS:
            logger.warning(f"Попытка отправить уведомление неавторизованному пользователю: {chat_id}")
            return False
            
        await context.bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode=parse_mode or ParseMode.MARKDOWN
        )
        return True
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления: {e}")
        return False

# Инициализация бота
def setup_handlers(application: Application) -> None:
    """Настройка обработчиков команд."""
    # Команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", get_status))
    application.add_handler(CommandHandler("orders", get_orders))
    application.add_handler(CommandHandler("logs", get_logs))
    
    # Обработка ошибок
    application.add_error_handler(error_handler)

async def error_handler(update: object, context: CallbackContext) -> None:
    """Обработчик ошибок бота."""
    logger.error(f"Ошибка при обработке обновления: {context.error}", exc_info=context.error)
    
    # Логируем ошибку в базу
    with SessionLocal() as db:
        log_system_event(
            db=db,
            level="ERROR",
            message=f"Ошибка в боте: {context.error}",
            source="telegram_bot",
            details={
                "update": str(update),
                "error": str(context.error)
            }
        )
    
    # Уведомляем админов
    error_message = (
        "⚠️ *Ошибка в боте*\n\n"
        f"```\n{context.error}\n```"
    )
    
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=error_message,
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление об ошибке: {e}")

def run_bot() -> None:
    """Запускает бота."""
    # Создаем приложение
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Настраиваем обработчики
    setup_handlers(application)
    
    # Запускаем бота
    logger.info("Бот запущен")
    application.run_polling()

if __name__ == "__main__":
    run_bot()
