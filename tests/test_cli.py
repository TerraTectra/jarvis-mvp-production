"""Tests for the CLI interface."""
import os
import sys
from io import StringIO
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from click.testing import CliRunner

# Add the src directory to the path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.cli import cli, scrape_projects, init_db, list_projects, send_report
from src.database.kwork_models import KworkProject, ProjectSnapshot, ScrapeSession
from src.database.kwork_crud import KworkCRUD
from src.integrations.kwork_scraper import KworkScraper


class TestCLI:
    """Test cases for the CLI interface."""
    
    @pytest.fixture(autouse=True)
    def setup_method(self, session):
        """Set up test fixtures before each test method."""
        self.runner = CliRunner()
        self.db_session = session
        self.crud = KworkCRUD(session)
        
        # Mock the get_db_session function
        self.db_patcher = patch(
            'src.database.database.get_db_session',
            return_value=AsyncMock(return_value=session)
        )
        self.mock_get_db = self.db_patcher.start()
        
        # Mock the KworkScraper
        self.scraper_patcher = patch('src.cli.KworkScraper')
        self.mock_scraper_class = self.scraper_patcher.start()
        self.mock_scraper = AsyncMock(spec=KworkScraper)
        self.mock_scraper_class.return_value = self.mock_scraper
        
        # Mock the send_telegram_report function
        self.telegram_patcher = patch('src.cli.send_telegram_report')
        self.mock_send_telegram = self.telegram_patcher.start()
        
        yield
        
        # Stop all patches
        self.db_patcher.stop()
        self.scraper_patcher.stop()
        self.telegram_patcher.stop()
    
    def test_cli_help(self):
        """Test the CLI help output."""
        result = self.runner.invoke(cli, ['--help'])
        assert result.exit_code == 0
        assert "Show this message and exit." in result.output
        assert "scrape" in result.output
        assert "init-db" in result.output
        assert "list" in result.output
        assert "report" in result.output
    
    @pytest.mark.asyncio
    async def test_scrape_projects(self):
        """Test the scrape-projects command."""
        # Mock the scraper's methods
        self.mock_scraper.scrape_projects.return_value = (5, 3, 2)
        
        # Run the command
        result = await scrape_projects(
            db_session=self.db_session,
            pages=2,
            headless=True,
            max_workers=3,
            category="web-development",
            price_min=1000,
            price_max=5000,
        )
        
        # Verify the scraper was called with the correct arguments
        self.mock_scraper_class.assert_called_once_with(
            base_url="https://kwork.ru/projects",
            db_session=self.db_session,
            headless=True,
            max_workers=3,
            max_pages=2,
            category="web-development",
            price_min=1000,
            price_max=5000,
        )
        
        # Verify the scraper's methods were called
        self.mock_scraper.scrape_projects.assert_awaited_once()
        
        # Verify the result
        assert result == (5, 3, 2)
    
    @pytest.mark.asyncio
    async def test_init_db(self):
        """Test the init-db command."""
        # Run the command
        await init_db(db_session=self.db_session, drop_tables=True)
        
        # Verify the tables were created
        # (We can't easily verify this with an in-memory SQLite database,
        # but we can check that no exceptions were raised)
        assert True
    
    @pytest.mark.asyncio
    async def test_list_projects(self, capsys):
        """Test the list-projects command."""
        # Create some test data
        project1 = KworkProject(
            kwork_id="test1",
            title="Test Project 1",
            url="https://kwork.ru/projects/test1",
            price=1000.0,
            category="Web Development",
            description="Test project 1 description",
        )
        
        project2 = KworkProject(
            kwork_id="test2",
            title="Test Project 2",
            url="https://kwork.ru/projects/test2",
            price=2000.0,
            category="Design",
            description="Test project 2 description",
        )
        
        self.db_session.add_all([project1, project2])
        await self.db_session.commit()
        
        # Run the command
        await list_projects(
            db_session=self.db_session,
            limit=1,
            category="Web Development",
            min_price=500,
            max_price=1500,
            sort_by="price",
            desc=True,
        )
        
        # Capture the output
        captured = capsys.readouterr()
        output = captured.out
        
        # Verify the output
        assert "Test Project 1" in output
        assert "Web Development" in output
        assert "1000.0" in output
        assert "Test Project 2" not in output  # Should be filtered out by category
    
    @pytest.mark.asyncio
    async def test_send_report(self):
        """Test the send-report command."""
        # Create a test scrape session
        session = ScrapeSession(
            max_pages=5,
            pages_scraped=3,
            projects_found=10,
            new_projects=5,
            errors_encountered=1,
            status="completed",
        )
        
        self.db_session.add(session)
        await self.db_session.commit()
        
        # Mock the send_telegram_report function
        self.mock_send_telegram.return_value = True
        
        # Run the command
        result = await send_report(
            db_session=self.db_session,
            chat_id="test_chat_id",
            token="test_token",
            days=1,
        )
        
        # Verify the report was sent
        self.mock_send_telegram.assert_awaited_once()
        
        # Verify the result
        assert result is True
    
    @pytest.mark.asyncio
    async def test_main_cli_scrape_command(self):
        """Test the main CLI with the scrape-projects command."""
        # Mock the scraper's methods
        self.mock_scraper.scrape_projects.return_value = (5, 3, 2)
        
        # Run the command
        result = self.runner.invoke(
            cli,
            [
                "scrape",
                "--pages", "2",
                "--headless",
                "--max-workers", "3",
                "--category", "web-development",
                "--price-min", "1000",
                "--price-max", "5000",
            ]
        )
        
        # Verify the command succeeded
        assert result.exit_code == 0
        
        # Verify the scraper was called with the correct arguments
        self.mock_scraper_class.assert_called_once()
        self.mock_scraper.scrape_projects.assert_awaited_once()
        
        # Verify the output
        assert "Scraping complete" in result.output
        assert "Pages scraped: 2" in result.output
        assert "Projects found: 5" in result.output
        assert "New projects: 3" in result.output
        assert "Errors: 2" in result.output
    
    @pytest.mark.asyncio
    async def test_main_cli_init_db_command(self):
        """Test the main CLI with the init-db command."""
        # Run the command
        result = self.runner.invoke(
            cli,
            ["init-db", "--drop-tables"]
        )
        
        # Verify the command succeeded
        assert result.exit_code == 0
        assert "Database initialized successfully" in result.output
    
    @pytest.mark.asyncio
    async def test_main_cli_list_command(self):
        """Test the main CLI with the list-projects command."""
        # Create some test data
        project = KworkProject(
            kwork_id="test1",
            title="Test Project 1",
            url="https://kwork.ru/projects/test1",
            price=1000.0,
            category="Web Development",
            description="Test project 1 description",
        )
        
        self.db_session.add(project)
        await self.db_session.commit()
        
        # Run the command
        result = self.runner.invoke(
            cli,
            ["list"]
        )
        
        # Verify the command succeeded
        assert result.exit_code == 0
        assert "Test Project 1" in result.output
        assert "Web Development" in result.output
        assert "1000.0" in result.output
    
    @pytest.mark.asyncio
    async def test_main_cli_report_command(self):
        """Test the main CLI with the report command."""
        # Create a test scrape session
        session = ScrapeSession(
            max_pages=5,
            pages_scraped=3,
            projects_found=10,
            new_projects=5,
            errors_encountered=1,
            status="completed",
        )
        
        self.db_session.add(session)
        await self.db_session.commit()
        
        # Mock the send_telegram_report function
        self.mock_send_telegram.return_value = True
        
        # Set environment variables for Telegram
        with patch.dict(os.environ, {
            "TELEGRAM_BOT_TOKEN": "test_token",
            "TELEGRAM_CHAT_ID": "test_chat_id",
        }):
            # Run the command
            result = self.runner.invoke(
                cli,
                ["report"]
            )
        
        # Verify the command succeeded
        assert result.exit_code == 0
        assert "Report sent successfully" in result.output
        
        # Verify the report was sent
        self.mock_send_telegram.assert_awaited_once()
    
    @pytest.mark.asyncio
    async def test_main_cli_missing_telegram_creds(self):
        """Test the report command with missing Telegram credentials."""
        # Remove any existing environment variables
        if "TELEGRAM_BOT_TOKEN" in os.environ:
            del os.environ["TELEGRAM_BOT_TOKEN"]
        if "TELEGRAM_CHAT_ID" in os.environ:
            del os.environ["TELEGRAM_CHAT_ID"]
        
        # Run the command without providing credentials
        result = self.runner.invoke(
            cli,
            ["report"]
        )
        
        # Verify the command failed with the expected error
        assert result.exit_code != 0
        assert "Telegram bot token and chat ID are required" in str(result.exception)
