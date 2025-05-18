"""
Настройка подключения к базе данных.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# URL подключения к БД (по умолчанию SQLite)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./jarvis.db")

# Создаем движок
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)

# Фабрика сессий
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Базовый класс для моделей
Base = declarative_base()
