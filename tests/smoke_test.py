"""
Smoke-тесты для проверки работоспособности API после деплоя.
"""
import os
import sys
import json
import time
import requests
from pathlib import Path
from typing import Dict, Any, Optional

# Добавляем корень проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Конфигурация
BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api")
AUTH_URL = os.getenv("AUTH_URL", f"{BASE_URL}/auth")
CI_USERNAME = os.getenv("CI_USERNAME")
CI_PASSWORD = os.getenv("CI_PASSWORD")
TIMEOUT = 10  # seconds

class TestFailedError(Exception):
    """Исключение для ошибок тестирования."""
    pass

class SmokeTester:
    """Класс для выполнения smoke-тестов API."""
    
    def __init__(self):
        self.session = requests.Session()
        self.access_token = None
        self.refresh_token = None
        self.test_results = []
    
    def log_test(self, name: str, success: bool, message: str = ""):
        """Логирует результат теста."""
        status = "✅ PASS" if success else "❌ FAIL"
        log_message = f"{status} - {name}"
        if message:
            log_message += f" | {message}"
        print(log_message)
        self.test_results.append((name, success, message))
    
    def run_test(self, name: str, test_func):
        """Запускает тест и обрабатывает исключения."""
        try:
            test_func()
            self.log_test(name, True)
            return True
        except Exception as e:
            self.log_test(name, False, str(e))
            return False
    
    def test_api_health(self):
        """Проверяет доступность API."""
        response = self.session.get(
            f"{BASE_URL}/health",
            timeout=TIMEOUT
        )
        response.raise_for_status()
        data = response.json()
        if data.get("status") != "ok":
            raise TestFailedError(f"Неверный статус API: {data}")
    
    def test_authentication(self):
        """Тестирует аутентификацию и получение токенов."""
        # Получение токенов
        response = self.session.post(
            f"{AUTH_URL}/token",
            data={
                "username": CI_USERNAME,
                "password": CI_PASSWORD
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=TIMEOUT
        )
        response.raise_for_status()
        
        tokens = response.json()
        self.access_token = tokens.get("access_token")
        self.refresh_token = tokens.get("refresh_token")
        
        if not self.access_token or not self.refresh_token:
            raise TestFailedError("Не удалось получить токены доступа")
        
        # Проверка доступа с токеном
        response = self.session.get(
            f"{BASE_URL}/reviews/recent",
            headers={"Authorization": f"Bearer {self.access_token}"},
            timeout=TIMEOUT
        )
        response.raise_for_status()
    
    def test_token_refresh(self):
        """Тестирует обновление токена доступа."""
        if not self.refresh_token:
            raise TestFailedError("Отсутствует refresh token")
            
        response = self.session.post(
            f"{AUTH_URL}/refresh",
            json={"refresh_token": self.refresh_token},
            headers={"Content-Type": "application/json"},
            timeout=TIMEOUT
        )
        response.raise_for_status()
        
        tokens = response.json()
        if not tokens.get("access_token"):
            raise TestFailedError("Не удалось обновить токен доступа")
    
    def test_protected_endpoints(self):
        """Тестирует защищенные эндпоинты."""
        if not self.access_token:
            raise TestFailedError("Отсутствует access token")
        
        endpoints = [
            ("GET", f"{BASE_URL}/reviews/recent"),
            # Добавьте другие защищенные эндпоинты
        ]
        
        for method, url in endpoints:
            response = self.session.request(
                method,
                url,
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=TIMEOUT
            )
            response.raise_for_status()
    
    def run_all_tests(self) -> bool:
        """Запускает все тесты и возвращает общий результат."""
        print("🚀 Запуск smoke-тестов...\n")
        
        tests = [
            ("Проверка доступности API", self.test_api_health),
            ("Аутентификация и получение токенов", self.test_authentication),
            ("Обновление токена доступа", self.test_token_refresh),
            ("Проверка защищенных эндпоинтов", self.test_protected_endpoints),
        ]
        
        all_passed = True
        for name, test_func in tests:
            if not self.run_test(name, test_func):
                all_passed = False
        
        # Вывод сводки
        print("\n📊 Результаты тестирования:")
        print("=" * 50)
        for name, success, message in self.test_results:
            status = "✅" if success else "❌"
            print(f"{status} {name}")
            if message and not success:
                print(f"   Ошибка: {message}")
        
        print("\n" + ("✅ Все тесты пройдены успешно!" if all_passed else "❌ Обнаружены ошибки!"))
        return all_passed


def main():
    """Основная функция для запуска тестов."""
    # Проверка обязательных переменных окружения
    required_vars = ["CI_USERNAME", "CI_PASSWORD"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"Ошибка: Не заданы обязательные переменные окружения: {', '.join(missing_vars)}")
        print("Пожалуйста, установите их в файле .env.staging")
        return 1
    
    # Запуск тестов
    tester = SmokeTester()
    success = tester.run_all_tests()
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
