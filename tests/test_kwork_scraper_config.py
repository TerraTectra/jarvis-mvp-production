"""Tests for the Kwork scraper configuration."""
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add the src directory to the path for imports
sys.path.append(str(Path(__file__).parent.parent / "src"))

from integrations.kwork_scraper import KworkScraper
from config import ScraperSettings, DatabaseSettings, TelegramSettings


class TestKworkScraperConfig:
    """Test cases for the Kwork scraper configuration."""
    
    def test_default_config(self):
        """Test that the scraper can be created with default settings."""
        # Create default settings
        scraper_settings = ScraperSettings()
        db_settings = DatabaseSettings()
        telegram_settings = TelegramSettings()
        
        # Create a scraper instance
        scraper = KworkScraper(scraper_settings, db_settings, telegram_settings)
        
        # Verify the settings were set correctly
        assert scraper.scraper_settings == scraper_settings
        assert scraper.db_settings == db_settings
        assert scraper.telegram_settings == telegram_settings
        
        # Verify default values
        assert scraper.scraper_settings.headless is True
        assert scraper.scraper_settings.pool_size > 0
        assert scraper.scraper_settings.max_pages > 0
        assert scraper.scraper_settings.request_timeout > 0
        
        # Verify Telegram is disabled by default
        assert scraper.telegram_settings.enabled is False
    
    def test_custom_config(self):
        """Test that the scraper can be created with custom settings."""
        # Create custom settings
        scraper_settings = ScraperSettings(
            base_url="https://kwork.ru/projects",
            headless=False,
            pool_size=3,
            max_pages=5,
            request_timeout=60,
        )
        
        db_settings = DatabaseSettings(
            url="sqlite+aiosqlite:///test.db",
            echo=True,
        )
        
        telegram_settings = TelegramSettings(
            enabled=True,
            token="test-token",
            chat_id="12345",
        )
        
        # Create a scraper instance
        scraper = KworkScraper(scraper_settings, db_settings, telegram_settings)
        
        # Verify the settings were set correctly
        assert scraper.scraper_settings == scraper_settings
        assert scraper.db_settings == db_settings
        assert scraper.telegram_settings == telegram_settings
        
        # Verify custom values
        assert scraper.scraper_settings.headless is False
        assert scraper.scraper_settings.pool_size == 3
        assert scraper.scraper_settings.max_pages == 5
        assert scraper.scraper_settings.request_timeout == 60
        
        # Verify Telegram is enabled
        assert scraper.telegram_settings.enabled is True
        assert scraper.telegram_settings.token == "test-token"
        assert scraper.telegram_settings.chat_id == "12345"
    
    def test_invalid_config(self):
        """Test that invalid configuration raises appropriate errors."""
        # Test invalid pool_size
        with pytest.raises(ValueError, match="pool_size must be greater than 0"):
            ScraperSettings(pool_size=0)
        
        # Test invalid max_pages
        with pytest.raises(ValueError, match="max_pages must be greater than 0"):
            ScraperSettings(max_pages=0)
        
        # Test invalid request_timeout
        with pytest.raises(ValueError, match="request_timeout must be greater than 0"):
            ScraperSettings(request_timeout=0)
        
        # Test invalid Telegram settings (enabled but no token or chat_id)
        with pytest.raises(ValueError, match="Telegram token and chat ID are required"):
            TelegramSettings(enabled=True, token=None, chat_id=None)
        
        # Test invalid database URL
        with pytest.raises(ValueError, match="Invalid database URL"):
            DatabaseSettings(url="invalid-url")
    
    def test_config_from_environment(self):
        """Test that configuration can be loaded from environment variables."""
        # Set environment variables
        with patch.dict(os.environ, {
            "SCRAPER_HEADLESS": "false",
            "SCRAPER_POOL_SIZE": "5",
            "SCRAPER_MAX_PAGES": "10",
            "SCRAPER_REQUEST_TIMEOUT": "30",
            "DATABASE_URL": "sqlite+aiosqlite:///test.db",
            "DATABASE_ECHO": "true",
            "TELEGRAM_ENABLED": "true",
            "TELEGRAM_BOT_TOKEN": "test-token",
            "TELEGRAM_CHAT_ID": "12345",
        }):
            # Create settings from environment
            scraper_settings = ScraperSettings()
            db_settings = DatabaseSettings()
            telegram_settings = TelegramSettings()
            
            # Verify the settings were loaded from environment variables
            assert scraper_settings.headless is False
            assert scraper_settings.pool_size == 5
            assert scraper_settings.max_pages == 10
            assert scraper_settings.request_timeout == 30
            
            assert db_settings.url == "sqlite+aiosqlite:///test.db"
            assert db_settings.echo is True
            
            assert telegram_settings.enabled is True
            assert telegram_settings.token == "test-token"
            assert telegram_settings.chat_id == "12345"
    
    def test_config_override(self):
        """Test that explicit configuration overrides environment variables."""
        # Set environment variables
        with patch.dict(os.environ, {
            "SCRAPER_HEADLESS": "true",
            "SCRAPER_POOL_SIZE": "3",
            "TELEGRAM_ENABLED": "false",
        }):
            # Create settings with explicit values
            scraper_settings = ScraperSettings(headless=False, pool_size=5)
            telegram_settings = TelegramSettings(enabled=True, token="test-token", chat_id="12345")
            
            # Verify explicit values take precedence over environment variables
            assert scraper_settings.headless is False  # Overridden
            assert scraper_settings.pool_size == 5  # Overridden
            
            # Environment variable still used for non-overridden values
            assert scraper_settings.max_pages == 10  # Default
            
            # Telegram settings should use explicit values
            assert telegram_settings.enabled is True  # Overridden
            assert telegram_settings.token == "test-token"
            assert telegram_settings.chat_id == "12345"
    
    def test_config_serialization(self):
        """Test that settings can be serialized to and from dictionaries."""
        # Create settings
        scraper_settings = ScraperSettings(
            base_url="https://kwork.ru/projects",
            headless=False,
            pool_size=3,
            max_pages=5,
            request_timeout=30,
        )
        
        db_settings = DatabaseSettings(
            url="sqlite+aiosqlite:///test.db",
            echo=True,
        )
        
        telegram_settings = TelegramSettings(
            enabled=True,
            token="test-token",
            chat_id="12345",
        )
        
        # Convert to dictionary
        scraper_dict = scraper_settings.dict()
        db_dict = db_settings.dict()
        telegram_dict = telegram_settings.dict()
        
        # Convert back to objects
        scraper_from_dict = ScraperSettings(**scraper_dict)
        db_from_dict = DatabaseSettings(**db_dict)
        telegram_from_dict = TelegramSettings(**telegram_dict)
        
        # Verify the objects are equal
        assert scraper_from_dict == scraper_settings
        assert db_from_dict == db_settings
        assert telegram_from_dict == telegram_settings
    
    def test_config_validation(self):
        """Test that configuration is properly validated."""
        # Test valid configuration
        try:
            ScraperSettings(
                base_url="https://kwork.ru/projects",
                headless=True,
                pool_size=3,
                max_pages=10,
                request_timeout=30,
            )
        except Exception as e:
            pytest.fail(f"Valid configuration raised an exception: {e}")
        
        # Test invalid configuration (pool_size <= 0)
        with pytest.raises(ValueError):
            ScraperSettings(pool_size=0)
        
        # Test invalid configuration (max_pages <= 0)
        with pytest.raises(ValueError):
            ScraperSettings(max_pages=0)
        
        # Test invalid configuration (request_timeout <= 0)
        with pytest.raises(ValueError):
            ScraperSettings(request_timeout=0)
        
        # Test invalid configuration (enabled but no token or chat_id)
        with pytest.raises(ValueError):
            TelegramSettings(enabled=True, token=None, chat_id=None)
        
        # Test invalid configuration (enabled but no token)
        with pytest.raises(ValueError):
            TelegramSettings(enabled=True, token=None, chat_id="12345")
        
        # Test invalid configuration (enabled but no chat_id)
        with pytest.raises(ValueError):
            TelegramSettings(enabled=True, token="test-token", chat_id=None)
        
        # Test invalid configuration (invalid database URL)
        with pytest.raises(ValueError):
            DatabaseSettings(url="invalid-url")
    
    def test_config_from_file(self, tmp_path):
        """Test that configuration can be loaded from a file."""
        # Create a temporary config file
        config_file = tmp_path / "config.toml"
        config_file.write_text("""
        [scraper]
        headless = false
        pool_size = 5
        max_pages = 10
        request_timeout = 30
        
        [database]
        url = "sqlite+aiosqlite:///test.db"
        echo = true
        
        [telegram]
        enabled = true
        token = "test-token"
        chat_id = "12345"
        """)
        
        # Load settings from file
        with patch('config.SETTINGS_FILE', str(config_file)):
            from config import get_settings
            settings = get_settings()
            
            # Verify the settings were loaded from the file
            assert settings.scraper.headless is False
            assert settings.scraper.pool_size == 5
            assert settings.scraper.max_pages == 10
            assert settings.scraper.request_timeout == 30
            
            assert settings.database.url == "sqlite+aiosqlite:///test.db"
            assert settings.database.echo is True
            
            assert settings.telegram.enabled is True
            assert settings.telegram.token == "test-token"
            assert settings.telegram.chat_id == "12345"
