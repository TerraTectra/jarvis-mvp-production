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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
    "Connection": "keep-alive"
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
    # Используем существующую сессию или создаем новую с контекстным менеджером
    session = get_session()
    try:
        url = f"{BASE_URL}/projects"
        print(f"🔍 Парсинг страницы: {url}")
        print(f"📝 Заголовки запроса: {HEADERS}")
        print("🔓 Отключена проверка SSL (режим отладки)")
        
        # Используем существующую сессию для запроса
        async with session.get(url, timeout=30, ssl=False) as response:
            if response.status != 200:
                logger.warning(f"Не удалось загрузить страницу: {response.status}")
                return []
                
            html = await response.text()
            soup = BeautifulSoup(html, 'html.parser')
            
            orders = []
            # Обновленные селекторы для новой версии Kwork
            for card in soup.select('.card__content'):
                if len(orders) >= limit:
                    break
                    
                # Заголовок и ID заказа
                title_elem = card.select_one('a[href^="/projects/"] h2')
                if not title_elem:
                    continue
                    
                title = title_elem.get_text(strip=True)
                
                # ID заказа из ссылки
                link_elem = card.select_one('a[href^="/projects/"]')
                order_id = link_elem['href'].split('/')[-1] if link_elem and 'href' in link_elem.attrs else ''
                
                # Описание
                description = card.select_one('.wants-card__description-text, .breakwords')
                
                # Бюджет
                price = card.select_one('.wants-card__price, .wants-card__price.higher')
                
                # Категория
                category = card.select_one('a[href^="/projects/"] + div a')
                
                # Пропускаем без ID
                if not order_id:
                    continue
                
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
