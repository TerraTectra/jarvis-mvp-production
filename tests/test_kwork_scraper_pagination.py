"""Tests for the Kwork scraper pagination functionality."""
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
from integrations.kwork_parser import KworkParser
from database.kwork_models import KworkProject, ProjectSnapshot, ScrapeSession
from config import ScraperSettings, DatabaseSettings, TelegramSettings


class TestKworkScraperPagination:
    """Test cases for the Kwork scraper pagination functionality."""
    
    @pytest.fixture
    def scraper_settings(self):
        """Create a test scraper settings object."""
        return ScraperSettings(
            base_url="https://kwork.ru/projects",
            headless=True,
            pool_size=1,
            max_pages=3,  # Test with 3 pages
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
            enabled=False,
            token=None,
            chat_id=None,
        )
    
    @pytest.fixture
    def mock_web_driver(self):
        """Create a mock WebDriver."""
        mock_driver = MagicMock()
        mock_driver.session_id = "test-session-id"
        mock_driver.get = AsyncMock()
        mock_driver.page_source = "<html><body>Test page</body></html>"
        mock_driver.quit = AsyncMock()
        return mock_driver
    
    @pytest.fixture
    def mock_web_driver_pool(self, mock_web_driver):
        """Create a mock WebDriverPool."""
        with patch('integrations.kwork_scraper.WebDriverPool') as mock_pool:
            mock_pool_instance = AsyncMock()
            mock_pool_instance.acquire = AsyncMock(return_value=mock_web_driver)
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
    
    @pytest.mark.asyncio
    async def test_pagination(
        self, 
        scraper_settings, 
        db_settings, 
        telegram_settings,
        mock_web_driver_pool,
        mock_kwork_parser,
        db_session,
    ):
        """Test that the scraper handles pagination correctly."""
        # Create test projects for each page
        projects_per_page = 10
        test_projects = [
            {
                "kwork_id": f"test-{page}-{i}",
                "title": f"Test Project {page}-{i}",
                "url": f"https://kwork.ru/projects/test-{page}-{i}",
                "price": 1000.0 * (i + 1),
                "category": "Web Development",
                "description": f"Test project {page}-{i} description",
                "date_posted": f"2023-01-{i+1:02d}T00:00:00",
            }
            for page in range(1, scraper_settings.max_pages + 1)
            for i in range(projects_per_page)
        ]
        
        # Configure the mock parser to return different projects for each page
        def get_projects_for_page(*args, **kwargs):
            page = kwargs.get('page', 1)
            start_idx = (page - 1) * projects_per_page
            end_idx = page * projects_per_page
            return test_projects[start_idx:end_idx]
        
        mock_kwork_parser.parse_project_cards.side_effect = get_projects_for_page
        
        # Create a scraper instance
        scraper = KworkScraper(scraper_settings, db_settings, telegram_settings)
        
        # Run the scraper
        result = await scraper.scrape_projects()
        
        # Verify the result
        assert result["status"] == "completed"
        assert result["pages_scraped"] == scraper_settings.max_pages
        assert result["projects_found"] == scraper_settings.max_pages * projects_per_page
        assert result["new_projects"] == scraper_settings.max_pages * projects_per_page
        assert result["errors_encountered"] == 0
        
        # Verify the parser was called for each page
        assert mock_kwork_parser.parse_project_cards.call_count == scraper_settings.max_pages
        
        # Verify the correct page numbers were used
        for page in range(1, scraper_settings.max_pages + 1):
            assert call(driver=mock_web_driver_pool._acquire.return_value, page=page) in mock_kwork_parser.parse_project_cards.call_args_list
        
        # Verify all projects were saved to the database
        projects = (await db_session.execute("SELECT * FROM kwork_projects")).fetchall()
        assert len(projects) == scraper_settings.max_pages * projects_per_page
        
        # Verify the snapshots were created
        snapshots = (await db_session.execute("SELECT * FROM project_snapshots")).fetchall()
        assert len(snapshots) == scraper_settings.max_pages * projects_per_page
    
    @pytest.mark.asyncio
    async def test_pagination_with_duplicates(
        self, 
        scraper_settings, 
        db_settings, 
        telegram_settings,
        mock_web_driver_pool,
        mock_kwork_parser,
        db_session,
    ):
        """Test that the scraper handles duplicate projects across pages."""
        # Create test projects with duplicates across pages
        projects_per_page = 10
        duplicate_project = {
            "kwork_id": "duplicate-123",
            "title": "Duplicate Project",
            "url": "https://kwork.ru/projects/duplicate-123",
            "price": 1000.0,
            "category": "Web Development",
            "description": "This project appears on multiple pages",
            "date_posted": "2023-01-01T00:00:00",
        }
        
        test_projects = []
        for page in range(1, scraper_settings.max_pages + 1):
            # Add some unique projects
            page_projects = [
                {
                    "kwork_id": f"test-{page}-{i}",
                    "title": f"Test Project {page}-{i}",
                    "url": f"https://kwork.ru/projects/test-{page}-{i}",
                    "price": 1000.0 * (i + 1),
                    "category": "Web Development",
                    "description": f"Test project {page}-{i} description",
                    "date_posted": f"2023-01-{i+1:02d}T00:00:00",
                }
                for i in range(projects_per_page - 1)  # Leave room for the duplicate
            ]
            
            # Add the duplicate project to each page
            page_projects.append(duplicate_project)
            test_projects.append(page_projects)
        
        # Configure the mock parser to return different projects for each page
        def get_projects_for_page(*args, **kwargs):
            page = kwargs.get('page', 1)
            return test_projects[page - 1]
        
        mock_kwork_parser.parse_project_cards.side_effect = get_projects_for_page
        
        # Create a scraper instance
        scraper = KworkScraper(scraper_settings, db_settings, telegram_settings)
        
        # Run the scraper
        result = await scraper.scrape_projects()
        
        # Verify the result
        assert result["status"] == "completed"
        assert result["pages_scraped"] == scraper_settings.max_pages
        
        # The duplicate project should only be counted once
        expected_unique_projects = (scraper_settings.max_pages * (projects_per_page - 1)) + 1
        assert result["projects_found"] == scraper_settings.max_pages * projects_per_page
        assert result["new_projects"] == expected_unique_projects
        assert result["errors_encountered"] == 0
        
        # Verify the duplicate project was only saved once
        projects = (await db_session.execute("SELECT * FROM kwork_projects WHERE kwork_id = 'duplicate-123'")).fetchall()
        assert len(projects) == 1
        
        # But a new snapshot was created for each occurrence
        snapshots = (await db_session.execute("SELECT * FROM project_snapshots WHERE project_id = :project_id", 
                                           {"project_id": projects[0][0]})).fetchall()
        assert len(snapshots) == scraper_settings.max_pages
    
    @pytest.mark.asyncio
    async def test_pagination_with_empty_page(
        self, 
        scraper_settings, 
        db_settings, 
        telegram_settings,
        mock_web_driver_pool,
        mock_kwork_parser,
        db_session,
    ):
        """Test that the scraper stops when it encounters an empty page."""
        # Create test projects for the first two pages
        projects_per_page = 10
        test_projects = [
            {
                "kwork_id": f"test-{page}-{i}",
                "title": f"Test Project {page}-{i}",
                "url": f"https://kwork.ru/projects/test-{page}-{i}",
                "price": 1000.0 * (i + 1),
                "category": "Web Development",
                "description": f"Test project {page}-{i} description",
                "date_posted": f"2023-01-{i+1:02d}T00:00:00",
            }
            for page in range(1, 3)  # Only two pages of data
            for i in range(projects_per_page)
        ]
        
        # Configure the mock parser to return projects for the first two pages, then an empty list
        def get_projects_for_page(*args, **kwargs):
            page = kwargs.get('page', 1)
            if page > 2:  # Empty page for page 3
                return []
            
            start_idx = (page - 1) * projects_per_page
            end_idx = page * projects_per_page
            return test_projects[start_idx:end_idx]
        
        mock_kwork_parser.parse_project_cards.side_effect = get_projects_for_page
        
        # Create a scraper instance with max_pages=3
        scraper = KworkScraper(scraper_settings, db_settings, telegram_settings)
        
        # Run the scraper
        result = await scraper.scrape_projects()
        
        # Verify the result
        assert result["status"] == "completed"
        assert result["pages_scraped"] == 2  # Should stop after the empty page
        assert result["projects_found"] == 2 * projects_per_page
        assert result["new_projects"] == 2 * projects_per_page
        assert result["errors_encountered"] == 0
        
        # Verify the parser was only called twice (for pages 1 and 2)
        assert mock_kwork_parser.parse_project_cards.call_count == 2
    
    @pytest.mark.asyncio
    async def test_pagination_with_error(
        self, 
        scraper_settings, 
        db_settings, 
        telegram_settings,
        mock_web_driver_pool,
        mock_kwork_parser,
        db_session,
    ):
        """Test that the scraper handles errors during pagination."""
        # Configure the mock parser to raise an exception on the second page
        def get_projects_for_page(*args, **kwargs):
            page = kwargs.get('page', 1)
            if page == 2:
                raise Exception("Test error")
            
            # Return some test projects for the first page
            return [
                {
                    "kwork_id": f"test-{page}-{i}",
                    "title": f"Test Project {page}-{i}",
                    "url": f"https://kwork.ru/projects/test-{page}-{i}",
                    "price": 1000.0 * (i + 1),
                    "category": "Web Development",
                    "description": f"Test project {page}-{i} description",
                    "date_posted": f"2023-01-{i+1:02d}T00:00:00",
                }
                for i in range(5)  # 5 projects per page
            ]
        
        mock_kwork_parser.parse_project_cards.side_effect = get_projects_for_page
        
        # Create a scraper instance
        scraper = KworkScraper(scraper_settings, db_settings, telegram_settings)
        
        # Run the scraper
        result = await scraper.scrape_projects()
        
        # Verify the result
        assert result["status"] == "error"
        assert result["pages_scraped"] == 1  # Should stop after the error
        assert result["projects_found"] == 5
        assert result["new_projects"] == 5
        assert result["errors_encountered"] == 1  # One error occurred
        
        # Verify the projects from the first page were still saved
        projects = (await db_session.execute("SELECT * FROM kwork_projects")).fetchall()
        assert len(projects) == 5
