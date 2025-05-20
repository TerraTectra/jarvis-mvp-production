import asyncio
from src.integrations.kwork import fetch_kwork_orders

async def test():
    print("Запуск тестового парсинга Kwork...")
    try:
        orders = await fetch_kwork_orders(5)
        print(f"Найдено заказов: {len(orders)}")
        for i, order in enumerate(orders, 1):
            print(f"\n--- Заказ {i} ---")
            print(f"ID: {order.get('id')}")
            print(f"Название: {order.get('title')}")
            print(f"Бюджет: {order.get('budget', 'Нет данных')}")
            print(f"Категория: {order.get('category', 'Нет данных')}")
            print(f"Ссылка: {order.get('url', 'Нет данных')}")
    except Exception as e:
        print(f"Ошибка: {e}")

if __name__ == "__main__":
    asyncio.run(test())
