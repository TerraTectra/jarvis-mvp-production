"""Tests for the logging configuration."""
import logging
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add the src directory to the path for imports
sys.path.append(str(Path(__file__).parent.parent / "src"))

from config.logging_config import setup_logging, get_logger, LOG_FORMAT, LOG_LEVEL


class TestLoggingConfig:
    """Test cases for the logging configuration."""
    
    def test_setup_logging_default(self, tmp_path):
        """Test setting up logging with default settings."""
        # Call setup_logging with default parameters
        log_file = tmp_path / "test.log"
        setup_logging(log_file=log_file)
        
        # Get the root logger
        logger = logging.getLogger()
        
        # Verify the log level is set correctly
        assert logger.level == LOG_LEVEL
        
        # Verify the log file was created
        assert log_file.exists()
        
        # Verify the log format
        formatter = logger.handlers[0].formatter
        assert formatter._fmt == LOG_FORMAT
    
    def test_setup_logging_custom_level(self, tmp_path):
        """Test setting up logging with a custom log level."""
        # Call setup_logging with a custom log level
        log_file = tmp_path / "test.log"
        setup_logging(log_file=log_file, log_level=logging.DEBUG)
        
        # Get the root logger
        logger = logging.getLogger()
        
        # Verify the log level is set correctly
        assert logger.level == logging.DEBUG
    
    def test_setup_logging_no_file(self):
        """Test setting up logging without a log file."""
        # Call setup_logging without a log file
        setup_logging(log_file=None)
        
        # Get the root logger
        logger = logging.getLogger()
        
        # Verify there are no file handlers
        file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
        assert len(file_handlers) == 0
        
        # Verify there is at least one stream handler
        stream_handlers = [h for h in logger.handlers if isinstance(h, logging.StreamHandler)]
        assert len(stream_handlers) > 0
    
    def test_get_logger(self):
        """Test getting a logger with a specific name."""
        # Get a logger with a specific name
        logger = get_logger("test_logger")
        
        # Verify the logger has the correct name
        assert logger.name == "test_logger"
        
        # Verify the logger has the correct level
        assert logger.level == LOG_LEVEL
    
    def test_logging_output(self, tmp_path, capsys):
        """Test that log messages are output correctly."""
        # Set up logging to a file and stdout
        log_file = tmp_path / "test.log"
        setup_logging(log_file=log_file, log_level=logging.INFO)
        
        # Get a logger
        logger = get_logger("test_logger")
        
        # Log a message
        test_message = "This is a test log message"
        logger.info(test_message)
        
        # Verify the message was written to the log file
        assert log_file.exists()
        with open(log_file, "r") as f:
            log_content = f.read()
        
        assert test_message in log_content
        
        # Verify the message was written to stdout
        captured = capsys.readouterr()
        assert test_message in captured.out
    
    def test_logging_levels(self, tmp_path, capsys):
        """Test that log levels are respected."""
        # Set up logging with INFO level
        log_file = tmp_path / "test.log"
        setup_logging(log_file=log_file, log_level=logging.INFO)
        
        # Get a logger
        logger = get_logger("test_logger")
        
        # Log messages at different levels
        debug_message = "This is a debug message"
        info_message = "This is an info message"
        warning_message = "This is a warning message"
        error_message = "This is an error message"
        
        logger.debug(debug_message)
        logger.info(info_message)
        logger.warning(warning_message)
        logger.error(error_message)
        
        # Verify the log file contains only messages at INFO level and above
        with open(log_file, "r") as f:
            log_content = f.read()
        
        assert debug_message not in log_content
        assert info_message in log_content
        assert warning_message in log_content
        assert error_message in log_content
        
        # Verify stdout contains only messages at INFO level and above
        captured = capsys.readouterr()
        assert debug_message not in captured.out
        assert info_message in captured.out
        assert warning_message in captured.out
        assert error_message in captured.out
    
    def test_logging_exception(self, tmp_path, capsys):
        """Test logging an exception."""
        # Set up logging
        log_file = tmp_path / "test.log"
        setup_logging(log_file=log_file, log_level=logging.ERROR)
        
        # Get a logger
        logger = get_logger("test_logger")
        
        # Log an exception
        try:
            raise ValueError("Test error")
        except ValueError as e:
            logger.exception("An error occurred")
        
        # Verify the exception was logged
        with open(log_file, "r") as f:
            log_content = f.read()
        
        assert "An error occurred" in log_content
        assert "ValueError: Test error" in log_content
        assert "Traceback" in log_content
    
    def test_logging_multiple_handlers(self, tmp_path):
        """Test that multiple handlers can be added to a logger."""
        # Set up logging to a file
        log_file1 = tmp_path / "test1.log"
        log_file2 = tmp_path / "test2.log"
        
        # Get a logger and add two file handlers
        logger = logging.getLogger("test_logger")
        logger.setLevel(logging.INFO)
        
        # Remove any existing handlers
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        # Add two file handlers
        handler1 = logging.FileHandler(log_file1)
        handler2 = logging.FileHandler(log_file2)
        
        formatter = logging.Formatter(LOG_FORMAT)
        handler1.setFormatter(formatter)
        handler2.setFormatter(formatter)
        
        logger.addHandler(handler1)
        logger.addHandler(handler2)
        
        # Log a message
        test_message = "This is a test message"
        logger.info(test_message)
        
        # Verify the message was written to both log files
        with open(log_file1, "r") as f1, open(log_file2, "r") as f2:
            log_content1 = f1.read()
            log_content2 = f2.read()
        
        assert test_message in log_content1
        assert test_message in log_content2
    
    def test_logging_rotating_file_handler(self, tmp_path):
        """Test setting up a rotating file handler."""
        from logging.handlers import RotatingFileHandler
        
        # Set up logging with a rotating file handler
        log_file = tmp_path / "rotating.log"
        
        # Get a logger
        logger = logging.getLogger("rotating_logger")
        logger.setLevel(logging.INFO)
        
        # Remove any existing handlers
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
        
        # Add a rotating file handler
        handler = RotatingFileHandler(
            log_file,
            maxBytes=1024,  # 1 KB
            backupCount=3,
        )
        
        formatter = logging.Formatter(LOG_FORMAT)
        handler.setFormatter(formatter)
        
        logger.addHandler(handler)
        
        # Log enough messages to trigger rotation
        for i in range(1000):
            logger.info(f"Test message {i}")
        
        # Verify the log file and backups were created
        log_files = list(tmp_path.glob("rotating.log*"))
        assert len(log_files) > 1  # Should have at least one backup file
        
        # Verify the total size is limited
        total_size = sum(f.stat().st_size for f in log_files)
        assert total_size < 5 * 1024  # Should be less than 5 KB in total
