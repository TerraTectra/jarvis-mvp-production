#!/usr/bin/env python3
"""
Jarvis MVP - Запуск системы
Использование:
  python run.py [режим] [опции]

Режимы:
  api       Запуск API-сервера (по умолчанию)
  auto      Запуск автоответчика
  bot       Запуск Telegram-бота
  all       Запуск всего сразу (в разных процессах)

Опции:
  --debug   Включить режим отладки
  --help    Показать это сообщение
"""
import os
import sys
import subprocess
import signal
from typing import List
import argparse

def run_command(command: List[str], name: str) -> subprocess.Popen:
    """Запускает команду в отдельном процессе."""
    print(f"🚀 Запускаю {name}...")
    return subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True
    )

def print_output(process: subprocess.Popen, prefix: str):
    """Выводит вывод процесса с префиксом."""
    if process.stdout:
        for line in process.stdout:
            print(f"[{prefix}] {line}", end='')

def main():
    # Парсинг аргументов командной строки
    parser = argparse.ArgumentParser(description='Jarvis MVP - Запуск системы')
    parser.add_argument('mode', nargs='?', default='api', 
                      choices=['api', 'auto', 'bot', 'all'],
                      help='Режим работы (по умолчанию: api)')
    parser.add_argument('--debug', action='store_true', help='Включить режим отладки')
    args = parser.parse_args()

    # Настройка окружения
    os.environ['PYTHONPATH'] = os.path.dirname(os.path.abspath(__file__))
    debug_flag = '--debug' if args.debug else ''

    processes = []

    try:
        if args.mode in ['api', 'all']:
            processes.append(run_command(
                [sys.executable, '-m', 'src.main', debug_flag],
                'API-сервер'
            ))

        if args.mode in ['auto', 'all']:
            processes.append(run_command(
                [sys.executable, '-m', 'src.automation.auto_responder', debug_flag],
                'Автоответчик'
            ))

        if args.mode in ['bot', 'all']:
            processes.append(run_command(
                [sys.executable, '-m', 'src.bot.telegram_bot', debug_flag],
                'Telegram-бот'
            ))

        # Вывод логов всех процессов
        while True:
            for process in processes:
                if process.poll() is not None:
                    print(f"❌ Процесс завершился с кодом {process.returncode}")
                    processes.remove(process)
                    if not processes:
                        return
            
            for process in processes:
                print_output(process, process.args[2])

    except KeyboardInterrupt:
        print("\n🛑 Остановка всех процессов...")
        for process in processes:
            if process.poll() is None:
                process.terminate()
        sys.exit(0)

if __name__ == "__main__":
    main()
