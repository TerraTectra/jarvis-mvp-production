"""Tests for the main Kwork scraper functionality."""
import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock, call

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

# Add the src directory to the path for imports
sys.path.append(str(Path(__file__).parent.parent / "src"))

from integrations.kwork_scraper import KworkScraper, main
from database.kwork_models import KworkProject, ProjectSnapshot, ScrapeSession
from config import ScraperSettings, DatabaseSettings, TelegramSettings, Settings


class TestKworkScraperMain:
    """Test cases for the main Kwork scraper functionality."""
    
    @pytest.fixture
    def scraper_settings(self):
        """Create a test scraper settings object."""
        return ScraperSettings(
            base_url="https://kwork.ru/projects",
            headless=True,
            pool_size=2,
            max_pages=2,
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
            # Create a mock driver
            mock_driver = MagicMock()
            mock_driver.session_id = "test-session-id"
            mock_driver.get = AsyncMock()
            mock_driver.page_source = "<html><body>Test page</body></html>"
            mock_driver.quit = AsyncMock()
            
            # Configure the mock pool
            mock_pool_instance = AsyncMock()
            mock_pool_instance.acquire = AsyncMock(return_value=mock_driver)
            mock_pool_instance.release = AsyncMock()
            mock_pool.return_value = mock_pool_instance
            
            yield mock_pool_instance, mock_driver
    
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
            mock_reporter.send_report = AsyncMock()
            mock_reporter.return_value = mock_reporter_instance
            
            yield mock_reporter_instance
    
    @pytest.fixture
    def mock_database(self, db_session):
        """Create a mock database session."""
        with patch('integrations.kwork_scraper.get_db_session') as mock_session:
            mock_session.return_value = db_session
            yield db_session
    
    @pytest.mark.asyncio
    async def test_scrape_projects(
        self, 
        scraper_settings, 
        db_settings, 
        telegram_settings,
        mock_web_driver_pool,
        mock_kwork_parser,
        mock_telegram_reporter,
        mock_database,
        db_session
    ):
        """Test scraping projects from Kwork."""
        # Create test data
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
            {
                "kwork_id": "test2",
                "title": "Test Project 2",
                "url": "https://kwork.ru/projects/test2",
                "price": 2000.0,
                "category": "Design",
                "description": "Test project 2 description",
                "date_posted": "2023-01-02T00:00:00",
            },
        ]
        
        # Configure the mock parser to return test projects
        mock_kwork_parser.parse_project_cards.return_value = test_projects
        
        # Create a scraper instance
        scraper = KworkScraper(scraper_settings, db_settings, telegram_settings)
        
        # Run the scraper
        result = await scraper.scrape_projects()
        
        # Verify the result
        assert result["status"] == "completed"
        assert result["pages_scraped"] == 2
        assert result["projects_found"] == 2
        assert result["new_projects"] == 2
        assert result["errors_encountered"] == 0
        
        # Verify the parser was called with the correct arguments
        mock_kwork_parser.parse_project_cards.assert_called()
        
        # Verify the projects were saved to the database
        projects = (await db_session.execute("SELECT * FROM kwork_projects")).fetchall()
        assert len(projects) == 2
        
        # Verify the snapshots were created
        snapshots = (await db_session.execute("SELECT * FROM project_snapshots")).fetchall()
        assert len(snapshots) == 2
        
        # Verify the scrape session was created
        sessions = (await db_session.execute("SELECT * FROM scrape_sessions")).fetchall()
        assert len(sessions) == 1
        
        # Verify the report was sent
        mock_telegram_reporter.send_report.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_scrape_projects_with_errors(
        self, 
        scraper_settings, 
        db_settings, 
        telegram_settings,
        mock_web_driver_pool,
        mock_kwork_parser,
        mock_telegram_reporter,
        mock_database,
    ):
        """Test scraping projects with errors."""
        # Configure the mock parser to raise an exception
        mock_kwork_parser.parse_project_cards.side_effect = Exception("Test error")
        
        # Create a scraper instance
        scraper = KworkScraper(scraper_settings, db_settings, telegram_settings)
        
        # Run the scraper
        result = await scraper.scrape_projects()
        
        # Verify the result
        assert result["status"] == "error"
        assert result["errors_encountered"] > 0
        
        # Verify the error was logged
        # (In a real test, you would check the logs here)
    
    @pytest.mark.asyncio
    async def test_main_function(
        self, 
        scraper_settings, 
        db_settings, 
        telegram_settings,
        mock_web_driver_pool,
        mock_kwork_parser,
        mock_telegram_reporter,
        mock_database,
    ):
        """Test the main function."""
        # Create test settings
        settings = Settings(
            scraper=scraper_settings,
            database=db_settings,
            telegram=telegram_settings,
        )
        
        # Patch the get_settings function
        with patch('integrations.kwork_scraper.get_settings', return_value=settings):
            # Run the main function
            await main()
            
            # Verify the scraper was called
            mock_kwork_parser.parse_project_cards.assert_called()
            
            # Verify the report was sent
            mock_telegram_reporter.send_report.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_main_function_with_args(
        self, 
        scraper_settings, 
        db_settings, 
        telegram_settings,
        mock_web_driver_pool,
        mock_kwork_parser,
        mock_telegram_reporter,
        mock_database,
    ):
        """Test the main function with command-line arguments."""
        # Create test settings
        settings = Settings(
            scraper=scraper_settings,
            database=db_settings,
            telegram=telegram_settings,
        )
        
        # Test with --max-pages argument
        with patch('sys.argv', ['kwork_scraper.py', '--max-pages', '5']), \
             patch('integrations.kwork_scraper.get_settings', return_value=settings):
            
            # Run the main function
            await main()
            
            # Verify the scraper was called with the correct max_pages
            assert mock_kwork_parser.parse_project_calls[0][0].max_pages == 5
        
        # Test with --headless=False argument
        with patch('sys.argv', ['kwork_scraper.py', '--headless', 'False']), \
             patch('integrations.kwork_scraper.get_settings', return_value=settings):
            
            # Run the main function
            await main()
            
            # Verify the scraper was called with headless=False
            assert mock_web_driver_pool[0].call_args[1]['headless'] is False
    
    @pytest.mark.asyncio
    async def test_main_function_keyboard_interrupt(
        self, 
        scraper_settings, 
        db_settings, 
        telegram_settings,
        mock_web_driver_pool,
        mock_kwork_parser,
        mock_telegram_reporter,
        mock_database,
    ):
        """Test handling of KeyboardInterrupt in the main function."""
        # Configure the mock parser to raise KeyboardInterrupt
        mock_kwork_parser.parse_project_cards.side_effect = KeyboardInterrupt()
        
        # Create test settings
        settings = Settings(
            scraper=scraper_settings,
            database=db_settings,
            telegram=telegram_settings,
        )
        
        # Patch the get_settings function
        with patch('integrations.kwork_scraper.get_settings', return_value=settings):
            # Run the main function
            await main()
            
            # Verify the scraper was interrupted
            mock_telegram_reporter.send_report.assert_called_once()
            
            # Verify the report indicates the scraper was interrupted
            report_call = mock_telegram_reporter.send_report.call_args[0][0]
            assert "interrupted" in report_call.lower()
    
    @pytest.mark.asyncio
    async def test_main_function_unhandled_exception(
        self, 
        scraper_settings, 
        db_settings, 
        telegram_settings,
        mock_web_driver_pool,
        mock_kwork_parser,
        mock_telegram_reporter,
        mock_database,
    ):
        """Test handling of unhandled exceptions in the main function."""
        # Configure the mock parser to raise an exception
        mock_kwork_parser.parse_project_cards.side_effect = Exception("Test error")
        
        # Create test settings
        settings = Settings(
            scraper=scraper_settings,
            database=db_settings,
            telegram=telegram_settings,
        )
        
        # Patch the get_settings function
        with patch('integrations.kwork_scraper.get_settings', return_value=settings), \
             pytest.raises(Exception, match="Test error"):
            
            # Run the main function
            await main()
            
            # Verify the error was reported
            mock_telegram_reporter.send_report.assert_called_once()
            
            # Verify the report indicates an error occurred
            report_call = mock_telegram_reporter.send_report.call_args[0][0]
            assert "error" in report_call.lower()
