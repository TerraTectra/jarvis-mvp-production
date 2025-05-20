"""Test configuration and fixtures."""
import asyncio
import os
import sys
from pathlib import Path
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)

# Set test environment variables before any imports
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["ALGORITHM"] = "HS256"

# Now import the database models and other dependencies
from src.database import Base, engine, SessionLocal, get_db
from src.database.kwork_crud import KworkCRUD
from src.kwork.models import KworkOrder, KworkReply, KworkFilter

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import Kwork models after path is set
from src.kwork.models import KworkOrder, KworkReply, KworkFilter  # noqa: E402
from unittest.mock import patch, AsyncMock  # noqa: E402


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def async_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create and configure a SQLAlchemy async engine for testing."""
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Drop all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session(async_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """Create a new database session for testing."""
    async with async_engine.connect() as conn:
        # Begin a transaction
        transaction = await conn.begin()
        
        # Create a session
        TestingSessionLocal = async_sessionmaker(
            autocommit=False, autoflush=False, bind=conn
        )
        session = TestingSessionLocal()
        
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()


@pytest.fixture
def db_crud(db_session: AsyncSession) -> KworkCRUD:
    """Create a KworkCRUD instance with a test session."""
    return KworkCRUD(db_session)


@pytest.fixture
def test_client():
    """Create a test client for the FastAPI app."""
    from fastapi.testclient import TestClient
    from src.main import app

    # Override database dependency
    def override_get_db():
        try:
            db = SessionLocal()
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client
    
    # Clean up
    app.dependency_overrides.clear()


@pytest.fixture
def mock_browser_pool():
    """
    Mock the BrowserPool class for testing without real browser instances.
    
    This prevents actual browser windows from opening during tests.
    """
    with patch('src.integrations.kwork_scraper.BrowserPool') as mock_pool:
        # Create a mock instance of BrowserPool
        mock_instance = mock_pool.return_value
        
        # Set up the async context manager methods
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = None
        
        # Set up the get_browser method to return a mock browser
        mock_browser = AsyncMock()
        mock_instance.get_browser.return_value = mock_browser
        
        yield mock_instance


@pytest.fixture
def mock_webdriver():
    """
    Mock the Selenium WebDriver for testing without a real browser.
    
    This prevents actual browser windows from opening during tests.
    """
    with patch('selenium.webdriver.Chrome') as mock_driver:
        # Create a mock WebDriver instance
        mock_instance = MagicMock()
        mock_driver.return_value = mock_instance
        
        # Set up default return values for WebDriver methods
        mock_instance.page_source = "<html><body>Test Page</body></html>"
        mock_instance.find_elements.return_value = []
        
        yield mock_instance


@pytest.fixture
async def test_scraper(session: AsyncSession, mock_browser_pool):
    """
    Create a test KworkScraper instance with a mock browser pool.
    
    This provides a fully configured scraper instance for testing.
    """
    # Create a scraper instance with test configuration
    scraper = KworkScraper(
        base_url="https://kwork.ru/projects",
        pool_size=1,
        headless=True,
        max_pages=1,
    )
    
    # Override the database session with the test session
    scraper.db_session = session
    scraper.crud = KworkCRUD(session)
    
    # Set up the mock browser pool
    scraper.browser_pool = mock_browser_pool
    
    # Create a mock browser for the pool to return
    mock_browser = MagicMock()
    mock_browser_pool.get_browser.return_value.__aenter__.return_value = mock_browser
    
    # Set up default return values for the mock browser
    mock_browser.page_source = "<html><body>Test Page</body></html>"
    mock_browser.find_elements.return_value = []
    
    # Yield the scraper to the test
    yield scraper
    
    # Cleanup: close the scraper
    await scraper.close()


@pytest.fixture
def sample_project_data():
    """
    Provide sample project data for testing.
    
    This fixture returns a dictionary with sample project data that can be used
    to create test projects in the database.
    """
    return {
        "kwork_id": "123",
        "title": "Test Project",
        "url": "https://kwork.ru/project/123",
        "price": 1000.0,
        "category": "Web Development",
        "description": "This is a test project",
        "date_posted": "2023-01-01T00:00:00",
    }
