"""Tests for the Telegram reporting functionality."""
import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from src.integrations.telegram_report import (
    format_project_report,
    send_telegram_report,
    format_scrape_session_report,
    get_scrape_session_stats,
    format_project_stats_report,
)
from src.database.kwork_models import KworkProject, ProjectSnapshot, ScrapeSession


class TestTelegramReport:
    """Test cases for Telegram reporting functionality."""
    
    @pytest.fixture
    def sample_projects(self, db_session):
        """Create sample projects for testing."""
        # Create a scrape session
        session = ScrapeSession(
            max_pages=5,
            pages_scraped=3,
            projects_found=10,
            new_projects=5,
            errors_encountered=1,
            status="completed",
        )
        db_session.add(session)
        
        # Create some projects
        projects = []
        for i in range(3):
            project = KworkProject(
                kwork_id=f"test{i}",
                title=f"Test Project {i}",
                url=f"https://kwork.ru/projects/test{i}",
                price=1000.0 + (i * 500),
                category="Web Development",
                description=f"Test project {i} description",
                created_at=datetime.utcnow() - timedelta(days=i),
            )
            db_session.add(project)
            projects.append(project)
            
            # Add a snapshot
            snapshot = ProjectSnapshot(
                project=project,
                price=1000.0 + (i * 500),
                scrape_session=session,
            )
            db_session.add(snapshot)
        
        # Add another project in a different category
        other_project = KworkProject(
            kwork_id="other1",
            title="Other Project",
            url="https://kwork.ru/projects/other1",
            price=2000.0,
            category="Design",
            description="Other project description",
            created_at=datetime.utcnow(),
        )
        db_session.add(other_project)
        projects.append(other_project)
        
        # Add a snapshot for the other project
        other_snapshot = ProjectSnapshot(
            project=other_project,
            price=2000.0,
            scrape_session=session,
        )
        db_session.add(other_snapshot)
        
        # Commit the changes
        db_session.commit()
        
        return projects, session
    
    def test_format_project_report(self, sample_projects):
        """Test formatting a project report."""
        projects, _ = sample_projects
        report = format_project_report(projects[0])
        
        assert "Test Project 0" in report
        assert "1000.0" in report
        assert "Web Development" in report
        assert "kwork.ru/projects/test0" in report
    
    def test_format_project_report_without_url(self, sample_projects):
        """Test formatting a project report without a URL."""
        projects, _ = sample_projects
        projects[0].url = None
        report = format_project_report(projects[0])
        
        assert "Test Project 0" in report
        assert "URL: N/A" in report
    
    def test_format_scrape_session_report(self, sample_projects):
        """Test formatting a scrape session report."""
        _, session = sample_projects
        report = format_scrape_session_report(session)
        
        assert "Scraping Session Report" in report
        assert "Status: completed" in report
        assert "Pages scraped: 3/5" in report
        assert "Projects found: 10" in report
        assert "New projects: 5" in report
        assert "Errors: 1" in report
    
    @pytest.mark.asyncio
    async def test_get_scrape_session_stats(self, sample_projects, db_session):
        """Test getting scrape session statistics."""
        projects, session = sample_projects
        
        # Add another session for a different date
        other_session = ScrapeSession(
            max_pages=3,
            pages_scraped=3,
            projects_found=5,
            new_projects=2,
            errors_encountered=0,
            status="completed",
            created_at=datetime.utcnow() - timedelta(days=1),
        )
        db_session.add(other_session)
        
        # Add a snapshot for the other session
        other_snapshot = ProjectSnapshot(
            project=projects[0],
            price=1000.0,
            scrape_session=other_session,
        )
        db_session.add(other_snapshot)
        
        await db_session.commit()
        
        # Test getting stats for the last 7 days
        stats = await get_scrape_session_stats(db_session, days=7)
        
        assert stats["total_sessions"] == 2
        assert stats["total_pages_scraped"] == 6
        assert stats["total_projects_found"] == 15
        assert stats["total_new_projects"] == 7
        assert stats["total_errors"] == 1
        assert stats["avg_projects_per_session"] == 7.5
        assert stats["success_rate"] == 0.5  # 1 out of 2 sessions had no errors
    
    def test_format_project_stats_report(self, sample_projects):
        """Test formatting a project statistics report."""
        projects, _ = sample_projects
        
        # Create some project statistics
        project_stats = [
            {"category": "Web Development", "count": 3, "avg_price": 2000.0},
            {"category": "Design", "count": 1, "avg_price": 2000.0},
        ]
        
        report = format_project_stats_report(project_stats)
        
        assert "Project Statistics" in report
        assert "Web Development: 3 projects" in report
        assert "Design: 1 project" in report
        assert "Average price: 2000.0" in report
    
    @pytest.mark.asyncio
    async def test_send_telegram_report_success(self, sample_projects, db_session):
        """Test sending a Telegram report successfully."""
        # Mock the telegram.Bot class
        with patch('src.integrations.telegram_report.Bot') as mock_bot_class:
            # Create a mock bot instance
            mock_bot = AsyncMock()
            mock_bot_class.return_value = mock_bot
            
            # Mock the send_message method
            mock_bot.send_message.return_value = MagicMock(message_id=123)
            
            # Call the function
            result = await send_telegram_report(
                db_session=db_session,
                chat_id="test_chat_id",
                token="test_token",
                days=7,
            )
            
            # Verify the bot was created with the correct token
            mock_bot_class.assert_called_once_with(token="test_token")
            
            # Verify send_message was called
            mock_bot.send_message.assert_awaited_once()
            
            # Verify the result
            assert result is True
    
    @pytest.mark.asyncio
    async def test_send_telegram_report_no_data(self, db_session):
        """Test sending a Telegram report when no data is available."""
        # Mock the telegram.Bot class
        with patch('src.integrations.telegram_report.Bot') as mock_bot_class:
            # Create a mock bot instance
            mock_bot = AsyncMock()
            mock_bot_class.return_value = mock_bot
            
            # Call the function with no data in the database
            result = await send_telegram_report(
                db_session=db_session,
                chat_id="test_chat_id",
                token="test_token",
                days=7,
            )
            
            # Verify send_message was not called
            mock_bot.send_message.assert_not_awaited()
            
            # Verify the result
            assert result is False
    
    @pytest.mark.asyncio
    async def test_send_telegram_report_error(self, sample_projects, db_session):
        """Test error handling when sending a Telegram report."""
        # Mock the telegram.Bot class to raise an exception
        with patch('src.integrations.telegram_report.Bot') as mock_bot_class:
            # Create a mock bot instance that raises an exception
            mock_bot = AsyncMock()
            mock_bot_class.return_value = mock_bot
            mock_bot.send_message.side_effect = Exception("Test error")
            
            # Call the function and verify it handles the exception
            result = await send_telegram_report(
                db_session=db_session,
                chat_id="test_chat_id",
                token="test_token",
                days=7,
            )
            
            # Verify the result
            assert result is False
    
    @pytest.mark.asyncio
    async def test_send_telegram_report_with_custom_message(self, db_session):
        """Test sending a custom message via Telegram."""
        # Mock the telegram.Bot class
        with patch('src.integrations.telegram_report.Bot') as mock_bot_class:
            # Create a mock bot instance
            mock_bot = AsyncMock()
            mock_bot_class.return_value = mock_bot
            
            # Call the function with a custom message
            result = await send_telegram_report(
                db_session=db_session,
                chat_id="test_chat_id",
                token="test_token",
                message="Test message",
            )
            
            # Verify send_message was called with the custom message
            mock_bot.send_message.assert_awaited_once_with(
                chat_id="test_chat_id",
                text="Test message",
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )
            
            # Verify the result
            assert result is True
