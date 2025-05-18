"""
Модуль для работы с базой данных.
"""
from .session import Base, engine, SessionLocal

# Импортируем модели, чтобы Base их зарегистрировал
from . import models  # noqa

# Создаем таблицы
Base.metadata.create_all(bind=engine)

def get_db():
    """Генератор сессий базы данных."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
