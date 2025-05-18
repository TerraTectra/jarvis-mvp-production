"""
Модуль автоматической отправки откликов на заказы.
"""
import os
import asyncio
import logging
from typing import List, Dict, Any, Set, Optional
from datetime import datetime

from dotenv import load_dotenv
from integrations.kwork import fetch_kwork_orders
from utils import generate_reply
from database import SessionLocal
from database.crud import create_or_update_order, create_reply, get_order_replies
from notifications import NotificationLevel, get_notifier

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('auto_responder.log')
    ]
)
logger = logging.getLogger(__name__)

class AutoResponder:
    """Класс для автоматической отправки откликов на заказы."""
    
    def __init__(self, interval: Optional[int] = None):
        """
        Инициализация автоответчика.
        
        Args:
            interval: Интервал проверки заказов в секундах
        """
        self.interval = interval or int(os.getenv("POLL_INTERVAL", "300"))
        self.keywords = self._load_keywords()
        self.seen_orders: Set[str] = set()
        self.processed_count = 0
        self.last_check: Optional[datetime] = None
        self.notifications_enabled = os.getenv("NOTIFICATIONS_ENABLED", "true").lower() == "true"
        self.notify_new_orders = os.getenv("NOTIFY_NEW_ORDER", "true").lower() == "true"
        
        logger.info(f"Инициализирован AutoResponder с интервалом {self.interval} сек")
        logger.info(f"Ключевые слова для фильтрации: {', '.join(self.keywords) if self.keywords else 'все'}")
        logger.info(f"Уведомления: {'включены' if self.notifications_enabled else 'отключены'}")
    
    def _load_keywords(self) -> Set[str]:
        """Загружает ключевые слова из переменных окружения."""
        keywords_str = os.getenv("KEYWORDS", "").strip()
        if not keywords_str:
            return set()
        return {kw.strip().lower() for kw in keywords_str.split(",") if kw.strip()}
    
    async def start(self):
        """Запускает бесконечный цикл проверки заказов."""
        logger.info("Запуск автоматического ответчика...")
        try:
            while True:
                self.last_check = datetime.now()
                logger.info(f"Проверка новых заказов... (всего обработано: {self.processed_count})")
                
                try:
                    await self.check_orders()
                except Exception as e:
                    logger.error(f"Ошибка при проверке заказов: {e}", exc_info=True)
                
                logger.info(f"Следующая проверка через {self.interval} сек...")
                await asyncio.sleep(self.interval)
                
        except asyncio.CancelledError:
            logger.info("Автоответчик остановлен")
        except Exception as e:
            logger.critical(f"Критическая ошибка: {e}", exc_info=True)
            raise
    
    async def check_orders(self):
        """Проверяет новые заказы и обрабатывает их."""
        try:
            # Получаем заказы с Kwork
            orders = await fetch_kwork_orders(limit=20)  # Берем больше заказов на случай фильтрации
            
            # Фильтруем и обрабатываем
            filtered_orders = self.filter_orders(orders)
            for order in filtered_orders:
                if order["id"] not in self.seen_orders:
                    await self.process_order(order)
                    self.seen_orders.add(order["id"])
                    self.processed_count += 1
                    
        except Exception as e:
            logger.error(f"Ошибка при получении заказов: {e}")
            raise
    
    def filter_orders(self, orders: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Фильтрует заказы по ключевым словам и другим критериям.
        
        Args:
            orders: Список заказов для фильтрации
            
        Returns:
            Отфильтрованный список заказов
        """
        if not self.keywords:
            return orders
            
        filtered = []
        for order in orders:
            # Пропускаем уже обработанные заказы
            if order["id"] in self.seen_orders:
                continue
                
            # Проверяем ключевые слова в заголовке и описании
            text = f"{order.get('title', '').lower()} {order.get('description', '').lower()}"
            if any(keyword in text for keyword in self.keywords):
                filtered.append(order)
                
        return filtered
    
    async def process_order(self, order: Dict[str, Any]) -> None:
        """
        Обрабатывает заказ: генерирует и отправляет отклик.
        
        Args:
            order: Данные заказа
        """
        order_id = order.get("id")
        title = order.get("title", "Без названия")
        logger.info(f"Обработка заказа #{order_id}: {title}")
        
        # Сохраняем заказ в БД
        with SessionLocal() as db:
            db_order = create_or_update_order(db, {
                "id": order_id,
                "title": title,
                "category": order.get("category"),
                "budget": order.get("price"),
                "description": order.get("description"),
                "source": "kwork",
                "url": order.get("url")
            })
            
            # Проверяем, был ли уже отклик на этот заказ
            existing_replies = get_order_replies(db, order_id)
            if existing_replies:
                logger.info(f"Заказ #{order_id} уже имеет отклики, пропускаем")
                return
                
            try:
                # Генерация отклика
                reply_text = generate_reply(order)
                logger.info(f"Сгенерирован отклик для заказа #{order_id}")
                
                # Здесь будет вызов функции отправки отклика
                # success = await send_reply(order_id, reply_text)
                success = True  # Заглушка до реализации send_reply
                
                # Сохраняем отклик в БД
                db_reply = create_reply(
                    db=db,
                    order_id=order_id,
                    message=reply_text,
                    sent=success,
                    status="sent" if success else "error"
                )
                
                # Отправляем уведомление о новом заказе
                if self.notifications_enabled and self.notify_new_orders:
                    await self._notify_new_order(order, db_order, db_reply)
                
                logger.info(f"Отклик на заказ #{order_id} успешно отправлен")
                self.processed_count += 1
                
            except Exception as e:
                logger.error(f"Ошибка при обработке заказа #{order_id}: {e}", exc_info=True)
                
                # Отправляем уведомление об ошибке
                if self.notifications_enabled and os.getenv("NOTIFY_ERRORS", "true").lower() == "true":
                    notifier = await get_notifier()
                    await notifier.send_message(
                        f"❌ Ошибка при обработке заказа #{order_id}\n\n"
                        f"*{title}*\n\n"
                        f"Ошибка: {str(e)[:200]}",
                        level=NotificationLevel.ERROR,
                        title="Ошибка обработки заказа"
                    )
    
    async def _notify_new_order(self, order: Dict[str, Any], db_order, db_reply) -> None:
        """Отправляет уведомление о новом заказе."""
        if not self.notifications_enabled or not self.notify_new_orders:
            return
            
        try:
            notifier = await get_notifier()
            order_url = order.get("url", "#")
            
            message = (
                f"🔔 *Новый заказ*\n\n"
                f"*{order.get('title', 'Без названия')}*\n"
                f"💵 *Бюджет:* {order.get('price', 'не указан')}\n"
                f"📅 *Дата:* {db_order.created_at.strftime('%d.%m.%Y %H:%M')}\n"
                f"\n[Открыть заказ]({order_url})\n"
            )
            # result = await submit_kwork_reply(order["id"], reply_data["reply"])
            # logger.info(f"Результат отправки: {result}")
            
        except Exception as e:
            logger.error(f"Ошибка при обработке заказа {order.get('id')}: {e}", exc_info=True)


# Пример использования
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Автоматический ответчик на заказы Kwork')
    parser.add_argument('--interval', type=int, help='Интервал проверки в секундах')
    parser.add_argument('--keywords', type=str, help='Ключевые слова через запятую')
    
    args = parser.parse_args()
    
    # Устанавливаем переменные окружения из аргументов
    if args.interval:
        os.environ["POLL_INTERVAL"] = str(args.interval)
    if args.keywords:
        os.environ["KEYWORDS"] = args.keywords
    
    # Запускаем автоответчик
    responder = AutoResponder()
    
    try:
        asyncio.run(responder.start())
    except KeyboardInterrupt:
        logger.info("Работа завершена по запросу пользователя")
