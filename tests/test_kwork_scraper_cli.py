"""Tests for the Kwork scraper command-line interface."""
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from click.testing import CliRunner

# Add the src directory to the path for imports
sys.path.append(str(Path(__file__).parent.parent / "src"))

from cli import cli
from config import Settings, ScraperSettings, DatabaseSettings, TelegramSettings


class TestKworkScraperCLI:
    """Test cases for the Kwork scraper command-line interface."""
    
    @pytest.fixture
    def runner(self):
        """Create a CLI runner for testing."""
        return CliRunner()
    
    @pytest.fixture
    def mock_settings(self):
        """Create a mock settings object."""
        return Settings(
            scraper=ScraperSettings(
                base_url="https://kwork.ru/projects",
                headless=True,
                pool_size=3,
                max_pages=10,
                request_timeout=30,
            ),
            database=DatabaseSettings(
                url="sqlite+aiosqlite:///test.db",
                echo=False,
            ),
            telegram=TelegramSettings(
                enabled=True,
                token="test-token",
                chat_id="12345",
            ),
        )
    
    @pytest.fixture
    def mock_scraper(self):
        """Create a mock KworkScraper."""
        with patch('cli.KworkScraper') as mock_scraper:
            mock_instance = AsyncMock()
            mock_instance.scrape_projects = AsyncMock(return_value={
                "status": "completed",
                "pages_scraped": 1,
                "projects_found": 5,
                "new_projects": 3,
                "errors_encountered": 0,
            })
            mock_scraper.return_value = mock_instance
            yield mock_instance
    
    def test_help(self, runner):
        """Test the --help option."""
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Show this message and exit." in result.output
    
    def test_version(self, runner):
        """Test the --version option."""
        from cli import __version__
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.output
    
    @patch('cli.get_settings')
    def test_run_default(self, mock_get_settings, runner, mock_settings, mock_scraper):
        """Test running the scraper with default options."""
        mock_get_settings.return_value = mock_settings
        
        result = runner.invoke(cli, ["run"])
        
        assert result.exit_code == 0
        assert "Starting Kwork scraper" in result.output
        assert "Scraping completed" in result.output
        
        # Verify the scraper was called with the correct settings
        mock_scraper.assert_called_once_with(
            scraper_settings=mock_settings.scraper,
            db_settings=mock_settings.database,
            telegram_settings=mock_settings.telegram,
        )
        
        # Verify the scraper was called
        mock_scraper.scrape_projects.assert_awaited_once()
    
    @patch('cli.get_settings')
    def test_run_with_options(self, mock_get_settings, runner, mock_settings, mock_scraper):
        """Test running the scraper with custom options."""
        mock_get_settings.return_value = mock_settings
        
        result = runner.invoke(cli, [
            "run",
            "--headless", "false",
            "--pool-size", "5",
            "--max-pages", "20",
            "--timeout", "60",
        ])
        
        assert result.exit_code == 0
        assert "Starting Kwork scraper" in result.output
        assert "Scraping completed" in result.output
        
        # Verify the scraper was called with the overridden settings
        args, kwargs = mock_scraper.call_args
        assert args[0].headless is False
        assert args[0].pool_size == 5
        assert args[0].max_pages == 20
        assert args[0].request_timeout == 60
    
    @patch('cli.get_settings')
    def test_run_with_config_file(self, mock_get_settings, runner, mock_settings, mock_scraper, tmp_path):
        """Test running the scraper with a custom config file."""
        # Create a temporary config file
        config_file = tmp_path / "config.toml"
        config_file.write_text("""
        [scraper]
        headless = false
        pool_size = 5
        max_pages = 20
        request_timeout = 60
        
        [database]
        url = "sqlite+aiosqlite:///custom.db"
        echo = true
        
        [telegram]
        enabled = true
        token = "custom-token"
        chat_id = "54321"
        """)
        
        result = runner.invoke(cli, ["--config", str(config_file), "run"])
        
        assert result.exit_code == 0
        
        # Verify the settings were loaded from the config file
        args, _ = mock_get_settings.call_args
        assert args[0] == str(config_file)
        
        # Verify the scraper was called with the settings from the config file
        args, _ = mock_scraper.call_args
        assert args[0].headless is False
        assert args[0].pool_size == 5
        assert args[0].max_pages == 20
        assert args[0].request_timeout == 60
        
        assert args[1].url == "sqlite+aiosqlite:///custom.db"
        assert args[1].echo is True
        
        assert args[2].enabled is True
        assert args[2].token == "custom-token"
        assert args[2].chat_id == "54321"
    
    @patch('cli.get_settings')
    def test_run_with_error(self, mock_get_settings, runner, mock_settings, mock_scraper):
        """Test handling of errors during scraping."""
        mock_get_settings.return_value = mock_settings
        
        # Configure the mock scraper to raise an exception
        mock_scraper.scrape_projects.side_effect = Exception("Test error")
        
        result = runner.invoke(cli, ["run"])
        
        assert result.exit_code == 1
        assert "Error: Test error" in result.output
    
    @patch('cli.get_settings')
    def test_run_keyboard_interrupt(self, mock_get_settings, runner, mock_settings, mock_scraper):
        """Test handling of keyboard interrupt."""
        mock_get_settings.return_value = mock_settings
        
        # Configure the mock scraper to raise KeyboardInterrupt
        mock_scraper.scrape_projects.side_effect = KeyboardInterrupt()
        
        result = runner.invoke(cli, ["run"])
        
        assert result.exit_code == 0
        assert "Scraping interrupted by user" in result.output
    
    @patch('cli.get_settings')
    def test_run_with_invalid_options(self, mock_get_settings, runner, mock_settings):
        """Test running the scraper with invalid options."""
        mock_get_settings.return_value = mock_settings
        
        # Test with invalid pool size
        result = runner.invoke(cli, ["run", "--pool-size", "0"])
        assert result.exit_code == 2
        assert "pool_size must be greater than 0" in result.output
        
        # Test with invalid max pages
        result = runner.invoke(cli, ["run", "--max-pages", "0"])
        assert result.exit_code == 2
        assert "max_pages must be greater than 0" in result.output
        
        # Test with invalid timeout
        result = runner.invoke(cli, ["run", "--timeout", "0"])
        assert result.exit_code == 2
        assert "request_timeout must be greater than 0" in result.output
    
    @patch('cli.get_settings')
    def test_run_with_telegram_disabled(self, mock_get_settings, runner, mock_settings, mock_scraper):
        """Test running the scraper with Telegram notifications disabled."""
        # Disable Telegram in the settings
        mock_settings.telegram.enabled = False
        mock_get_settings.return_value = mock_settings
        
        result = runner.invoke(cli, ["run"])
        
        assert result.exit_code == 0
        assert "Telegram notifications are disabled" in result.output
        
        # Verify the scraper was still called
        mock_scraper.scrape_projects.assert_awaited_once()
    
    @patch('cli.get_settings')
    def test_run_with_invalid_config_file(self, mock_get_settings, runner, tmp_path):
        """Test running the scraper with an invalid config file."""
        # Create an invalid config file
        config_file = tmp_path / "invalid.toml"
        config_file.write_text("invalid toml")
        
        result = runner.invoke(cli, ["--config", str(config_file), "run"])
        
        assert result.exit_code == 1
        assert "Error loading config file" in result.output
    
    @patch('cli.get_settings')
    def test_run_with_missing_config_file(self, mock_get_settings, runner):
        """Test running the scraper with a missing config file."""
        result = runner.invoke(cli, ["--config", "nonexistent.toml", "run"])
        
        assert result.exit_code == 1
        assert "Config file not found" in result.output
    
    @patch('cli.get_settings')
    def test_run_with_verbose(self, mock_get_settings, runner, mock_settings, mock_scraper):
        """Test running the scraper with verbose output."""
        mock_get_settings.return_value = mock_settings
        
        result = runner.invoke(cli, ["--verbose", "run"])
        
        assert result.exit_code == 0
        assert "Debug logging enabled" in result.output
    
    @patch('cli.get_settings')
    def test_run_with_log_file(self, mock_get_settings, runner, mock_settings, mock_scraper, tmp_path):
        """Test running the scraper with logging to a file."""
        mock_get_settings.return_value = mock_settings
        
        log_file = tmp_path / "test.log"
        
        result = runner.invoke(cli, ["--log-file", str(log_file), "run"])
        
        assert result.exit_code == 0
        assert log_file.exists()
        
        # Verify the log file contains the expected content
        log_content = log_file.read_text()
        assert "Starting Kwork scraper" in log_content
        assert "Scraping completed" in log_content
    
    @patch('cli.get_settings')
    def test_run_with_dry_run(self, mock_get_settings, runner, mock_settings, mock_scraper):
        """Test running the scraper in dry-run mode."""
        mock_get_settings.return_value = mock_settings
        
        result = runner.invoke(cli, ["--dry-run", "run"])
        
        assert result.exit_code == 0
        assert "Dry run mode enabled" in result.output
        assert "Would start scraping" in result.output
        
        # Verify the scraper was not called
        mock_scraper.assert_not_called()
    
    @patch('cli.get_settings')
    def test_run_with_version_flag(self, mock_get_settings, runner, mock_settings):
        """Test the --version flag."""
        from cli import __version__
        
        result = runner.invoke(cli, ["--version"])
        
        assert result.exit_code == 0
        assert __version__ in result.output
        
        # Verify the scraper was not called
        mock_get_settings.assert_not_called()
    
    @patch('cli.get_settings')
    def test_run_with_help_flag(self, mock_get_settings, runner, mock_settings):
        """Test the --help flag."""
        result = runner.invoke(cli, ["--help"])
        
        assert result.exit_code == 0
        assert "Show this message and exit." in result.output
        
        # Verify the scraper was not called
        mock_get_settings.assert_not_called()
    
    @patch('cli.get_settings')
    def test_run_with_invalid_command(self, mock_get_settings, runner, mock_settings):
        """Test running with an invalid command."""
        result = runner.invoke(cli, ["invalid-command"])
        
        assert result.exit_code == 2
        assert "No such command" in result.output
        
        # Verify the scraper was not called
        mock_get_settings.assert_not_called()
    
    @patch('cli.get_settings')
    def test_run_with_invalid_option(self, mock_get_settings, runner, mock_settings):
        """Test running with an invalid option."""
        result = runner.invoke(cli, ["--invalid-option"])
        
        assert result.exit_code == 2
        assert "No such option" in result.output
        
        # Verify the scraper was not called
        mock_get_settings.assert_not_called()
