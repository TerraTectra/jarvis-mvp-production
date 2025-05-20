"""
Модуль для загрузки переменных окружения из .env файла.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

def load_dotenv():
    """Загружает переменные окружения из .env файла."""
    # Ищем .env файл в корне проекта (на два уровня выше от текущего файла)
    env_path = Path(__file__).parent.parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✅ Загружены переменные окружения из {env_path}")
    else:
        print(f"⚠️ Файл .env не найден по пути {env_path}. Используются системные переменные окружения.")
