"""
Модуль для управления прокси-соединениями и ротацией.
"""
import json
import random
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
import requests
from loguru import logger

class ProxyManager:
    def __init__(self, config_path: str = "config/proxies.json"):
        """
        Инициализация менеджера прокси.
        
        Args:
            config_path: Путь к файлу конфигурации прокси
        """
        self.config_path = Path(config_path)
        self.proxies: List[Dict[str, Any]] = []
        self.settings: Dict[str, Any] = {}
        self._load_config()
        self._validate_proxies()

    def _load_config(self) -> None:
        """Загрузка конфигурации прокси из файла."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                self.proxies = config.get('proxies', [])
                self.settings = config.get('settings', {})
                
                # Инициализация метрик для каждого прокси
                for proxy in self.proxies:
                    proxy.setdefault('enabled', True)
                    proxy.setdefault('lastUsed', None)
                    proxy.setdefault('successRate', 0)
                    proxy.setdefault('timeout', 5000)
                    
        except FileNotFoundError:
            logger.warning(f"Proxy config file not found: {self.config_path}")
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in proxy config: {self.config_path}")

    def _save_config(self) -> None:
        """Сохранение конфигурации прокси в файл."""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'proxies': self.proxies,
                    'settings': self.settings
                }, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save proxy config: {e}")

    def _validate_proxy(self, proxy: Dict[str, Any]) -> bool:
        """
        Проверка работоспособности прокси.
        
        Args:
            proxy: Конфигурация прокси
            
        Returns:
            bool: True если прокси рабочий, иначе False
        """
        if not proxy.get('enabled', True):
            return False
            
        test_url = "http://httpbin.org/ip"
        proxies = {
            'http': self._format_proxy_url(proxy),
            'https': self._format_proxy_url(proxy)
        }
        
        try:
            start_time = time.time()
            response = requests.get(
                test_url,
                proxies=proxies,
                timeout=proxy.get('timeout', 10) / 1000
            )
            response.raise_for_status()
            
            # Обновляем метрики прокси
            proxy['lastUsed'] = time.time()
            proxy['successRate'] = min(100, (proxy.get('successRate', 0) + 1) * 1.1)
            proxy['responseTime'] = int((time.time() - start_time) * 1000)  # мс
            
            return True
            
        except Exception as e:
            logger.warning(f"Proxy {proxy.get('host')} validation failed: {e}")
            proxy['successRate'] = max(0, (proxy.get('successRate', 0) * 0.9) - 10)
            if proxy['successRate'] < 20:  # Отключаем проблемные прокси
                proxy['enabled'] = False
            return False

    def _validate_proxies(self) -> None:
        """Проверка всех прокси из конфига."""
        for proxy in self.proxies:
            if proxy.get('enabled', True):
                self._validate_proxy(proxy)
        self._save_config()

    def _format_proxy_url(self, proxy: Dict[str, Any]) -> str:
        """
        Форматирование URL прокси.
        
        Args:
            proxy: Конфигурация прокси
            
        Returns:
            str: Отформатированный URL прокси
        """
        protocol = proxy.get('protocol', 'http')
        host = proxy['host']
        port = proxy['port']
        
        if 'auth' in proxy:
            username = proxy['auth'].get('username', '')
            password = proxy['auth'].get('password', '')
            return f"{protocol}://{username}:{password}@{host}:{port}"
        return f"{protocol}://{host}:{port}"

    def get_random_proxy(self) -> Optional[Dict[str, str]]:
        """
        Получение случайного рабочего прокси.
        
        Returns:
            Optional[Dict[str, str]]: Конфигурация прокси или None, если нет рабочих
        """
        active_proxies = [
            p for p in self.proxies 
            if p.get('enabled', True)
        ]
        
        if not active_proxies:
            logger.warning("No active proxies available")
            return None
            
        # Выбираем прокси с учетом рейтинга
        weights = [p.get('successRate', 10) for p in active_proxies]
        selected = random.choices(active_proxies, weights=weights, k=1)[0]
        
        return {
            'http': self._format_proxy_url(selected),
            'https': self._format_proxy_url(selected)
        }

    def report_success(self, proxy_url: str) -> None:
        """
        Отметить успешное использование прокси.
        
        Args:
            proxy_url: URL прокси
        """
        for proxy in self.proxies:
            if self._format_proxy_url(proxy) in (proxy_url, proxy_url.replace('https://', 'http://')):
                proxy['successRate'] = min(100, (proxy.get('successRate', 0) + 1) * 1.1)
                proxy['lastUsed'] = time.time()
                break
        self._save_config()

    def report_failure(self, proxy_url: str) -> None:
        """
        Отметить неудачное использование прокси.
        
        Args:
            proxy_url: URL прокси
        """
        for proxy in self.proxies:
            if self._format_proxy_url(proxy) in (proxy_url, proxy_url.replace('https://', 'http://')):
                proxy['successRate'] = max(0, (proxy.get('successRate', 0) * 0.9) - 10)
                if proxy['successRate'] < 20:  # Отключаем проблемные прокси
                    proxy['enabled'] = False
                break
        self._save_config()

    def enable_all_proxies(self) -> None:
        """Активировать все прокси."""
        for proxy in self.proxies:
            proxy['enabled'] = True
        self._save_config()
        logger.info("All proxies have been enabled")

    def get_proxy_stats(self) -> Dict[str, Any]:
        """
        Получить статистику по прокси.
        
        Returns:
            Dict[str, Any]: Статистика
        """
        return {
            'total': len(self.proxies),
            'enabled': sum(1 for p in self.proxies if p.get('enabled', False)),
            'disabled': sum(1 for p in self.proxies if not p.get('enabled', True)),
            'avg_success_rate': sum(p.get('successRate', 0) for p in self.proxies) / max(1, len(self.proxies)),
            'last_updated': time.time()
        }
