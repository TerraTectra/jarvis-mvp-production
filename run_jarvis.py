"""
Главный скрипт для запуска Jarvis MVP.
"""
import asyncio
import os
import sys
import signal
import logging
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.logging import RichHandler

# Добавляем корневую директорию в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent))

console = Console()
app = typer.Typer()

# Настройка логирования
def setup_logging():
    """Настройка системы логирования."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_file = os.getenv("LOG_FILE", "logs/jarvis.log")
    
    # Создаем директорию для логов, если её нет
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    
    # Формат логов
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Базовый конфиг с выводом в консоль
    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=[
            RichHandler(rich_tracebacks=True, console=console),
        ]
    )
    
    # Добавляем файловый хендлер, если указан файл
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(logging.Formatter(log_format))
        logging.getLogger().addHandler(file_handler)
    
    return logging.getLogger(__name__)

async def start_kwork_poller():
    """Запускает Kwork Poller."""
    from src.kwork.tasks import KworkPoller
    
    logger = logging.getLogger("kwork.poller")
    poll_interval = int(os.getenv("POLL_INTERVAL", "300"))
    
    poller = KworkPoller(poll_interval=poll_interval)
    
    try:
        logger.info(f"🚀 Запуск Kwork Poller (интервал: {poll_interval} сек)")
        await poller.start()
    except asyncio.CancelledError:
        logger.info("🛑 Остановка Kwork Poller...")
    except Exception as e:
        logger.error(f"❌ Ошибка в Kwork Poller: {e}", exc_info=True)
    finally:
        if poller.is_running():
            await poller.stop()

async def start_telegram_bot():
    """Запускает Telegram бота."""
    from src.bot.telegram_bot import main as start_bot
    
    logger = logging.getLogger("telegram.bot")
    
    try:
        logger.info("🤖 Запуск Telegram бота...")
        await start_bot()
    except asyncio.CancelledError:
        logger.info("🛑 Остановка Telegram бота...")
    except Exception as e:
        logger.error(f"❌ Ошибка в Telegram боте: {e}", exc_info=True)

async def run_all():
    """Запускает все компоненты системы."""
    logger = logging.getLogger("jarvis")
    
    # Запускаем компоненты конкурентно
    tasks = [
        asyncio.create_task(start_kwork_poller()),
        asyncio.create_task(start_telegram_bot())
    ]
    
    # Обработка сигналов завершения
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown(sig, tasks)))
    
    logger.info("🚀 Jarvis MVP запущен и готов к работе!")
    
    # Ждем завершения всех задач
    await asyncio.gather(*tasks, return_exceptions=True)

async def shutdown(signal, tasks):
    """Корректное завершение работы."""
    logger = logging.getLogger("jarvis.shutdown")
    logger.info(f"🛑 Получен сигнал {signal.name}, завершение работы...")
    
    # Отменяем все задачи
    for task in tasks:
        if not task.done():
            task.cancel()
    
    # Даем задачам время на завершение
    await asyncio.sleep(1)
    
    logger.info("👋 Работа завершена")

@app.command()
def start():
    """Запускает все компоненты Jarvis MVP."""
    # Настройка логирования
    logger = setup_logging()
    
    # Проверка обязательных переменных окружения
    required_vars = ["KWORK_TOKEN", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        console.print(
            Panel(
                f"❌ Отсутствуют обязательные переменные окружения: {', '.join(missing_vars)}\n\n"
                "Запустите скрипт настройки:\n"
                "  python scripts/setup_env.py",
                title="Ошибка конфигурации",
                style="red"
            )
        )
        sys.exit(1)
    
    # Запуск основного цикла
    try:
        asyncio.run(run_all())
    except KeyboardInterrupt:
        logger.info("Принудительное завершение...")
    except Exception as e:
        logger.critical(f"Критическая ошибка: {e}", exc_info=True)
        sys.exit(1)

@app.command()
def setup():
    """Запускает интерактивную настройку окружения."""
    os.system("python scripts/setup_env.py")

if __name__ == "__main__":
    app()
