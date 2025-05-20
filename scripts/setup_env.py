"""
Скрипт для настройки окружения Jarvis MVP.
"""
import os
import shutil
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.prompt import Prompt, Confirm

app = typer.Typer()
console = Console()

def check_env_file() -> bool:
    """Проверяет существование .env файла."""
    env_file = Path(".env")
    example_env = Path(".env.example")
    
    if not env_file.exists():
        if Confirm.ask(f"Файл .env не найден. Создать из {example_env}?"):
            shutil.copy(example_env, env_file)
            console.print(f"✅ Создан файл .env на основе {example_env}", style="green")
            return True
        return False
    return True

def setup_kwork_token():
    """Настройка Kwork токена."""
    console.print("\n[bold]Настройка Kwork API[/bold]")
    console.print("-" * 30)
    
    token = Prompt.ask(
        "Введите ваш Kwork API токен (нажмите Enter, чтобы пропустить)",
        default=""
    )
    
    if token and token != "your_kwork_token_here":
        update_env_file("KWORK_TOKEN", token)
        console.print("✅ Kwork токен обновлен", style="green")
    else:
        console.print("ℹ️ Используется существующий или стандартный токен", style="yellow")
    
    # Установка интервала опроса
    interval = Prompt.ask(
        "Интервал опроса Kwork (секунды, по умолчанию 300)",
        default="300"
    )
    
    try:
        interval = int(interval)
        if interval < 60:
            console.print("⚠️ Интервал слишком мал, установлено 60 секунд", style="yellow")
            interval = 60
        update_env_file("POLL_INTERVAL", str(interval))
    except ValueError:
        console.print("⚠️ Неверный формат, используется значение по умолчанию (300)", style="yellow")
        update_env_file("POLL_INTERVAL", "300")

def setup_telegram():
    """Настройка Telegram бота."""
    console.print("\n[bold]Настройка Telegram бота[/bold]")
    console.print("-" * 30)
    
    token = Prompt.ask(
        "Введите токен вашего Telegram бота (нажмите Enter, чтобы пропустить)",
        default=os.getenv("TELEGRAM_BOT_TOKEN", "")
    )
    
    if token and token != "your_telegram_bot_token":
        update_env_file("TELEGRAM_BOT_TOKEN", token)
        
        chat_id = Prompt.ask(
            "Введите ваш Chat ID (нажмите Enter, чтобы пропустить)",
            default=os.getenv("TELEGRAM_CHAT_ID", "")
        )
        
        if chat_id and chat_id != "your_chat_id":
            update_env_file("TELEGRAM_CHAT_ID", chat_id)
            console.print("✅ Настройки Telegram обновлены", style="green")
        else:
            console.print("⚠️ Chat ID не обновлен", style="yellow")
    else:
        console.print("⚠️ Токен бота не обновлен", style="yellow")

def update_env_file(key: str, value: str):
    """Обновляет или добавляет переменную в .env файл."""
    env_file = Path(".env")
    
    # Читаем существующие переменные
    if env_file.exists():
        with open(env_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    else:
        lines = []
    
    # Ищем и обновляем переменную
    key_found = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f"{key}={value}\n"
            key_found = True
            break
    
    # Если переменная не найдена, добавляем в конец
    if not key_found:
        lines.append(f"{key}={value}\n")
    
    # Записываем обратно в файл
    with open(env_file, 'w', encoding='utf-8') as f:
        f.writelines(lines)

def create_logs_directory():
    """Создает директорию для логов, если её нет."""
    logs_dir = Path("logs")
    if not logs_dir.exists():
        logs_dir.mkdir()
        console.print(f"✅ Создана директория {logs_dir}", style="green")

@app.command()
def setup():
    """Основная функция настройки окружения."""
    console.print("🛠 [bold]Настройка окружения Jarvis MVP[/bold]")
    console.print("=" * 40 + "\n")
    
    # Проверяем и создаем .env файл при необходимости
    if not check_env_file():
        console.print("❌ Для продолжения требуется .env файл", style="red")
        return
    
    # Настраиваем Kwork
    setup_kwork_token()
    
    # Настраиваем Telegram
    setup_telegram()
    
    # Создаем директорию для логов
    create_logs_directory()
    
    console.print("\n✅ [bold green]Настройка окружения завершена![/bold green]")
    console.print("\nЗапустите бота командой:")
    console.print("  python scripts/manage_kwork.py start\n", style="bold")

if __name__ == "__main__":
    app()
