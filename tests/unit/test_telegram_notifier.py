"""Unit tests for the Telegram notifier module."""
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import Update, Message, Chat
from telegram.ext import CallbackContext

# Add the src directory to the path for imports
sys.path.append(str(Path(__file__).parent.parent.parent / "src"))

from services.telegram_notifier import TelegramNotifier, TelegramBot
from database.kwork_models import ScrapeSession, KworkProject, ProjectSnapshot
from config import TelegramSettings


class TestTelegramNotifier:
    """Test cases for the TelegramNotifier class."""
    
    @pytest.fixture
    def mock_bot(self):
        """Create a mock Telegram bot."""
        with patch('telegram.Bot') as mock_bot_class:
            mock_bot = AsyncMock()
            mock_bot_class.return_value = mock_bot
            yield mock_bot
    
    @pytest.fixture
    def telegram_notifier(self, mock_bot):
        """Create a TelegramNotifier instance with a mock bot."""
        settings = TelegramSettings(
            enabled=True,
            bot_token="test_token",
            chat_id=12345,
            error_chat_id=54321,
        )
        return TelegramNotifier(settings)
    
    @pytest.fixture
    def test_scrape_session(self):
        """Create a test ScrapeSession instance."""
        return ScrapeSession(
            id=1,
            started_at="2023-01-01T00:00:00",
            completed_at="2023-01-01T01:00:00",
            status="completed",
            pages_scraped=5,
            projects_found=10,
            new_projects=3,
            errors_encountered=1,
        )
    
    @pytest.fixture
    def test_project(self):
        """Create a test KworkProject instance."""
        return KworkProject(
            kwork_id="test1",
            title="Test Project",
            url="https://kwork.ru/projects/test1",
            price=1000.0,
            category="Web Development",
        )
    
    @pytest.fixture
    def test_snapshot(self):
        """Create a test ProjectSnapshot instance."""
        return ProjectSnapshot(
            kwork_id="test1",
            title="Test Project",
            description="Test project description",
            price=1000.0,
            category="Web Development",
            date_posted="2023-01-01T00:00:00",
            scrape_session_id=1,
        )
    
    @pytest.mark.asyncio
    async def test_send_message(self, telegram_notifier, mock_bot):
        """Test sending a simple message."""
        message = "Test message"
        await telegram_notifier.send_message(message)
        
        # Verify the message was sent to the default chat
        mock_bot.send_message.assert_awaited_once()
        args, kwargs = mock_bot.send_message.await_args
        assert kwargs["chat_id"] == 12345
        assert kwargs["text"] == message
        assert kwargs["parse_mode"] == "HTML"
        assert kwargs["disable_web_page_preview"] is True
    
    @pytest.mark.asyncio
    async def test_send_error_message(self, telegram_notifier, mock_bot):
        """Test sending an error message."""
        error = "Test error"
        await telegram_notifier.send_error(error)
        
        # Verify the error was sent to the error chat
        mock_bot.send_message.assert_awaited_once()
        args, kwargs = mock_bot.send_message.await_args
        assert kwargs["chat_id"] == 54321
        assert "ERROR" in kwargs["text"]
        assert error in kwargs["text"]
    
    @pytest.mark.asyncio
    async def test_notify_scrape_started(self, telegram_notifier, mock_bot, test_scrape_session):
        """Test notifying about a scrape session start."""
        await telegram_notifier.notify_scrape_started(test_scrape_session)
        
        # Verify the notification was sent
        mock_bot.send_message.assert_awaited_once()
        args, kwargs = mock_bot.send_message.await_args
        assert "🚀 Starting new scrape session" in kwargs["text"]
        assert str(test_scrape_session.id) in kwargs["text"]
    
    @pytest.mark.asyncio
    async def test_notify_scrape_completed(self, telegram_notifier, mock_bot, test_scrape_session):
        """Test notifying about a scrape session completion."""
        await telegram_notifier.notify_scrape_completed(test_scrape_session)
        
        # Verify the notification was sent
        mock_bot.send_message.assert_awaited_once()
        args, kwargs = mock_bot.send_message.await_args
        assert "✅ Scrape session completed" in kwargs["text"]
        assert str(test_scrape_session.id) in kwargs["text"]
        assert str(test_scrape_session.projects_found) in kwargs["text"]
        assert str(test_scrape_session.new_projects) in kwargs["text"]
    
    @pytest.mark.asyncio
    async def test_notify_scrape_error(self, telegram_notifier, mock_bot, test_scrape_session):
        """Test notifying about a scrape error."""
        error = "Test error message"
        test_scrape_session.error_message = error
        
        await telegram_notifier.notify_scrape_error(test_scrape_session, error)
        
        # Verify the error notification was sent to the error chat
        mock_bot.send_message.assert_awaited_once()
        args, kwargs = mock_bot.send_message.await_args
        assert "❌ Scrape session failed" in kwargs["text"]
        assert str(test_scrape_session.id) in kwargs["text"]
        assert error in kwargs["text"]
    
    @pytest.mark.asyncio
    async def test_notify_new_projects(self, telegram_notifier, mock_bot, test_project, test_snapshot):
        """Test notifying about new projects."""
        projects = [
            (test_project, test_snapshot),
        ]
        
        await telegram_notifier.notify_new_projects(projects)
        
        # Verify the notification was sent
        mock_bot.send_message.assert_awaited_once()
        args, kwargs = mock_bot.send_message.await_args
        assert "🆕 New projects found (1)" in kwargs["text"]
        assert test_project.title in kwargs["text"]
        assert str(int(test_project.price)) in kwargs["text"]
    
    @pytest.mark.asyncio
    async def test_notify_daily_summary(self, telegram_notifier, mock_bot):
        """Test sending a daily summary."""
        summary = {
            "total_projects": 100,
            "new_projects_today": 5,
            "scrape_sessions_today": 2,
            "errors_today": 1,
            "top_categories": [
                {"name": "Web Development", "count": 50},
                {"name": "Design", "count": 30},
                {"name": "Marketing", "count": 20},
            ]
        }
        
        await telegram_notifier.notify_daily_summary(summary)
        
        # Verify the summary was sent
        mock_bot.send_message.assert_awaited_once()
        args, kwargs = mock_bot.send_message.await_args
        assert "📊 Daily Summary" in kwargs["text"]
        assert "Total projects: 100" in kwargs["text"]
        assert "New projects today: 5" in kwargs["text"]
        assert "Scrape sessions: 2" in kwargs["text"]
        assert "Errors: 1" in kwargs["text"]
        assert "Web Development (50)" in kwargs["text"]
    
    @pytest.mark.asyncio
    async def test_send_project_details(self, telegram_notifier, mock_bot, test_project, test_snapshot):
        """Test sending project details."""
        await telegram_notifier.send_project_details(test_project, test_snapshot)
        
        # Verify the project details were sent
        mock_bot.send_message.assert_awaited_once()
        args, kwargs = mock_bot.send_message.await_args
        assert test_project.title in kwargs["text"]
        assert str(int(test_project.price)) in kwargs["text"]
        assert test_project.category in kwargs["text"]
        assert test_snapshot.description in kwargs["text"]
        assert test_project.url in kwargs["text"]
    
    @pytest.mark.asyncio
    async def test_send_project_details_without_snapshot(self, telegram_notifier, mock_bot, test_project):
        """Test sending project details without a snapshot."""
        await telegram_notifier.send_project_details(test_project, None)
        
        # Verify the project details were sent without snapshot data
        mock_bot.send_message.assert_awaited_once()
        args, kwargs = mock_bot.send_message.await_args
        assert test_project.title in kwargs["text"]
        assert str(int(test_project.price)) in kwargs["text"]
        assert test_project.category in kwargs["text"]
        assert "No description available" in kwargs["text"]
    
    @pytest.mark.asyncio
    async def test_disabled_notifier(self):
        """Test that the notifier does nothing when disabled."""
        settings = TelegramSettings(
            enabled=False,
            bot_token="test_token",
            chat_id=12345,
            error_chat_id=54321,
        )
        notifier = TelegramNotifier(settings)
        
        # This should not raise any errors or send any messages
        await notifier.send_message("Test message")
        
        # No messages should be sent when disabled
        assert not notifier.bot


class TestTelegramBot:
    """Test cases for the TelegramBot class."""
    
    @pytest.fixture
    def mock_bot(self):
        """Create a mock Telegram bot."""
        with patch('telegram.Bot') as mock_bot_class, \
             patch('telegram.ext.Application') as mock_app_class:
            
            mock_bot = AsyncMock()
            mock_bot_class.return_value = mock_bot
            
            mock_app = AsyncMock()
            mock_app_class.builder.return_value = mock_app
            mock_app.bot = mock_bot
            
            yield mock_bot, mock_app
    
    @pytest.fixture
    def telegram_bot(self, mock_bot):
        """Create a TelegramBot instance with a mock bot."""
        _, mock_app = mock_bot
        settings = TelegramSettings(
            enabled=True,
            bot_token="test_token",
            chat_id=12345,
            error_chat_id=54321,
        )
        return TelegramBot(settings)
    
    @pytest.mark.asyncio
    async def test_start(self, telegram_bot, mock_bot):
        """Test starting the Telegram bot."""
        mock_bot, mock_app = mock_bot
        
        await telegram_bot.start()
        
        # Verify the application was initialized and started
        mock_app.add_handler.assert_called()
        mock_app.run_polling.assert_awaited_once()
    
    @pytest.mark.asyncio
    async def test_stop(self, telegram_bot, mock_bot):
        """Test stopping the Telegram bot."""
        mock_bot, mock_app = mock_bot
        
        # Start the bot first
        await telegram_bot.start()
        
        # Now stop it
        await telegram_bot.stop()
        
        # Verify the application was stopped
        mock_app.stop.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_register_command_handler(self, telegram_bot, mock_bot):
        """Test registering a command handler."""
        mock_bot, mock_app = mock_bot
        
        async def test_handler(update, context):
            pass
        
        # Register a test command handler
        telegram_bot.register_command_handler("test", test_handler)
        
        # Start the bot to register the handler
        await telegram_bot.start()
        
        # Verify the handler was registered
        mock_app.add_handler.assert_called()
        
        # Check that our command was registered
        call_args = [call[0][0] for call in mock_app.add_handler.call_args_list]
        assert any(
            hasattr(handler, "commands") and "test" in handler.commands
            for handler in call_args
        )
    
    @pytest.mark.asyncio
    async def test_send_message(self, telegram_bot, mock_bot):
        """Test sending a message through the bot."""
        mock_bot, _ = mock_bot
        
        # Start the bot
        await telegram_bot.start()
        
        # Send a test message
        await telegram_bot.send_message(12345, "Test message")
        
        # Verify the message was sent
        mock_bot.send_message.assert_awaited_once_with(
            chat_id=12345,
            text="Test message",
            parse_mode="HTML",
            disable_web_page_preview=True
        )


if __name__ == "__main__":
    pytest.main(["-v", "tests/unit/test_telegram_notifier.py"])
