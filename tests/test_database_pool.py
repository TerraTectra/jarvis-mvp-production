"""Tests for the database connection pool."""
import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Add the src directory to the path for imports
sys.path.append(str(Path(__file__).parent.parent / "src"))

from database.database import Database, get_db_session, init_db, close_db, get_engine, get_session_factory
from database.kwork_models import Base
from config import DatabaseSettings


class TestDatabase:
    """Test cases for the Database class."""
    
    @pytest.fixture
    def db_settings(self):
        """Create a test database settings object."""
        return DatabaseSettings(
            url="sqlite+aiosqlite:///:memory:",
            echo=False,
        )
    
    @pytest.fixture
    def db(self, db_settings):
        """Create a test database instance."""
        return Database(db_settings)
    
    @pytest.mark.asyncio
    async def test_init_db(self, db):
        """Test initializing the database."""
        # Initialize the database
        await db.init_db()
        
        # Verify the engine and session factory were created
        assert db.engine is not None
        assert db.session_factory is not None
        
        # Verify the tables were created
        async with db.engine.begin() as conn:
            tables = await conn.run_sync(
                lambda sync_conn: inspect(sync_conn).get_table_names()
            )
            
            assert "kwork_projects" in tables
            assert "project_snapshots" in tables
            assert "scrape_sessions" in tables
    
    @pytest.mark.asyncio
    async def test_create_session(self, db):
        """Test creating a database session."""
        # Initialize the database
        await db.init_db()
        
        # Create a session
        async with db.create_session() as session:
            # Verify the session is an instance of AsyncSession
            assert isinstance(session, AsyncSession)
            
            # Verify the session is bound to the engine
            assert session.bind is db.engine
    
    @pytest.mark.asyncio
    async def test_close_db(self, db):
        """Test closing the database connection."""
        # Initialize the database
        await db.init_db()
        
        # Get the engine and session factory
        engine = db.engine
        session_factory = db.session_factory
        
        # Close the database
        await db.close()
        
        # Verify the engine and session factory were set to None
        assert db.engine is None
        assert db.session_factory is None
        
        # Verify the engine was disposed
        with pytest.raises(Exception):
            await engine.connect()
    
    @pytest.mark.asyncio
    async def test_context_manager(self, db):
        """Test using the database as a context manager."""
        async with db:
            # Verify the database was initialized
            assert db.engine is not None
            assert db.session_factory is not None
            
            # Verify we can create a session
            async with db.create_session() as session:
                assert session is not None
        
        # Verify the database was closed
        assert db.engine is None
        assert db.session_factory is None


class TestDatabaseModule:
    """Test cases for the database module functions."""
    
    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        """Set up test fixtures."""
        # Set the test database URL
        self.test_db_url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
        
        # Patch the get_settings function to return test settings
        self.settings_patcher = patch(
            "database.database.get_settings",
            return_value=MagicMock(
                database=MagicMock(
                    url=self.test_db_url,
                    echo=False,
                )
            )
        )
        self.mock_get_settings = self.settings_patcher.start()
        
        # Initialize the database
        asyncio.run(init_db())
        
        yield
        
        # Clean up
        self.settings_patcher.stop()
        asyncio.run(close_db())
    
    @pytest.mark.asyncio
    async def test_init_db(self):
        """Test the init_db function."""
        # Verify the engine and session factory were created
        engine = get_engine()
        session_factory = get_session_factory()
        
        assert engine is not None
        assert session_factory is not None
        
        # Verify the tables were created
        async with engine.begin() as conn:
            tables = await conn.run_sync(
                lambda sync_conn: inspect(sync_conn).get_table_names()
            )
            
            assert "kwork_projects" in tables
            assert "project_snapshots" in tables
            assert "scrape_sessions" in tables
    
    @pytest.mark.asyncio
    async def test_get_db_session(self):
        """Test the get_db_session function."""
        # Get a database session
        async with get_db_session() as session:
            # Verify the session is an instance of AsyncSession
            assert isinstance(session, AsyncSession)
            
            # Verify the session is bound to the engine
            engine = get_engine()
            assert session.bind is engine
    
    @pytest.mark.asyncio
    async def test_close_db(self):
        """Test the close_db function."""
        # Get the engine and session factory
        engine = get_engine()
        session_factory = get_session_factory()
        
        # Close the database
        await close_db()
        
        # Verify the engine and session factory were set to None
        with pytest.raises(RuntimeError):
            get_engine()
        
        with pytest.raises(RuntimeError):
            get_session_factory()
        
        # Verify the engine was disposed
        with pytest.raises(Exception):
            await engine.connect()
    
    @pytest.mark.asyncio
    async def test_concurrent_sessions(self):
        """Test that multiple sessions can be used concurrently."""
        # Create multiple sessions
        sessions = []
        for i in range(5):
            session = await get_db_session().__aenter__()
            sessions.append(session)
        
        # Verify all sessions are unique
        assert len(set(id(s) for s in sessions)) == 5
        
        # Close all sessions
        for session in sessions:
            await session.close()
    
    @pytest.mark.asyncio
    async def test_session_rollback_on_error(self):
        """Test that sessions are rolled back on error."""
        from sqlalchemy import insert
        from database.kwork_models import KworkProject
        
        try:
            async with get_db_session() as session:
                # Create a test project
                project = KworkProject(
                    kwork_id="test123",
                    title="Test Project",
                    url="https://kwork.ru/projects/test123",
                    price=1000.0,
                    category="Web Development",
                    description="Test project description",
                )
                
                # Add the project to the session
                session.add(project)
                
                # Simulate an error
                raise Exception("Test error")
        except Exception:
            pass
        
        # Verify the project was not committed to the database
        async with get_db_session() as session:
            result = await session.execute(
                "SELECT COUNT(*) FROM kwork_projects WHERE kwork_id = 'test123'"
            )
            count = result.scalar()
            
            assert count == 0
    
    @pytest.mark.asyncio
    async def test_session_commit(self):
        """Test committing a transaction."""
        from database.kwork_models import KworkProject
        
        # Create a test project
        project = KworkProject(
            kwork_id="test456",
            title="Test Project",
            url="https://kwork.ru/projects/test456",
            price=1000.0,
            category="Web Development",
            description="Test project description",
        )
        
        # Add and commit the project
        async with get_db_session() as session:
            session.add(project)
            await session.commit()
        
        # Verify the project was committed to the database
        async with get_db_session() as session:
            result = await session.execute(
                "SELECT COUNT(*) FROM kwork_projects WHERE kwork_id = 'test456'"
            )
            count = result.scalar()
            
            assert count == 1
