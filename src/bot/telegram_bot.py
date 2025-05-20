"""
Telegram-бот для уведомлений и управления Jarvis MVP.
"""
import asyncio
import os
import logging
import nest_asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Union
from pathlib import Path

# Загружаем переменные окружения
from dotenv import load_dotenv

# Импорты SQLAlchemy
from sqlalchemy import select, desc, func, text
from sqlalchemy.ext.asyncio import AsyncSession

# Импорты Telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackContext,
    CallbackQueryHandler,
    ContextTypes,
)
from telegram.constants import ParseMode

# Импорты приложения
from src.database.models import SystemLog, Order, Reply, User
from src.database.session import async_session_factory
from src.bot.decorators import admin_required, with_session

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Загружаем .env файл из корня проекта
env_path = Path(__file__).parent.parent.parent / '.env'
if env_path.exists():
    load_dotenv(env_path)
    logger.info(f"✅ Загружены переменные окружения из {env_path}")
else:
    logger.warning(f"⚠️ Файл .env не найден по пути {env_path}. Используются системные переменные окружения.")

# Применяем патч для вложенных циклов событий
nest_asyncio.apply()

# Загрузка конфигурации
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_IDS = [int(id_str) for id_str in os.getenv("TELEGRAM_ADMIN_IDS", "").split(",") if id_str and id_str.strip().isdigit()]

# Make Telegram optional for testing
TELEGRAM_ENABLED = bool(TELEGRAM_TOKEN and ADMIN_IDS)

if not TELEGRAM_ENABLED:
    logger.warning("Telegram bot is disabled. Set TELEGRAM_TOKEN and TELEGRAM_ADMIN_IDS in .env to enable it.")

# Глобальные переменные для управления состоянием бота
_bot_running = False  # Флаг состояния работы бота
_bot_instance = None  # Ссылка на экземпляр бота

# Инициализируем логгер
logger = logging.getLogger(__name__)

# Утилиты для форматирования
def format_order(order) -> str:
    """
    Форматирует заказ для отображения в Telegram.
    
    Args:
        order: Объект заказа
        
    Returns:
        Отформатированная строка с информацией о заказе
    """
    if not order:
        return "❌ Информация о заказе отсутствует"
        
    return (
        f"📝 *{getattr(order, 'title', 'Без названия')}*\n"
        f"🆔 `{getattr(order, 'id', 'N/A')}`\n"
        f"💼 {getattr(order, 'category', 'Без категории')}\n"
        f"💰 {getattr(order, 'budget', 'Не указан')}\n"
        f"📅 {getattr(order, 'created_at', datetime.now()).strftime('%d.%m.%Y %H:%M')}\n"
        f"🔗 [Открыть заказ]({getattr(order, 'url', '#')})\n"
    )

def format_reply(reply) -> str:
    """
    Форматирует отклик для отображения в Telegram.
    
    Args:
        reply: Объект отклика
        
    Returns:
        Отформатированная строка с информацией об отклике
    """
    if not reply:
        return "❌ Информация об отклике отсутствует"
        
    status_emoji = "✅" if getattr(reply, 'sent', False) else "❌"
    created_at = getattr(reply, 'created_at', datetime.now())
    message = getattr(reply, 'message', 'Нет сообщения')
    
    return (
        f"{status_emoji} *Отклик*\n"
        f"🆔 `{getattr(reply, 'id', 'N/A')}`\n"
        f"📅 {created_at.strftime('%d.%m.%Y %H:%M') if created_at else 'N/A'}\n"
        f"📝 {message[:50]}{'...' if len(message) > 50 else ''}"
    )

# Обработчики команд
@admin_required
async def start(update: Update, context: CallbackContext) -> None:
    """
    Обработчик команды /start.
    
    Args:
        update: Объект обновления Telegram
        context: Контекст бота
    """
    if not update.message:
        return
        
    # Добавляем информацию о пользователе в контекст бота
    if 'admin_ids' not in context.bot_data:
        context.bot_data['admin_ids'] = set(ADMIN_IDS)
    
    # Формируем сообщение со списком команд
    commands = [
        "/start - Показать это сообщение",
        "/status - Статус системы",
        "/orders [кол-во] - Последние заказы (по умолчанию 5)",
        "/logs [кол-во] [уровень] - Последние логи"
    ]
    
    await update.message.reply_text(
        "🤖 *Jarvis MVP Bot*\n\n"
        "*Доступные команды:*\n" + 
        "\n".join(commands) +
        "\n\nБот будет присылать уведомления о новых заказах и результатах отправки откликов.",
        parse_mode=ParseMode.MARKDOWN
    )

@with_session
@admin_required
async def get_status(update: Update, context: CallbackContext, session: AsyncSession) -> None:
    """
    Обработчик команды /status.
    
    Args:
        update: Объект обновления Telegram
        context: Контекст бота
        session: Сессия базы данных
    """
    if not update.message:
        return
        
    try:
        # Получаем статистику из базы данных
        # Получаем количество заказов
        result = await session.execute(select(func.count(Order.id)))
        total_orders = result.scalar() or 0
        
        # Получаем количество успешных откликов
        result = await session.execute(
            select(func.count(Reply.id)).where(Reply.sent == True)
        )
        sent_replies = result.scalar() or 0
        
        # Получаем количество ошибок
        result = await session.execute(
            select(func.count(Reply.id)).where(Reply.sent == False)
        )
        failed_replies = result.scalar() or 0
        
        # Получаем последнюю ошибку
        result = await session.execute(
            select(SystemLog)
            .where(SystemLog.level == 'error')
            .order_by(desc(SystemLog.created_at))
            .limit(1)
        )
        last_error = result.scalar_one_or_none()
        
        # Получаем статистику по времени работы
        uptime = "N/A"
        if hasattr(context.bot_data, 'start_time'):
            uptime = str(datetime.now() - context.bot_data.start_time).split('.')[0]
        
        # Формируем сообщение
        message = (
            "📊 *Статус системы*\n\n"
            f"• Время работы: `{uptime}`\n"
            f"• Всего заказов: `{total_orders}`\n"
            f"• Успешных откликов: `{sent_replies}`\n"
            f"• Ошибок: `{failed_replies}`\n\n"
        )
        
        if last_error:
            message += (
                "*Последняя ошибка:*\n"
                f"• Время: `{last_error.created_at.strftime('%d.%m.%Y %H:%M:%S') if last_error.created_at else 'N/A'}`\n"
                f"• Сообщение: `{last_error.message}`\n"
            )
            
            if last_error.details:
                details = str(last_error.details)
                if len(details) > 100:
                    details = details[:97] + '...'
                message += f"• Детали: `{details}`\n"
        
        await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
        
    except Exception as e:
        logger.error(f"Error in get_status: {e}", exc_info=True)
        await update.message.reply_text("❌ Произошла ошибка при получении статуса.")
        raise  # Будет обработано декоратором with_session

@with_session
@admin_required
async def get_orders(update: Update, context: CallbackContext, session: AsyncSession) -> None:
    """
    Обработчик команды /orders.
    
    Args:
        update: Объект обновления Telegram
        context: Контекст бота
        session: Сессия базы данных
    """
    if not update.message:
        return
        
    try:
        # Получаем количество заказов из аргументов или используем значение по умолчанию
        limit = 5
        if context.args and context.args[0].isdigit():
            limit = min(int(context.args[0]), 20)  # Ограничиваем максимальное количество
        
        # Получаем последние заказы
        result = await session.execute(
            select(Order)
            .order_by(Order.created_at.desc())
            .limit(limit)
        )
        orders = result.scalars().all()
        
        if not orders:
            await update.message.reply_text("📭 Заказов пока нет.")
            return
            
        # Формируем сообщение с заказами
        message = "📋 *Последние заказы*\n\n"
        for order in orders:
            message += f"• {getattr(order, 'title', 'Без названия')} (`{getattr(order, 'id', 'N/A')}`)\n"
            message += f"  💰 {getattr(order, 'budget', 'Не указан')}\n"
            created_at = getattr(order, 'created_at', datetime.now())
            message += f"  📅 {created_at.strftime('%d.%m %H:%M') if created_at else 'N/A'}\n"
            message += f"  🔗 [Открыть]({getattr(order, 'url', '#')})\n\n"
            
        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            disable_web_page_preview=True
        )
        
    except Exception as e:
        logger.error(f"Error in get_orders: {e}", exc_info=True)
        await update.message.reply_text("❌ Произошла ошибка при получении списка заказов.")
        raise  # Будет обработано декоратором with_session

@with_session
@admin_required
async def get_logs(update: Update, context: CallbackContext, session: AsyncSession) -> None:
    """
    Обработчик команды /logs.
    
    Args:
        update: Объект обновления Telegram
        context: Контекст бота
        session: Сессия базы данных
    """
    if not update.message:
        return
        
    try:
        # Получаем параметры из аргументов
        limit = 10
        log_level = None
        
        if context.args:
            # Первый аргумент - количество логов
            if context.args[0].isdigit():
                limit = min(int(context.args[0]), 50)  # Ограничиваем максимальное количество
                # Второй аргумент (опционально) - уровень логов
                if len(context.args) > 1:
                    log_level = context.args[1].lower()
            else:
                # Если первый аргумент не число, считаем его уровнем логов
                log_level = context.args[0].lower()
        
        # Строим запрос с фильтрацией по уровню, если указан
        query = select(SystemLog).order_by(desc(SystemLog.created_at)).limit(limit)
        if log_level:
            query = query.where(SystemLog.level == log_level)
        
        # Выполняем запрос
        result = await session.execute(query)
        logs = result.scalars().all()
        
        if not logs:
            await update.message.reply_text("📭 Логов пока нет.")
            return
            
        # Формируем сообщение с логами
        message = "📜 *Последние логи*"
        if log_level:
            message += f" (уровень: {log_level.upper()})"
        message += "\n\n"
        
        for log in logs:
            # Выбираем эмодзи в зависимости от уровня лога
            level_emoji = "ℹ️"
            if log.level == 'warning':
                level_emoji = "⚠️"
            elif log.level == 'error':
                level_emoji = "❌"
                
            # Форматируем время
            created_at = getattr(log, 'created_at', datetime.now())
            time_str = created_at.strftime('%d.%m %H:%M') if created_at else 'N/A'
            
            # Добавляем запись лога
            message += f"{level_emoji} *{log.level.upper()}* {time_str}\n"
            message += f"`{log.message}`\n"
            
            # Добавляем детали, если они есть
            if log.details:
                details = str(log.details)
                if len(details) > 100:  # Ограничиваем длину деталей
                    details = details[:97] + '...'
                message += f"_Детали:_ `{details}`\n"
            
            message += "\n"  # Разделитель между логами
            
        # Отправляем сообщение
        await update.message.reply_text(
            message,
            parse_mode=ParseMode.MARKDOWN
        )
        
    except Exception as e:
        logger.error(f"Error in get_logs: {e}", exc_info=True)
        await update.message.reply_text("❌ Произошла ошибка при получении логов.")
        raise  # Будет обработано декоратором with_session

async def send_notification(
    chat_id: Union[int, str],
    message: str,
    parse_mode: Optional[str] = None,
    context: Optional[CallbackContext] = None
) -> bool:
    """
    Отправляет уведомление в Telegram.
    
    Args:
        chat_id: ID чата или имя пользователя для отправки
        message: Текст сообщения
        parse_mode: Режим парсинга (по умолчанию None)
        context: Контекст бота (по умолчанию None)
    
    Returns:
        True, если сообщение отправлено успешно, False в противном случае
    """
    bot = None
    try:
        # Если передан контекст, используем его бота
        if context is not None and hasattr(context, 'bot'):
            bot = context.bot
        else:
            # Иначе создаем нового бота
            from telegram import Bot
            bot = Bot(token=TELEGRAM_TOKEN)
        
        # Отправляем сообщение
        await bot.send_message(
            chat_id=chat_id,
            text=message,
            parse_mode=parse_mode or ParseMode.MARKDOWN
        )
        return True
        
    except Exception as e:
        logger.error(f"Failed to send notification to {chat_id}: {e}", exc_info=True)
        return False
    finally:
        # Если создавали бота вручную, закрываем сессию
        if bot is not None and (context is None or bot is not getattr(context, 'bot', None)):
            try:
                await bot.close()
            except Exception as e:
                logger.error(f"Error closing bot session: {e}")

# Инициализация бота
def setup_handlers(application: Application) -> None:
    """
    Настройка обработчиков команд.
    
    Args:
        application: Экземпляр приложения Telegram бота
    """
    try:
        # Регистрируем обработчики команд с декораторами
        application.add_handler(CommandHandler("start", start))
        
        # Создаем обертки для хендлеров с сессиями
        def create_handler(handler_func):
            """Создает обертку для хендлера с сессией."""
            async def wrapper(update: Update, context: CallbackContext) -> None:
                if not update.effective_user:
                    return
                    
                # Проверяем права администратора
                if update.effective_user.id not in ADMIN_IDS:
                    if update.effective_message:
                        await update.effective_message.reply_text(
                            "⛔ У вас недостаточно прав для выполнения этой команды."
                        )
                    return
                    
                # Создаем сессию и вызываем хендлер
                async with async_session_factory() as session:
                    try:
                        return await handler_func(update, context, session)
                    except Exception as e:
                        logger.error(f"Error in handler {handler_func.__name__}: {e}", exc_info=True)
                        if update.effective_message:
                            await update.effective_message.reply_text(
                                f"❌ Произошла ошибка при выполнении команды: {str(e)}"
                            )
                        raise
            return wrapper
        
        # Регистрируем хендлеры с обертками
        status_handler = create_handler(get_status)
        orders_handler = create_handler(get_orders)
        logs_handler = create_handler(get_logs)
        
        application.add_handler(CommandHandler("status", status_handler))
        application.add_handler(CommandHandler("orders", orders_handler))
        application.add_handler(CommandHandler("logs", logs_handler))
        
        # Регистрируем обработчик ошибок
        application.add_error_handler(error_handler)
        
        # Добавляем данные в контекст бота
        if not hasattr(application, 'bot_data'):
            application.bot_data = {}
            
        application.bot_data.update({
            'admin_ids': set(ADMIN_IDS),
            'admin_id': ADMIN_IDS[0] if ADMIN_IDS else None,  # Первый администратор как основной
            'start_time': datetime.now(),
            'bot_username': None  # Будет установлено при запуске
        })
        
        logger.info("Обработчики команд инициализированы")
        
    except Exception as e:
        logger.error(f"Ошибка при настройке обработчиков: {e}", exc_info=True)
        raise

async def error_handler(update: object, context: CallbackContext) -> None:
    """
    Глобальный обработчик ошибок бота.
    
    Args:
        update: Объект обновления Telegram (может быть None)
        context: Контекст бота с информацией об ошибке
    """
    try:
        # Получаем информацию об ошибке
        error = getattr(context, 'error', None)
        if error is None:
            return
            
        # Игнорируем ошибки отмены задач
        if isinstance(error, asyncio.CancelledError):
            return
            
        # Логируем ошибку
        logger.error("Exception while handling an update:", exc_info=error)
        
        # Если бот отключен, выходим
        if not TELEGRAM_ENABLED or not ADMIN_IDS:
            return
        
        # Получаем ID администратора из контекста или используем первый из списка
        admin_id = None
        try:
            if hasattr(context, 'bot_data') and context.bot_data:
                admin_id = context.bot_data.get('admin_id')
        except Exception:
            pass
            
        admin_id = admin_id or (ADMIN_IDS[0] if ADMIN_IDS else None)
        if not admin_id:
            return
            
        # Формируем сообщение об ошибке
        error_message = [
            "⚠️ *Ошибка в боте*",
            f"• Ошибка: `{error.__class__.__name__}`",
            f"• Сообщение: `{str(error)[:300]}`"  # Ограничиваем длину сообщения
        ]
        
        # Добавляем информацию об обновлении, если оно есть
        if update is not None:
            try:
                if hasattr(update, 'effective_chat') and update.effective_chat:
                    error_message.append(f"• Чат: `{update.effective_chat.id}`")
                if hasattr(update, 'effective_user') and update.effective_user:
                    error_message.append(f"• Пользователь: `{update.effective_user.id}`")
                if hasattr(update, 'update_id'):
                    error_message.append(f"• Update ID: `{update.update_id}`")
            except Exception as e:
                logger.error(f"Error getting update info: {e}")
        
        # Отправляем уведомление администратору
        await send_notification(
            chat_id=admin_id,
            message='\n'.join(error_message),
            parse_mode=ParseMode.MARKDOWN,
            context=context
        )
        
        # Если есть traceback, логируем его и отправляем администратору
        import traceback
        try:
            tb_list = traceback.format_exception(type(error), error, error.__traceback__)
            tb_string = ''.join(tb_list)
            
            # Логируем полный traceback
            logger.error(f"Full traceback:\n{tb_string}")
            
            # Отправляем только часть traceback, если он слишком большой
            if len(tb_string) > 4000:
                tb_string = "\n...\n" + '\n'.join(tb_string.split('\n')[-50:])  # Последние 50 строк
                
            if tb_string:
                await send_notification(
                    chat_id=admin_id,
                    message=f'```\n{tb_string}\n```',
                    parse_mode=ParseMode.MARKDOWN,
                    context=context
                )
        except Exception as e:
            logger.error(f"Error processing traceback: {e}")
            
    except Exception as e:
        logger.error(f"Critical error in error handler: {e}", exc_info=True)
        # Пытаемся отправить хотя бы уведомление об ошибке в лог
        try:
            logger.error(f"Original error that caused the issue: {error}")
        except:
            pass

async def run_bot() -> None:
    """
    Запускает Telegram бота.
    
    Returns:
        None
    """
    global _bot_running, _bot_instance
    
    if _bot_running:
        logger.warning("Бот уже запущен")
        return
    
    if not TELEGRAM_ENABLED:
        logger.warning("Telegram бот отключен. Проверьте настройки в .env файле.")
        return
    
    application = None
    bot_info = None
    
    try:
        _bot_running = True
        
        # Создаем приложение
        logger.info("Инициализация бота...")
        application = Application.builder().token(TELEGRAM_TOKEN).build()
        _bot_instance = application
        
        # Настраиваем обработчики
        setup_handlers(application)
        
        # Инициализируем бота
        logger.info("Инициализация бота...")
        await application.initialize()
        await application.start()
        
        # Получаем информацию о боте
        bot_info = await application.bot.get_me()
        logger.info(f"Бот запущен как @{bot_info.username} (ID: {bot_info.id})")
        
        # Обновляем имя бота в контексте
        if hasattr(application, 'bot_data'):
            application.bot_data['bot_username'] = bot_info.username
        
        # Устанавливаем команды бота
        try:
            await application.bot.set_my_commands([
                ("start", "Запустить бота"),
                ("status", "Показать статус системы"),
                ("orders", "Показать последние заказы"),
                ("logs", "Показать логи")
            ])
            logger.info("Команды бота успешно обновлены")
        except Exception as e:
            logger.error(f"Ошибка при установке команд бота: {e}")
        
        # Отправляем уведомление администраторам о запуске
        startup_time = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
        startup_message = [
            "✅ *Бот запущен*",
            f"• Время: `{startup_time}`",
            f"• Бот: @{bot_info.username}",
            f"• Версия: `{datetime.now().strftime('%Y.%m.%d')}`"
        ]
        
        for admin_id in ADMIN_IDS:
            try:
                await send_notification(
                    chat_id=admin_id,
                    message='\n'.join(startup_message),
                    parse_mode=ParseMode.MARKDOWN,
                    context=application
                )
                logger.debug(f"Уведомление о запуске отправлено администратору {admin_id}")
            except Exception as e:
                logger.error(f"Не удалось отправить уведомление администратору {admin_id}: {e}")
        
        # Запускаем опрос обновлений
        logger.info("Бот готов к работе и ожидает обновлений...")
        await application.run_polling(drop_pending_updates=True)
        
    except asyncio.CancelledError:
        logger.info("Получен сигнал на завершение работы бота")
    except Exception as e:
        logger.critical(f"Критическая ошибка в боте: {e}", exc_info=True)
        
        # Пытаемся уведомить администратора об ошибке
        if ADMIN_IDS:
            try:
                error_message = [
                    "❌ *Критическая ошибка бота!*",
                    f"• Ошибка: `{e.__class__.__name__}`",
                    f"• Сообщение: `{str(e)[:300]}`"
                ]
                
                await send_notification(
                    chat_id=ADMIN_IDS[0],
                    message='\n'.join(error_message),
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as notify_err:
                logger.error(f"Не удалось отправить уведомление об ошибке: {notify_err}")
        
        raise
    finally:
        try:
            # Отправляем уведомление о выключении
            if _bot_running and ADMIN_IDS and bot_info:
                try:
                    await send_notification(
                        chat_id=ADMIN_IDS[0],
                        message=f"🛑 *Бот @{bot_info.username} остановлен*\n"
                               f"• Время: `{datetime.now().strftime('%d.%m.%Y %H:%M:%S')}`",
                        parse_mode=ParseMode.MARKDOWN
                    )
                except Exception as e:
                    logger.error(f"Не удалось отправить уведомление об остановке: {e}")
            
            # Останавливаем бота
            if application:
                try:
                    await application.stop()
                    await application.shutdown()
                except Exception as e:
                    logger.error(f"Ошибка при остановке приложения: {e}")
        finally:
            _bot_running = False
            _bot_instance = None
            logger.info("Бот остановлен")

def main() -> None:
    """
    Основная функция для запуска бота.
    
    Обрабатывает корректное завершение работы при получении сигналов ОС.
    """
    # Настраиваем обработчик сигналов
    import signal
    
    # Создаем и настраиваем цикл событий
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Переменная для отслеживания состояния работы
    is_running = True
    
    def signal_handler(signum, frame):
        """Обработчик сигналов ОС."""
        nonlocal is_running
        signal_name = signal.Signals(signum).name if hasattr(signal, 'Signals') else signum
        logger.warning(f"Получен сигнал {signal_name}, завершаем работу...")
        is_running = False
        
        # Если бот все еще запущен, останавливаем его
        global _bot_instance
        if _bot_instance is not None:
            logger.info("Остановка бота...")
            try:
                loop.create_task(_bot_instance.stop())
            except Exception as e:
                logger.error(f"Ошибка при остановке бота: {e}")
    
    # Регистрируем обработчики сигналов
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, signal_handler)
        except (ValueError, OSError) as e:
            logger.warning(f"Не удалось зарегистрировать обработчик для сигнала {sig}: {e}")
    
    try:
        logger.info("Запуск бота...")
        
        # Запускаем бота в цикле событий
        bot_task = loop.create_task(run_bot())
        
        # Основной цикл работы
        while is_running:
            try:
                loop.run_until_complete(asyncio.sleep(1))
            except asyncio.CancelledError:
                logger.info("Получен запрос на отмену задач")
                is_running = False
            except Exception as e:
                logger.error(f"Ошибка в основном цикле: {e}", exc_info=True)
                is_running = False
        
        # Даем боту время на корректное завершение
        if not bot_task.done():
            logger.info("Ожидание завершения работы бота...")
            try:
                loop.run_until_complete(asyncio.wait_for(bot_task, timeout=10))
            except asyncio.TimeoutError:
                logger.warning("Таймаут ожидания завершения бота, принудительная остановка")
                bot_task.cancel()
            except Exception as e:
                logger.error(f"Ошибка при ожидании завершения бота: {e}")
        
    except KeyboardInterrupt:
        logger.info("Получен сигнал прерывания (Ctrl+C)")
    except Exception as e:
        logger.critical(f"Критическая ошибка: {e}", exc_info=True)
    finally:
        try:
            # Отменяем все оставшиеся задачи
            pending = asyncio.all_tasks(loop=loop)
            if pending:
                logger.info(f"Отмена {len(pending)} оставшихся задач...")
                for task in pending:
                    task.cancel()
                
                # Даем задачам время на корректное завершение
                try:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                except Exception as e:
                    logger.error(f"Ошибка при завершении задач: {e}")
            
            # Закрываем цикл событий
            logger.info("Завершение работы...")
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()
            
        except Exception as e:
            logger.error(f"Ошибка при завершении: {e}", exc_info=True)
        
        logger.info("Приложение завершено")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.critical(f"Фатальная ошибка: {e}", exc_info=True)
        raise
