#!/usr/bin/env python3
"""
Utility script for sending Telegram notifications.

This script can be used to send notifications to a Telegram chat
using a bot token and chat ID.
"""

import os
import sys
import json
import argparse
from typing import Optional, Dict, Any
import requests
from pathlib import Path

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent

# Default configuration
DEFAULT_CONFIG = {
    "telegram_bot_token": "",
    "telegram_chat_id": "",
    "ci_telegram_notify": "false"
}

class TelegramNotifier:
    """Handles sending notifications to Telegram."""
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize the Telegram notifier with configuration.
        
        Args:
            config_path: Path to a JSON configuration file. If not provided,
                       looks for a .env file in the project root.
        """
        self.config = DEFAULT_CONFIG.copy()
        self.load_config(config_path)
    
    def load_config(self, config_path: Optional[Path] = None) -> None:
        """Load configuration from a file.
        
        Args:
            config_path: Path to the configuration file. If None, looks for .env.
        """
        # Try to load from .env file if no config path is provided
        if config_path is None:
            env_file = PROJECT_ROOT / ".env"
            if env_file.exists():
                self._load_env_file(env_file)
                return
        else:
            if config_path.suffix == '.json':
                self._load_json_config(config_path)
            else:
                self._load_env_file(config_path)
    
    def _load_env_file(self, env_file: Path) -> None:
        """Load configuration from a .env file."""
        try:
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        key, value = line.split('=', 1)
                        key = key.strip().lower()
                        value = value.strip().strip('"\'')
                        
                        if key == 'telegram_bot_token':
                            self.config['telegram_bot_token'] = value
                        elif key == 'telegram_chat_id':
                            self.config['telegram_chat_id'] = value
                        elif key == 'ci_telegram_notify':
                            self.config['ci_telegram_notify'] = value.lower() == 'true'
        except Exception as e:
            print(f"Error loading .env file: {e}", file=sys.stderr)
    
    def _load_json_config(self, config_file: Path) -> None:
        """Load configuration from a JSON file."""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                self.config.update({
                    'telegram_bot_token': config_data.get('telegram_bot_token', ''),
                    'telegram_chat_id': config_data.get('telegram_chat_id', ''),
                    'ci_telegram_notify': config_data.get('ci_telegram_notify', False)
                })
        except Exception as e:
            print(f"Error loading JSON config: {e}", file=sys.stderr)
    
    def send_message(self, message: str, parse_mode: str = 'Markdown') -> bool:
        """Send a message to the configured Telegram chat.
        
        Args:
            message: The message to send.
            parse_mode: The parse mode for the message (Markdown or HTML).
            
        Returns:
            bool: True if the message was sent successfully, False otherwise.
        """
        if not self.config['ci_telegram_notify']:
            print("Telegram notifications are disabled (CI_TELEGRAM_NOTIFY is False)")
            return False
            
        if not self.config['telegram_bot_token'] or not self.config['telegram_chat_id']:
            print("Telegram bot token or chat ID is not configured", file=sys.stderr)
            return False
        
        url = f"https://api.telegram.org/bot{self.config['telegram_bot_token']}/sendMessage"
        
        try:
            response = requests.post(
                url,
                json={
                    'chat_id': self.config['telegram_chat_id'],
                    'text': message,
                    'parse_mode': parse_mode,
                    'disable_web_page_preview': True
                },
                timeout=10
            )
            
            response.raise_for_status()
            result = response.json()
            
            if not result.get('ok', False):
                print(f"Failed to send message: {result}", file=sys.stderr)
                return False
                
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"Error sending message: {e}", file=sys.stderr)
            return False
    
    def send_ci_notification(
        self, 
        status: str, 
        repo: str, 
        branch: str, 
        commit_hash: str, 
        commit_message: str,
        ci_url: str = "",
        additional_info: str = ""
    ) -> bool:
        """Send a CI notification to Telegram.
        
        Args:
            status: The status of the CI run (e.g., 'success', 'failure', 'error').
            repo: The repository name (e.g., 'username/repo').
            branch: The branch name.
            commit_hash: The commit hash.
            commit_message: The commit message.
            ci_url: URL to the CI run (optional).
            additional_info: Additional information to include (optional).
            
        Returns:
            bool: True if the message was sent successfully, False otherwise.
        """
        # Map status to emoji
        status_emoji = {
            'success': '✅',
            'failure': '❌',
            'error': '⚠️',
            'pending': '⏳',
            'cancelled': '⏹️'
        }.get(status.lower(), 'ℹ️')
        
        # Truncate commit message if too long
        if len(commit_message) > 50:
            commit_message = commit_message[:47] + '...'
        
        # Build the message
        message = (
            f"{status_emoji} *CI {status.upper()}*\n"
            f"*Repo:* `{repo}`\n"
            f"*Branch:* `{branch}`\n"
            f"*Commit:* `{commit_hash[:7]}`\n"
            f"*Message:* {commit_message}"
        )
        
        if ci_url:
            message += f"\n[View CI Run]({ci_url})"
            
        if additional_info:
            message += f"\n\n{additional_info}"
        
        return self.send_message(message)

def main() -> int:
    """Main entry point for the Telegram notifier."""
    parser = argparse.ArgumentParser(description='Send notifications to Telegram')
    parser.add_argument('message', nargs='?', help='The message to send')
    parser.add_argument('--config', help='Path to configuration file')
    parser.add_argument('--ci', action='store_true', help='Send a CI notification')
    parser.add_argument('--status', help='CI status (success, failure, error, etc.)')
    parser.add_argument('--repo', help='Repository name (e.g., username/repo)')
    parser.add_argument('--branch', help='Branch name')
    parser.add_argument('--commit-hash', help='Commit hash')
    parser.add_argument('--commit-message', help='Commit message')
    parser.add_argument('--ci-url', help='URL to the CI run')
    parser.add_argument('--additional-info', help='Additional information to include')
    
    args = parser.parse_args()
    
    notifier = TelegramNotifier(Path(args.config) if args.config else None)
    
    if args.ci:
        if not all([args.status, args.repo, args.branch, args.commit_hash, args.commit_message]):
            print("Error: --ci requires --status, --repo, --branch, --commit-hash, and --commit-message", file=sys.stderr)
            return 1
            
        return 0 if notifier.send_ci_notification(
            status=args.status,
            repo=args.repo,
            branch=args.branch,
            commit_hash=args.commit_hash,
            commit_message=args.commit_message,
            ci_url=args.ci_url or "",
            additional_info=args.additional_info or ""
        ) else 1
    
    if not args.message:
        print("Error: message is required", file=sys.stderr)
        return 1
    
    return 0 if notifier.send_message(args.message) else 1

if __name__ == "__main__":
    sys.exit(main())
