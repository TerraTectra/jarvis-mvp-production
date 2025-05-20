#!/usr/bin/env python3
"""
CI/CD Pipeline Configuration

This script manages the configuration for the CI/CD pipeline.
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
import yaml

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent
os.chdir(PROJECT_ROOT)

# Default configuration
DEFAULT_CONFIG = {
    "version": "1.0.0",
    "pipeline": {
        "stages": [
            {
                "name": "setup",
                "description": "Setup environment and install dependencies",
                "enabled": True
            },
            {
                "name": "lint",
                "description": "Run linting and code style checks",
                "enabled": True
            },
            {
                "name": "test",
                "description": "Run tests",
                "enabled": True
            },
            {
                "name": "build",
                "description": "Build the application",
                "enabled": True
            },
            {
                "name": "deploy",
                "description": "Deploy the application",
                "enabled": False
            },
            {
                "name": "notify",
                "description": "Send notifications",
                "enabled": True
            }
        ],
        "notifications": {
            "enabled": True,
            "providers": ["console", "file", "telegram"],
            "telegram": {
                "enabled": False,
                "bot_token": "",
                "chat_id": ""
            },
            "slack": {
                "enabled": False,
                "webhook_url": ""
            },
            "email": {
                "enabled": False,
                "smtp_server": "",
                "smtp_port": 587,
                "username": "",
                "password": "",
                "from_email": "",
                "to_emails": []
            }
        },
        "environments": {
            "development": {
                "enabled": True,
                "description": "Local development environment"
            },
            "staging": {
                "enabled": False,
                "description": "Staging environment for testing"
            },
            "production": {
                "enabled": False,
                "description": "Production environment"
            }
        },
        "docker": {
            "enabled": True,
            "build_args": {},
            "image_name": "jarvis-mvp",
            "image_tag": "latest",
            "registry": "",
            "context": ".",
            "dockerfile": "Dockerfile"
        },
        "python": {
            "version": "3.9",
            "dependencies": ["requirements.txt", "requirements-dev.txt"],
            "test_command": "pytest -v --cov=src --cov-report=term-missing tests",
            "lint_command": "ruff check --fix src tests",
            "type_check_command": "mypy --strict src tests",
            "format_command": "black --check --diff src tests && isort --check-only --diff src tests"
        },
        "github_actions": {
            "enabled": True,
            "workflow_file": ".github/workflows/ci.yml",
            "on": {
                "push": {
                    "branches": ["main", "develop"],
                    "tags": ["v*.*.*"]
                },
                "pull_request": {
                    "branches": ["*"]
                },
                "schedule": [
                    {"cron": "0 0 * * *"}  # Daily at midnight
                ]
            },
            "env": {
                "PYTHON_VERSION": "3.9",
                "DOCKER_BUILDKIT": "1"
            },
            "secrets": [
                "CODECOV_TOKEN",
                "DOCKERHUB_USERNAME",
                "DOCKERHUB_TOKEN",
                "SSH_PRIVATE_KEY",
                "PRODUCTION_HOST",
                "PRODUCTION_USER",
                "TELEGRAM_BOT_TOKEN",
                "TELEGRAM_CHAT_ID"
            ]
        },
        "logging": {
            "level": "INFO",
            "file": "ci/logs/ci.log",
            "max_size_mb": 10,
            "backup_count": 5
        }
    }
}

class PipelineConfig:
    """Manage CI/CD pipeline configuration."""
    
    def __init__(self, config_file: Optional[Path] = None):
        """Initialize the pipeline configuration."""
        self.config_file = config_file or PROJECT_ROOT / "ci" / "config.json"
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load the configuration from file or use defaults."""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error loading config file: {e}", file=sys.stderr)
                return DEFAULT_CONFIG
        return DEFAULT_CONFIG
    
    def save_config(self, output_file: Optional[Path] = None) -> bool:
        """Save the configuration to a file."""
        output_file = output_file or self.config_file
        try:
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2)
            return True
        except IOError as e:
            print(f"Error saving config file: {e}", file=sys.stderr)
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value by dot notation key."""
        keys = key.split('.')
        value = self.config
        
        try:
            for k in keys:
                if k.isdigit() and isinstance(value, list):
                    value = value[int(k)]
                else:
                    value = value[k]
            return value
        except (KeyError, IndexError, TypeError):
            return default
    
    def set(self, key: str, value: Any) -> bool:
        """Set a configuration value by dot notation key."""
        keys = key.split('.')
        config = self.config
        
        try:
            for k in keys[:-1]:
                if k not in config:
                    config[k] = {}
                config = config[k]
            
            # Handle list indices
            if keys[-1].isdigit() and isinstance(config, list):
                idx = int(keys[-1])
                if idx < len(config):
                    config[idx] = value
                else:
                    config.append(value)
            else:
                config[keys[-1]] = value
            
            return True
        except (KeyError, IndexError, TypeError) as e:
            print(f"Error setting config value: {e}", file=sys.stderr)
            return False
    
    def validate(self) -> bool:
        """Validate the configuration."""
        # TODO: Implement validation logic
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert the configuration to a dictionary."""
        return self.config
    
    def to_yaml(self) -> str:
        """Convert the configuration to YAML format."""
        return yaml.dump(self.config, default_flow_style=False)
    
    def to_env(self) -> str:
        """Convert the configuration to .env format."""
        env_lines = []
        
        def flatten_dict(d, parent_key=''):
            items = []
            for k, v in d.items():
                new_key = f"{parent_key}_{k}" if parent_key else k
                if isinstance(v, dict):
                    items.extend(flatten_dict(v, new_key).items())
                else:
                    items.append((new_key.upper(), v))
            return dict(items)
        
        flat_config = flatten_dict(self.config)
        for key, value in flat_config.items():
            if isinstance(value, (str, int, float, bool)):
                env_lines.append(f"{key.upper()}={value}")
            elif isinstance(value, (list, tuple)):
                env_lines.append(f"{key.upper()}={','.join(str(v) for v in value)}")
        
        return "\n".join(env_lines)

def main() -> int:
    """Main entry point for the pipeline configuration script."""
    parser = argparse.ArgumentParser(description='Manage CI/CD pipeline configuration')
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Init command
    init_parser = subparsers.add_parser('init', help='Initialize a new configuration file')
    init_parser.add_argument(
        '-f', '--force',
        action='store_true',
        help='Overwrite existing configuration file'
    )
    
    # Get command
    get_parser = subparsers.add_parser('get', help='Get a configuration value')
    get_parser.add_argument('key', help='Configuration key (dot notation)')
    get_parser.add_argument(
        '--format',
        choices=['json', 'yaml', 'env'],
        default='json',
        help='Output format'
    )
    
    # Set command
    set_parser = subparsers.add_parser('set', help='Set a configuration value')
    set_parser.add_argument('key', help='Configuration key (dot notation)')
    set_parser.add_argument('value', help='Value to set')
    
    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate the configuration')
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Export the configuration')
    export_parser.add_argument(
        '--format',
        choices=['json', 'yaml', 'env'],
        default='json',
        help='Output format'
    )
    export_parser.add_argument(
        '-o', '--output',
        type=Path,
        help='Output file (default: stdout)'
    )
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    config = PipelineConfig()
    
    if args.command == 'init':
        if config.config_file.exists() and not args.force:
            print(f"Configuration file already exists: {config.config_file}")
            print("Use --force to overwrite.")
            return 1
        
        if config.save_config():
            print(f"Initialized new configuration at: {config.config_file}")
            return 0
        return 1
    
    elif args.command == 'get':
        value = config.get(args.key)
        if value is None:
            print(f"Key not found: {args.key}", file=sys.stderr)
            return 1
        
        if args.format == 'json':
            print(json.dumps(value, indent=2))
        elif args.format == 'yaml':
            print(yaml.dump(value, default_flow_style=False))
        elif args.format == 'env':
            if isinstance(value, dict):
                for k, v in value.items():
                    print(f"{k.upper()}={v}")
            else:
                print(f"{args.key.upper()}={value}")
        return 0
    
    elif args.command == 'set':
        # Try to convert value to appropriate type
        try:
            value = json.loads(args.value)
        except json.JSONDecodeError:
            value = args.value
        
        if config.set(args.key, value):
            if config.save_config():
                print(f"Updated {args.key} = {value}")
                return 0
        return 1
    
    elif args.command == 'validate':
        if config.validate():
            print("Configuration is valid.")
            return 0
        print("Configuration is invalid.", file=sys.stderr)
        return 1
    
    elif args.command == 'export':
        if args.format == 'json':
            output = json.dumps(config.to_dict(), indent=2)
        elif args.format == 'yaml':
            output = config.to_yaml()
        elif args.format == 'env':
            output = config.to_env()
        
        if args.output:
            try:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                with open(args.output, 'w', encoding='utf-8') as f:
                    f.write(output)
                print(f"Exported configuration to: {args.output}")
            except IOError as e:
                print(f"Error writing to file: {e}", file=sys.stderr)
                return 1
        else:
            print(output)
        
        return 0
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
