"""
Модуль для отправки откликов на заказы Kwork.
"""
import os
import logging
import asyncio
from typing import Dict, Any, Optional
import aiohttp
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация
BASE_URL = "https://kwork.ru"
API_URL = f"{BASE_URL}/api"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/91.0.4472.124 Safari/537.36",
    "Accept": "application/json",
    "Content-Type": "application/x-www-form-urlencoded"
}

# Кэш для хранения сессии
_session = None

def get_session() -> aiohttp.ClientSession:
    """Возвращает сессию aiohttp."""
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession(headers=HEADERS)
    return _session

async def close_session():
    """Закрывает сессию aiohttp."""
    global _session
    if _session and not _session.closed:
        await _session.close()
        _session = None

async def submit_kwork_reply(order_id: str, message: str) -> Dict[str, Any]:
    """
    Отправляет отклик на заказ через Kwork API.
    
    Args:
        order_id: ID заказа
        message: Текст отклика
        
    Returns:
        Словарь с результатом операции
    """
    token = os.getenv("KWORK_TOKEN")
    if not token:
        error_msg = "KWORK_TOKEN не найден в переменных окружения"
        logger.error(error_msg)
        return {
            "status": "error",
            "reason": error_msg,
            "order_id": order_id
        }
    
    # Формируем данные для отправки
    data = {
        "project_id": order_id,
        "offer": message,
        "token": token
    }
    
    session = get_session()
    url = f"{API_URL}/v1/projects/offer"
    
    try:
        async with session.post(url, data=data) as response:
            response_data = await response.json()
            
            if response.status == 200 and response_data.get("success"):
                logger.info(f"Отклик на заказ {order_id} успешно отправлен")
                return {
                    "status": "ok",
                    "order_id": order_id,
                    "message": "Отклик успешно отправлен",
                    "data": response_data
                }
            else:
                error_msg = response_data.get("message", "Неизвестная ошибка")
                logger.error(f"Ошибка при отправке отклика на заказ {order_id}: {error_msg}")
                return {
                    "status": "error",
                    "order_id": order_id,
                    "reason": error_msg,
                    "data": response_data
                }
    except Exception as e:
        error_msg = f"Исключение при отправке отклика: {str(e)}"
        logger.error(error_msg)
        return {
            "status": "error",
            "order_id": order_id,
            "reason": error_msg
        }

# Пример использования
if __name__ == "__main__":
    async def main():
        # Тестовый вызов
        test_order_id = "0001"
        test_message = "Готов к выполнению"
        
        print(f"Отправка тестового отклика на заказ {test_order_id}...")
        result = await submit_kwork_reply(test_order_id, test_message)
        print("Результат:", result)
        
        # Закрываем сессию
        await close_session()
    
    # Запускаем асинхронную функцию
    asyncio.run(main())
