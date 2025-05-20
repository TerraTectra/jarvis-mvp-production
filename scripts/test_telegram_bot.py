"""
Test script for the Telegram bot.
This script tests the basic functionality of the Telegram bot.
"""
import asyncio
import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from dotenv import load_dotenv
from telegram import Bot

# Load environment variables
load_dotenv()

# Get Telegram bot token and chat ID from environment variables
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
ADMIN_IDS = os.getenv("TELEGRAM_ADMIN_ID", "").split(",") if os.getenv("TELEGRAM_ADMIN_ID") else []

async def test_send_message():
    """Test sending a message to the Telegram bot."""
    if not BOT_TOKEN or BOT_TOKEN == "your_telegram_bot_token":
        print("❌ Error: TELEGRAM_BOT_TOKEN is not set in .env file")
        return
    
    if not CHAT_ID or CHAT_ID == "your_chat_id":
        print("❌ Error: TELEGRAM_CHAT_ID is not set in .env file")
        return
    
    try:
        bot = Bot(token=BOT_TOKEN)
        
        # Test sending a message
        message = "🔄 *Тестовое сообщение от Jarvis MVP*\n\n" \
                 "Это тестовое сообщение для проверки работы бота.\n" \
                 "Если вы видите это сообщение, значит бот работает корректно."
        
        await bot.send_message(
            chat_id=CHAT_ID,
            text=message,
            parse_mode="Markdown"
        )
        
        print("✅ Тестовое сообщение успешно отправлено!")
        
    except Exception as e:
        print(f"❌ Ошибка при отправке сообщения: {e}")

async def main():
    """Main function to run the test."""
    print("🚀 Запуск теста Telegram бота...\n")
    
    print(f"🔑 BOT_TOKEN: {'установлен' if BOT_TOKEN and BOT_TOKEN != 'your_telegram_bot_token' else 'не установлен'}")
    print(f"💬 CHAT_ID: {CHAT_ID if CHAT_ID and CHAT_ID != 'your_chat_id' else 'не установлен'}")
    print(f"👑 ADMIN_IDS: {ADMIN_IDS if ADMIN_IDS and ADMIN_IDS[0] != 'your_admin_id' else 'не установлены'}\n")
    
    await test_send_message()

if __name__ == "__main__":
    asyncio.run(main())
