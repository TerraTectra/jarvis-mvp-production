"""
Проверка соединения с базой данных с использованием async/await.
"""
import asyncio
from sqlalchemy import text
from src.database.session import get_db

async def test_connection():
    """Проверяет соединение с базой данных."""
    print("🔍 Проверка соединения с базой данных...")
    try:
        # Получаем асинхронный генератор
        db_gen = get_db()
        # Получаем сессию
        db = await anext(db_gen)
        
        # Выполняем тестовый запрос
        result = await db.execute(text("SELECT 1"))
        data = result.scalar()
        
        if data == 1:
            print("✅ Соединение с базой данных установлено успешно!")
            return True
        else:
            print(f"❌ Неожиданный результат запроса: {data}")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка при подключении к базе данных: {e}")
        return False
    finally:
        # Закрываем генератор, если он был создан
        if 'db_gen' in locals():
            try:
                await db_gen.aclose()
            except Exception as e:
                print(f"⚠️ Ошибка при закрытии соединения: {e}")

if __name__ == "__main__":
    asyncio.run(test_connection())
