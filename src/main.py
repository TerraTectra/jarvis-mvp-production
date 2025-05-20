import uvicorn
import asyncio
import argparse
import sys
import os
import logging
from pathlib import Path
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

# Импортируем бота
from src.bot import run_bot, TELEGRAM_AVAILABLE

# Ensure logs directory exists
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / "jarvis.log", mode='a', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Добавляем корневую директорию в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Create FastAPI instance with debug mode
app = FastAPI(
    title="Jarvis MVP API",
    description="API для автоматического ответчика на заказы",
    version="0.1.0",
    debug=True
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import and include API routers
from src.api import auth
app.include_router(auth.router, prefix="/api/v1/auth")
from src.automation.auto_responder import AutoResponder
from src.api.dependencies import get_db
from src.core.security import get_password_hash, verify_password
from src.crud.user import get_user_by_username, create_user
from src.schemas.user import UserCreate, Token, UserResponse
from src.database.session import init_db, async_session

async def start_kwork_poller():
    """Запускает опросщик заказов Kwork."""
    from src.kwork.tasks import KworkPoller
    
    poller = KworkPoller()
    try:
        await poller.start()
    except asyncio.CancelledError:
        logger.info("Kwork poller stopped by user")
    except Exception as e:
        logger.error(f"Error in Kwork poller: {e}", exc_info=True)
    finally:
        if poller.is_running():
            await poller.stop()

async def start_auto_responder():
    """Запускает автоматический ответчик."""
    responder = AutoResponder()
    try:
        await responder.start()
    except asyncio.CancelledError:
        logger.info("Auto responder stopped by user")
    except Exception as e:
        print(f"Ошибка в автоответчике: {e}", file=sys.stderr)
        raise

@app.on_event("startup")
async def startup_event():
    """Инициализация при запуске приложения."""
    await init_db()
    
    # Start background tasks
    asyncio.create_task(start_auto_responder())
    asyncio.create_task(start_kwork_poller())
    
    # Start Telegram bot if enabled
    if TELEGRAM_AVAILABLE and os.getenv("TELEGRAM_TOKEN") and os.getenv("TELEGRAM_ADMIN_ID"):
        asyncio.create_task(run_bot())
        print("✅ Telegram бот запущен")
    else:
        print(f"⚠️ Telegram бот не запущен. TELEGRAM_AVAILABLE={TELEGRAM_AVAILABLE}, TELEGRAM_TOKEN={'установлен' if os.getenv('TELEGRAM_TOKEN') else 'не установлен'}, TELEGRAM_ADMIN_ID={'установлен' if os.getenv('TELEGRAM_ADMIN_ID') else 'не установлен'}")
    
    print("✅ База данных инициализирована")

def main():
    parser = argparse.ArgumentParser(description='Jarvis MVP - автоматический ответчик на заказы')
    parser.add_argument('--auto', action='store_true', help='Запустить в автоматическом режиме')
    parser.add_argument('--interval', type=int, help='Интервал проверки в секундах (только для --auto)')
    parser.add_argument('--keywords', type=str, help='Ключевые слова для фильтрации через запятую')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Хост для запуска сервера')
    parser.add_argument('--port', type=int, default=8000, help='Порт для запуска сервера')
    parser.add_argument('--reload', action='store_true', help='Автоматическая перезагрузка при изменениях')
    
    args = parser.parse_args()
    
    # Устанавливаем переменные окружения из аргументов
    if args.interval:
        os.environ["POLL_INTERVAL"] = str(args.interval)
    if args.keywords:
        os.environ["KEYWORDS"] = args.keywords
    
    if args.auto:
        print("Запуск в автоматическом режиме...")
        print(f"Интервал проверки: {os.getenv('POLL_INTERVAL', '300')} сек")
        print(f"Ключевые слова: {os.getenv('KEYWORDS', 'все')}")
        print("Для остановки нажмите Ctrl+C\n")
        
        try:
            asyncio.run(start_auto_responder())
        except KeyboardInterrupt:
            print("\nРабота завершена по запросу пользователя")
    else:
        # Запуск API сервера
        print("🚀 Запуск сервера Jarvis MVP API...")
        print(f"🔗 Доступно по адресу: http://{args.host}:{args.port}")
        print(f"📚 Документация: http://{args.host}:{args.port}/docs\n")
        uvicorn.run(
            "src.main:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
            reload_dirs=["src"],
            log_level="info"
        )

if __name__ == "__main__":
    main()
