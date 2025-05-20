#!/usr/bin/env python3
"""
Скрипт для добавления тестовой записи в логи.
"""
import asyncio
import sys
from pathlib import Path

# Добавляем корень проекта в PYTHONPATH
sys.path.append(str(Path(__file__).parent.parent))

from src.database.models import SystemLog
from src.database.session import async_session
from datetime import datetime

async def insert_test_log():
    """Добавляет тестовую запись в логи."""
    async with async_session() as session:
        try:
            log = SystemLog(
                level="INFO",
                message="🔧 Тестовая запись лога",
                source="test_insert",
                details="Проверка отображения в /logs",
                created_at=datetime.utcnow()
            )
            session.add(log)
            await session.commit()
            print("✅ Тестовая запись успешно добавлена в логи")
            return True
        except Exception as e:
            print(f"❌ Ошибка при добавлении тестовой записи: {e}")
            await session.rollback()
            return False

if __name__ == "__main__":
    asyncio.run(insert_test_log())
