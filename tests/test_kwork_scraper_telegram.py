"""Tests for the Kwork scraper Telegram notifications."""
import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

# Add the src directory to the path for imports
sys.path.append(str(Path(__file__).parent.parent / "src"))

from integrations.kwork_scraper import KworkScraper
from integrations.telegram_reporter import TelegramReporter
from database.kwork_models import KworkProject, ProjectSnapshot, ScrapeSession
from config import ScraperSettings, DatabaseSettings, TelegramSettings


class TestKworkScraperTelegram:
    """Test cases for the Kwork scraper Telegram notifications."""
    
    @pytest.fixture
    def scraper_settings(self):
        """Create a test scraper settings object."""
        return ScraperSettings(
            base_url="https://kwork.ru/projects",
            headless=True,
            pool_size=1,
            max_pages=1,
            request_timeout=30,
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
            
            yield mock_pool_instance
    
    @pytest.fixture
    def mock_kwork_parser(self):
        """Create a mock KworkParser."""
        with patch('integrations.kwork_scraper.KworkParser') as mock_parser:
            mock_parser_instance = MagicMock()
            mock_parser_instance.parse_project_cards = AsyncMock(return_value=[])
            mock_parser.return_value = mock_parser_instance
            
            yield mock_parser_instance
    
    @pytest.fixture
    def mock_telegram_reporter(self):
        """Create a mock TelegramReporter."""
        with patch('integrations.kwork_scraper.TelegramReporter') as mock_reporter:
            mock_reporter_instance = MagicMock()
            mock_reporter_instance.send_report = AsyncMock()
            mock_reporter.return_value = mock_reporter_instance
            
            yield mock_reporter_instance
    
    @pytest.mark.asyncio
    async def test_telegram_notification_on_success(
        self, 
        scraper_settings, 
        db_settings, 
        telegram_settings,
        mock_web_driver_pool,
        mock_kwork_parser,
        mock_telegram_reporter,
        db_session,
    ):
        """Test that a success notification is sent to Telegram."""
        # Configure the mock parser to return test projects
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
        
        # Create a scraper instance
        scraper = KworkScraper(scraper_settings, db_settings, telegram_settings)
        
        # Run the scraper
        result = await scraper.scrape_projects()
        
        # Verify the result
        assert result["status"] == "completed"
        
        # Verify the success notification was sent
        mock_telegram_reporter.send_report.assert_called_once()
        
        # Verify the report contains the expected information
        report = mock_telegram_reporter.send_report.call_args[0][0]
        assert "✅ Scraping completed successfully" in report
        assert "📄 Pages scraped: 1" in report
        assert "📊 Projects found: 1" in report
        assert "🆕 New projects: 1" in report
        assert "❌ Errors: 0" in report
    
    @pytest.mark.asyncio
    async def test_telegram_notification_on_error(
        self, 
        scraper_settings, 
        db_settings, 
        telegram_settings,
        mock_web_driver_pool,
        mock_kwork_parser,
        mock_telegram_reporter,
        db_session,
    ):
        """Test that an error notification is sent to Telegram."""
        # Configure the mock parser to raise an exception
        mock_kwork_parser.parse_project_cards.side_effect = Exception("Test error")
        
        # Create a scraper instance
        scraper = KworkScraper(scraper_settings, db_settings, telegram_settings)
        
        # Run the scraper
        result = await scraper.scrape_projects()
        
        # Verify the result
        assert result["status"] == "error"
        
        # Verify the error notification was sent
        mock_telegram_reporter.send_report.assert_called_once()
        
        # Verify the report contains the expected information
        report = mock_telegram_reporter.send_report.call_args[0][0]
        assert "❌ Scraping failed" in report
        assert "Test error" in report
    
    @pytest.mark.asyncio
    async def test_telegram_notification_on_interrupt(
        self, 
        scraper_settings, 
        db_settings, 
        telegram_settings,
        mock_web_driver_pool,
        mock_kwork_parser,
        mock_telegram_reporter,
        db_session,
    ):
        """Test that an interrupt notification is sent to Telegram."""
        # Configure the mock parser to raise KeyboardInterrupt
        mock_kwork_parser.parse_project_cards.side_effect = KeyboardInterrupt()
        
        # Create a scraper instance
        scraper = KworkScraper(scraper_settings, db_settings, telegram_settings)
        
        # Run the scraper
        result = await scraper.scrape_projects()
        
        # Verify the result
        assert result["status"] == "interrupted"
        
        # Verify the interrupt notification was sent
        mock_telegram_reporter.send_report.assert_called_once()
        
        # Verify the report contains the expected information
        report = mock_telegram_reporter.send_report.call_args[0][0]
        assert "⏸ Scraping interrupted by user" in report
    
    @pytest.mark.asyncio
    async def test_telegram_notification_disabled(
        self, 
        scraper_settings, 
        db_settings, 
        telegram_settings,
        mock_web_driver_pool,
        mock_kwork_parser,
        db_session,
    ):
        """Test that no notification is sent when Telegram is disabled."""
        # Disable Telegram notifications
        telegram_settings.enabled = False
        
        # Create a mock TelegramReporter
        with patch('integrations.kwork_scraper.TelegramReporter') as mock_reporter:
            mock_reporter_instance = MagicMock()
            mock_reporter_instance.send_report = AsyncMock()
            mock_reporter.return_value = mock_reporter_instance
            
            # Create a scraper instance
            scraper = KworkScraper(scraper_settings, db_settings, telegram_settings)
            
            # Run the scraper
            result = await scraper.scrape_projects()
            
            # Verify the result
            assert result["status"] == "completed"
            
            # Verify no notification was sent
            mock_reporter_instance.send_report.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_telegram_notification_error(
        self, 
        scraper_settings, 
        db_settings, 
        telegram_settings,
        mock_web_driver_pool,
        mock_kwork_parser,
        mock_telegram_reporter,
        db_session,
    ):
        """Test that Telegram notification errors are handled gracefully."""
        # Configure the mock parser to return test projects
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
        
        # Configure the mock TelegramReporter to raise an exception
        mock_telegram_reporter.send_report.side_effect = Exception("Telegram error")
        
        # Create a scraper instance
        scraper = KworkScraper(scraper_settings, db_settings, telegram_settings)
        
        # Run the scraper (should not raise an exception)
        result = await scraper.scrape_projects()
        
        # Verify the result
        assert result["status"] == "completed"
        
        # Verify the error was logged
        # (In a real test, you would check the logs here)
    
    @pytest.mark.asyncio
    async def test_telegram_notification_format(
        self, 
        scraper_settings, 
        db_settings, 
        telegram_settings,
    ):
        """Test the format of the Telegram notification."""
        from integrations.telegram_reporter import format_report
        
        # Create a test result
        result = {
            "status": "completed",
            "pages_scraped": 5,
            "projects_found": 25,
            "new_projects": 10,
            "errors_encountered": 2,
            "start_time": "2023-01-01T00:00:00",
            "end_time": "2023-01-01T01:00:00",
            "duration": "1:00:00",
        }
        
        # Format the report
        report = format_report(result)
        
        # Verify the report contains the expected information
        assert "✅ Scraping completed successfully" in report
        assert "📄 Pages scraped: 5" in report
        assert "📊 Projects found: 25" in report
        assert "🆕 New projects: 10" in report
        assert "❌ Errors: 2" in report
        assert "⏱ Duration: 1:00:00" in report
        
        # Test with error status
        result["status"] = "error"
        result["error"] = "Test error"
        
        report = format_report(result)
        
        assert "❌ Scraping failed" in report
        assert "Test error" in report
        
        # Test with interrupt status
        result["status"] = "interrupted"
        
        report = format_report(result)
        
        assert "⏸ Scraping interrupted by user" in report
