"""Tests for the Kwork scraper error handling."""
import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock, call

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

# Add the src directory to the path for imports
sys.path.append(str(Path(__file__).parent.parent / "src"))

from integrations.kwork_scraper import KworkScraper
from database.kwork_models import KworkProject, ProjectSnapshot, ScrapeSession
from config import ScraperSettings, DatabaseSettings, TelegramSettings


class TestKworkScraperErrors:
    """Test cases for the Kwork scraper error handling."""
    
    @pytest.fixture
    def scraper_settings(self):
        """Create a test scraper settings object."""
        return ScraperSettings(
            base_url="https://kwork.ru/projects",
            headless=True,
            pool_size=1,
            max_pages=1,
            request_timeout=5,  # Shorter timeout for testing
        )
    
    @pytest.fixture
    def db_settings(self):
        """Create a test database settings object."""
        return DatabaseSettings(
            url="sqlite+aiosqlite:///:memory:",
            echo=False,
        )
    
    @pytest.fixture
    def telegram_settings(self):
        """Create a test Telegram settings object."""
        return TelegramSettings(
            enabled=True,
            token="test-token",
            chat_id="12345",
        )
    
    @pytest.fixture
    def mock_web_driver_pool(self):
        """Create a mock WebDriverPool."""
        with patch('integrations.kwork_scraper.WebDriverPool') as mock_pool:
            mock_driver = MagicMock()
            mock_driver.session_id = "test-session-id"
            mock_driver.get = AsyncMock()
            mock_driver.page_source = "<html><body>Test page</body></html>"
            mock_driver.quit = AsyncMock()
            
            mock_pool_instance = AsyncMock()
            mock_pool_instance.acquire = AsyncMock(return_value=mock_driver)
            mock_pool_instance.release = AsyncMock()
            mock_pool.return_value = mock_pool_instance
            
            yield mock_pool_instance, mock_driver
    
    @pytest.mark.asyncio
    async def test_web_driver_error(
        self, 
        scraper_settings, 
        db_settings, 
        telegram_settings,
        mock_web_driver_pool,
        db_session,
    ):
        """Test handling of WebDriver errors."""
        # Configure the mock WebDriver to raise an exception
        mock_pool, mock_driver = mock_web_driver_pool
        mock_driver.get.side_effect = Exception("WebDriver error")
        
        # Create a scraper instance
        scraper = KworkScraper(scraper_settings, db_settings, telegram_settings)
        
        # Run the scraper
        result = await scraper.scrape_projects()
        
        # Verify the result
        assert result["status"] == "error"
        assert result["errors_encountered"] > 0
        
        # Verify the error was logged
        # (In a real test, you would check the logs here)
        
        # Verify the scrape session was saved with error status
        result = await db_session.execute(select(ScrapeSession))
        sessions = result.scalars().all()
        
        assert len(sessions) == 1
        assert sessions[0].status == "error"
    
    @pytest.mark.asyncio
    async def test_parser_error(
        self, 
        scraper_settings, 
        db_settings, 
        telegram_settings,
        mock_web_driver_pool,
        db_session,
    ):
        """Test handling of parser errors."""
        # Create a mock KworkParser that raises an exception
        with patch('integrations.kwork_scraper.KworkParser') as mock_parser:
            mock_parser_instance = MagicMock()
            mock_parser_instance.parse_project_cards = AsyncMock(
                side_effect=Exception("Parser error")
            )
            mock_parser.return_value = mock_parser_instance
            
            # Create a scraper instance
            scraper = KworkScraper(scraper_settings, db_settings, telegram_settings)
            
            # Run the scraper
            result = await scraper.scrape_projects()
            
            # Verify the result
            assert result["status"] == "error"
            assert result["errors_encountered"] > 0
            
            # Verify the error was logged
            # (In a real test, you would check the logs here)
            
            # Verify the scrape session was saved with error status
            result = await db_session.execute(select(ScrapeSession))
            sessions = result.scalars().all()
            
            assert len(sessions) == 1
            assert sessions[0].status == "error"
    
    @pytest.mark.asyncio
    async def test_database_error(
        self, 
        scraper_settings, 
        db_settings, 
        telegram_settings,
        mock_web_driver_pool,
        mock_kwork_parser,
    ):
        """Test handling of database errors."""
        # Configure the mock KworkParser to return test projects
        test_projects = [
            {
                "kwork_id": "test1",
                "title": "Test Project 1",
                "url": "https://kwork.ru/projects/test1",
                "price": 1000.0,
                "category": "Web Development",
                "description": "Test project 1 description",
                "date_posted": "2023-01-01T00:00:00",
            },
        ]
        
        mock_kwork_parser.parse_project_cards.return_value = test_projects
        
        # Create a mock database session that raises an exception
        with patch('integrations.kwork_scraper.get_db_session') as mock_session:
            mock_session.return_value = AsyncMock(
                __aenter__=AsyncMock(side_effect=Exception("Database error")),
                __aexit__=AsyncMock()
            )
            
            # Create a scraper instance
            scraper = KworkScraper(scraper_settings, db_settings, telegram_settings)
            
            # Run the scraper
            result = await scraper.scrape_projects()
            
            # Verify the result
            assert result["status"] == "error"
            assert result["errors_encountered"] > 0
    
    @pytest.mark.asyncio
    async def test_telegram_error(
        self, 
        scraper_settings, 
        db_settings, 
        telegram_settings,
        mock_web_driver_pool,
        mock_kwork_parser,
        db_session,
    ):
        """Test handling of Telegram notification errors."""
        # Configure the mock KworkParser to return no projects
        mock_kwork_parser.parse_project_cards.return_value = []
        
        # Create a mock TelegramReporter that raises an exception
        with patch('integrations.kwork_scraper.TelegramReporter') as mock_reporter:
            mock_reporter_instance = MagicMock()
            mock_reporter_instance.send_report = AsyncMock(side_effect=Exception("Telegram error"))
            mock_reporter.return_value = mock_reporter_instance
            
            # Create a scraper instance
            scraper = KworkScraper(scraper_settings, db_settings, telegram_settings)
            
            # Run the scraper
            result = await scraper.scrape_projects()
            
            # Verify the result
            assert result["status"] == "completed"  # Telegram errors should not fail the scrape
            
            # Verify the error was logged
            # (In a real test, you would check the logs here)
    
    @pytest.mark.asyncio
    async def test_network_error(
        self, 
        scraper_settings, 
        db_settings, 
        telegram_settings,
        mock_web_driver_pool,
        db_session,
    ):
        """Test handling of network errors."""
        # Configure the mock WebDriver to simulate a network error
        mock_pool, mock_driver = mock_web_driver_pool
        mock_driver.get.side_effect = TimeoutError("Network timeout")
        
        # Create a scraper instance with a short timeout
        settings = scraper_settings.copy()
        settings.request_timeout = 1
        
        scraper = KworkScraper(settings, db_settings, telegram_settings)
        
        # Run the scraper
        result = await scraper.scrape_projects()
        
        # Verify the result
        assert result["status"] == "error"
        assert result["errors_encountered"] > 0
        
        # Verify the error was logged
        # (In a real test, you would check the logs here)
        
        # Verify the scrape session was saved with error status
        result = await db_session.execute(select(ScrapeSession))
        sessions = result.scalars().all()
        
        assert len(sessions) == 1
        assert sessions[0].status == "error"
    
    @pytest.mark.asyncio
    async def test_unhandled_exception(
        self, 
        scraper_settings, 
        db_settings, 
        telegram_settings,
        mock_web_driver_pool,
        db_session,
    ):
        """Test handling of unhandled exceptions."""
        # Create a mock WebDriverPool that raises an unexpected exception
        mock_pool, mock_driver = mock_web_driver_pool
        mock_pool.acquire.side_effect = Exception("Unexpected error")
        
        # Create a scraper instance
        scraper = KworkScraper(scraper_settings, db_settings, telegram_settings)
        
        # Run the scraper
        result = await scraper.scrape_projects()
        
        # Verify the result
        assert result["status"] == "error"
        assert result["errors_encountered"] > 0
        
        # Verify the error was logged
        # (In a real test, you would check the logs here)
        
        # Verify the scrape session was saved with error status
        result = await db_session.execute(select(ScrapeSession))
        sessions = result.scalars().all()
        
        assert len(sessions) == 1
        assert sessions[0].status == "error"
    
    @pytest.mark.asyncio
    async def test_keyboard_interrupt(
        self, 
        scraper_settings, 
        db_settings, 
        telegram_settings,
        mock_web_driver_pool,
        db_session,
    ):
        """Test handling of keyboard interrupt."""
        # Create a mock WebDriver that simulates a long-running operation
        mock_pool, mock_driver = mock_web_driver_pool
        mock_driver.get = AsyncMock(side_effect=KeyboardInterrupt())
        
        # Create a scraper instance
        scraper = KworkScraper(scraper_settings, db_settings, telegram_settings)
        
        # Run the scraper
        result = await scraper.scrape_projects()
        
        # Verify the result
        assert result["status"] == "interrupted"
        
        # Verify the scrape session was saved with interrupted status
        result = await db_session.execute(select(ScrapeSession))
        sessions = result.scalars().all()
        
        assert len(sessions) == 1
        assert sessions[0].status == "interrupted"
