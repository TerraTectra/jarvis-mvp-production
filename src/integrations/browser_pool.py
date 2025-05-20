"""Async browser pool for concurrent web scraping."""
import asyncio
from typing import List, Optional, Dict, Any, AsyncIterator, Tuple
from contextlib import asynccontextmanager
from dataclasses import dataclass
import logging

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType

from loguru import logger


@dataclass
class BrowserConfig:
    """Configuration for browser instances."""
    headless: bool = True
    window_size: Tuple[int, int] = (1920, 1080)
    user_agent: Optional[str] = None
    proxy: Optional[str] = None
    disable_images: bool = True
    disable_javascript: bool = False
    disable_extensions: bool = True
    disable_gpu: bool = True
    no_sandbox: bool = True
    disable_dev_shm: bool = True
    disable_automation: bool = True
    disable_logging: bool = True
    
    def to_chrome_options(self) -> ChromeOptions:
        """Convert to ChromeOptions object."""
        options = ChromeOptions()
        
        # Basic options
        if self.headless:
            options.add_argument("--headless=new")
        
        if self.window_size:
            options.add_argument(f"--window-size={self.window_size[0]},{self.window_size[1]}")
        
        if self.user_agent:
            options.add_argument(f"user-agent={self.user_agent}")
            
        if self.proxy:
            options.add_argument(f"--proxy-server={self.proxy}")
        
        # Performance optimizations
        if self.disable_images:
            options.add_argument("--blink-settings=imagesEnabled=false")
            options.add_experimental_option("prefs", {
                "profile.managed_default_content_settings.images": 2,
                "profile.default_content_setting_values.images": 2,
            })
            
        if self.disable_javascript:
            options.add_argument("--disable-javascript")
            options.add_experimental_option("prefs", {
                "profile.managed_default_content_settings.javascript": 2,
                "profile.default_content_setting_values.javascript": 2,
            })
        
        # Security and automation flags
        if self.no_sandbox:
            options.add_argument("--no-sandbox")
            
        if self.disable_gpu:
            options.add_argument("--disable-gpu")
            
        if self.disable_dev_shm:
            options.add_argument("--disable-dev-shm-usage")
            
        if self.disable_extensions:
            options.add_argument("--disable-extensions")
            
        if self.disable_automation:
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option("useAutomationExtension", False)
        
        # Disable logging if needed
        if self.disable_logging:
            options.add_argument("--log-level=3")
            options.add_experimental_option("excludeSwitches", ["enable-logging"])
        
        return options


class BrowserPool:
    """Async browser pool for concurrent web scraping."""
    
    def __init__(self, pool_size: int = 3, config: Optional[BrowserConfig] = None):
        """Initialize the browser pool.
        
        Args:
            pool_size: Number of browser instances in the pool
            config: Browser configuration
        """
        self.pool_size = pool_size
        self.config = config or BrowserConfig()
        self.browsers: List[webdriver.Chrome] = []
        self.available: asyncio.Queue = asyncio.Queue()
        self.lock = asyncio.Lock()
        self.is_initialized = False
        
    async def initialize(self) -> None:
        """Initialize the browser pool."""
        if self.is_initialized:
            return
            
        logger.info(f"Initializing browser pool with {self.pool_size} instances")
        
        # Create browser instances
        for _ in range(self.pool_size):
            browser = await self._create_browser()
            self.browsers.append(browser)
            await self.available.put(browser)
            
        self.is_initialized = True
        logger.info("Browser pool initialized")
    
    async def _create_browser(self) -> webdriver.Chrome:
        """Create a new browser instance."""
        options = self.config.to_chrome_options()
        
        try:
            # Try to use webdriver-manager to handle the driver
            service = ChromeService(ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install())
            browser = webdriver.Chrome(service=service, options=options)
        except Exception as e:
            logger.warning(f"Failed to use webdriver-manager: {e}")
            # Fallback to system Chrome
            browser = webdriver.Chrome(options=options)
        
        # Set page load timeout
        browser.set_page_load_timeout(60)
        browser.set_script_timeout(30)
        
        # Set window size
        if self.config.window_size:
            browser.set_window_size(*self.config.window_size)
            
        return browser
    
    @asynccontextmanager
    async def get_browser(self, timeout: float = 60.0) -> AsyncIterator[webdriver.Chrome]:
        """Get a browser from the pool.
        
        Args:
            timeout: Maximum time to wait for a browser (seconds)
            
        Yields:
            webdriver.Chrome: A browser instance
            
        Raises:
            asyncio.TimeoutError: If no browser is available within timeout
        """
        if not self.is_initialized:
            await self.initialize()
            
        try:
            # Wait for a browser to become available
            browser = await asyncio.wait_for(self.available.get(), timeout=timeout)
            
            try:
                yield browser
            finally:
                # Clear cookies and return browser to the pool
                browser.delete_all_cookies()
                await self.available.put(browser)
        except Exception as e:
            logger.error(f"Error in browser context: {e}")
            raise
    
    async def close(self) -> None:
        """Close all browser instances."""
        if not self.is_initialized:
            return
            
        logger.info("Closing browser pool...")
        
        # Close all browsers
        for browser in self.browsers:
            try:
                browser.quit()
            except Exception as e:
                logger.error(f"Error closing browser: {e}")
                
        # Clear the pool
        self.browsers.clear()
        while not self.available.empty():
            try:
                await self.available.get_nowait()
            except asyncio.QueueEmpty:
                break
                
        self.is_initialized = False
        logger.info("Browser pool closed")
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()


# Default browser pool instance
_default_pool: Optional[BrowserPool] = None


def get_browser_pool(pool_size: int = 3, config: Optional[BrowserConfig] = None) -> BrowserPool:
    """Get or create a default browser pool."""
    global _default_pool
    
    if _default_pool is None or not _default_pool.is_initialized:
        _default_pool = BrowserPool(pool_size=pool_size, config=config)
        
    return _default_pool
