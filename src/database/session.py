"""
Database connection and session management.
"""
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, AsyncEngine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from dotenv import load_dotenv
from typing import AsyncGenerator

# Load environment variables
load_dotenv()

# Database URL (defaults to SQLite)
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./kwork_scraper_staging.db")

# Create async engine
engine: AsyncEngine = create_async_engine(
    SQLALCHEMY_DATABASE_URL,
    echo=True,
    future=True,
    poolclass=NullPool if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else None,
    connect_args={"check_same_thread": False} 
    if SQLALCHEMY_DATABASE_URL.startswith("sqlite") 
    else {}
)

# Async session factory
async_session = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

# For backward compatibility
SessionLocal = async_session

# Base class for models
Base = declarative_base()

# Dependency to get DB session
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that provides a database session."""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize the database by creating all tables."""
    # Import models to ensure they are registered with SQLAlchemy's Base
    from src import models  # noqa: F401
    from src.kwork import models as kwork_models  # noqa: F401
    
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    print("✅ Database tables created/verified")
