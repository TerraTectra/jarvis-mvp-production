"""Tests for the browser pool module."""
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock

import pytest
from selenium.webdriver import Chrome, ChromeOptions

from src.integrations.browser_pool import BrowserPool, BrowserConfig


@pytest.mark.asyncio
async def test_browser_pool_initialization():
    """Test that the browser pool initializes correctly."""
    # Create a mock Chrome WebDriver
    with patch('selenium.webdriver.Chrome') as mock_chrome:
        # Create a browser pool with 2 instances
        config = BrowserConfig(
            headless=True,
            window_size=(1280, 1024),
            disable_images=True,
            disable_javascript=False,
        )
        
        async with BrowserPool(pool_size=2, config=config) as pool:
            # Verify the pool was initialized
            assert pool is not None
            assert pool.pool_size == 2
            assert len(pool.browsers) == 2
            
            # Verify Chrome was called with the correct options
            mock_chrome.assert_called()
            
            # Get a browser from the pool
            async with pool.get_browser() as browser:
                assert browser is not None
                # Verify we got one of the browsers from the pool
                assert browser in pool.browsers


@pytest.mark.asyncio
async def test_browser_config_to_chrome_options():
    """Test that BrowserConfig correctly converts to ChromeOptions."""
    config = BrowserConfig(
        headless=True,
        window_size=(1280, 1024),
        user_agent="test-user-agent",
        proxy="http://proxy.example.com:8080",
        disable_images=True,
        disable_javascript=True,
        no_sandbox=True,
        disable_gpu=True,
        disable_dev_shm=True,
        disable_extensions=True,
        disable_automation=True,
        disable_logging=True,
    )
    
    # Convert to ChromeOptions
    options = config.to_chrome_options()
    
    # Verify the options were set correctly
    assert isinstance(options, ChromeOptions)
    
    # Check some of the arguments
    args = []
    for arg_list in options.arguments:
        if isinstance(arg_list, list):
            args.extend(arg_list)
        else:
            args.append(arg_list)
    
    assert "--headless=new" in args
    assert "--window-size=1280,1024" in args
    assert "--no-sandbox" in args
    assert "--disable-gpu" in args
    assert "--disable-dev-shm-usage" in args
    assert "--disable-extensions" in args
    assert "--disable-blink-features=AutomationControlled" in args
    assert "--log-level=3" in args


@pytest.mark.asyncio
async def test_browser_pool_concurrent_access():
    """Test that the browser pool handles concurrent access correctly."""
    # Create a mock Chrome WebDriver
    with patch('selenium.webdriver.Chrome') as mock_chrome:
        # Create a browser pool with 2 instances
        async with BrowserPool(pool_size=2) as pool:
            # Create a list to store the browsers we get from the pool
            browsers = set()
            
            # Define a coroutine that gets a browser and adds it to the set
            async def get_browser():
                async with pool.get_browser() as browser:
                    browsers.add(browser)
                    # Simulate some work
                    await asyncio.sleep(0.1)
            
            # Run multiple coroutines concurrently
            await asyncio.gather(*[get_browser() for _ in range(5)])
            
            # Verify we used both browsers in the pool
            assert len(browsers) == 2


@pytest.mark.asyncio
async def test_browser_pool_timeout():
    """Test that the browser pool raises a timeout when no browsers are available."""
    # Create a mock Chrome WebDriver
    with patch('selenium.webdriver.Chrome'):
        # Create a browser pool with 1 instance
        async with BrowserPool(pool_size=1) as pool:
            # Get the only browser in the pool
            async with pool.get_browser():
                # Try to get another browser with a short timeout
                with pytest.raises(asyncio.TimeoutError):
                    async with pool.get_browser(timeout=0.1):
                        pass  # Should not reach here


@pytest.mark.asyncio
async def test_browser_pool_error_handling():
    """Test that the browser pool handles browser creation errors."""
    # Mock Chrome to raise an exception on creation
    with patch('selenium.webdriver.Chrome', side_effect=Exception("Test error")):
        # Try to create a browser pool
        with pytest.raises(Exception, match="Test error"):
            async with BrowserPool(pool_size=1) as pool:
                pass  # Should not reach here


@pytest.mark.asyncio
async def test_browser_pool_close():
    """Test that the browser pool closes all browsers properly."""
    # Create mock browsers
    mock_browsers = [MagicMock(spec=Chrome) for _ in range(2)]
    
    # Patch Chrome to return our mock browsers
    with patch('selenium.webdriver.Chrome', side_effect=mock_browsers):
        # Create a browser pool
        pool = BrowserPool(pool_size=2)
        await pool.initialize()
        
        # Verify we have the expected number of browsers
        assert len(pool.browsers) == 2
        
        # Close the pool
        await pool.close()
        
        # Verify all browsers were closed
        for browser in mock_browsers:
            browser.quit.assert_called_once()
        
        # Verify the pool is marked as not initialized
        assert not pool.is_initialized
        assert len(pool.browsers) == 0


@pytest.mark.asyncio
async def test_get_browser_pool_singleton():
    """Test that get_browser_pool returns a singleton instance."""
    from src.integrations.browser_pool import get_browser_pool
    
    # Get the browser pool twice
    pool1 = get_browser_pool()
    pool2 = get_browser_pool()
    
    # Verify they're the same instance
    assert pool1 is pool2
    
    # Verify they have the same configuration
    assert pool1.pool_size == pool2.pool_size
    assert pool1.config == pool2.config


@pytest.mark.asyncio
async def test_browser_pool_with_real_browser():
    """Test the browser pool with a real browser (requires Chrome to be installed)."""
    # Skip this test in CI environments
    if os.getenv('CI'):
        pytest.skip("Skipping real browser test in CI environment")
    
    # Create a browser pool with a real browser
    config = BrowserConfig(
        headless=True,
        window_size=(1280, 1024),
    )
    
    async with BrowserPool(pool_size=1, config=config) as pool:
        # Get a browser from the pool
        async with pool.get_browser() as browser:
            # Navigate to a test page
            browser.get("https://example.com")
            
            # Verify the page loaded
            assert "Example Domain" in browser.title
            
            # Take a screenshot (for debugging)
            screenshot = browser.get_screenshot_as_png()
            assert len(screenshot) > 0
