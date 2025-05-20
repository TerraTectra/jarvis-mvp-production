"""Tests for the Kwork scraper."""
import asyncio
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.database.kwork_models import Base, KworkProject, ProjectSnapshot, ScrapeSession
from src.database.kwork_crud import KworkCRUD
from src.integrations.kwork_scraper import KworkScraper
from src.integrations.browser_pool import BrowserPool, BrowserConfig

# Test database URL
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="module")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
async def db_engine():
    """Create a test database and tables."""
    engine = create_async_engine(TEST_DB_URL, echo=False)
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Drop all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine):
    """Create a new database session for a test."""
    connection = await db_engine.connect()
    transaction = await connection.begin()
    
    # Create a session maker
    async_session = sessionmaker(
        bind=connection,
        expire_on_commit=False,
        class_=AsyncSession,
    )
    
    session = async_session()
    
    yield session
    
    await session.close()
    await transaction.rollback()
    await connection.close()


@pytest.fixture
async def crud(db_session):
    """Create a KworkCRUD instance with a test session."""
    return KworkCRUD(db_session)


@pytest.fixture
def mock_browser_pool():
    """Mock the BrowserPool class."""
    with patch('src.integrations.kwork_scraper.BrowserPool') as mock_pool:
        mock_instance = mock_pool.return_value
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = None
        yield mock_instance


@pytest.fixture
def mock_webdriver():
    """Mock the Selenium WebDriver."""
    with patch('selenium.webdriver.Chrome') as mock_driver:
        mock_driver.return_value = MagicMock()
        yield mock_driver


@pytest.fixture
async def test_scraper(db_session):
    """Create a test KworkScraper instance."""
    scraper = KworkScraper(
        base_url="https://kwork.ru/projects",
        pool_size=1,
        headless=True,
        max_pages=1,
    )
    
    # Override the database session
    scraper.db_session = db_session
    scraper.crud = KworkCRUD(db_session)
    
    # Create a mock browser pool
    scraper.browser_pool = AsyncMock(spec=BrowserPool)
    
    # Create a mock browser
    mock_browser = MagicMock()
    scraper.browser_pool.get_browser.return_value.__aenter__.return_value = mock_browser
    
    yield scraper
    
    # Cleanup
    await scraper.close()


@pytest.mark.asyncio
async def test_scraper_initialization(test_scraper):
    """Test that the scraper initializes correctly."""
    assert test_scraper is not None
    assert test_scraper.base_url == "https://kwork.ru/projects"
    assert test_scraper.pool_size == 1
    assert test_scraper.headless is True
    assert test_scraper.max_pages == 1


@pytest.mark.asyncio
async def test_scrape_page_success(test_scraper, mock_webdriver):
    """Test successful page scraping."""
    # Mock the browser and page source
    mock_browser = test_scraper.browser_pool.get_browser.return_value.__aenter__.return_value
    mock_browser.page_source = """
    <html>
        <body>
            <div class="card">
                <a href="/project/123" class="wants-card__header-title">Test Project</a>
                <div class="wants-card__description">Test Description</div>
                <div class="wants-card__price">1 000 ₽</div>
                <div class="wants-card__category">Web Development</div>
                <div class="wants-card__published">5 минут назад</div>
            </div>
        </body>
    </html>
    """
    
    # Mock the find_elements method to return a list with our mock element
    mock_element = MagicMock()
    mock_element.get_attribute.return_value = "/project/123"
    mock_element.find_element.return_value.text = "Test Project"
    
    # Set up the return values for the mock element's find_elements calls
    mock_element.find_elements.return_value = []
    
    # Set up the return value for the browser's find_elements
    mock_browser.find_elements.return_value = [mock_element]
    
    # Test the _scrape_page method
    projects = await test_scraper._scrape_page(1)
    
    # Verify the results
    assert len(projects) == 1
    assert projects[0]["title"] == "Test Project"
    assert projects[0]["url"] == "https://kwork.ru/project/123"
    assert projects[0]["price"] == 1000.0
    assert projects[0]["category"] == "Web Development"


@pytest.mark.asyncio
async def test_scrape_page_no_projects(test_scraper, mock_webdriver):
    """Test scraping a page with no projects."""
    # Mock the browser and page source with no projects
    mock_browser = test_scraper.browser_pool.get_browser.return_value.__aenter__.return_value
    mock_browser.page_source = "<html><body><div>No projects here</div></body></html>"
    mock_browser.find_elements.return_value = []
    
    # Test the _scrape_page method
    projects = await test_scraper._scrape_page(1)
    
    # Verify no projects were found
    assert len(projects) == 0


@pytest.mark.asyncio
async def test_scrape_projects(test_scraper, mock_webdriver):
    """Test the main scrape_projects method."""
    # Mock the _scrape_page method to return test data
    test_projects = [
        {
            "kwork_id": "123",
            "title": "Test Project 1",
            "url": "https://kwork.ru/project/123",
            "price": 1000.0,
            "category": "Web Development",
            "description": "Test Description 1",
            "date_posted": "2023-01-01T00:00:00",
        },
        {
            "kwork_id": "456",
            "title": "Test Project 2",
            "url": "https://kwork.ru/project/456",
            "price": 2000.0,
            "category": "Design",
            "description": "Test Description 2",
            "date_posted": "2023-01-02T00:00:00",
        },
    ]
    
    # Patch the _scrape_page method to return our test data
    with patch.object(test_scraper, '_scrape_page', return_value=test_projects) as mock_scrape:
        # Test the scrape_projects method
        projects = await test_scraper.scrape_projects(limit=2)
        
        # Verify the results
        assert len(projects) == 2
        assert projects[0]["title"] == "Test Project 1"
        assert projects[1]["title"] == "Test Project 2"
        
        # Verify the database was updated
        db_projects = await test_scraper.crud.get_recent_projects(limit=10)
        assert len(db_projects) == 2
        assert {p.title for p in db_projects} == {"Test Project 1", "Test Project 2"}


@pytest.mark.asyncio
async def test_scrape_projects_with_errors(test_scraper, mock_webdriver, caplog):
    """Test error handling in the scrape_projects method."""
    # Mock the _scrape_page method to raise an exception
    with patch.object(
        test_scraper, 
        '_scrape_page', 
        side_effect=Exception("Test error")
    ) as mock_scrape:
        # Test the scrape_projects method with error handling
        projects = await test_scraper.scrape_projects()
        
        # Verify the results
        assert len(projects) == 0
        
        # Verify the error was logged
        assert "Error during scraping" in caplog.text


@pytest.mark.asyncio
async def test_scraper_context_manager():
    """Test the scraper as a context manager."""
    with patch('src.integrations.kwork_scraper.BrowserPool') as mock_pool_class:
        # Set up the mock browser pool
        mock_pool = AsyncMock()
        mock_pool.__aenter__.return_value = mock_pool
        mock_pool_class.return_value = mock_pool
        
        # Create and use the scraper in a context manager
        async with KworkScraper() as scraper:
            assert scraper is not None
            assert scraper.browser_pool is not None
        
        # Verify the browser pool was properly closed
        mock_pool.__aexit__.assert_called_once()


@pytest.mark.asyncio
async def test_cli_scrape_command(capsys, monkeypatch, tmp_path):
    """Test the CLI scrape command."""
    # Create a test output file
    output_file = tmp_path / "projects.json"
    
    # Mock the scrape_kwork function
    async def mock_scrape_kwork(*args, **kwargs):
        return [
            {
                "kwork_id": "123",
                "title": "Test Project",
                "url": "https://kwork.ru/project/123",
                "price": 1000.0,
                "category": "Web Development",
            }
        ]
    
    # Apply the mock
    monkeypatch.setattr(
        'src.integrations.kwork_scraper.scrape_kwork',
        mock_scrape_kwork
    )
    
    # Import the CLI module
    from src.cli import cli
    
    # Test the CLI command
    result = await cli.main(["scrape", "--max-pages", "1", "--output", str(output_file)])
    
    # Verify the output
    captured = capsys.readouterr()
    assert "Scraped 1 projects" in captured.out
    
    # Verify the output file was created
    assert output_file.exists()
    with open(output_file, 'r') as f:
        projects = json.load(f)
        assert len(projects) == 1
        assert projects[0]["title"] == "Test Project"
