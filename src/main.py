import uvicorn
from src.api import app
import asyncio
import argparse
import sys
import os

from automation.auto_responder import AutoResponder

async def start_auto_responder():
    """Запускает автоматический ответчик."""
    responder = AutoResponder()
    try:
        await responder.start()
    except asyncio.CancelledError:
        print("\nАвтоматический ответчик остановлен")
    except Exception as e:
        print(f"Ошибка в автоответчике: {e}", file=sys.stderr)
        raise

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Jarvis MVP - автоматический ответчик на заказы')
    parser.add_argument('--auto', action='store_true', help='Запустить в автоматическом режиме')
    parser.add_argument('--interval', type=int, help='Интервал проверки в секундах (только для --auto)')
    parser.add_argument('--keywords', type=str, help='Ключевые слова для фильтрации через запятую')
    
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
        print("🔗 Доступно по адресу: http://127.0.0.1:8000")
        print("📚 Документация: http://127.0.0.1:8000/docs\n")
        uvicorn.run(app, host="127.0.0.1", port=8000)
