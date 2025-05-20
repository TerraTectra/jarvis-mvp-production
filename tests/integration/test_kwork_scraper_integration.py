"""Integration tests for the Kwork scraper."""
import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select

# Add the src directory to the path for imports
sys.path.append(str(Path(__file__).parent.parent.parent / "src"))

from integrations.kwork_scraper import KworkScraper
from database.kwork_models import Base, KworkProject, ProjectSnapshot, ScrapeSession
from database.database import get_db_session
from config import ScraperSettings, DatabaseSettings, TelegramSettings

# Use a test database in memory for integration tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

class TestKworkScraperIntegration:
    """Integration tests for the Kwork scraper."""
    
    @pytest.fixture(autouse=True)
    async def setup_db(self):
        """Set up the test database."""
        # Create engine and tables
        self.engine = create_async_engine(TEST_DATABASE_URL, echo=False)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        # Create session factory
        self.SessionLocal = sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )
        
        # Override the get_db_session dependency
        async def override_get_db():
            async with self.SessionLocal() as session:
                yield session
        
        # Save the original get_db_session
        self.original_get_db = get_db_session
        # Replace the original with our override
        get_db_session.__code__ = override_get_db.__code__
        
        yield
        
        # Clean up
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await self.engine.dispose()
    
    @pytest.fixture
    def scraper_settings(self):
        """Create test scraper settings."""
        return ScraperSettings(
            base_url="https://kwork.ru/projects",
            headless=True,
            pool_size=1,
            max_pages=1,
            request_timeout=30,
        )
    
    @pytest.fixture
    def db_settings(self):
        """Create test database settings."""
        return DatabaseSettings(
            url=TEST_DATABASE_URL,
            echo=False,
        )
    
    @pytest.fixture
    def telegram_settings(self):
        """Create test Telegram settings."""
        return TelegramSettings(
            enabled=False,  # Disable for tests
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
    
    @pytest.fixture
    def mock_kwork_parser(self):
        """Create a mock KworkParser."""
        with patch('integrations.kwork_scraper.KworkParser') as mock_parser:
            mock_parser_instance = MagicMock()
            mock_parser_instance.parse_project_cards = AsyncMock(return_value=[])
            mock_parser.return_value = mock_parser_instance
            
            yield mock_parser_instance
    
    @pytest.mark.asyncio
    async def test_scrape_projects_integration(
        self,
        scraper_settings,
        db_settings,
        telegram_settings,
        mock_web_driver_pool,
        mock_kwork_parser,
    ):
        """Test the full scraping workflow with database integration."""
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
        
        mock_kwork_parser.parse_project_cards.return_value = test_projects
        
        # Create a scraper instance
        scraper = KworkScraper(scraper_settings, db_settings, telegram_settings)
        
        # Run the scraper
        result = await scraper.scrape_projects()
        
        # Verify the result
        assert result["status"] == "completed"
        assert result["projects_found"] == 2
        assert result["new_projects"] == 2
        
        # Verify the projects were saved to the database
        async with self.SessionLocal() as session:
            # Check projects
            projects_result = await session.execute(select(KworkProject))
            projects = projects_result.scalars().all()
            
            assert len(projects) == 2
            assert {p.kwork_id for p in projects} == {"test1", "test2"}
            
            # Check snapshots
            snapshots_result = await session.execute(select(ProjectSnapshot))
            snapshots = snapshots_result.scalars().all()
            
            assert len(snapshots) == 2
            assert {s.kwork_id for s in snapshots} == {"test1", "test2"}
            
            # Check scrape session
            sessions_result = await session.execute(select(ScrapeSession))
            sessions = sessions_result.scalars().all()
            
            assert len(sessions) == 1
            assert sessions[0].status == "completed"
            assert sessions[0].pages_scraped == 1
            assert sessions[0].projects_found == 2
            assert sessions[0].new_projects == 2
    
    @pytest.mark.asyncio
    async def test_scrape_projects_with_duplicates(
        self,
        scraper_settings,
        db_settings,
        telegram_settings,
        mock_web_driver_pool,
        mock_kwork_parser,
    ):
        """Test scraping with duplicate projects."""
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
        
        # First run - should save the project
        result1 = await scraper.scrape_projects()
        assert result1["status"] == "completed"
        assert result1["projects_found"] == 1
        assert result1["new_projects"] == 1
        
        # Second run - should detect the project as a duplicate
        result2 = await scraper.scrape_projects()
        assert result2["status"] == "completed"
        assert result2["projects_found"] == 1
        assert result2["new_projects"] == 0
        
        # Verify only one project was saved to the database
        async with self.SessionLocal() as session:
            projects_result = await session.execute(select(KworkProject))
            projects = projects_result.scalars().all()
            
            assert len(projects) == 1
            assert projects[0].kwork_id == "test1"
            
            # Verify two snapshots were created (one for each scrape)
            snapshots_result = await session.execute(select(ProjectSnapshot))
            snapshots = snapshots_result.scalars().all()
            
            assert len(snapshots) == 2
            assert all(s.kwork_id == "test1" for s in snapshots)
    
    @pytest.mark.asyncio
    async def test_scrape_projects_with_error(
        self,
        scraper_settings,
        db_settings,
        telegram_settings,
        mock_web_driver_pool,
        mock_kwork_parser,
    ):
        """Test error handling during scraping."""
        # Configure the mock parser to raise an exception
        mock_kwork_parser.parse_project_cards.side_effect = Exception("Test error")
        
        # Create a scraper instance
        scraper = KworkScraper(scraper_settings, db_settings, telegram_settings)
        
        # Run the scraper
        result = await scraper.scrape_projects()
        
        # Verify the result
        assert result["status"] == "error"
        assert result["errors_encountered"] > 0
        
        # Verify the error was recorded in the database
        async with self.SessionLocal() as session:
            sessions_result = await session.execute(select(ScrapeSession))
            sessions = sessions_result.scalars().all()
            
            assert len(sessions) == 1
            assert sessions[0].status == "error"
            assert "Test error" in sessions[0].error_message
    
    @pytest.mark.asyncio
    async def test_scrape_projects_with_empty_page(
        self,
        scraper_settings,
        db_settings,
        telegram_settings,
        mock_web_driver_pool,
        mock_kwork_parser,
    ):
        """Test scraping an empty page."""
        # Configure the mock parser to return no projects
        mock_kwork_parser.parse_project_cards.return_value = []
        
        # Create a scraper instance
        scraper = KworkScraper(scraper_settings, db_settings, telegram_settings)
        
        # Run the scraper
        result = await scraper.scrape_projects()
        
        # Verify the result
        assert result["status"] == "completed"
        assert result["projects_found"] == 0
        assert result["new_projects"] == 0
        
        # Verify the session was recorded in the database
        async with self.SessionLocal() as session:
            sessions_result = await session.execute(select(ScrapeSession))
            sessions = sessions_result.scalars().all()
            
            assert len(sessions) == 1
            assert sessions[0].status == "completed"
            assert sessions[0].projects_found == 0
            assert sessions[0].new_projects == 0
    
    @pytest.mark.asyncio
    async def test_scrape_projects_with_pagination(
        self,
        scraper_settings,
        db_settings,
        telegram_settings,
        mock_web_driver_pool,
        mock_kwork_parser,
    ):
        """Test scraping with multiple pages."""
        # Configure the mock parser to return different projects on each page
        def mock_parse_project_cards(*args, **kwargs):
            page = kwargs.get("page", 1)
            
            if page == 1:
                return [
                    {
                        "kwork_id": f"test{page}-1",
                        "title": f"Test Project {page}-1",
                        "url": f"https://kwork.ru/projects/test{page}-1",
                        "price": 1000.0,
                        "category": "Web Development",
                        "description": f"Test project {page}-1 description",
                        "date_posted": "2023-01-01T00:00:00",
                    },
                ]
            elif page == 2:
                return [
                    {
                        "kwork_id": f"test{page}-1",
                        "title": f"Test Project {page}-1",
                        "url": f"https://kwork.ru/projects/test{page}-1",
                        "price": 2000.0,
                        "category": "Design",
                        "description": f"Test project {page}-1 description",
                        "date_posted": "2023-01-02T00:00:00",
                    },
                ]
            else:
                return []
        
        mock_kwork_parser.parse_project_cards.side_effect = mock_parse_project_cards
        
        # Create a scraper instance with max_pages=2
        settings = ScraperSettings(
            base_url="https://kwork.ru/projects",
            headless=True,
            pool_size=1,
            max_pages=2,
            request_timeout=30,
        )
        
        scraper = KworkScraper(settings, db_settings, telegram_settings)
        
        # Run the scraper
        result = await scraper.scrape_projects()
        
        # Verify the result
        assert result["status"] == "completed"
        assert result["pages_scraped"] == 2
        assert result["projects_found"] == 2
        assert result["new_projects"] == 2
        
        # Verify the projects were saved to the database
        async with self.SessionLocal() as session:
            projects_result = await session.execute(select(KworkProject))
            projects = projects_result.scalars().all()
            
            assert len(projects) == 2
            assert {p.kwork_id for p in projects} == {"test1-1", "test2-1"}
            
            # Check scrape session
            sessions_result = await session.execute(select(ScrapeSession))
            sessions = sessions_result.scalars().all()
            
            assert len(sessions) == 1
            assert sessions[0].status == "completed"
            assert sessions[0].pages_scraped == 2
            assert sessions[0].projects_found == 2
            assert sessions[0].new_projects == 2
