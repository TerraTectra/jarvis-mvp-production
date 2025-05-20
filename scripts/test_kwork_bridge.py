#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестовый скрипт для проверки работы Kwork Node Bridge.
"""
import asyncio
import io
import json
import logging
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Настройка кодировки для Windows
if sys.platform == 'win32':
    import io
    import sys
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Настройка кодировки для логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(stream=sys.stdout)
    ]
)

# Загружаем переменные окружения из .env файла
load_dotenv()

# Добавляем корневую директорию в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.kwork.node_bridge import KworkNodeBridge, KworkBridgeError

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/kwork_bridge_test.log"),
    ],
)
logger = logging.getLogger(__name__)

async def test_connection(bridge: KworkNodeBridge) -> None:
    """Проверяет соединение с Kwork API."""
    try:
        logger.info("Testing connection to Kwork API...")
        profile = bridge.get_profile()
        logger.info("✅ Successfully connected to Kwork API")
        logger.info(f"Profile: {json.dumps(profile, indent=2, ensure_ascii=False)}")
        return True
    except KworkBridgeError as e:
        logger.error(f"❌ Connection test failed: {e}")
        return False

async def test_get_orders(bridge: KworkNodeBridge) -> None:
    """Тестирует получение списка заказов."""
    try:
        logger.info("Fetching recent orders...")
        orders = bridge.get_orders(limit=5)
        logger.info(f"✅ Successfully fetched {len(orders)} orders")
        
        if orders:
            logger.info("Latest order:")
            logger.info(json.dumps(orders[0], indent=2, ensure_ascii=False))
        
        return True
    except KworkBridgeError as e:
        logger.error(f"❌ Failed to fetch orders: {e}")
        return False

async def test_send_reply(bridge: KworkNodeBridge, order_id: str = None) -> None:
    """Тестирует отправку отклика (только если указан order_id)."""
    if not order_id:
        logger.info("Skipping send_reply test - no order_id provided")
        return True
    
    try:
        logger.info(f"Sending test reply to order {order_id}...")
        message = "Здравствуйте! Готов выполнить ваш заказ. Опыт более 5 лет."
        result = bridge.send_reply(
            order_id=order_id,
            message=message,
            price=1000,  # Пример цены
            days=3,      # Пример срока
        )
        logger.info(f"✅ Successfully sent reply: {json.dumps(result, indent=2, ensure_ascii=False)}")
        return True
    except KworkBridgeError as e:
        logger.error(f"❌ Failed to send reply: {e}")
        return False


async def test_session_refresh() -> None:
    """Тестирует автоматическое обновление сессии."""
    try:
        logger.info("🔍 Testing session refresh functionality...")
        
        # Создаем мост с очень коротким временем жизни сессии (1 секунда)
        bridge = KworkNodeBridge(session_ttl=1)
        
        # Даем время на истечение сессии
        logger.info("Waiting for session to expire...")
        await asyncio.sleep(2)
        
        # Пытаемся получить заказы - должен произойти refresh сессии
        logger.info("Fetching orders after session expiration...")
        orders = bridge.get_orders(limit=1)
        
        if orders:
            logger.info(f"✅ Successfully fetched {len(orders)} orders after session refresh")
            return True
        
        logger.warning("No orders received after session refresh")
        return False
        
    except Exception as e:
        logger.error(f"❌ Session refresh test failed: {e}")
        return False
    finally:
        if 'bridge' in locals():
            bridge._stop_process()

async def main() -> None:
    """Основная функция тестирования."""
    # Создаем директорию для логов
    os.makedirs("logs", exist_ok=True)
    
    logger.info("🚀 Starting Kwork Bridge Test")
    logger.info("-" * 50)
    
    # Проверяем переменные окружения
    required_vars = ["KWORK_USERNAME", "KWORK_PASSWORD"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"❌ Отсутствуют обязательные переменные окружения: {', '.join(missing_vars)}")
        logger.info("\nПожалуйста, установите их в файле .env или в переменных окружения:")
        logger.info("KWORK_USERNAME=ваш_логин")
        logger.info("KWORK_PASSWORD=ваш_пароль")
        if not os.getenv("KWORK_PINCODE"):
            logger.info("KWORK_PINCODE=  # опционально, если включена 2FA")
        return
    
    # Выводим информацию о подключении (без пароля)
    logger.info(f"🔑 Используется аккаунт: {os.getenv('KWORK_USERNAME')}")
    if os.getenv('KWORK_PINCODE'):
        logger.info("🔒 Используется 2FA с пин-кодом")
    
    # Проверяем наличие Node.js
    try:
        import subprocess
        subprocess.run(["node", "--version"], capture_output=True, check=True)
    except (subprocess.SubprocessError, FileNotFoundError):
        logger.error("❌ Node.js is not installed or not in PATH")
        logger.info("\nPlease install Node.js from https://nodejs.org/")
        return
    
    # Инициализируем мост
    bridge = None
    try:
        bridge = KworkNodeBridge()
        
        # Запускаем тесты
        logger.info("🔍 Running tests...\n")
        
        # Базовые тесты
        await test_connection(bridge)
        print()
        
        if await test_get_orders(bridge):
            print()
            # Тестируем отправку отклика, если нужно
            if len(sys.argv) > 1:
                order_id = sys.argv[1]
                await test_send_reply(bridge, order_id)
        
        # Тестируем обновление сессии
        print("\n" + "="*50)
        logger.info("🚀 Testing session refresh...")
        await test_session_refresh()
        
        logger.info("\n✅ All tests completed")
        
    except KworkBridgeError as e:
        logger.error(f"❌ Kwork Bridge Error: {e}")
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}", exc_info=True)
    finally:
        if bridge:
            bridge._stop_process()

if __name__ == "__main__":
    asyncio.run(main())
