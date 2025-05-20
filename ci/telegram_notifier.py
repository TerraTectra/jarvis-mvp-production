#!/usr/bin/env python3
"""
Telegram Notifier for CI/CD Pipeline

This module provides functionality to send notifications to Telegram
about the status of CI/CD pipeline steps.
"""

import os
import sys
import json
import logging
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List, Union, Tuple
import requests
from datetime import datetime
from functools import wraps
import threading
from queue import Queue

# Global queue for handling bot updates
update_queue = Queue()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('ci.telegram_notifier')

class TelegramNotifier:
    """Handle sending notifications to Telegram with interactive buttons."""
    
    def __init__(self, token: str = None, chat_id: str = None, enabled: bool = None):
        """Initialize the Telegram notifier with interactive features.
        
        Args:
            token: Telegram bot token
            chat_id: Telegram chat ID to send messages to
            enabled: Whether notifications are enabled
        """
        self.token = token or os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = chat_id or os.getenv('TELEGRAM_CHAT_ID')
        self.enabled = (
            enabled if enabled is not None 
            else os.getenv('CI_TELEGRAM_NOTIFY', 'false').lower() == 'true'
        )
        self.base_url = f"https://api.telegram.org/bot{self.token}"
        self.logs_dir = Path("ci/logs")
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.last_message_id = None
        self.last_chat_id = None
        self.bot_thread = None
        self.running = False
        
        # Create symlink to latest log
        self.latest_log = self.logs_dir / "last_run.log"
        self._update_latest_log_symlink()
    
    def _update_latest_log_symlink(self) -> None:
        """Update the latest log symlink to point to the most recent log file."""
        try:
            # Find the most recent log file
            log_files = list(self.logs_dir.glob("pipeline_*.log"))
            if log_files:
                latest_log = max(log_files, key=os.path.getmtime)
                # Create or update symlink
                if self.latest_log.exists():
                    self.latest_log.unlink()
                self.latest_log.symlink_to(latest_log.absolute())
        except Exception as e:
            logger.error(f"Failed to update latest log symlink: {e}")
    
    def _ensure_latest_log(self) -> Optional[Path]:
        """Ensure the latest log symlink exists and return its path."""
        if not self.latest_log.exists() or not self.latest_log.is_symlink():
            self._update_latest_log_symlink()
        return self.latest_log if self.latest_log.exists() else None
    
    def _send_message(
        self, 
        text: str, 
        parse_mode: str = 'Markdown',
        reply_markup: Optional[Dict] = None,
        message_id: Optional[int] = None,
        chat_id: Optional[str] = None
    ) -> Tuple[bool, Optional[int]]:
        """Send or edit a message in the configured Telegram chat.
        
        Args:
            text: Message text to send
            parse_mode: Parse mode for the message (Markdown or HTML)
            reply_markup: Inline keyboard markup
            message_id: Message ID to edit (if None, sends a new message)
            chat_id: Chat ID to send the message to (uses default if None)
            
        Returns:
            Tuple of (success, message_id)
        """
        target_chat_id = chat_id or self.chat_id
        if not self.enabled or not self.token or not target_chat_id:
            logger.warning("Telegram notifications are disabled or not properly configured")
            return False, None
        
        try:
            if message_id is not None:
                # Edit existing message
                url = f"{self.base_url}/editMessageText"
                payload = {
                    'chat_id': target_chat_id,
                    'message_id': message_id,
                    'text': text,
                    'parse_mode': parse_mode,
                    'disable_web_page_preview': True
                }
                if reply_markup:
                    payload['reply_markup'] = reply_markup
            else:
                # Send new message
                url = f"{self.base_url}/sendMessage"
                payload = {
                    'chat_id': target_chat_id,
                    'text': text,
                    'parse_mode': parse_mode,
                    'disable_web_page_preview': True
                }
                if reply_markup:
                    payload['reply_markup'] = reply_markup
            
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            result = response.json()
            
            # Update last message info
            if result.get('ok', False):
                msg = result.get('result', {})
                msg_id = msg.get('message_id')
                self.last_message_id = msg_id
                self.last_chat_id = msg.get('chat', {}).get('id', target_chat_id)
                logger.info(f"Telegram message sent/edited: {text[:50]}...")
                return True, msg_id
            
            logger.error(f"Failed to send Telegram message: {result.get('description', 'Unknown error')}")
            return False, None
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False, None
    
    def _get_inline_keyboard(self) -> Dict:
        """Get the default inline keyboard for CI actions."""
        return {
            'inline_keyboard': [
                [
                    {'text': '▶️ Перезапустить CI', 'callback_data': 'restart_ci'},
                    {'text': '📄 Посмотреть лог', 'callback_data': 'view_log'}
                ]
            ]
        }
    
    def _get_log_keyboard(self) -> Dict:
        """Get the inline keyboard for log viewing actions."""
        return {
            'inline_keyboard': [
                [
                    {'text': '🔄 Обновить лог', 'callback_data': 'view_log'},
                    {'text': '🔙 Назад', 'callback_data': 'main_menu'}
                ]
            ]
        }
    
    def notify_step_start(self, step_name: str, description: str = "") -> bool:
        """Send a notification that a pipeline step has started.
        
        Args:
            step_name: Name of the step that started
            description: Optional description of the step
            
        Returns:
            bool: True if the notification was sent successfully
        """
        message = f"🔄 *[CI] {step_name}*"
        if description:
            message += f"\n_{description}_"
        
        # Add action buttons
        keyboard = self._get_inline_keyboard()
        success, _ = self._send_message(
            f"{message}\n\n_Выберите действие:_",
            reply_markup=keyboard
        )
        return success
    
    def notify_step_success(self, step_name: str, duration: float = None) -> bool:
        """Send a notification that a pipeline step completed successfully.
        
        Args:
            step_name: Name of the step that completed
            duration: Duration of the step in seconds
            
        Returns:
            bool: True if the notification was sent successfully
        """
        message = f"✅ *[CI] {step_name} PASSED*"
        if duration is not None:
            message += f" in {duration:.1f}s"
        
        # Update the existing message with success status
        if self.last_message_id:
            keyboard = self._get_inline_keyboard()
            success, _ = self._send_message(
                f"{message}\n\n_Выберите действие:_",
                reply_markup=keyboard,
                message_id=self.last_message_id
            )
            return success
        else:
            keyboard = self._get_inline_keyboard()
            success, _ = self._send_message(
                f"{message}\n\n_Выберите действие:_",
                reply_markup=keyboard
            )
            return success
    
    def notify_step_failure(
        self, 
        step_name: str, 
        error: str = None, 
        log_file: str = None,
        log_lines: int = 10
    ) -> bool:
        """Send a notification that a pipeline step failed.
        
        Args:
            step_name: Name of the step that failed
            error: Error message or description
            log_file: Path to the log file to include
            log_lines: Number of lines from the end of the log to include
            
        Returns:
            bool: True if the notification was sent successfully
        """
        message = f"❌ *[CI] {step_name} FAILED*"
        
        if error:
            message += f"\n\n*Error:*\n`{str(error)[:1000]}`"
        
        # Add log file content if provided
        log_content = ""
        if log_file:
            log_path = Path(log_file)
            if log_path.exists():
                try:
                    with open(log_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        log_content = ''.join(lines[-log_lines:])
                        
                    if len(lines) > log_lines:
                        log_content = f"...{len(lines) - log_lines} more lines...\n{log_content}"
                    
                    message += f"\n\n*Last {log_lines} lines of log:*\n```\n{log_content}\n```"
                except Exception as e:
                    logger.error(f"Failed to read log file {log_file}: {e}")
                    message += f"\n\n*Error reading log file:* {e}"
        
        # Update the existing message with failure status
        if self.last_message_id:
            keyboard = self._get_inline_keyboard()
            success, _ = self._send_message(
                f"{message}\n\n_Выберите действие:_",
                reply_markup=keyboard,
                message_id=self.last_message_id
            )
            return success
        else:
            keyboard = self._get_inline_keyboard()
            success, _ = self._send_message(
                f"{message}\n\n_Выберите действие:_",
                reply_markup=keyboard
            )
            return success
    
    def notify_pipeline_success(self, duration: float, steps: List[Dict[str, Any]]) -> bool:
        """Send a notification that the entire pipeline completed successfully.
        
        Args:
            duration: Total duration of the pipeline in seconds
            steps: List of step dictionaries with 'name' and 'duration' keys
            
        Returns:
            bool: True if the notification was sent successfully
        """
        message = f"🏆 *[CI] Pipeline SUCCESS* in {duration:.1f}s\n\n"
        message += "*Steps completed:*\n"
        
        for i, step in enumerate(steps, 1):
            step_name = step.get('name', f'Step {i}')
            step_duration = step.get('duration', 0)
            message += f"  {i}. ✅ {step_name} ({step_duration:.1f}s)\n"
        
        # Update the latest log symlink
        self._update_latest_log_symlink()
        
        # Add action buttons
        keyboard = self._get_inline_keyboard()
        success, _ = self._send_message(
            f"{message}\n\n_Выберите действие:_",
            reply_markup=keyboard
        )
        return success
    
    def notify_pipeline_failure(
        self, 
        failed_step: str, 
        error: str = None,
        duration: float = None,
        log_file: str = None
    ) -> bool:
        """Send a notification that the pipeline failed.
        
        Args:
            failed_step: Name of the step that caused the failure
            error: Error message or description
            duration: Total duration before failure in seconds
            log_file: Path to the log file to include
            
        Returns:
            bool: True if the notification was sent successfully
        """
        message = f"🚨 *[CI] Pipeline FAILED*"
        
        if duration is not None:
            message += f" after {duration:.1f}s"
        
        message += f"\n\n*Failed step:* {failed_step}"
        
        if error:
            message += f"\n\n*Error:*\n`{str(error)[:1000]}`"
        
        # Update the latest log symlink
        self._update_latest_log_symlink()
        
        # Add log file content if provided
        if log_file and Path(log_file).exists():
            message += f"\n\n*See log file:* `{log_file}`"
        
        # Add action buttons
        keyboard = self._get_inline_keyboard()
        success, _ = self._send_message(
            f"{message}\n\n_Выберите действие:_",
            reply_markup=keyboard
        )
        return success
        
    def send_log_file(self, chat_id: Optional[str] = None) -> bool:
        """Send the latest log file to the specified chat.
        
        Args:
            chat_id: Telegram chat ID (uses default if None)
            
        Returns:
            bool: True if the log was sent successfully
        """
        if not self.enabled or not self.token:
            return False
            
        chat_id = chat_id or self.chat_id
        log_file = self._ensure_latest_log()
        
        if not log_file or not log_file.exists():
            self._send_message("❌ Лог не найден.", chat_id=chat_id)
            return False
            
        try:
            url = f"{self.base_url}/sendDocument"
            with open(log_file, 'rb') as f:
                files = {'document': (log_file.name, f, 'text/plain')}
                data = {'chat_id': chat_id, 'caption': f'📄 Лог выполнения CI/CD'}
                response = requests.post(url, files=files, data=data, timeout=30)
                response.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"Failed to send log file: {e}")
            self._send_message(f"❌ Не удалось отправить лог: {str(e)}", chat_id=chat_id)
            return False
    
    def restart_pipeline(self, chat_id: Optional[str] = None) -> bool:
        """Restart the CI/CD pipeline.
        
        Args:
            chat_id: Telegram chat ID (uses default if None)
            
        Returns:
            bool: True if the restart command was initiated successfully
        """
        if not self.enabled or not self.token:
            return False
            
        chat_id = chat_id or self.chat_id
        
        try:
            # Send initial message
            message = "🔄 *Запускаю перезапуск CI/CD пайплайна...*"
            success, msg_id = self._send_message(message, chat_id=chat_id)
            
            if not success:
                return False
                
            # Run the pipeline in a separate thread to avoid blocking
            def run_pipeline():
                try:
                    cmd = [sys.executable, "ci/run_pipeline.py", "--all"]
                    if os.getenv('CI_TELEGRAM_NOTIFY', '').lower() == 'true':
                        cmd.append("--no-telegram")  # Prevent duplicate notifications
                        
                    env = os.environ.copy()
                    env['PYTHONPATH'] = os.getcwd()
                    
                    # Start the pipeline
                    process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        env=env,
                        cwd=os.getcwd()
                    )
                    
                    # Update message with output
                    output = []
                    for line in iter(process.stdout.readline, ''):
                        output.append(line)
                        if len(output) > 10:  # Keep last 10 lines
                            output.pop(0)
                        
                        # Update message with current output
                        status = "\n".join(output[-10:])
                        self._send_message(
                            f"{message}\n\n*Вывод:*\n```\n{status}\n```",
                            chat_id=chat_id,
                            message_id=msg_id
                        )
                    
                    # Wait for process to complete
                    process.wait()
                    
                    # Send final status
                    if process.returncode == 0:
                        self._send_message(
                            "✅ *Пайплайн успешно перезапущен!*\n\n"
                            "_Для просмотра лога используйте команду /last_log_",
                            chat_id=chat_id
                        )
                    else:
                        self._send_message(
                            f"❌ *Ошибка при выполнении пайплайна (код: {process.returncode})*\n\n"
                            "_Для просмотра лога используйте команду /last_log_",
                            chat_id=chat_id
                        )
                        
                except Exception as e:
                    logger.error(f"Error in pipeline thread: {e}")
                    self._send_message(
                        f"❌ *Ошибка при перезапуске пайплайна:*\n`{str(e)}`",
                        chat_id=chat_id
                    )
            
            # Start the pipeline in a background thread
            thread = threading.Thread(target=run_pipeline, daemon=True)
            thread.start()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to restart pipeline: {e}")
            self._send_message(
                f"❌ Не удалось запустить перезапуск пайплайна: {str(e)}",
                chat_id=chat_id
            )
            return False
    
    def handle_callback(self, update: Dict) -> bool:
        """Handle a callback query from Telegram.
        
        Args:
            update: The Telegram update object
            
        Returns:
            bool: True if the callback was handled successfully
        """
        try:
            callback_query = update.get('callback_query', {})
            data = callback_query.get('data')
            message = callback_query.get('message', {})
            chat_id = message.get('chat', {}).get('id')
            message_id = message.get('message_id')
            
            if not all([data, chat_id, message_id]):
                return False
            
            # Answer the callback query (removes the loading indicator)
            self._answer_callback(callback_query['id'])
            
            if data == 'restart_ci':
                # Show confirmation before restarting
                keyboard = {
                    'inline_keyboard': [
                        [
                            {'text': '✅ Да, перезапустить', 'callback_data': 'confirm_restart'},
                            {'text': '❌ Отмена', 'callback_data': 'cancel_restart'}
                        ]
                    ]
                }
                self._send_message(
                    "⚠️ *Вы уверены, что хотите перезапустить CI/CD пайплайн?*\n\n"
                    "Это может занять некоторое время.",
                    chat_id=chat_id,
                    message_id=message_id,
                    reply_markup=keyboard
                )
                return True
                
            elif data == 'confirm_restart':
                self._send_message("🔄 Запускаю перезапуск пайплайна...", chat_id=chat_id, message_id=message_id)
                return self.restart_pipeline(chat_id=chat_id)
                
            elif data == 'cancel_restart':
                keyboard = self._get_inline_keyboard()
                self._send_message(
                    "❌ Перезапуск отменен.",
                    chat_id=chat_id,
                    message_id=message_id,
                    reply_markup=keyboard
                )
                return True
                
            elif data == 'view_log':
                self._send_message("📥 Загружаю лог...", chat_id=chat_id, message_id=message_id)
                success = self.send_log_file(chat_id=chat_id)
                if success:
                    keyboard = self._get_log_keyboard()
                    self._send_message(
                        "📄 *Лог загружен.*\n\n_Выберите действие:_",
                        chat_id=chat_id,
                        message_id=message_id,
                        reply_markup=keyboard
                    )
                return success
                
            elif data == 'main_menu':
                keyboard = self._get_inline_keyboard()
                self._send_message(
                    "🏠 *Главное меню*\n\n_Выберите действие:_",
                    chat_id=chat_id,
                    message_id=message_id,
                    reply_markup=keyboard
                )
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Error handling callback: {e}")
            return False
    
    def _answer_callback(self, callback_query_id: str) -> bool:
        """Answer a callback query to remove the loading indicator."""
        try:
            url = f"{self.base_url}/answerCallbackQuery"
            payload = {'callback_query_id': callback_query_id}
            response = requests.post(url, json=payload, timeout=5)
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to answer callback: {e}")
            return False

def get_telegram_notifier() -> Optional[TelegramNotifier]:
    """Create and return a TelegramNotifier instance if configured.
    
    Returns:
        Optional[TelegramNotifier]: Configured TelegramNotifier or None if not configured
    """
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    chat_id = os.getenv('TELEGRAM_CHAT_ID')
    enabled = os.getenv('CI_TELEGRAM_NOTIFY', 'false').lower() == 'true'
    
    if not enabled:
        logger.info("Telegram notifications are disabled (CI_TELEGRAM_NOTIFY=false)")
        return None
        
    if not token or not chat_id:
        logger.warning("Telegram bot token or chat ID not configured")
        return None
        
    return TelegramNotifier(token, chat_id, enabled)


def handle_telegram_webhook():
    """Handle incoming Telegram webhook requests.
    
    This function should be called from your web framework's request handler.
    The request body should be a JSON object containing the Telegram update.
    
    Returns:
        dict: Response to send back to Telegram
    """
    try:
        # Get the JSON data from the request
        if not os.environ.get('REQUEST_BODY'):
            logger.error("No request body found in environment")
            return {"statusCode": 400, "body": "No request body"}
            
        update = json.loads(os.environ['REQUEST_BODY'])
        
        # Get the notifier instance
        notifier = get_telegram_notifier()
        if not notifier:
            return {"statusCode": 500, "body": "Telegram notifier not configured"}
        
        # Handle callback queries (button presses)
        if 'callback_query' in update:
            notifier.handle_callback(update)
            return {"statusCode": 200, "body": "OK"}
        
        # Handle commands
        if 'message' in update and 'text' in update['message']:
            message = update['message']
            text = message['text'].strip()
            chat_id = message['chat']['id']
            
            if text == '/start':
                notifier._send_message(
                    "🤖 *CI/CD Бот активирован*\n\n"
                    "Я буду уведомлять вас о статусе выполнения CI/CD пайплайна.\n\n"
                    "*Доступные команды:*\n"
                    "/last_log - Показать последний лог\n"
                    "/restart - Перезапустить CI/CD пайплайн\n"
                    "/help - Показать помощь",
                    chat_id=chat_id
                )
            elif text == '/last_log':
                notifier.send_log_file(chat_id=chat_id)
            elif text == '/restart':
                notifier.restart_pipeline(chat_id=chat_id)
            elif text == '/help':
                notifier._send_message(
                    "*Доступные команды:*\n\n"
                    "/start - Начать работу с ботом\n"
                    "/last_log - Показать последний лог выполнения\n"
                    "/restart - Перезапустить CI/CD пайплайн\n"
                    "/help - Показать это сообщение",
                    chat_id=chat_id
                )
        
        return {"statusCode": 200, "body": "OK"}
        
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in request: {e}")
        return {"statusCode": 400, "body": "Invalid JSON"}
    except Exception as e:
        logger.error(f"Error handling webhook: {e}")
        return {"statusCode": 500, "body": f"Error: {str(e)}"}

# Example usage
if __name__ == "__main__":
    # Initialize notifier with environment variables
    notifier = get_telegram_notifier()
    
    if not notifier:
        print("Telegram notifier not configured")
        sys.exit(1)
    
    # Example notifications
    notifier.notify_step_start("Tests", "Running unit tests...")
    notifier.notify_step_success("Linting", 12.5)
    notifier.notify_step_failure("Tests", "2 tests failed", log_lines=5)
    notifier.notify_pipeline_success(45.2, [
        {"name": "Linting", "duration": 5.1},
        {"name": "Type Checking", "duration": 7.3},
        {"name": "Tests", "duration": 32.8}
    ])
