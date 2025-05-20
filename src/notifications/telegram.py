"""
Модуль для работы с Telegram API.
"""
import logging
from typing import Optional, Dict, Any, List, Union

import requests

logger = logging.getLogger(__name__)

class Bot:
    """Класс для работы с Telegram Bot API."""
    
    BASE_URL = "https://api.telegram.org/bot{token}/{method}"
    
    def __init__(self, token: str):
        """
        Инициализация бота.
        
        Args:
            token: Токен бота
        """
        self.token = token
    
    def _make_request(self, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Выполняет запрос к Telegram API.
        
        Args:
            method: Название метода API
            params: Параметры запроса
            
        Returns:
            Ответ от API в виде словаря
        """
        url = self.BASE_URL.format(token=self.token, method=method)
        try:
            response = requests.post(url, json=params or {})
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при запросе к Telegram API: {e}")
            return {"ok": False, "description": str(e)}
    
    def send_message(
        self,
        chat_id: Union[int, str],
        text: str,
        parse_mode: Optional[str] = None,
        disable_web_page_preview: bool = True,
        disable_notification: bool = False,
        reply_to_message_id: Optional[int] = None,
        reply_markup: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Отправляет сообщение.
        
        Args:
            chat_id: ID чата
            text: Текст сообщения
            parse_mode: Форматирование (Markdown или HTML)
            disable_web_page_preview: Отключить предпросмотр ссылок
            disable_notification: Отключить уведомление
            reply_to_message_id: ID сообщения для ответа
            reply_markup: Дополнительные параметры разметки
            
        Returns:
            Ответ от API
        """
        params = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": disable_web_page_preview,
            "disable_notification": disable_notification,
        }
        
        if parse_mode:
            params["parse_mode"] = parse_mode
        if reply_to_message_id:
            params["reply_to_message_id"] = reply_to_message_id
        if reply_markup:
            params["reply_markup"] = reply_markup
            
        return self._make_request("sendMessage", params)
    
    def get_me(self) -> Dict[str, Any]:
        """
        Получает информацию о боте.
        
        Returns:
            Информация о боте
        """
        return self._make_request("getMe")
