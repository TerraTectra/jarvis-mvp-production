"""Tests for the main application entry point."""
import asyncio
import sys
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

# Add the src directory to the path for imports
sys.path.append(str(Path(__file__).parent.parent / "src"))

from main import main, parse_args


class TestMain:
    """Test cases for the main application entry point."""
    
    @pytest.fixture(autouse=True)
    def setup_method(self):
        """Set up test fixtures before each test method."""
        # Patch the necessary modules
        self.patchers = [
            patch('main.KworkScraper'),
            patch('main.get_db_session'),
            patch('main.send_telegram_report'),
            patch('main.KworkCRUD'),
        ]
        
        # Start all patches
        self.mock_scraper_class, self.mock_get_db, \
        self.mock_send_telegram, self.mock_crud_class = (
            p.start() for p in self.patchers
        )
        
        # Set up return values for the mocks
        self.mock_scraper = AsyncMock()
        self.mock_scraper_class.return_value = self.mock_scraper
        
        self.mock_db_session = AsyncMock()
        self.mock_get_db.return_value = self.mock_db_session
        
        self.mock_crud = AsyncMock()
        self.mock_crud_class.return_value = self.mock_crud
        
        # Set up default return values for the scraper
        self.mock_scraper.scrape_projects.return_value = (5, 3, 1)  # pages, projects, errors
        
        yield
        
        # Stop all patches
        for p in self.patchers:
            p.stop()
    
    @pytest.mark.asyncio
    async def test_parse_args_default(self):
        """Test parsing command-line arguments with default values."""
        args = parse_args([])
        
        assert args.command == 'scrape'
        assert args.pages == 1
        assert args.headless is False
        assert args.max_workers == 3
        assert args.category is None
        assert args.price_min is None
        assert args.price_max is None
        assert args.chat_id is None
        assert args.token is None
        assert args.days == 1
    
    @pytest.mark.asyncio
    async def test_parse_args_scrape(self):
        """Test parsing command-line arguments for the scrape command."""
        args = parse_args([
            'scrape',
            '--pages', '5',
            '--headless',
            '--max-workers', '5',
            '--category', 'web-development',
            '--price-min', '1000',
            '--price-max', '5000',
        ])
        
        assert args.command == 'scrape'
        assert args.pages == 5
        assert args.headless is True
        assert args.max_workers == 5
        assert args.category == 'web-development'
        assert args.price_min == 1000
        assert args.price_max == 5000
    
    @pytest.mark.asyncio
    async def test_parse_args_report(self):
        """Test parsing command-line arguments for the report command."""
        args = parse_args([
            'report',
            '--chat-id', '12345',
            '--token', 'test_token',
            '--days', '7',
        ])
        
        assert args.command == 'report'
        assert args.chat_id == '12345'
        assert args.token == 'test_token'
        assert args.days == 7
    
    @pytest.mark.asyncio
    async def test_main_scrape_command(self, capsys):
        """Test the main function with the scrape command."""
        # Mock command-line arguments
        with patch('sys.argv', [
            'main.py',
            'scrape',
            '--pages', '2',
            '--headless',
            '--max-workers', '3',
            '--category', 'web-development',
        ]):
            # Call the main function
            await main()
            
            # Verify the output
            captured = capsys.readouterr()
            output = captured.out
            
            assert "Starting Kwork scraper" in output
            assert "Pages to scrape: 2" in output
            assert "Max workers: 3" in output
            assert "Category: web-development" in output
            assert "Scraping complete" in output
            assert "Pages scraped: 2" in output
            assert "Projects found: 5" in output
            assert "New projects: 3" in output
            assert "Errors: 1" in output
    
    @pytest.mark.asyncio
    async def test_main_report_command(self, capsys):
        """Test the main function with the report command."""
        # Mock the database session to return some data
        mock_session = AsyncMock()
        self.mock_get_db.return_value = mock_session
        
        # Mock the send_telegram_report function
        self.mock_send_telegram.return_value = True
        
        # Mock command-line arguments
        with patch('sys.argv', [
            'main.py',
            'report',
            '--chat-id', '12345',
            '--token', 'test_token',
            '--days', '7',
        ]):
            # Call the main function
            await main()
            
            # Verify the output
            captured = capsys.readouterr()
            output = captured.out
            
            assert "Sending Telegram report" in output
            assert "Report sent successfully" in output
            
            # Verify the send_telegram_report function was called with the correct arguments
            self.mock_send_telegram.assert_awaited_once_with(
                db_session=mock_session,
                chat_id='12345',
                token='test_token',
                days=7,
                message=None,
            )
    
    @pytest.mark.asyncio
    async def test_main_with_telegram_env_vars(self, capsys, monkeypatch):
        """Test that the main function uses environment variables for Telegram credentials."""
        # Set environment variables for Telegram
        monkeypatch.setenv('TELEGRAM_BOT_TOKEN', 'env_token')
        monkeypatch.setenv('TELEGRAM_CHAT_ID', 'env_chat_id')
        
        # Mock the send_telegram_report function
        self.mock_send_telegram.return_value = True
        
        # Mock command-line arguments (no chat_id or token provided)
        with patch('sys.argv', ['main.py', 'report']):
            # Call the main function
            await main()
            
            # Verify the send_telegram_report function was called with the environment variables
            self.mock_send_telegram.assert_awaited_once_with(
                db_session=self.mock_db_session,
                chat_id='env_chat_id',
                token='env_token',
                days=1,
                message=None,
            )
    
    @pytest.mark.asyncio
    async def test_main_with_custom_message(self, capsys):
        """Test sending a custom message via the report command."""
        # Mock the send_telegram_report function
        self.mock_send_telegram.return_value = True
        
        # Mock command-line arguments with a custom message
        with patch('sys.argv', [
            'main.py',
            'report',
            '--chat-id', '12345',
            '--token', 'test_token',
            '--message', 'Test message',
        ]):
            # Call the main function
            await main()
            
            # Verify the send_telegram_report function was called with the custom message
            self.mock_send_telegram.assert_awaited_once_with(
                db_session=self.mock_db_session,
                chat_id='12345',
                token='test_token',
                days=1,
                message='Test message',
            )
    
    @pytest.mark.asyncio
    async def test_main_scrape_with_telegram_notification(self, capsys, monkeypatch):
        """Test that the scrape command sends a Telegram notification on completion."""
        # Set environment variables for Telegram
        monkeypatch.setenv('TELEGRAM_BOT_TOKEN', 'env_token')
        monkeypatch.setenv('TELEGRAM_CHAT_ID', 'env_chat_id')
        
        # Mock the send_telegram_report function
        self.mock_send_telegram.return_value = True
        
        # Mock command-line arguments for the scrape command
        with patch('sys.argv', [
            'main.py',
            'scrape',
            '--pages', '2',
        ]):
            # Call the main function
            await main()
            
            # Verify the send_telegram_report function was called with the correct arguments
            self.mock_send_telegram.assert_awaited_once()
            
            # Get the call arguments
            call_args = self.mock_send_telegram.await_args[1]
            
            assert call_args['chat_id'] == 'env_chat_id'
            assert call_args['token'] == 'env_token'
            assert call_args['message'] is not None
            assert "Scraping complete" in call_args['message']
            assert "Pages scraped: 2" in call_args['message']
            assert "Projects found: 5" in call_args['message']
            assert "New projects: 3" in call_args['message']
            assert "Errors: 1" in call_args['message']
    
    @pytest.mark.asyncio
    async def test_main_with_invalid_command(self, capsys):
        """Test the main function with an invalid command."""
        # Mock command-line arguments with an invalid command
        with patch('sys.argv', ['main.py', 'invalid_command']):
            # Call the main function and expect it to exit with an error
            with pytest.raises(SystemExit) as exc_info:
                await main()
            
            # Verify the exit code is 2 (standard error code for command-line errors)
            assert exc_info.value.code == 2
            
            # Verify the error message is displayed
            captured = capsys.readouterr()
            assert "invalid choice" in captured.err.lower()
    
    @pytest.mark.asyncio
    async def test_main_with_keyboard_interrupt(self, capsys):
        """Test that the main function handles KeyboardInterrupt gracefully."""
        # Mock the scraper to raise a KeyboardInterrupt
        self.mock_scraper.scrape_projects.side_effect = KeyboardInterrupt()
        
        # Mock command-line arguments for the scrape command
        with patch('sys.argv', ['main.py', 'scrape']):
            # Call the main function
            await main()
            
            # Verify the output
            captured = capsys.readouterr()
            assert "Operation cancelled by user" in captured.out
    
    @pytest.mark.asyncio
    async def test_main_with_unexpected_error(self, capsys):
        """Test that the main function handles unexpected errors gracefully."""
        # Mock the scraper to raise an unexpected error
        self.mock_scraper.scrape_projects.side_effect = Exception("Test error")
        
        # Mock command-line arguments for the scrape command
        with patch('sys.argv', ['main.py', 'scrape']):
            # Call the main function and expect it to exit with an error
            with pytest.raises(SystemExit) as exc_info:
                await main()
            
            # Verify the exit code is 1 (standard error code for unexpected errors)
            assert exc_info.value.code == 1
            
            # Verify the error message is displayed
            captured = capsys.readouterr()
            assert "An error occurred" in captured.out
            assert "Test error" in captured.out
