"""
Инициализация моделей базы данных.
"""
import asyncio
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy.sql import func
from datetime import datetime
import bcrypt

# URL подключения к базе данных
DATABASE_URL = "postgresql+asyncpg://TerraTectra:272829Dr@localhost:5432/jarvis_staging"

# Создаем базовый класс для моделей
Base = declarative_base()

# Определяем модели
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    is_superuser = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Связи
    roles = relationship("UserRole", back_populates="user")

class Role(Base):
    __tablename__ = "roles"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Связи
    users = relationship("UserRole", back_populates="role")
    permissions = relationship("RolePermission", back_populates="role")

class Permission(Base):
    __tablename__ = "permissions"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Связи
    roles = relationship("RolePermission", back_populates="permission")

class UserRole(Base):
    __tablename__ = "user_roles"
    
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Связи
    user = relationship("User", back_populates="roles")
    role = relationship("Role", back_populates="users")

class RolePermission(Base):
    __tablename__ = "role_permissions"
    
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    permission_id = Column(Integer, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Связи
    role = relationship("Role", back_populates="permissions")
    permission = relationship("Permission", back_populates="roles")

async def init_db():
    """Инициализация базы данных и создание таблиц."""
    print("🔄 Инициализация базы данных...")
    
    # Создаем движок
    engine = create_async_engine(DATABASE_URL, echo=True)
    
    # Создаем все таблицы
    async with engine.begin() as conn:
        print("🛠️  Создание таблиц...")
        await conn.run_sync(Base.metadata.create_all)
    
    print("✅ Таблицы успешно созданы!")
    
    # Создаем сессию для добавления начальных данных
    async_session = sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )
    
    async with async_session() as session:
        try:
            # Проверяем, есть ли уже роли
            from sqlalchemy import select
            result = await session.execute(select(Role).where(Role.name == "admin"))
            admin_role = result.scalar_one_or_none()
            
            if not admin_role:
                print("🛠️  Создание ролей и разрешений...")
                # Создаем роли
                admin_role = Role(name="admin", description="Администратор системы")
                user_role = Role(name="user", description="Обычный пользователь")
                
                session.add_all([admin_role, user_role])
                await session.flush()  # Получаем ID ролей
                
                # Создаем разрешения
                permissions = [
                    Permission(name="user:read", description="Просмотр пользователей"),
                    Permission(name="user:create", description="Создание пользователей"),
                    Permission(name="user:update", description="Обновление пользователей"),
                    Permission(name="user:delete", description="Удаление пользователей"),
                    Permission(name="role:manage", description="Управление ролями"),
                    Permission(name="permission:manage", description="Управление разрешениями"),
                ]
                session.add_all(permissions)
                await session.flush()
                
                # Назначаем все права роли администратора
                for perm in permissions:
                    session.add(RolePermission(role_id=admin_role.id, permission_id=perm.id))
                
                await session.commit()
                print("✅ Роли и разрешения успешно созданы!")
            
            # Проверяем, есть ли уже суперпользователь
            result = await session.execute(select(User).where(User.email == "admin@jarvis.local"))
            admin_user = result.scalar_one_or_none()
            
            if not admin_user:
                print("🛠️  Создание суперпользователя...")
                # Создаем суперпользователя
                hashed_password = bcrypt.hashpw("Admin123!".encode('utf-8'), bcrypt.gensalt())
                admin_user = User(
                    username="admin",
                    email="admin@jarvis.local",
                    hashed_password=hashed_password.decode('utf-8'),
                    is_superuser=True,
                    is_active=True
                )
                session.add(admin_user)
                await session.flush()
                
                # Назначаем роль администратора
                session.add(UserRole(user_id=admin_user.id, role_id=admin_role.id))
                await session.commit()
                
                print("✅ Суперпользователь успешно создан!")
                print(f"👤 Имя пользователя: admin")
                print(f"📧 Email: admin@jarvis.local")
                print("🔑 Пароль: Admin123!")
            else:
                print("ℹ️  Суперпользователь уже существует.")
                
        except Exception as e:
            await session.rollback()
            print(f"❌ Ошибка при инициализации базы данных: {e}")
            raise
        finally:
            await session.close()
    
    await engine.dispose()
    print("✅ Инициализация базы данных завершена!")

if __name__ == "__main__":
    asyncio.run(init_db())
