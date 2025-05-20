"""Test database configuration and setup."""
import os
import pytest
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Use in-memory SQLite database for testing with async support
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def engine():
    """Create and configure an async SQLAlchemy engine for testing."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=True)
    return engine

@pytest.fixture(scope="session")
async def tables(engine):
    """Create all database tables."""
    from src.database.models import Base
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.fixture
async def db_session(engine, tables):
    """Create a clean database session for testing."""
    async with engine.connect() as conn:
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

@pytest.fixture(scope="session")
async def app():
    """Create a test FastAPI application."""
    # Import here to avoid circular imports
    from fastapi import FastAPI
    from src.api import router as api_router
    
    app = FastAPI()
    app.include_router(api_router)
    
    # Set test environment variables
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    os.environ["SECRET_KEY"] = "test-secret-key"
    
    return app

@pytest.fixture
async def client(app, db_session):
    """Create a test client for the FastAPI application."""
    from fastapi.testclient import TestClient
    from fastapi import Depends
    from src.dependencies import get_db
    
    # Override the database dependency
    async def override_get_db():
        try:
            yield db_session
        finally:
            await db_session.close()
    
    app.dependency_overrides[get_db] = override_get_db
    
    async with TestClient(app) as test_client:
        yield test_client
    
    # Clean up
    app.dependency_overrides.clear()
