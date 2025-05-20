"""
Модуль для решения капчи с использованием Puppeteer и сервисов антикапчи.
"""
import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Dict, Optional, Any
from loguru import logger

# Настройка логирования
logging.basicConfig(level=logging.INFO)

class CaptchaSolver:
    """Класс для решения капч с использованием различных сервисов."""
    
    def __init__(self, service: str = '2captcha', api_key: Optional[str] = None):
        """
        Инициализация решателя капч.
        
        Args:
            service: Сервис для решения капч (2captcha, anti-captcha, capmonster)
            api_key: API ключ сервиса
        """
        self.service = service.lower()
        self.api_key = api_key or os.getenv(f'{service.upper()}_API_KEY')
        self.supported_services = ['2captcha', 'anti-captcha', 'capmonster']
        
        if not self.api_key:
            logger.warning(f"No API key provided for {service}. Captcha solving will be disabled.")
        
        # Директория для хранения сессий
        self.sessions_dir = Path('data/sessions')
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
    
    async def solve_recaptcha(self, site_key: str, page_url: str, **kwargs) -> Optional[Dict[str, Any]]:
        """
        Решение reCAPTCHA.
        
        Args:
            site_key: Ключ сайта reCAPTCHA
            page_url: URL страницы с капчей
            **kwargs: Дополнительные параметры
            
        Returns:
            Optional[Dict[str, Any]]: Результат решения или None в случае ошибки
        """
        if not self.api_key:
            logger.error("No API key provided for captcha solving")
            return None
            
        try:
            if self.service == '2captcha':
                return await self._solve_2captcha(
                    method='userrecaptcha',
                    sitekey=site_key,
                    pageurl=page_url,
                    **kwargs
                )
            elif self.service == 'anti-captcha':
                return await self._solve_anti_captcha(
                    type='NoCaptchaTaskProxyless',
                    websiteURL=page_url,
                    websiteKey=site_key,
                    **kwargs
                )
            elif self.service == 'capmonster':
                return await self._solve_capmonster(
                    type='NoCaptchaTaskProxyless',
                    websiteURL=page_url,
                    websiteKey=site_key,
                    **kwargs
                )
            else:
                logger.error(f"Unsupported captcha service: {self.service}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to solve reCAPTCHA: {e}")
            return None
    
    async def _solve_2captcha(self, **params) -> Optional[Dict[str, Any]]:
        """Решить капчу через 2captcha.com."""
        from twocaptcha import TwoCaptcha
        
        try:
            solver = TwoCaptcha(self.api_key)
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: solver.solve_captcha(**params)
            )
            return {'success': True, 'code': result['code']}
        except Exception as e:
            logger.error(f"2Captcha error: {e}")
            return None
    
    async def _solve_anti_captcha(self, **params) -> Optional[Dict[str, Any]]:
        """Решить капчу через anti-captcha.com."""
        from python3_anticaptcha import NoCaptchaTaskProxyless
        
        try:
            solver = NoCaptchaTaskProxyless.NoCaptchaTaskProxyless(
                anticaptcha_key=self.api_key
            )
            result = solver.captcha_handler(**params)
            
            if result['errorId'] == 0:
                return {'success': True, 'code': result['solution']['gRecaptchaResponse']}
            else:
                logger.error(f"Anti-Captcha error: {result['errorCode']} - {result['errorDescription']}")
                return None
        except Exception as e:
            logger.error(f"Anti-Captcha error: {e}")
            return None
    
    async def _solve_capmonster(self, **params) -> Optional[Dict[str, Any]]:
        """Решить капчу через capmonster.cloud."""
        import capmonster_cloud
        
        try:
            client = capmonster_cloud.Client(self.api_key)
            result = await client.solve_captcha('recaptchaV2Enterprise', {
                'websiteURL': params['websiteURL'],
                'websiteKey': params['websiteKey'],
                'isInvisible': params.get('isInvisible', False)
            })
            return {'success': True, 'code': result['gRecaptchaResponse']}
        except Exception as e:
            logger.error(f"CapMonster error: {e}")
            return None
    
    def save_session(self, session_id: str, data: Dict[str, Any]) -> None:
        """
        Сохранение сессии.
        
        Args:
            session_id: Идентификатор сессии
            data: Данные сессии
        """
        session_file = self.sessions_dir / f"{session_id}.json"
        try:
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"Session {session_id} saved successfully")
        except Exception as e:
            logger.error(f"Failed to save session {session_id}: {e}")
    
    def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Загрузка сессии.
        
        Args:
            session_id: Идентификатор сессии
            
        Returns:
            Optional[Dict[str, Any]]: Данные сессии или None, если не найдены
        """
        session_file = self.sessions_dir / f"{session_id}.json"
        if not session_file.exists():
            return None
            
        try:
            with open(session_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load session {session_id}: {e}")
            return None
    
    def clear_session(self, session_id: str) -> bool:
        """
        Удаление сессии.
        
        Args:
            session_id: Идентификатор сессии
            
        Returns:
            bool: True если успешно, иначе False
        """
        session_file = self.sessions_dir / f"{session_id}.json"
        try:
            if session_file.exists():
                session_file.unlink()
                logger.info(f"Session {session_id} cleared successfully")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to clear session {session_id}: {e}")
            return False
