"""Tests for database migrations."""
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

# Add the src directory to the path for imports
sys.path.append(str(Path(__file__).parent.parent / "src"))

from database.database import Base, get_db_url
from database.kwork_models import KworkProject, ProjectSnapshot, ScrapeSession


class TestMigrations:
    """Test cases for database migrations."""
    
    @pytest.fixture
    def alembic_cfg(self, tmp_path):
        """Create a test Alembic configuration."""
        # Create a temporary directory for the test database
        db_path = tmp_path / "test.db"
        test_db_url = f"sqlite:///{db_path}"
        
        # Create a test Alembic configuration
        config = Config()
        config.set_main_option("script_location", str(Path(__file__).parent.parent / "migrations"))
        config.set_main_option("sqlalchemy.url", test_db_url)
        
        # Set up logging
        config.attributes["configure_logger"] = False
        
        return config, test_db_url
    
    def test_migrations_upgrade_downgrade(self, alembic_cfg):
        """Test that migrations can be applied and reverted."""
        config, test_db_url = alembic_cfg
        
        # Run migrations up to the head
        command.upgrade(config, "head")
        
        # Verify the database has the expected tables
        engine = create_engine(test_db_url)
        inspector = inspect(engine)
        
        # Check that all expected tables exist
        assert "kwork_projects" in inspector.get_table_names()
        assert "project_snapshots" in inspector.get_table_names()
        assert "scrape_sessions" in inspector.get_table_names()
        
        # Run migrations down to the base
        command.downgrade(config, "base")
        
        # Verify the database has no tables
        assert not inspector.get_table_names()
        
        # Clean up
        engine.dispose()
    
    def test_migration_models_match(self, alembic_cfg, db_session):
        """Test that the models match the database schema after migrations."""
        config, test_db_url = alembic_cfg
        
        # Run migrations up to the head
        command.upgrade(config, "head")
        
        # Create the tables from models
        engine = create_engine(test_db_url)
        Base.metadata.create_all(engine)
        
        # Get the database schema
        inspector = inspect(engine)
        
        # Verify the kwork_projects table
        assert "kwork_projects" in inspector.get_table_names()
        kwork_columns = {c["name"]: c for c in inspector.get_columns("kwork_projects")}
        
        # Check column types and constraints
        assert kwork_columns["id"]["type"].python_type == int
        assert kwork_columns["kwork_id"]["type"].python_type == str
        assert kwork_columns["title"]["type"].python_type == str
        assert kwork_columns["url"]["type"].python_type == str
        assert kwork_columns["price"]["type"].python_type == float
        assert kwork_columns["category"]["type"].python_type == str
        assert kwork_columns["description"]["type"].python_type == str
        assert kwork_columns["created_at"]["type"].python_type == datetime
        assert kwork_columns["updated_at"]["type"].python_type == datetime
        
        # Verify the project_snapshots table
        assert "project_snapshots" in inspector.get_table_names()
        snapshot_columns = {c["name"]: c for c in inspector.get_columns("project_snapshots")}
        
        # Check column types and constraints
        assert snapshot_columns["id"]["type"].python_type == int
        assert snapshot_columns["project_id"]["type"].python_type == int
        assert snapshot_columns["scrape_session_id"]["type"].python_type == int
        assert snapshot_columns["price"]["type"].python_type == float
        assert snapshot_columns["created_at"]["type"].python_type == datetime
        
        # Verify the scrape_sessions table
        assert "scrape_sessions" in inspector.get_table_names()
        session_columns = {c["name"]: c for c in inspector.get_columns("scrape_sessions")}
        
        # Check column types and constraints
        assert session_columns["id"]["type"].python_type == int
        assert session_columns["max_pages"]["type"].python_type == int
        assert session_columns["pages_scraped"]["type"].python_type == int
        assert session_columns["projects_found"]["type"].python_type == int
        assert session_columns["new_projects"]["type"].python_type == int
        assert session_columns["errors_encountered"]["type"].python_type == int
        assert session_columns["status"]["type"].python_type == str
        assert session_columns["start_time"]["type"].python_type == datetime
        assert session_columns["end_time"]["type"].python_type == datetime
        
        # Clean up
        engine.dispose()
    
    def test_migration_data_integrity(self, alembic_cfg, db_session):
        """Test that data integrity is maintained during migrations."""
        config, test_db_url = alembic_cfg
        
        # Run migrations up to the head
        command.upgrade(config, "head")
        
        # Create a test session
        engine = create_engine(test_db_url)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        try:
            # Create a test project
            project = KworkProject(
                kwork_id="test123",
                title="Test Project",
                url="https://kwork.ru/projects/test123",
                price=1000.0,
                category="Web Development",
                description="Test project description",
            )
            session.add(project)
            
            # Create a test scrape session
            scrape_session = ScrapeSession(
                max_pages=5,
                pages_scraped=3,
                projects_found=10,
                new_projects=5,
                errors_encountered=1,
                status="completed",
            )
            session.add(scrape_session)
            session.commit()
            
            # Create a test project snapshot
            snapshot = ProjectSnapshot(
                project_id=project.id,
                scrape_session_id=scrape_session.id,
                price=1000.0,
            )
            session.add(snapshot)
            session.commit()
            
            # Verify the data was inserted correctly
            assert project.id is not None
            assert scrape_session.id is not None
            assert snapshot.id is not None
            
            # Verify the relationships
            assert len(project.snapshots) == 1
            assert project.snapshots[0].id == snapshot.id
            assert len(scrape_session.snapshots) == 1
            assert scrape_session.snapshots[0].id == snapshot.id
            
            # Run migrations down and back up to test data preservation
            command.downgrade(config, "base")
            command.upgrade(config, "head")
            
            # Verify the data is still there
            session = Session()
            project = session.query(KworkProject).first()
            assert project is not None
            assert project.kwork_id == "test123"
            assert project.title == "Test Project"
            assert project.price == 1000.0
            
            # Verify the relationships are still intact
            assert len(project.snapshots) == 1
            assert project.snapshots[0].price == 1000.0
            
        finally:
            session.close()
            engine.dispose()
    
    def test_migration_rollback(self, alembic_cfg):
        """Test that migrations can be rolled back."""
        config, test_db_url = alembic_cfg
        
        # Run migrations up to the head
        command.upgrade(config, "head")
        
        # Get the current revision
        current_rev = command.current(config)
        assert current_rev is not None
        
        # Roll back one migration
        command.downgrade(config, "-1")
        
        # Get the new current revision
        new_rev = command.current(config)
        assert new_rev != current_rev
        
        # Run migrations back up to the head
        command.upgrade(config, "head")
        
        # Verify we're back at the head
        final_rev = command.current(config)
        assert final_rev == current_rev
    
    def test_migration_stamp(self, alembic_cfg):
        """Test the stamp command."""
        config, test_db_url = alembic_cfg
        
        # Stamp the database with the head revision
        command.stamp(config, "head")
        
        # Verify the database is marked as being at the head
        current_rev = command.current(config)
        assert current_rev is not None
        
        # Get the head revision
        script = ScriptDirectory.from_config(config)
        head_rev = script.get_current_head()
        
        # The current revision should match the head
        assert current_rev == head_rev
    
    def test_migration_history(self, alembic_cfg):
        """Test the history command."""
        config, test_db_url = alembic_cfg
        
        # Get the migration history
        with patch('sys.stdout', new_callable=StringIO) as stdout:
            command.history(config)
            output = stdout.getvalue()
        
        # Verify the output contains the expected information
        assert "Rev: " in output
        assert "Parent: " in output
        assert "Path: " in output
    
    def test_migration_show(self, alembic_cfg):
        """Test the show command."""
        config, test_db_url = alembic_cfg
        
        # Get the head revision
        script = ScriptDirectory.from_config(config)
        head_rev = script.get_current_head()
        
        # Show the head revision
        with patch('sys.stdout', new_callable=StringIO) as stdout:
            command.show(config, head_rev)
            output = stdout.getvalue()
        
        # Verify the output contains the expected information
        assert f"Rev: {head_rev}" in output
        assert "Revises: " in output
        assert "Create tables" in output or "Add column" in output or "Modify column" in output
