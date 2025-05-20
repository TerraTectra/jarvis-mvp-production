"""Tests for the web driver pool."""
import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.webdriver import WebDriver as ChromeDriver

# Add the src directory to the path for imports
sys.path.append(str(Path(__file__).parent.parent / "src"))

from webdriver_pool import WebDriverPool, get_web_driver_pool, close_web_driver_pool
from config import ScraperSettings


class TestWebDriverPool:
    """Test cases for the WebDriverPool class."""
    
    @pytest.fixture
    def scraper_settings(self):
        """Create a test scraper settings object."""
        return ScraperSettings(
            base_url="https://kwork.ru/projects",
            headless=True,
            pool_size=3,
            max_pages=10,
            request_timeout=30,
        )
    
    @pytest.fixture
    def mock_web_driver(self):
        """Create a mock WebDriver instance."""
        with patch('selenium.webdriver.Chrome') as mock_driver:
            # Configure the mock WebDriver
            mock_driver.return_value = MagicMock(spec=ChromeDriver)
            mock_driver.return_value.session_id = "test-session-id"
            mock_driver.return_value.get = AsyncMock()
            mock_driver.return_value.quit = AsyncMock()
            
            yield mock_driver.return_value
    
    @pytest.fixture
    def mock_chrome_options(self):
        """Create a mock ChromeOptions instance."""
        with patch('selenium.webdriver.ChromeOptions') as mock_options:
            mock_options.return_value = MagicMock(spec=Options)
            yield mock_options.return_value
    
    @pytest.fixture
    def mock_web_driver_service(self):
        """Create a mock ChromeService instance."""
        with patch('selenium.webdriver.chrome.service.Service') as mock_service:
            mock_service.return_value = MagicMock()
            yield mock_service.return_value
    
    @pytest.mark.asyncio
    async def test_init(self, scraper_settings, mock_web_driver, mock_chrome_options, mock_web_driver_service):
        """Test initializing the web driver pool."""
        # Create a web driver pool
        pool = WebDriverPool(scraper_settings)
        
        # Initialize the pool
        await pool.init()
        
        # Verify the pool was initialized correctly
        assert pool.pool_size == scraper_settings.pool_size
        assert len(pool._pool) == scraper_settings.pool_size
        assert pool._initialized is True
        
        # Verify the web drivers were created with the correct options
        for driver in pool._pool:
            assert isinstance(driver, MagicMock)
            assert driver.session_id == "test-session-id"
        
        # Clean up
        await pool.close()
    
    @pytest.mark.asyncio
    async def test_acquire_release(self, scraper_settings, mock_web_driver, mock_chrome_options, mock_web_driver_service):
        """Test acquiring and releasing a web driver."""
        # Create and initialize a web driver pool
        pool = WebDriverPool(scraper_settings)
        await pool.init()
        
        # Acquire a web driver
        driver = await pool.acquire()
        
        # Verify the driver was acquired
        assert driver is not None
        assert driver in pool._acquired_drivers
        
        # Release the driver
        await pool.release(driver)
        
        # Verify the driver was released
        assert driver not in pool._acquired_drivers
        
        # Clean up
        await pool.close()
    
    @pytest.mark.asyncio
    async def test_acquire_timeout(self, scraper_settings, mock_web_driver, mock_chrome_options, mock_web_driver_service):
        """Test that acquire raises a TimeoutError when no drivers are available."""
        # Create a pool with a single driver
        settings = scraper_settings.copy()
        settings.pool_size = 1
        
        pool = WebDriverPool(settings)
        await pool.init()
        
        # Acquire the only available driver
        driver = await pool.acquire()
        
        # Try to acquire another driver (should timeout)
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(pool.acquire(), timeout=1)
        
        # Release the driver
        await pool.release(driver)
        
        # Clean up
        await pool.close()
    
    @pytest.mark.asyncio
    async def test_context_manager(self, scraper_settings, mock_web_driver, mock_chrome_options, mock_web_driver_service):
        """Test using the web driver pool as a context manager."""
        async with WebDriverPool(scraper_settings) as pool:
            # Verify the pool was initialized
            assert pool._initialized is True
            assert len(pool._pool) == scraper_settings.pool_size
            
            # Acquire a driver
            driver = await pool.acquire()
            
            # Verify the driver was acquired
            assert driver is not None
            assert driver in pool._acquired_drivers
            
            # Release the driver
            await pool.release(driver)
        
        # Verify the pool was closed
        assert pool._initialized is False
        assert len(pool._pool) == 0
    
    @pytest.mark.asyncio
    async def test_close(self, scraper_settings, mock_web_driver, mock_chrome_options, mock_web_driver_service):
        """Test closing the web driver pool."""
        # Create and initialize a web driver pool
        pool = WebDriverPool(scraper_settings)
        await pool.init()
        
        # Acquire all drivers
        drivers = []
        for _ in range(scraper_settings.pool_size):
            driver = await pool.acquire()
            drivers.append(driver)
        
        # Close the pool
        await pool.close()
        
        # Verify the pool was closed
        assert pool._initialized is False
        assert len(pool._pool) == 0
        assert len(pool._acquired_drivers) == 0
        
        # Verify all drivers were closed
        for driver in drivers:
            driver.quit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_restart_driver(self, scraper_settings, mock_web_driver, mock_chrome_options, mock_web_driver_service):
        """Test restarting a web driver."""
        # Create and initialize a web driver pool
        pool = WebDriverPool(scraper_settings)
        await pool.init()
        
        # Get a driver
        driver = await pool.acquire()
        
        # Reset the mock to track calls
        driver.quit.reset_mock()
        
        # Restart the driver
        await pool._restart_driver(driver)
        
        # Verify the old driver was closed
        driver.quit.assert_called_once()
        
        # Verify a new driver was created
        assert len(pool._pool) == scraper_settings.pool_size - 1
        assert len(pool._acquired_drivers) == 1
        
        # Clean up
        await pool.release(driver)
        await pool.close()


class TestWebDriverPoolModule:
    """Test cases for the web driver pool module functions."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures."""
        # Reset the global pool
        from webdriver_pool import _global_pool
        _global_pool = None
        
        # Patch the get_settings function
        self.settings_patcher = patch(
            "webdriver_pool.get_settings",
            return_value=MagicMock(
                scraper=MagicMock(
                    headless=True,
                    pool_size=2,
                )
            )
        )
        self.mock_get_settings = self.settings_patcher.start()
        
        # Patch the WebDriver class
        self.web_driver_patcher = patch('selenium.webdriver.Chrome')
        self.mock_web_driver = self.web_driver_patcher.start()
        self.mock_web_driver.return_value = MagicMock()
        self.mock_web_driver.return_value.session_id = "test-session-id"
        self.mock_web_driver.return_value.get = AsyncMock()
        self.mock_web_driver.return_value.quit = AsyncMock()
        
        yield
        
        # Clean up
        self.settings_patcher.stop()
        self.web_driver_patcher.stop()
        asyncio.run(close_web_driver_pool())
    
    @pytest.mark.asyncio
    async def test_get_web_driver_pool(self):
        """Test getting the global web driver pool."""
        # Get the global pool
        pool = await get_web_driver_pool()
        
        # Verify the pool was created
        assert pool is not None
        assert pool._initialized is True
        assert pool.pool_size == 2
        
        # Get the pool again (should return the same instance)
        pool2 = await get_web_driver_pool()
        assert pool is pool2
    
    @pytest.mark.asyncio
    async def test_close_web_driver_pool(self):
        """Test closing the global web driver pool."""
        # Get the global pool
        pool = await get_web_driver_pool()
        
        # Close the pool
        await close_web_driver_pool()
        
        # Verify the pool was closed
        assert pool._initialized is False
        
        # Get the pool again (should create a new instance)
        pool2 = await get_web_driver_pool()
        assert pool is not pool2
    
    @pytest.mark.asyncio
    async def test_web_driver_pool_context_manager(self):
        """Test using the web driver pool as a context manager."""
        from webdriver_pool import web_driver_pool
        
        async with web_driver_pool() as pool:
            # Verify the pool was initialized
            assert pool is not None
            assert pool._initialized is True
            
            # Get a driver
            driver = await pool.acquire()
            assert driver is not None
            
            # Release the driver
            await pool.release(driver)
        
        # Verify the pool was closed
        assert pool._initialized is False
    
    @pytest.mark.asyncio
    async def test_web_driver_pool_concurrent_access(self):
        """Test concurrent access to the web driver pool."""
        from webdriver_pool import web_driver_pool
        
        async def use_driver():
            async with web_driver_pool() as pool:
                driver = await pool.acquire()
                try:
                    # Simulate some work
                    await asyncio.sleep(0.1)
                    return driver.session_id
                finally:
                    await pool.release(driver)
        
        # Create multiple tasks that use the pool concurrently
        tasks = [use_driver() for _ in range(5)]
        results = await asyncio.gather(*tasks)
        
        # Verify all tasks completed successfully
        assert len(results) == 5
        assert all(isinstance(session_id, str) for session_id in results)
