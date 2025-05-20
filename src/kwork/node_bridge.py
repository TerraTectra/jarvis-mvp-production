"""
Python обертка для работы с Kwork API через Node.js мост с поддержкой прокси и капчи.
"""
import asyncio
import json
import logging
import os
import platform
import select
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Tuple, Callable, Awaitable

# Windows-specific imports
if os.name == 'nt':
    import msvcrt

from loguru import logger

# Настройки по умолчанию
DEFAULT_NODE_PATH = "node"
DEFAULT_SCRIPT_PATH = "scripts/kwork_node_bridge.js"
DEFAULT_TIMEOUT = 30  # секунды


@dataclass
class KworkOrder:
    """Модель заказа с Kwork."""
    id: str
    title: str
    description: str
    price: str
    url: str
    timestamp: float = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь."""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'price': self.price,
            'url': self.url,
            'timestamp': self.timestamp or time.time()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'KworkOrder':
        """Создание экземпляра из словаря."""
        return cls(
            id=str(data['id']),
            title=data.get('title', ''),
            description=data.get('description', ''),
            price=data.get('price', ''),
            url=data.get('url', ''),
            timestamp=data.get('timestamp')
        )


class KworkBridgeError(Exception):
    """Базовое исключение для ошибок KworkBridge."""
    pass


class KworkAuthError(KworkBridgeError):
    """Ошибка аутентификации."""
    pass


class KworkAPIError(KworkBridgeError):
    """Ошибка API Kwork."""
    pass


class KworkProxyError(KworkBridgeError):
    """Ошибка работы с прокси."""
    pass

from dotenv import load_dotenv

# Настройка логирования
logger = logging.getLogger(__name__)

# Enable debug logging for this module
logger.setLevel(logging.DEBUG)

# Create console handler with a higher log level
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
# Create formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
# Add the handler to the logger
logger.addHandler(ch)

class KworkBridgeError(Exception):
    """Ошибка работы с Kwork API через Node.js мост."""
    pass

class KworkNodeBridge:
    """
    Класс для взаимодействия с Kwork API через Node.js мост.
    
    Пример использования:
    ```python
    bridge = KworkNodeBridge()
    profile = bridge.get_profile()
    orders = bridge.get_orders()
    ```
    """
    
    def __init__(
        self,
        node_path: str = "node",
        script_path: Optional[Path] = None,
        timeout: int = 60,
        max_retries: int = 3,
        session_ttl: int = 900,  # 15 минут по умолчанию
    ):
        """
        Инициализация моста.
        
        Args:
            node_path: Путь к Node.js исполняемому файлу
            script_path: Путь к скрипту kwork_node_bridge.js
            timeout: Таймаут выполнения команд в секундах
            max_retries: Максимальное количество попыток при ошибках
            session_ttl: Время жизни сессии в секундах
        """
        self.node_path = node_path
        self.timeout = timeout
        self.max_retries = max_retries
        
        # Устанавливаем SESSION_TTL в переменные окружения
        os.environ['SESSION_TTL'] = str(session_ttl)
        
        # Определяем путь к скрипту
        if script_path is None:
            script_path = (
                Path(__file__).parent.parent.parent / "scripts" / "kwork_node_bridge.js"
            )
        self.script_path = script_path
        
        # Проверяем существование скрипта
        if not self.script_path.exists():
            raise KworkBridgeError(f"Node.js script not found: {self.script_path}")
        
        # Процесс Node.js
        self._process: Optional[subprocess.Popen] = None
        
        # Загружаем переменные окружения
        load_dotenv()
        
        # Проверяем обязательные переменные
        self._check_credentials()
    
    def _check_credentials(self) -> None:
        """Проверяет наличие обязательных учетных данных."""
        required_vars = ["KWORK_USERNAME", "KWORK_PASSWORD"]
        missing = [var for var in required_vars if not os.getenv(var)]
        
        if missing:
            raise KworkBridgeError(
                f"Missing required environment variables: {', '.join(missing)}"
            )
            
        # KWORK_PINCODE is optional
        if not os.getenv("KWORK_PINCODE"):
            logger.warning("KWORK_PINCODE is not set. 2FA will not be used if enabled on the account.")
    
    def _start_process(self) -> None:
        """Запускает Node.js процесс с мостом."""
        if self._process is not None:
            return
            
        try:
            # Ensure the script path is absolute
            script_path = str(self.script_path.absolute())
            
            logger.debug(f"Starting Node.js process: {self.node_path} {script_path}")
            
            # Start the Node.js process with unbuffered I/O
            self._process = subprocess.Popen(
                [self.node_path, script_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0,  # Unbuffered mode
                text=False,  # Binary mode for unbuffered I/O
                universal_newlines=False  # Binary mode for unbuffered I/O
            )
            
            # Set up non-blocking I/O
            import os
            
            def set_non_blocking(fd):
                if os.name == 'nt':
                    # On Windows, we'll use the default blocking mode
                    # as non-blocking I/O is more complex on Windows
                    pass
                else:
                    # For Unix-like systems
                    import fcntl
                    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
                    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)
            
            # Skip setting non-blocking mode on Windows
            if os.name != 'nt':
                set_non_blocking(self._process.stdout.fileno())
                set_non_blocking(self._process.stderr.fileno())
            
            # Read stderr in a separate thread to prevent blocking
            def log_stderr():
                while True:
                    line = self._process.stderr.readline()
                    if not line and self._process.poll() is not None:
                        break
                    if line:
                        logger.debug(f"[Node.js] {line.strip()}")
            
            import threading
            stderr_thread = threading.Thread(target=log_stderr, daemon=True)
            stderr_thread.start()
            
            # Give the process time to start and send any initial logs
            time.sleep(0.5)
            
            # Check if the process is still running
            if self._process.poll() is not None:
                _, stderr = self._process.communicate(timeout=5)
                error_msg = stderr if stderr else 'Unknown error'
                self._stop_process()
                raise KworkBridgeError(f"Node.js process exited with error: {error_msg}")
            
            logger.debug("Node.js process started successfully")
            
            # Send an init command to verify the bridge is working
            try:
                init_cmd = json.dumps({"command": "init"}).encode('utf-8') + b'\n'
                self._process.stdin.write(init_cmd)
                self._process.stdin.flush()
                
                # Read the response to the init command
                raw_output = self._process.stdout.readline()
                if not raw_output:
                    raise KworkBridgeError("No response to init command from Node.js bridge")
                
                output = raw_output.decode('utf-8', errors='replace').strip()
                logger.debug(f"Init response: {output}")
                
                try:
                    response = json.loads(output)
                    if response.get("status") == "error":
                        raise KworkBridgeError(f"Node.js bridge init error: {response.get('message', 'Unknown error')}")
                except json.JSONDecodeError:
                    # If we can't parse the response, log it but continue
                    logger.warning(f"Unexpected response to init command: {output}")
                
            except Exception as e:
                self._stop_process()
                raise KworkBridgeError(f"Failed to initialize Node.js bridge: {str(e)}")
                
        except Exception as e:
            self._stop_process()
            raise KworkBridgeError(f"Failed to start Node.js process: {str(e)}")
    
    def _stop_process(self) -> None:
        """Останавливает Node.js процесс."""
        if self._process is not None:
            try:
                # Try to gracefully terminate the process
                if self._process.poll() is None:
                    try:
                        # Send a close command
                        close_cmd = json.dumps({"command": "close"}).encode('utf-8') + b'\n'
                        self._process.stdin.write(close_cmd)
                        self._process.stdin.flush()
                        
                        # Wait for the process to terminate
                        self._process.wait(timeout=5)
                    except (subprocess.TimeoutExpired, BrokenPipeError, OSError):
                        # If graceful termination fails, force kill the process
                        self._process.kill()
                        self._process.wait()
                
                # Close file descriptors
                for stream in [self._process.stdin, self._process.stdout, self._process.stderr]:
                    if stream:
                        try:
                            stream.close()
                        except Exception as e:
                            logger.warning(f"Error closing process stream: {e}")
                            
            except Exception as e:
                logger.warning(f"Error stopping Node.js process: {e}")
                try:
                    self._process.kill()
                except:
                    pass
            finally:
                self._process = None
    
    def _execute_command(
        self, command: str, **params: Any
    ) -> Dict[str, Any]:
        """
        Выполняет команду через Node.js мост.
        
        Args:
            command: Название команды
            **params: Параметры команды
            
        Returns:
            Словарь с результатом выполнения
            
        Raises:
            KworkBridgeError: В случае ошибки выполнения команды
        """
        if not self._process:
            self._start_process()
        
        # Log the command being executed
        logger.debug(f"Executing command: {command} with params: {params}")
            
        try:
            # Prepare and send the command
            command_data = {"command": command, "params": params}
            command_json = json.dumps(command_data, ensure_ascii=False)
            command_bytes = command_json.encode('utf-8') + b'\n'
            
            logger.debug(f"Sending command: {command_json}")
            
            # Write the command to stdin
            try:
                self._process.stdin.write(command_bytes)
                self._process.stdin.flush()
                logger.debug("Command sent successfully")
            except BrokenPipeError as e:
                logger.error("Broken pipe when sending command. Process may have died.")
                self._stop_process()
                raise KworkBridgeError("Node.js process is not responding")
            
            # Read the response with a timeout
            start_time = time.time()
            timeout = 30  # 30 seconds timeout
            output_lines = []
            
            def read_stdout_line(timeout_sec=1.0):
                """Read a line from stdout with timeout."""
                line = b''
                start = time.time()
                
                while time.time() - start < timeout_sec:
                    # Check if there's data available to read
                    if os.name == 'nt':
                        # On Windows, try to read directly and handle the blocking
                        try:
                            # Try to read a single byte to check if there's data
                            char = self._process.stdout.read(1)
                            if char:
                                # If we got a byte, read the rest of the line
                                line = char + self._process.stdout.readline()
                                return line
                        except Exception as e:
                            logger.debug(f"Error reading from stdout: {e}")
                            pass
                        time.sleep(0.1)
                    else:
                        # On Unix, use select
                        rlist, _, _ = select.select([self._process.stdout], [], [], 0.1)
                        if self._process.stdout in rlist:
                            line = self._process.stdout.readline()
                            if line:
                                return line
                        time.sleep(0.1)
                
                return line
                
            # Main read loop
            while time.time() - start_time < timeout:
                # Read a line with timeout
                line_bytes = read_stdout_line(1.0)
                
                if line_bytes:
                    try:
                        line = line_bytes.decode('utf-8').strip()
                        logger.debug(f"Received line: {line}")
                        
                        try:
                            response = json.loads(line)
                            if response.get('type') == 'response':
                                return response.get('data', {})
                            elif response.get('type') == 'error':
                                error_msg = response.get('message', 'Unknown error')
                                logger.error(f"Node.js error: {error_msg}")
                                raise KworkBridgeError(f"Node.js error: {error_msg}")
                            else:
                                output_lines.append(line)
                        except json.JSONDecodeError:
                            output_lines.append(line)
                    except UnicodeDecodeError as e:
                        logger.warning(f"Failed to decode line: {e}")
                
                # Check if process has terminated
                if self._process.poll() is not None:
                    error_output = self._process.stderr.read().decode('utf-8', errors='replace')
                    logger.error(f"Node.js process terminated unexpectedly. Error: {error_output}")
                    raise KworkBridgeError(f"Node.js process terminated: {error_output}")
                
                # Small sleep to prevent busy waiting
                time.sleep(0.1)
            
            # If we get here, we've timed out
            error_msg = f"Timeout waiting for response to command: {command}"
            logger.error(error_msg)
            logger.error(f"Collected output so far: {output_lines}")
            raise KworkBridgeError(error_msg)
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            raise KworkBridgeError(f"Invalid JSON response: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in _execute_command: {str(e)}", exc_info=True)
            raise KworkBridgeError(f"Error executing command: {str(e)}")
    
    def get_profile(self) -> Dict[str, Any]:
        """
        Получает профиль пользователя.
        
        Returns:
            Словарь с данными профиля
        """
        return self._execute_command("getProfile")
    
    def get_orders(self, **params: Any) -> List[Dict[str, Any]]:
        """
        Получает список заказов.
        
        Args:
            **params: Параметры фильтрации заказов
            
        Returns:
            Список заказов
        """
        return self._execute_command("getOrders", **params)
    
    def send_reply(
        self, order_id: Union[str, int], message: str, **options: Any
    ) -> Dict[str, Any]:
        """
        Отправляет отклик на заказ.
        
        Args:
            order_id: ID заказа
            message: Текст отклика
            **options: Дополнительные параметры (цена, сроки и т.д.)
            
        Returns:
            Результат отправки отклика
        """
        return self._execute_command(
            "sendReply", orderId=str(order_id), message=message, **options
        )
    
    def __enter__(self):
        """Поддержка контекстного менеджера."""
        self._start_process()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Остановка процесса при выходе из контекста."""
        self._stop_process()
    
    def __del__(self):
        """Деструктор, останавливающий процесс."""
        self._stop_process()
