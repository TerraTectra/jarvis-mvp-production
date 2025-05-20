"""Tests for the configuration module."""
import os
import sys
from pathlib import Path
from unittest.mock import patch, mock_open

import pytest
from pydantic import ValidationError

# Add the src directory to the path for imports
sys.path.append(str(Path(__file__).parent.parent / "src"))

from config import Settings, get_settings, load_env_file, DatabaseSettings, TelegramSettings, ScraperSettings


class TestSettings:
    """Test cases for the Settings class."""
    
    def test_default_settings(self):
        """Test that default settings are loaded correctly."""
        settings = Settings()
        
        # Verify database settings
        assert settings.database.url == "sqlite+aiosqlite:///kwork_scraper.db"
        assert settings.database.echo is False
        
        # Verify scraper settings
        assert settings.scraper.base_url == "https://kwork.ru/projects"
        assert settings.scraper.headless is True
        assert settings.scraper.pool_size == 3
        assert settings.scraper.max_pages == 10
        assert settings.scraper.request_timeout == 30
        
        # Verify Telegram settings
        assert settings.telegram.enabled is False
        assert settings.telegram.token is None
        assert settings.telegram.chat_id is None
    
    def test_environment_variables(self):
        """Test that environment variables override defaults."""
        with patch.dict(os.environ, {
            "DATABASE_URL": "postgresql://user:pass@localhost:5432/test_db",
            "DATABASE_ECHO": "true",
            "SCRAPER_HEADLESS": "false",
            "SCRAPER_POOL_SIZE": "5",
            "TELEGRAM_ENABLED": "true",
            "TELEGRAM_BOT_TOKEN": "test_token",
            "TELEGRAM_CHAT_ID": "12345",
        }):
            settings = Settings()
            
            # Verify database settings
            assert settings.database.url == "postgresql://user:pass@localhost:5432/test_db"
            assert settings.database.echo is True
            
            # Verify scraper settings
            assert settings.scraper.headless is False
            assert settings.scraper.pool_size == 5
            
            # Verify Telegram settings
            assert settings.telegram.enabled is True
            assert settings.telegram.token == "test_token"
            assert settings.telegram.chat_id == "12345"
    
    def test_invalid_database_url(self):
        """Test validation of database URL."""
        with patch.dict(os.environ, {"DATABASE_URL": "invalid-url"}):
            with pytest.raises(ValidationError) as exc_info:
                Settings()
            
            assert "Invalid database URL" in str(exc_info.value)
    
    def test_invalid_pool_size(self):
        """Test validation of pool size."""
        with patch.dict(os.environ, {"SCRAPER_POOL_SIZE": "0"}):
            with pytest.raises(ValidationError) as exc_info:
                Settings()
            
            assert "ensure this value is greater than 0" in str(exc_info.value)
    
    def test_telegram_validation(self):
        """Test validation of Telegram settings."""
        # Test that token and chat_id are required when enabled is True
        with patch.dict(os.environ, {"TELEGRAM_ENABLED": "true"}):
            with pytest.raises(ValidationError) as exc_info:
                Settings()
            
            assert "Telegram token and chat ID are required" in str(exc_info.value)
        
        # Test that token and chat_id are not required when enabled is False
        with patch.dict(os.environ, {"TELEGRAM_ENABLED": "false"}):
            settings = Settings()
            assert settings.telegram.enabled is False
            assert settings.telegram.token is None
            assert settings.telegram.chat_id is None


class TestLoadEnvFile:
    """Test cases for the load_env_file function."""
    
    def test_load_env_file_success(self, tmp_path):
        """Test loading environment variables from a file."""
        # Create a temporary .env file
        env_file = tmp_path / ".env"
        env_file.write_text("""
        # This is a comment
        DATABASE_URL=postgresql://user:pass@localhost:5432/test_db
        DATABASE_ECHO=true
        SCRAPER_HEADLESS=false
        
        # Another comment
        TELEGRAM_ENABLED=true
        TELEGRAM_BOT_TOKEN=test_token
        TELEGRAM_CHAT_ID=12345
        """)
        
        # Load the environment variables
        env_vars = load_env_file(env_file)
        
        # Verify the environment variables were loaded correctly
        assert env_vars["DATABASE_URL"] == "postgresql://user:pass@localhost:5432/test_db"
        assert env_vars["DATABASE_ECHO"] == "true"
        assert env_vars["SCRAPER_HEADLESS"] == "false"
        assert env_vars["TELEGRAM_ENABLED"] == "true"
        assert env_vars["TELEGRAM_BOT_TOKEN"] == "test_token"
        assert env_vars["TELEGRAM_CHAT_ID"] == "12345"
        assert "This is a comment" not in env_vars
    
    def test_load_env_file_nonexistent(self, tmp_path):
        """Test loading a non-existent .env file."""
        env_file = tmp_path / "nonexistent.env"
        
        # Loading a non-existent file should not raise an error
        env_vars = load_env_file(env_file)
        
        # The result should be an empty dictionary
        assert env_vars == {}
    
    def test_load_env_file_invalid_format(self, tmp_path):
        """Test loading an invalid .env file."""
        # Create a temporary .env file with invalid format
        env_file = tmp_path / ".env"
        env_file.write_text("INVALID_LINE")
        
        # Loading an invalid file should not raise an error
        env_vars = load_env_file(env_file)
        
        # The invalid line should be ignored
        assert env_vars == {}


class TestGetSettings:
    """Test cases for the get_settings function."""
    
    def test_get_settings_singleton(self):
        """Test that get_settings returns a singleton instance."""
        settings1 = get_settings()
        settings2 = get_settings()
        
        # The same instance should be returned each time
        assert settings1 is settings2
    
    def test_get_settings_with_overrides(self):
        """Test that get_settings can be overridden for testing."""
        # Create a test settings instance
        test_settings = Settings(
            database=DatabaseSettings(url="sqlite:///test.db"),
            scraper=ScraperSettings(headless=False, pool_size=1),
            telegram=TelegramSettings(enabled=False),
        )
        
        # Override the settings
        settings = get_settings(settings_override=test_settings)
        
        # Verify the overridden settings
        assert settings.database.url == "sqlite:///test.db"
        assert settings.scraper.headless is False
        assert settings.scraper.pool_size == 1
        assert settings.telegram.enabled is False
    
    def test_get_settings_with_env_file(self, tmp_path):
        """Test that get_settings loads from a .env file."""
        # Create a temporary .env file
        env_file = tmp_path / ".env"
        env_file.write_text("""
        DATABASE_URL=postgresql://user:pass@localhost:5432/test_db
        SCRAPER_HEADLESS=false
        TELEGRAM_ENABLED=true
        TELEGRAM_BOT_TOKEN=test_token
        TELEGRAM_CHAT_ID=12345
        """)
        
        # Load settings with the .env file
        with patch.dict(os.environ, {"DOTENV_PATH": str(env_file)}):
            settings = get_settings()
            
            # Verify the settings were loaded from the .env file
            assert settings.database.url == "postgresql://user:pass@localhost:5432/test_db"
            assert settings.scraper.headless is False
            assert settings.telegram.enabled is True
            assert settings.telegram.token == "test_token"
            assert settings.telegram.chat_id == "12345"


class TestDatabaseSettings:
    """Test cases for the DatabaseSettings class."""
    
    def test_default_database_settings(self):
        """Test default database settings."""
        settings = DatabaseSettings()
        
        assert settings.url == "sqlite+aiosqlite:///kwork_scraper.db"
        assert settings.echo is False
    
    def test_database_url_validation(self):
        """Test validation of database URL."""
        # Valid URL
        settings = DatabaseSettings(url="postgresql://user:pass@localhost:5432/test_db")
        assert settings.url == "postgresql://user:pass@localhost:5432/test_db"
        
        # Invalid URL
        with pytest.raises(ValueError) as exc_info:
            DatabaseSettings(url="invalid-url")
        
        assert "Invalid database URL" in str(exc_info.value)


class TestScraperSettings:
    """Test cases for the ScraperSettings class."""
    
    def test_default_scraper_settings(self):
        """Test default scraper settings."""
        settings = ScraperSettings()
        
        assert settings.base_url == "https://kwork.ru/projects"
        assert settings.headless is True
        assert settings.pool_size == 3
        assert settings.max_pages == 10
        assert settings.request_timeout == 30
    
    def test_scraper_settings_validation(self):
        """Test validation of scraper settings."""
        # Invalid pool_size
        with pytest.raises(ValueError) as exc_info:
            ScraperSettings(pool_size=0)
        
        assert "ensure this value is greater than 0" in str(exc_info.value)
        
        # Invalid max_pages
        with pytest.raises(ValueError) as exc_info:
            ScraperSettings(max_pages=0)
        
        assert "ensure this value is greater than 0" in str(exc_info.value)
        
        # Invalid request_timeout
        with pytest.raises(ValueError) as exc_info:
            ScraperSettings(request_timeout=0)
        
        assert "ensure this value is greater than 0" in str(exc_info.value)


class TestTelegramSettings:
    """Test cases for the TelegramSettings class."""
    
    def test_default_telegram_settings(self):
        """Test default Telegram settings."""
        settings = TelegramSettings()
        
        assert settings.enabled is False
        assert settings.token is None
        assert settings.chat_id is None
    
    def test_telegram_settings_validation(self):
        """Test validation of Telegram settings."""
        # When enabled is True, token and chat_id are required
        with pytest.raises(ValueError) as exc_info:
            TelegramSettings(enabled=True)
        
        assert "Telegram token and chat ID are required when enabled is True" in str(exc_info.value)
        
        # When enabled is False, token and chat_id are not required
        settings = TelegramSettings(enabled=False)
        assert settings.enabled is False
        assert settings.token is None
        assert settings.chat_id is None
        
        # When enabled is True, both token and chat_id must be provided
        with pytest.raises(ValueError) as exc_info:
            TelegramSettings(enabled=True, token="test_token")
        
        assert "Telegram token and chat ID are required when enabled is True" in str(exc_info.value)
        
        with pytest.raises(ValueError) as exc_info:
            TelegramSettings(enabled=True, chat_id="12345")
        
        assert "Telegram token and chat ID are required when enabled is True" in str(exc_info.value)
        
        # Valid settings when enabled is True
        settings = TelegramSettings(
            enabled=True,
            token="test_token",
            chat_id="12345",
        )
        
        assert settings.enabled is True
        assert settings.token == "test_token"
        assert settings.chat_id == "12345"
