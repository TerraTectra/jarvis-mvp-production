"""Tests for the database models and CRUD operations."""
import asyncio
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.kwork_models import (
    Base,
    KworkProject,
    ProjectSnapshot,
    ScrapeSession,
)
from src.database.kwork_crud import KworkCRUD


@pytest.mark.asyncio
async def test_create_project(session: AsyncSession, db_crud: KworkCRUD):
    """Test creating a new project in the database."""
    # Create a test project
    project_data = {
        "kwork_id": "test123",
        "title": "Test Project",
        "url": "https://kwork.ru/projects/test123",
        "price": 1000.0,
        "category": "Web Development",
        "description": "Test project description",
        "date_posted": datetime.utcnow(),
    }
    
    # Create the project
    project = await db_crud.create_project(project_data)
    
    # Verify the project was created
    assert project is not None
    assert project.id is not None
    assert project.kwork_id == "test123"
    assert project.title == "Test Project"
    assert project.price == 1000.0
    
    # Verify a snapshot was created
    assert len(project.snapshots) == 1
    assert project.snapshots[0].price == 1000.0


@pytest.mark.asyncio
async def test_update_project(session: AsyncSession, db_crud: KworkCRUD):
    """Test updating an existing project in the database."""
    # Create a test project
    project_data = {
        "kwork_id": "test456",
        "title": "Test Project",
        "url": "https://kwork.ru/projects/test456",
        "price": 1000.0,
        "category": "Web Development",
    }
    project = await db_crud.create_project(project_data)
    
    # Update the project
    updated_data = {
        "title": "Updated Project",
        "price": 1500.0,
        "description": "Updated description",
    }
    updated_project = await db_crud.update_project(project.id, updated_data)
    
    # Verify the project was updated
    assert updated_project.title == "Updated Project"
    assert updated_project.price == 1500.0
    assert updated_project.description == "Updated description"
    
    # Verify a new snapshot was created
    assert len(updated_project.snapshots) == 2
    assert updated_project.snapshots[0].price == 1000.0  # Original price
    assert updated_project.snapshots[1].price == 1500.0  # Updated price


@pytest.mark.asyncio
async def test_get_project(session: AsyncSession, db_crud: KworkCRUD):
    """Test retrieving a project from the database."""
    # Create a test project
    project_data = {
        "kwork_id": "test789",
        "title": "Test Project",
        "url": "https://kwork.ru/projects/test789",
        "price": 1000.0,
        "category": "Web Development",
    }
    created_project = await db_crud.create_project(project_data)
    
    # Retrieve the project
    retrieved_project = await db_crud.get_project(created_project.id)
    
    # Verify the project was retrieved
    assert retrieved_project is not None
    assert retrieved_project.id == created_project.id
    assert retrieved_project.title == "Test Project"


@pytest.mark.asyncio
async def test_get_project_by_kwork_id(session: AsyncSession, db_crud: KworkCRUD):
    """Test retrieving a project by its Kwork ID."""
    # Create a test project
    project_data = {
        "kwork_id": "test101112",
        "title": "Test Project",
        "url": "https://kwork.ru/projects/test101112",
        "price": 1000.0,
        "category": "Web Development",
    }
    await db_crud.create_project(project_data)
    
    # Retrieve the project by Kwork ID
    retrieved_project = await db_crud.get_project_by_kwork_id("test101112")
    
    # Verify the project was retrieved
    assert retrieved_project is not None
    assert retrieved_project.kwork_id == "test101112"


@pytest.mark.asyncio
async def test_get_recent_projects(session: AsyncSession, db_crud: KworkCRUD):
    """Test retrieving recent projects from the database."""
    # Create multiple test projects
    for i in range(5):
        project_data = {
            "kwork_id": f"test{i}",
            "title": f"Test Project {i}",
            "url": f"https://kwork.ru/projects/test{i}",
            "price": 1000.0 + (i * 100),
            "category": "Web Development",
        }
        await db_crud.create_project(project_data)
    
    # Retrieve recent projects
    recent_projects = await db_crud.get_recent_projects(limit=3)
    
    # Verify the correct number of projects were retrieved
    assert len(recent_projects) == 3
    
    # Verify the projects are ordered by creation date (newest first)
    assert recent_projects[0].kwork_id == "test4"
    assert recent_projects[1].kwork_id == "test3"
    assert recent_projects[2].kwork_id == "test2"


@pytest.mark.asyncio
async def test_create_scrape_session(session: AsyncSession, db_crud: KworkCRUD):
    """Test creating a new scrape session."""
    # Create a scrape session
    session_data = {
        "max_pages": 10,
        "filters": {"category": "web-development"},
        "status": "in_progress",
    }
    
    # Create the session
    scrape_session = await db_crud.create_scrape_session(**session_data)
    
    # Verify the session was created
    assert scrape_session is not None
    assert scrape_session.id is not None
    assert scrape_session.max_pages == 10
    assert scrape_session.filters == {"category": "web-development"}
    assert scrape_session.status == "in_progress"
    assert scrape_session.start_time is not None
    assert scrape_session.end_time is None


@pytest.mark.asyncio
async def test_update_scrape_session(session: AsyncSession, db_crud: KworkCRUD):
    """Test updating a scrape session."""
    # Create a scrape session
    session_data = {
        "max_pages": 10,
        "status": "in_progress",
    }
    scrape_session = await db_crud.create_scrape_session(**session_data)
    
    # Update the session
    updated_data = {
        "pages_scraped": 5,
        "projects_found": 50,
        "new_projects": 10,
        "errors_encountered": 2,
        "status": "completed",
        "end_time": datetime.utcnow(),
    }
    updated_session = await db_crud.update_scrape_session(
        scrape_session.id,
        **updated_data
    )
    
    # Verify the session was updated
    assert updated_session.pages_scraped == 5
    assert updated_session.projects_found == 50
    assert updated_session.new_projects == 10
    assert updated_session.errors_encountered == 2
    assert updated_session.status == "completed"
    assert updated_session.end_time is not None


@pytest.mark.asyncio
async def test_get_latest_scrape_session(session: AsyncSession, db_crud: KworkCRUD):
    """Test retrieving the latest scrape session."""
    # Create multiple scrape sessions
    for i in range(3):
        await db_crud.create_scrape_session(
            max_pages=10,
            status="completed" if i < 2 else "in_progress"
        )
    
    # Get the latest session
    latest_session = await db_crud.get_latest_scrape_session()
    
    # Verify we got the most recent session
    assert latest_session is not None
    assert latest_session.status == "in_progress"


@pytest.mark.asyncio
async def test_upsert_project_new(session: AsyncSession, db_crud: KworkCRUD):
    """Test upserting a new project."""
    # Create project data
    project_data = {
        "kwork_id": "test_upsert_new",
        "title": "Test Upsert New",
        "url": "https://kwork.ru/projects/test_upsert_new",
        "price": 1000.0,
        "category": "Web Development",
    }
    
    # Upsert the project
    project, is_new = await db_crud.upsert_project(project_data)
    
    # Verify a new project was created
    assert is_new is True
    assert project is not None
    assert project.kwork_id == "test_upsert_new"
    assert project.title == "Test Upsert New"
    
    # Verify a snapshot was created
    assert len(project.snapshots) == 1
    assert project.snapshots[0].price == 1000.0


@pytest.mark.asyncio
async def test_upsert_project_existing(session: AsyncSession, db_crud: KworkCRUD):
    """Test upserting an existing project."""
    # Create a test project
    project_data = {
        "kwork_id": "test_upsert_existing",
        "title": "Test Upsert Existing",
        "url": "https://kwork.ru/projects/test_upsert_existing",
        "price": 1000.0,
        "category": "Web Development",
    }
    await db_crud.create_project(project_data)
    
    # Update the project data
    updated_data = {
        "kwork_id": "test_upsert_existing",  # Same Kwork ID
        "title": "Updated Title",
        "price": 1500.0,
    }
    
    # Upsert the project
    project, is_new = await db_crud.upsert_project(updated_data)
    
    # Verify the existing project was updated
    assert is_new is False
    assert project is not None
    assert project.title == "Updated Title"
    assert project.price == 1500.0
    
    # Verify a new snapshot was created
    assert len(project.snapshots) == 2
    assert project.snapshots[0].price == 1000.0  # Original price
    assert project.snapshots[1].price == 1500.0  # Updated price
