"""
Создание суперпользователя.
"""
import asyncio
import bcrypt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

# Настройки подключения к БД
DATABASE_URL = "postgresql+asyncpg://TerraTectra:272829Dr@localhost:5432/jarvis_staging"

async def get_async_session():
    """Создает асинхронную сессию для работы с БД."""
    engine = create_async_engine(DATABASE_URL, echo=True)
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    return async_session()

async def create_superuser():
    """Создает суперпользователя в базе данных."""
    print("🛠️  Создание суперпользователя...")
    
    # Данные суперпользователя
    username = "admin"
    email = "admin@jarvis.local"
    password = "Admin123!"
    
    # Хешируем пароль
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    
    async with await get_async_session() as session:
        try:
            # Проверяем, существует ли уже пользователь с таким email
            result = await session.execute(
                text("SELECT id FROM users WHERE email = :email"),
                {"email": email}
            )
            user_exists = result.scalar()
            
            if user_exists:
                print(f"⚠️ Пользователь с email {email} уже существует.")
                return
            
            # Создаем суперпользователя
            await session.execute(
                text("""
                    INSERT INTO users (username, email, hashed_password, is_superuser, is_active)
                    VALUES (:username, :email, :hashed_password, :is_superuser, :is_active)
                """),
                {
                    "username": username,
                    "email": email,
                    "hashed_password": hashed_password.decode('utf-8'),
                    "is_superuser": True,
                    "is_active": True
                }
            )
            
            await session.commit()
            print("✅ Суперпользователь успешно создан!")
            print(f"👤 Имя пользователя: {username}")
            print(f"📧 Email: {email}")
            print("🔑 Пароль: ********")
            
        except Exception as e:
            await session.rollback()
            print(f"❌ Ошибка при создании суперпользователя: {e}")
            raise

if __name__ == "__main__":
    asyncio.run(create_superuser())
