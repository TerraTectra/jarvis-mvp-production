"""Tests for the Kwork scraper database integration."""
import asyncio
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock, call

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

# Add the src directory to the path for imports
sys.path.append(str(Path(__file__).parent.parent / "src"))

from integrations.kwork_scraper import KworkScraper
from database.kwork_models import KworkProject, ProjectSnapshot, ScrapeSession
from config import ScraperSettings, DatabaseSettings, TelegramSettings


class TestKworkScraperDatabase:
    """Test cases for the Kwork scraper database integration."""
    
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
            enabled=False,
            token=None,
            chat_id=None,
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
    
    @pytest.mark.asyncio
    async def test_save_projects(
        self, 
        scraper_settings, 
        db_settings, 
        telegram_settings,
        mock_web_driver_pool,
        mock_kwork_parser,
        db_session,
    ):
        """Test saving projects to the database."""
        # Create test projects
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
        await scraper.scrape_projects()
        
        # Verify the projects were saved to the database
        result = await db_session.execute(select(KworkProject))
        projects = result.scalars().all()
        
        assert len(projects) == 2
        
        # Verify the project details
        project1 = next(p for p in projects if p.kwork_id == "test1")
        assert project1.title == "Test Project 1"
        assert project1.url == "https://kwork.ru/projects/test1"
        assert project1.price == 1000.0
        assert project1.category == "Web Development"
        assert project1.description == "Test project 1 description"
        
        # Verify the snapshots were created
        result = await db_session.execute(select(ProjectSnapshot))
        snapshots = result.scalars().all()
        
        assert len(snapshots) == 2
        
        # Verify the scrape session was created
        result = await db_session.execute(select(ScrapeSession))
        sessions = result.scalars().all()
        
        assert len(sessions) == 1
        session = sessions[0]
        assert session.pages_scraped == 1
        assert session.projects_found == 2
        assert session.new_projects == 2
        assert session.errors_encountered == 0
        assert session.status == "completed"
    
    @pytest.mark.asyncio
    async def test_update_existing_project(
        self, 
        scraper_settings, 
        db_settings, 
        telegram_settings,
        mock_web_driver_pool,
        mock_kwork_parser,
        db_session,
    ):
        """Test updating an existing project with new data."""
        # Create an existing project in the database
        existing_project = KworkProject(
            kwork_id="test1",
            title="Old Title",
            url="https://kwork.ru/projects/test1",
            price=500.0,
            category="Old Category",
            description="Old description",
            created_at=datetime.utcnow() - timedelta(days=1),
        )
        
        db_session.add(existing_project)
        await db_session.commit()
        
        # Create test projects with updated data
        test_projects = [
            {
                "kwork_id": "test1",
                "title": "New Title",
                "url": "https://kwork.ru/projects/test1",
                "price": 1000.0,
                "category": "New Category",
                "description": "New description",
                "date_posted": "2023-01-01T00:00:00",
            },
        ]
        
        # Configure the mock parser to return the test project
        mock_kwork_parser.parse_project_cards.return_value = test_projects
        
        # Create a scraper instance
        scraper = KworkScraper(scraper_settings, db_settings, telegram_settings)
        
        # Run the scraper
        result = await scraper.scrape_projects()
        
        # Verify the result
        assert result["status"] == "completed"
        assert result["projects_found"] == 1
        assert result["new_projects"] == 0  # Project was updated, not created
        
        # Verify the project was updated in the database
        result = await db_session.execute(
            select(KworkProject).where(KworkProject.kwork_id == "test1")
        )
        project = result.scalar_one()
        
        assert project.title == "New Title"
        assert project.price == 1000.0
        assert project.category == "New Category"
        assert project.description == "New description"
        assert project.updated_at > project.created_at
        
        # Verify a new snapshot was created
        result = await db_session.execute(
            select(ProjectSnapshot).where(ProjectSnapshot.project_id == project.id)
        )
        snapshots = result.scalars().all()
        
        assert len(snapshots) == 1
        assert snapshots[0].price == 1000.0
    
    @pytest.mark.asyncio
    async def test_skip_unchanged_project(
        self, 
        scraper_settings, 
        db_settings, 
        telegram_settings,
        mock_web_driver_pool,
        mock_kwork_parser,
        db_session,
    ):
        """Test that unchanged projects are not updated."""
        # Create an existing project in the database
        existing_project = KworkProject(
            kwork_id="test1",
            title="Test Project",
            url="https://kwork.ru/projects/test1",
            price=1000.0,
            category="Web Development",
            description="Test project description",
            created_at=datetime.utcnow() - timedelta(days=1),
        )
        
        db_session.add(existing_project)
        await db_session.commit()
        
        # Create test projects with the same data
        test_projects = [
            {
                "kwork_id": "test1",
                "title": "Test Project",
                "url": "https://kwork.ru/projects/test1",
                "price": 1000.0,
                "category": "Web Development",
                "description": "Test project description",
                "date_posted": "2023-01-01T00:00:00",
            },
        ]
        
        # Configure the mock parser to return the test project
        mock_kwork_parser.parse_project_cards.return_value = test_projects
        
        # Create a scraper instance
        scraper = KworkScraper(scraper_settings, db_settings, telegram_settings)
        
        # Run the scraper
        result = await scraper.scrape_projects()
        
        # Verify the result
        assert result["status"] == "completed"
        assert result["projects_found"] == 1
        assert result["new_projects"] == 0  # Project was not updated
        
        # Verify the project was not updated in the database
        result = await db_session.execute(
            select(KworkProject).where(KworkProject.kwork_id == "test1")
        )
        project = result.scalar_one()
        
        assert project.updated_at is None  # No update occurred
        
        # No new snapshot should have been created
        result = await db_session.execute(
            select(ProjectSnapshot).where(ProjectSnapshot.project_id == project.id)
        )
        snapshots = result.scalars().all()
        
        assert len(snapshots) == 0
    
    @pytest.mark.asyncio
    async def test_save_scrape_session(
        self, 
        scraper_settings, 
        db_settings, 
        telegram_settings,
        mock_web_driver_pool,
        mock_kwork_parser,
        db_session,
    ):
        """Test saving scrape session data."""
        # Configure the mock parser to return no projects
        mock_kwork_parser.parse_project_cards.return_value = []
        
        # Create a scraper instance
        scraper = KworkScraper(scraper_settings, db_settings, telegram_settings)
        
        # Run the scraper
        result = await scraper.scrape_projects()
        
        # Verify the result
        assert result["status"] == "completed"
        
        # Verify the scrape session was saved to the database
        result = await db_session.execute(select(ScrapeSession))
        sessions = result.scalars().all()
        
        assert len(sessions) == 1
        session = sessions[0]
        
        assert session.pages_scraped == 1
        assert session.projects_found == 0
        assert session.new_projects == 0
        assert session.errors_encountered == 0
        assert session.status == "completed"
        assert session.start_time is not None
        assert session.end_time is not None
        assert session.end_time >= session.start_time
    
    @pytest.mark.asyncio
    async def test_save_scrape_session_with_error(
        self, 
        scraper_settings, 
        db_settings, 
        telegram_settings,
        mock_web_driver_pool,
        mock_kwork_parser,
        db_session,
    ):
        """Test saving scrape session data when an error occurs."""
        # Configure the mock parser to raise an exception
        mock_kwork_parser.parse_project_cards.side_effect = Exception("Test error")
        
        # Create a scraper instance
        scraper = KworkScraper(scraper_settings, db_settings, telegram_settings)
        
        # Run the scraper
        result = await scraper.scrape_projects()
        
        # Verify the result
        assert result["status"] == "error"
        
        # Verify the scrape session was saved to the database with error status
        result = await db_session.execute(select(ScrapeSession))
        sessions = result.scalars().all()
        
        assert len(sessions) == 1
        session = sessions[0]
        
        assert session.status == "error"
        assert session.errors_encountered > 0
        assert session.end_time is not None
    
    @pytest.mark.asyncio
    async def test_concurrent_scraping(
        self, 
        scraper_settings, 
        db_settings, 
        telegram_settings,
        mock_web_driver_pool,
        mock_kwork_parser,
        db_session,
    ):
        """Test that multiple scrapers can run concurrently without conflicts."""
        # Create test projects
        test_projects = [
            {
                "kwork_id": f"test{i}",
                "title": f"Test Project {i}",
                "url": f"https://kwork.ru/projects/test{i}",
                "price": 1000.0 * (i + 1),
                "category": "Web Development",
                "description": f"Test project {i} description",
                "date_posted": f"2023-01-{i+1:02d}T00:00:00",
            }
            for i in range(10)
        ]
        
        # Configure the mock parser to return test projects
        mock_kwork_parser.parse_project_cards.return_value = test_projects
        
        # Create multiple scraper instances
        scrapers = [
            KworkScraper(scraper_settings, db_settings, telegram_settings)
            for _ in range(3)
        ]
        
        # Run the scrapers concurrently
        tasks = [scraper.scrape_projects() for scraper in scrapers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify all scrapers completed successfully
        for result in results:
            if isinstance(result, Exception):
                raise result
            assert result["status"] == "completed"
        
        # Verify the projects were saved to the database
        result = await db_session.execute(select(KworkProject))
        projects = result.scalars().all()
        
        # Should have 10 unique projects (duplicates should be handled)
        assert len(projects) == 10
        
        # Verify the scrape sessions were saved
        result = await db_session.execute(select(ScrapeSession))
        sessions = result.scalars().all()
        
        assert len(sessions) == 3  # One session per scraper
        
        # Verify the snapshots were created
        result = await db_session.execute(select(ProjectSnapshot))
        snapshots = result.scalars().all()
        
        # Should have 30 snapshots (10 projects * 3 scrapers)
        assert len(snapshots) == 30
