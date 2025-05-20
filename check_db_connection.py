"""
Проверка соединения с базой данных.
"""
import asyncio
from src.database.session import engine, Base

async def test_connection():
    """Проверка соединения с базой данных."""
    print("🔍 Проверка соединения с базой данных...")
    try:
        async with engine.connect() as conn:
            result = await conn.execute("SELECT 1")
            if result.scalar() == 1:
                print("✅ Соединение с базой данных установлено успешно!")
                return True
            else:
                print("❌ Неожиданный результат запроса")
                return False
    except Exception as e:
        print(f"❌ Ошибка при подключении к базе данных: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(test_connection())
