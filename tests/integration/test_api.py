"""Integration tests for the Kwork scraper API."""
import os
import sys
import asyncio
import pytest
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

# Add the src directory to the path for imports
sys.path.append(str(Path(__file__).parent.parent.parent / "src"))

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from database.database import get_db_session
from database.kwork_models import Base, KworkProject, ProjectSnapshot, ScrapeSession
from api.main import app
from config import DatabaseSettings

# Use a test database in memory for API tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


class TestKworkScraperAPI:
    """Integration tests for the Kwork scraper API endpoints."""
    
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
        
        self.original_get_db = get_db_session
        app.dependency_overrides[get_db_session] = override_get_db
        
        # Create a test client
        self.client = TestClient(app)
        
        # Add test data
        await self._create_test_data()
        
        yield
        
        # Clean up
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await self.engine.dispose()
        
        # Clear overrides
        app.dependency_overrides.clear()
    
    async def _create_test_data(self):
        """Create test data in the database."""
        async with self.SessionLocal() as session:
            # Create a test scrape session
            session.add_all([
                ScrapeSession(
                    id=1,
                    started_at=datetime.utcnow() - timedelta(hours=1),
                    completed_at=datetime.utcnow(),
                    status="completed",
                    pages_scraped=5,
                    projects_found=10,
                    new_projects=5,
                    errors_encountered=0,
                ),
                ScrapeSession(
                    id=2,
                    started_at=datetime.utcnow() - timedelta(days=1),
                    completed_at=datetime.utcnow() - timedelta(hours=23),
                    status="completed",
                    pages_scraped=3,
                    projects_found=6,
                    new_projects=3,
                    errors_encountered=0,
                ),
            ])
            
            # Create test projects
            session.add_all([
                KworkProject(
                    kwork_id="test1",
                    title="Test Project 1",
                    url="https://kwork.ru/projects/test1",
                    price=1000.0,
                    category="Web Development",
                    created_at=datetime.utcnow() - timedelta(days=1),
                    updated_at=datetime.utcnow(),
                ),
                KworkProject(
                    kwork_id="test2",
                    title="Test Project 2",
                    url="https://kwork.ru/projects/test2",
                    price=2000.0,
                    category="Design",
                    created_at=datetime.utcnow() - timedelta(hours=1),
                    updated_at=datetime.utcnow(),
                ),
            ])
            
            # Create test snapshots
            session.add_all([
                ProjectSnapshot(
                    kwork_id="test1",
                    title="Test Project 1",
                    description="Test project 1 description",
                    price=1000.0,
                    category="Web Development",
                    date_posted=datetime.utcnow() - timedelta(days=1),
                    scrape_session_id=1,
                ),
                ProjectSnapshot(
                    kwork_id="test2",
                    title="Test Project 2",
                    description="Test project 2 description",
                    price=2000.0,
                    category="Design",
                    date_posted=datetime.utcnow() - timedelta(hours=1),
                    scrape_session_id=1,
                ),
            ])
            
            await session.commit()
    
    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test the health check endpoint."""
        response = self.client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
    
    @pytest.mark.asyncio
    async def test_get_projects(self):
        """Test getting a list of projects."""
        response = self.client.get("/api/projects")
        assert response.status_code == 200
        
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] == 2
        assert len(data["items"]) == 2
        
        # Test pagination
        response = self.client.get("/api/projects?limit=1&offset=1")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["items"]) == 1
        assert data["total"] == 2
    
    @pytest.mark.asyncio
    async def test_get_project(self):
        """Test getting a single project by ID."""
        # Test existing project
        response = self.client.get("/api/projects/test1")
        assert response.status_code == 200
        
        data = response.json()
        assert data["kwork_id"] == "test1"
        assert data["title"] == "Test Project 1"
        
        # Test non-existent project
        response = self.client.get("/api/projects/nonexistent")
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_get_project_snapshots(self):
        """Test getting snapshots for a project."""
        # Test existing project with snapshots
        response = self.client.get("/api/projects/test1/snapshots")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data) == 1
        assert data[0]["kwork_id"] == "test1"
        
        # Test non-existent project
        response = self.client.get("/api/projects/nonexistent/snapshots")
        assert response.status_code == 200
        assert response.json() == []
    
    @pytest.mark.asyncio
    async def test_get_scrape_sessions(self):
        """Test getting a list of scrape sessions."""
        response = self.client.get("/api/scrape-sessions")
        assert response.status_code == 200
        
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] == 2
        assert len(data["items"]) == 2
        
        # Test pagination
        response = self.client.get("/api/scrape-sessions?limit=1")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["items"]) == 1
        assert data["total"] == 2
    
    @pytest.mark.asyncio
    async def test_get_scrape_session(self):
        """Test getting a single scrape session by ID."""
        # Test existing session
        response = self.client.get("/api/scrape-sessions/1")
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == 1
        assert data["status"] == "completed"
        
        # Test non-existent session
        response = self.client.get("/api/scrape-sessions/999")
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_get_scrape_session_projects(self):
        """Test getting projects from a specific scrape session."""
        response = self.client.get("/api/scrape-sessions/1/projects")
        assert response.status_code == 200
        
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] == 2  # Both projects are from session 1
        
        # Test non-existent session
        response = self.client.get("/api/scrape-sessions/999/projects")
        assert response.status_code == 200
        assert response.json()["total"] == 0
    
    @pytest.mark.asyncio
    async def test_search_projects(self):
        """Test searching for projects."""
        # Search by title
        response = self.client.get("/api/projects/search?query=Project")
        assert response.status_code == 200
        
        data = response.json()
        assert data["total"] == 2
        
        # Search by category
        response = self.client.get("/api/projects/search?category=Design")
        assert response.status_code == 200
        
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["category"] == "Design"
        
        # Search with no results
        response = self.client.get("/api/projects/search?query=Nonexistent")
        assert response.status_code == 200
        assert data["total"] >= 0


if __name__ == "__main__":
    pytest.main(["-v", "tests/integration/test_api.py"])
