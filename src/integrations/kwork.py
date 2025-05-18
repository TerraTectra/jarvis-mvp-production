"""
Модуль для работы с платформой Kwork.
Поддерживает получение заказов через API и парсинг HTML.
"""
import os
import asyncio
import logging
from typing import Dict, List, Optional, Any

import aiohttp
from bs4 import BeautifulSoup

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Конфигурация
BASE_URL = "https://kwork.ru"
API_URL = f"{BASE_URL}/api"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/91.0.4472.124 Safari/537.36"
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


async def fetch_kwork_orders(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Получает список заказов с Kwork.
    
    Args:
        limit: Максимальное количество заказов для получения
        
    Returns:
        Список словарей с информацией о заказах
    """
    try:
        # Сначала пробуем получить данные через API
        orders = await _fetch_kwork_api(limit)
        if not orders:
            # Если API не вернул данные, используем парсинг HTML
            logger.warning("API не вернул данные, используем парсинг HTML")
            orders = await _parse_kwork_html(limit)
        return orders
    except Exception as e:
        logger.error(f"Ошибка при получении заказов с Kwork: {e}")
        return []


async def _fetch_kwork_api(limit: int) -> List[Dict[str, Any]]:
    """
    Получает заказы через API Kwork.
    
    Args:
        limit: Максимальное количество заказов
        
    Returns:
        Список заказов или пустой список в случае ошибки
    """
    session = get_session()
    params = {
        "limit": limit,
        "page": 1,
        "sort": "new",
        "category_id": 0,  # Все категории
    }
    
    try:
        async with session.get(
            f"{API_URL}/v1/projects",
            params=params,
            timeout=10
        ) as response:
            if response.status != 200:
                logger.warning(f"API вернул статус {response.status}")
                return []
                
            data = await response.json()
            if not data.get("success"):
                logger.warning(f"API вернуло ошибку: {data.get('message', 'Неизвестная ошибка')}")
                return []
                
            return [
                {
                    "id": str(item["id"]),
                    "title": item["name"],
                    "category": item.get("category_name", ""),
                    "budget": item.get("price", 0),
                    "description": item.get("description", ""),
                    "url": f"{BASE_URL}/project/{item['id']}/view",
                    "source": "kwork"
                }
                for item in data.get("data", {}).get("projects", [])[:limit]
            ]
    except Exception as e:
        logger.warning(f"Ошибка при запросе к API Kwork: {e}")
        return []


async def _parse_kwork_html(limit: int) -> List[Dict[str, Any]]:
    """
    Парсит заказы с HTML-страницы Kwork.
    
    Args:
        limit: Максимальное количество заказов
        
    Returns:
        Список заказов
    """
    session = get_session()
    url = f"{BASE_URL}/projects"
    
    try:
        async with session.get(url, timeout=10) as response:
            if response.status != 200:
                logger.warning(f"Не удалось загрузить страницу: {response.status}")
                return []
                
            html = await response.text()
            soup = BeautifulSoup(html, 'html.parser')
            
            orders = []
            for card in soup.select('.card.wt-break-word')[:limit]:
                title_elem = card.select_one('.wants-card__title a')
                if not title_elem:
                    continue
                    
                title = title_elem.get_text(strip=True)
                order_id = card.get('data-id', '')
                description = card.select_one('.wants-card__description-text')
                price = card.select_one('.wants-card__price')
                category = card.select_one('.wants-card__category a')
                
                orders.append({
                    "id": order_id,
                    "title": title,
                    "category": category.get_text(strip=True) if category else "",
                    "budget": price.get_text(strip=True) if price else "Договорная",
                    "description": description.get_text(strip=True) if description else "",
                    "url": f"{BASE_URL}{title_elem['href']}" if title_elem.has_attr('href') else "",
                    "source": "kwork"
                })
                
            return orders
    except Exception as e:
        logger.error(f"Ошибка при парсинге HTML Kwork: {e}")
        return []


# Пример использования
if __name__ == "__main__":
    async def main():
        orders = await fetch_kwork_orders(5)
        for order in orders:
            print(f"{order['id']}: {order['title']} - {order['budget']}")
    
    asyncio.run(main())
