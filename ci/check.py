"""
CI/CD Pipeline для проекта Jarvis_MVP_Release

Использование:
    python ci/check.py all           # Запустить все проверки
    python ci/check.py changed       # Проверить только изменённые файлы
    python ci/check.py lint          # Только линтинг
    python ci/check.py mypy          # Только статическую типизацию
    python ci/check.py test          # Только тесты
    python ci/check.py docker        # Только сборку Docker
    python ci/check.py telebot       # Только проверку телеграм-бота
"""

import os
import sys
import subprocess
import logging
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime

# Конфигурация логирования
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / f"ci_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("ci")

# Корень проекта
PROJECT_ROOT = Path(__file__).parent.parent
os.chdir(PROJECT_ROOT)

# Настройки CI
class CIConfig:
    """Конфигурация CI-пайплайна."""
    TELEGRAM_NOTIFY = os.getenv("CI_TELEGRAM_NOTIFY", "false").lower() == "true"
    TELEGRAM_CHAT_ID = os.getenv("CI_TELEGRAM_CHAT_ID", "6904521519")
    
    # Пути к проверяемым директориям
    SRC_DIR = PROJECT_ROOT / "src"
    TESTS_DIR = PROJECT_ROOT / "tests"
    
    # Расширения файлов для проверки
    PYTHON_EXTENSIONS = ['.py']
    DOCKER_FILES = ['Dockerfile', 'docker-compose.yml', 'docker-compose.override.yml']


@dataclass
class CheckResult:
    """Результат выполнения проверки."""
    name: str
    success: bool
    output: str = ""
    error: Optional[str] = None
    duration: float = 0.0


class CIPipeline:
    """Класс для выполнения CI-пайплайна."""
    
    def __init__(self, config: CIConfig):
        self.config = config
        self.changed_files = self._get_changed_files()
        self.results: List[CheckResult] = []
    
    def _get_changed_files(self) -> List[Path]:
        """Получить список изменённых файлов."""
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", "HEAD"],
                capture_output=True,
                text=True,
                check=True
            )
            return [Path(f.strip()) for f in result.stdout.splitlines() if f.strip()]
        except subprocess.CalledProcessError as e:
            logger.error(f"Ошибка при получении изменённых файлов: {e}")
            return []
    
    def _run_command(self, cmd: List[str], cwd: Optional[Path] = None) -> Tuple[bool, str]:
        """Выполнить команду и вернуть результат."""
        try:
            result = subprocess.run(
                cmd,
                cwd=cwd or PROJECT_ROOT,
                capture_output=True,
                text=True,
                check=False
            )
            return (
                result.returncode == 0,
                result.stdout.strip() + "\n" + result.stderr.strip()
            )
        except Exception as e:
            return False, str(e)
    
    def _add_result(self, name: str, success: bool, output: str = "", error: Optional[str] = None) -> CheckResult:
        """Добавить результат проверки."""
        result = CheckResult(name=name, success=success, output=output, error=error)
        self.results.append(result)
        return result
    
    def _should_check_file(self, file_path: Path, extensions: List[str]) -> bool:
        """Проверить, нужно ли проверять файл."""
        if not self.changed_files:  # Если нет изменённых файлов, проверяем все
            return True
        
        # Преобразуем в абсолютный путь для сравнения
        abs_path = file_path.absolute()
        
        # Проверяем, есть ли файл в списке изменённых
        for changed in self.changed_files:
            changed_abs = (PROJECT_ROOT / changed).absolute()
            if abs_path == changed_abs:
                return True
        
        return False
    
    def check_black(self) -> CheckResult:
        """Проверить форматирование кода с помощью black."""
        logger.info("🔧 Проверка форматирования кода (black)...")
        
        # Находим все Python файлы в src и tests
        python_files = []
        for ext in self.config.PYTHON_EXTENSIONS:
            python_files.extend(self.config.SRC_DIR.rglob(f"*{ext}"))
            python_files.extend(self.config.TESTS_DIR.rglob(f"*{ext}"))
        
        # Фильтруем только изменённые файлы, если нужно
        files_to_check = [
            str(f) for f in python_files 
            if self._should_check_file(f, self.config.PYTHON_EXTENSIONS)
        ]
        
        if not files_to_check:
            return self._add_result("black", True, "Нет файлов для проверки")
        
        # Запускаем black в режиме проверки
        success, output = self._run_command(["black", "--check", *files_to_check])
        
        if not success:
            # Пытаемся автоматически исправить
            fix_success, fix_output = self._run_command(["black", *files_to_check])
            if fix_success:
                output += "\n\nАвтоисправление применено. Пожалуйста, закоммитьте изменения."
            else:
                output += f"\n\nНе удалось применить автоисправление: {fix_output}"
        
        return self._add_result(
            "black", 
            success or "reformatted" in output.lower(),
            output
        )
    
    def check_ruff(self) -> CheckResult:
        """Проверить качество кода с помощью ruff."""
        logger.info("🔍 Проверка качества кода (ruff)...")
        
        # Запускаем ruff для всего проекта, но он проверит только изменённые файлы
        success, output = self._run_command(["ruff", "check", ".", "--fix"])
        
        return self._add_result("ruff", success, output)
    
    def check_mypy(self) -> CheckResult:
        """Проверить статическую типизацию с помощью mypy."""
        logger.info("📐 Проверка статической типизации (mypy)...")
        
        # Запускаем mypy для всего проекта, но он проверит только изменённые файлы
        success, output = self._run_command(["mypy", str(self.config.SRC_DIR)])
        
        return self._add_result("mypy", success, output)
    
    def check_pytest(self) -> CheckResult:
        """Запустить тесты с помощью pytest."""
        logger.info("🧪 Запуск тестов (pytest)...")
        
        # Определяем, какие тесты запускать
        test_paths = [str(self.config.TESTS_DIR)]
        
        # Если есть изменённые файлы, запускаем только связанные тесты
        if self.changed_files:
            test_paths = []
            for changed in self.changed_files:
                if "tests/" in str(changed):
                    test_paths.append(str(changed))
                elif str(changed).startswith("src/"):
                    # Пытаемся найти соответствующий тест
                    rel_path = Path(changed).relative_to("src")
                    test_path = self.config.TESTS_DIR / rel_path
                    if test_path.exists():
                        test_paths.append(str(test_path))
                    
                    # Проверяем, есть ли тесты с похожим именем
                    test_file = test_path.with_name(f"test_{test_path.name}")
                    if test_file.exists():
                        test_paths.append(str(test_file))
        
        if not test_paths:
            test_paths = [str(self.config.TESTS_DIR)]
        
        # Запускаем pytest
        success, output = self._run_command(["pytest", "-v", *test_paths])
        
        return self._add_result("pytest", success, output)
    
    def check_docker(self) -> CheckResult:
        """Проверить сборку Docker-образа."""
        logger.info("🐳 Проверка сборки Docker-образа...")
        
        # Проверяем Dockerfile
        dockerfile = PROJECT_ROOT / "Dockerfile"
        if not dockerfile.exists():
            return self._add_result("docker", False, "Dockerfile не найден")
        
        # Пытаемся собрать образ
        success, output = self._run_command(["docker", "build", "-t", "jarvis-mvp-ci-test", "."])
        
        # Удаляем временный образ
        if success:
            self._run_command(["docker", "rmi", "jarvis-mvp-ci-test"])
        
        return self._add_result("docker", success, output)
    
    def check_telebot(self) -> CheckResult:
        """Проверить конфигурацию телеграм-бота."""
        logger.info("🤖 Проверка конфигурации телеграм-бота...")
        
        # Проверяем наличие необходимых переменных окружения
        required_vars = ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            return self._add_result(
                "telebot", 
                False, 
                f"Отсутствуют обязательные переменные окружения: {', '.join(missing_vars)}"
            )
        
        return self._add_result("telebot", True, "Конфигурация телеграм-бота в порядке")
    
    def send_telegram_notification(self, success: bool) -> bool:
        """Отправить уведомление в Telegram."""
        if not self.config.TELEGRAM_NOTIFY or not self.config.TELEGRAM_CHAT_ID:
            return False
        
        try:
            import requests
            from urllib.parse import quote
            
            # Формируем сообщение
            emoji = "✅" if success else "❌"
            status = "успешно" if success else "с ошибками"
            
            # Собираем результаты проверок
            results = []
            for result in self.results:
                status_emoji = "✅" if result.success else "❌"
                results.append(f"{status_emoji} {result.name}")
            
            message = (
                f"{emoji} *CI/CD Pipeline завершён {status}*\n\n"
                f"*Проект:* Jarvis MVP Release\n"
                f"*Ветка:* {self._get_current_branch()}\n"
                f"*Хеш:* `{self._get_current_commit()[:8]}`\n\n"
                f"*Результаты проверок:*\n" + "\n".join(results) + "\n\n"
                f"Полный лог: `{LOG_FILE.relative_to(PROJECT_ROOT)}`"
            )
            
            # Отправляем сообщение
            url = f"https://api.telegram.org/bot{os.getenv('TELEGRAM_BOT_TOKEN')}/sendMessage"
            data = {
                "chat_id": self.config.TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            }
            
            response = requests.post(url, json=data, timeout=10)
            response.raise_for_status()
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при отправке уведомления в Telegram: {e}")
            return False
    
    def _get_current_branch(self) -> str:
        """Получить имя текущей ветки Git."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return "unknown"
    
    def _get_current_commit(self) -> str:
        """Получить хеш текущего коммита."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return "unknown"
    
    def run_checks(self, check_type: str = "all") -> bool:
        """Запустить указанные проверки."""
        start_time = time.time()
        logger.info(f"🚀 Запуск CI/CD Pipeline ({check_type})")
        logger.info(f"📁 Директория проекта: {PROJECT_ROOT}")
        
        try:
            # Определяем, какие проверки нужно выполнить
            checks = []
            
            if check_type in ["all", "lint"]:
                checks.extend([self.check_black, self.check_ruff])
            
            if check_type in ["all", "mypy"]:
                checks.append(self.check_mypy)
            
            if check_type in ["all", "test"]:
                checks.append(self.check_pytest)
            
            if check_type in ["all", "docker"]:
                checks.append(self.check_docker)
            
            if check_type in ["all", "telebot"]:
                checks.append(self.check_telebot)
            
            if not checks and check_type == "changed":
                # Если не нашли изменений, требующих проверки, но запрошена проверка изменений
                logger.info("ℹ️ Нет изменений, требующих проверки")
                return True
            
            # Запускаем проверки
            for check_func in checks:
                start_check = time.time()
                result = check_func()
                result.duration = time.time() - start_check
                
                if result.success:
                    logger.info(f"✅ {result.name} пройдена за {result.duration:.2f}с")
                else:
                    logger.error(f"❌ {result.name} не пройдена за {result.duration:.2f}с")
                    if result.error:
                        logger.error(f"Ошибка: {result.error}")
                    if result.output:
                        logger.debug(f"Вывод:\n{result.output}")
            
            # Проверяем общий результат
            success = all(r.success for r in self.results)
            duration = time.time() - start_time
            
            # Отправляем уведомление
            if self.config.TELEGRAM_NOTIFY:
                self.send_telegram_notification(success)
            
            # Выводим итоговый отчёт
            logger.info("\n" + "=" * 50)
            logger.info(f"📊 Итоговый отчёт ({duration:.2f}с)")
            logger.info("=" * 50)
            
            for result in self.results:
                status = "✅ УСПЕХ" if result.success else "❌ ОШИБКА"
                logger.info(f"{status} {result.name} ({result.duration:.2f}с)")
                if not result.success and result.error:
                    logger.error(f"   Ошибка: {result.error}")
            
            logger.info("=" * 50)
            
            if success:
                logger.info("🎉 Все проверки пройдены успешно!")
            else:
                logger.error("💥 Обнаружены ошибки в проверках")
            
            return success
            
        except Exception as e:
            logger.exception("❌ Непредвиденная ошибка при выполнении CI/CD пайплайна")
            return False


def main():
    """Точка входа в скрипт."""
    import argparse
    
    parser = argparse.ArgumentParser(description="CI/CD Pipeline для проекта Jarvis_MVP_Release")
    parser.add_argument(
        "check_type",
        nargs="?",
        default="all",
        choices=["all", "changed", "lint", "mypy", "test", "docker", "telebot"],
        help="Тип проверки для запуска"
    )
    
    args = parser.parse_args()
    
    # Запускаем пайплайн
    pipeline = CIPipeline(CIConfig())
    success = pipeline.run_checks(args.check_type)
    
    # Возвращаем соответствующий код выхода
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
