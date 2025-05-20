#!/usr/bin/env python3
"""
CI/CD Pipeline Runner

This script provides a command-line interface to run the CI/CD pipeline
with various options and configurations.
"""

import os
import sys
import json
import argparse
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Tuple
from datetime import datetime, timedelta
import shutil
import platform
import logging
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import telegram_notifier after loading environment variables
try:
    from .telegram_notifier import get_telegram_notifier
except ImportError:
    # Fallback if telegram_notifier is not available
    def get_telegram_notifier():
        return None

# Authentication settings
AUTH_ENABLED = os.getenv("AUTH_ENABLED", "true").lower() == "true"
AUTH_URL = os.getenv("AUTH_URL", "http://localhost:8000/api/auth")
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api")
CI_USERNAME = os.getenv("CI_USERNAME", "ci_user")
CI_PASSWORD = os.getenv("CI_PASSWORD", "ci_password")

class TokenManager:
    """Manages authentication tokens for the CI pipeline."""
    
    def __init__(self):
        self.access_token = None
        self.refresh_token = None
        self.token_expires = None
    
    def get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers with the current access token."""
        if not AUTH_ENABLED:
            return {}
            
        if self.access_token is None or self._is_token_expired():
            self._authenticate()
            
        return {"Authorization": f"Bearer {self.access_token}"}
    
    def _is_token_expired(self) -> bool:
        """Check if the current access token is expired."""
        if not self.token_expires or not self.access_token:
            return True
        return datetime.utcnow() >= self.token_expires - timedelta(minutes=5)  # Refresh 5 minutes before expiration
    
    def _authenticate(self) -> bool:
        """Authenticate with the API and store tokens."""
        try:
            # Try to refresh token if we have one
            if self.refresh_token and not self._is_token_expired():
                success = self._refresh_token()
                if success:
                    return True
            
            # Otherwise, get new tokens with username/password
            auth_url = f"{AUTH_URL}/token"
            data = {
                "username": CI_USERNAME,
                "password": CI_PASSWORD
            }
            
            response = requests.post(
                auth_url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            response.raise_for_status()
            
            tokens = response.json()
            self.access_token = tokens["access_token"]
            self.refresh_token = tokens["refresh_token"]
            
            # Set token expiration (default to 25 minutes from now if we can't decode the token)
            try:
                from jose import jwt
                decoded = jwt.get_unverified_claims(self.access_token)
                self.token_expires = datetime.utcfromtimestamp(decoded["exp"])
            except Exception:
                self.token_expires = datetime.utcnow() + timedelta(minutes=25)
            
            return True
            
        except Exception as e:
            logging.error(f"Authentication failed: {e}")
            self.access_token = None
            self.refresh_token = None
            self.token_expires = None
            return False
    
    def _refresh_token(self) -> bool:
        """Refresh the access token using the refresh token."""
        if not self.refresh_token:
            return False
            
        try:
            refresh_url = f"{AUTH_URL}/refresh"
            data = {
                "refresh_token": self.refresh_token
            }
            
            response = requests.post(
                refresh_url,
                json=data,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            
            tokens = response.json()
            self.access_token = tokens["access_token"]
            
            # Update refresh token if a new one is provided
            if "refresh_token" in tokens:
                self.refresh_token = tokens["refresh_token"]
            
            # Update token expiration
            try:
                from jose import jwt
                decoded = jwt.get_unverified_claims(self.access_token)
                self.token_expires = datetime.utcfromtimestamp(decoded["exp"])
            except Exception:
                self.token_expires = datetime.utcnow() + timedelta(minutes=25)
            
            return True
            
        except Exception as e:
            logging.warning(f"Token refresh failed: {e}")
            return False

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent
os.chdir(PROJECT_ROOT)

# ANSI color codes
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def colorize(text: str, color: str) -> str:
    """Apply ANSI color to text if output is a terminal."""
    if sys.stdout.isatty() and hasattr(Colors, color.upper()):
        return f"{getattr(Colors, color.upper())}{text}{Colors.ENDC}"
    return text

class PipelineRunner:
    """CI/CD Pipeline Runner."""
    
    def __init__(self, verbose: bool = False, dry_run: bool = False):
        """Initialize the pipeline runner."""
        self.verbose = verbose
        self.dry_run = dry_run
        self.start_time = datetime.now()
        self.steps = []
        self.current_step = 0
        self.telegram_notifier = get_telegram_notifier()
        self.logs_dir = Path("ci/logs")
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.token_manager = TokenManager() if AUTH_ENABLED else None
        
        # Set up logging
        self.log_file = self.logs_dir / f"pipeline_{self.start_time.strftime('%Y%m%d_%H%M%S')}.log"
        logging.basicConfig(
            level=logging.DEBUG if verbose else logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger('ci.pipeline')
        self.results = {
            "status": "pending",
            "start_time": self.start_time.isoformat(),
            "end_time": None,
            "duration": None,
            "steps": []
        }
    
    def log(self, message: str, level: str = "info") -> None:
        """Log a message with the specified log level."""
        level_upper = level.upper()
        
        # Map level strings to logging levels
        level_map = {
            'DEBUG': logging.DEBUG,
            'INFO': logging.INFO,
            'WARNING': logging.WARNING,
            'ERROR': logging.ERROR,
            'CRITICAL': logging.CRITICAL,
            'SUCCESS': logging.INFO  # Map SUCCESS to INFO level
        }
        
        log_level = level_map.get(level_upper, logging.INFO)
        self.logger.log(log_level, message)
        
        # Also print to console with colors if not in verbose mode
        if not self.verbose and level_upper in ['ERROR', 'WARNING', 'SUCCESS', 'INFO']:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if level_upper == "ERROR":
                prefix = colorize(f"[{timestamp}] [{level_upper}]", "fail")
            elif level_upper == "WARNING":
                prefix = colorize(f"[{timestamp}] [{level_upper}]", "warning")
            elif level_upper == "SUCCESS":
                prefix = colorize(f"[{timestamp}] [SUCCESS]", "okgreen")
            elif level_upper == "INFO":
                prefix = colorize(f"[{timestamp}] [INFO]", "okblue")
            else:
                prefix = f"[{timestamp}] [{level_upper}]"
            
            print(f"{prefix} {message}")
    
    def run_command(self, cmd: Union[str, List[str]], cwd: Optional[Path] = None, requires_auth: bool = False) -> bool:
        """
        Run a shell command and return success status.
        
        Args:
            cmd: Command to run (string or list of args)
            cwd: Working directory for the command
            requires_auth: If True, adds authentication headers to the environment
            
        Returns:
            bool: True if the command succeeded, False otherwise
        """
        if isinstance(cmd, str):
            cmd = cmd.split()
        
        self.log(f"Running: {' '.join(cmd)}", "info")
        
        if self.dry_run:
            self.log("(dry run) Command would be executed", "warning")
            return True
        
        # Prepare environment with auth headers if needed
        env = os.environ.copy()
        if requires_auth and self.token_manager:
            try:
                auth_headers = self.token_manager.get_auth_headers()
                # Add auth headers to the environment for subprocesses
                for key, value in auth_headers.items():
                    env_key = f"HTTP_{key.upper().replace('-', '_')}"
                    env[env_key] = value
            except Exception as e:
                self.log(f"Failed to get auth token: {e}", "error")
                return False
        
        try:
            process = subprocess.run(
                cmd,
                cwd=str(cwd) if cwd else None,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                shell=isinstance(cmd, str)  # Use shell if cmd is a string
            )
            
            if self.verbose or process.stdout:
                self.log(f"Output:\n{process.stdout}", "info")
            
            if process.stderr:
                self.log(f"Errors:\n{process.stderr}", "warning")
            
            return True
            
        except subprocess.CalledProcessError as e:
            self.log(f"Command failed with exit code {e.returncode}", "error")
            if e.stdout:
                self.log(f"Output:\n{e.stdout}", "error")
            if e.stderr:
                self.log(f"Errors:\n{e.stderr}", "error")
            return False
        except Exception as e:
            self.log(f"Unexpected error: {e}", "error")
            return False
    
    def add_step(self, name: str, description: str = "") -> None:
        """Add a step to the pipeline.
        
        Args:
            name: Name of the step
            description: Optional description of the step
        """
        self.steps.append({
            "name": name,
            "description": description,
            "status": "pending",
            "start_time": None,
            "end_time": None,
            "duration": None,
            "output": ""
        })
        self.log(f"Added step: {name} - {description}", "DEBUG")
    
    def start_step(self, step_name: str) -> bool:
        """Start a pipeline step.
        
        Args:
            step_name: Name of the step to start
            
        Returns:
            bool: True if the step was started successfully
        """
        step = next((s for s in self.steps if s["name"] == step_name), None)
        if not step:
            self.log(f"Step not found: {step_name}", "error")
            return False
        
        step["start_time"] = datetime.now()
        step["status"] = "running"
        self.current_step = self.steps.index(step)
        
        self.log(f"Starting step: {step_name} - {step['description']}", "info")
        self.log("-" * 80, "info")
        
        # Send Telegram notification
        if self.telegram_notifier:
            self.telegram_notifier.notify_step_start(
                step_name=step_name,
                description=step['description']
            )
            
        return True
        
        return True
    
    def end_step(self, step_name: str, success: bool, output: str = "") -> bool:
        """End a pipeline step.
        
        Args:
            step_name: Name of the step to end
            success: Whether the step completed successfully
            output: Optional output from the step
            
        Returns:
            bool: True if the step was ended successfully
        """
        step = next((s for s in self.steps if s["name"] == step_name), None)
        if not step:
            self.log(f"Step not found: {step_name}", "error")
            return False
        
        step["end_time"] = datetime.now()
        step["duration"] = (step["end_time"] - step["start_time"]).total_seconds()
        step["status"] = "success" if success else "failed"
        step["output"] = output
        
        status_display = colorize("SUCCESS", "okgreen") if success else colorize("FAILED", "fail")
        self.log("-" * 80, "info")
        self.log(f"Step {step_name} completed: {status_display} (took {step['duration']:.2f}s)", "info")
        
        # Send Telegram notification
        if self.telegram_notifier:
            if success:
                self.telegram_notifier.notify_step_success(
                    step_name=step_name,
                    duration=step["duration"]
                )
            else:
                self.telegram_notifier.notify_step_failure(
                    step_name=step_name,
                    error=output[:1000] if output else "Unknown error",
                    log_file=str(self.log_file),
                    log_lines=10
                )
        
        return success
        
        return success
    
    def run_step(self, step_name: str, command: Union[str, List[str]], cwd: Optional[Path] = None) -> bool:
        """Run a pipeline step."""
        if not self.start_step(step_name):
            return False
        
        success = self.run_command(command, cwd)
        self.end_step(step_name, success)
        
        return success
    
    def run_pipeline(self) -> bool:
        """Run the entire pipeline.
        
        Returns:
            bool: True if all steps completed successfully, False otherwise
        """
        self.log(f"🚀 Starting CI/CD Pipeline at {self.start_time}", "header")
        
        if self.telegram_notifier:
            self.log("Telegram notifications are enabled", "info")
        else:
            self.log("Telegram notifications are disabled (set CI_TELEGRAM_NOTIFY=true to enable)", "info")
        
        all_steps_successful = True
        failed_step = None
        
        try:
            for step in self.steps:
                step_name = step["name"]
                
                if not self.start_step(step_name):
                    all_steps_successful = False
                    failed_step = step_name
                    break
                
                # Run the actual command for the step
                if step_name == "lint":
                    success = self.run_command("python -m black --check src tests && python -m isort --check-only src tests && python -m ruff check src tests")
                elif step_name == "typecheck":
                    success = self.run_command("python -m mypy src tests")
                elif step_name == "test":
                    success = self.run_command("python -m pytest -v --cov=src --cov-report=term-missing tests")
                elif step_name == "build":
                    success = self.run_command("docker build -t jarvis-mvp .")
                else:
                    # Default command for other steps
                    success = self.run_command(f"echo 'Running step: {step_name}'")
                
                if not self.end_step(step_name, success):
                    all_steps_successful = False
                    failed_step = step_name
                    break
                
                # If the step failed and we should stop on failure
                if not success and step.get("stop_on_failure", True):
                    all_steps_successful = False
                    failed_step = step_name
                    break
                    
        except Exception as e:
            self.log(f"Unexpected error in pipeline: {e}", "error")
            all_steps_successful = False
            failed_step = failed_step or "Unknown"
        
        # Calculate total duration
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        # Update overall status
        self.results["status"] = "success" if all_steps_successful else "failed"
        self.results["end_time"] = end_time.isoformat()
        self.results["duration"] = duration
        self.results["steps"] = self.steps
        
        # Send final notification
        if self.telegram_notifier:
            if all_steps_successful:
                self.telegram_notifier.notify_pipeline_success(
                    duration=duration,
                    steps=[{"name": s["name"], "duration": s.get("duration", 0)} for s in self.steps]
                )
            else:
                self.telegram_notifier.notify_pipeline_failure(
                    failed_step=failed_step,
                    duration=duration,
                    log_file=str(self.log_file)
                )
        
        # Print summary
        self.print_summary()
        
        return all_steps_successful
    
    def print_summary(self) -> None:
        """Print a summary of the pipeline execution."""
        print("\n" + "=" * 80)
        print(colorize("🏁 CI/CD Pipeline Execution Summary", "header") + "\n")
        
        # Calculate statistics
        total_steps = len(self.steps)
        passed_steps = sum(1 for s in self.steps if s["status"] == "success")
        failed_steps = total_steps - passed_steps
        
        # Print overall status
        status_display = (
            colorize("SUCCESS", "okgreen")
            if self.results["status"] == "success"
            else colorize("FAILED", "fail")
        )
        
        print(f"Status:       {status_display}")
        print(f"Start Time:   {self.start_time}")
        print(f"End Time:     {self.results['end_time']}")
        print(f"Duration:     {self.results['duration']:.2f} seconds")
        print(f"Steps:        {passed_steps} passed, {failed_steps} failed, {total_steps} total\n")
        
        # Print steps summary
        print("Steps:")
        for i, step in enumerate(self.steps, 1):
            status = (
                colorize("✓", "okgreen")
                if step["status"] == "success"
                else colorize("✗", "fail")
            )
            duration = f"{step.get('duration', 0):.2f}s" if 'duration' in step else "N/A"
            print(f"  {i:2d}. [{status}] {step['name'].ljust(15)} {duration:>8} - {step.get('description', '')}")
        
        # Print log file location
        print("\n" + "=" * 80)
        print(f"\nLog file: {self.log_file.absolute()}")
        
        # Print final status message
        if self.results["status"] == "success":
            self.log("\n🎉 Pipeline completed successfully!", "SUCCESS")
        else:
            self.log("\n❌ Pipeline failed!", "ERROR")

def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Run the CI/CD pipeline')
    
    # General options
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without making any changes'
    )
    parser.add_argument(
        '--no-telegram',
        action='store_true',
        help='Disable Telegram notifications even if configured'
    )
    
    # Pipeline steps
    steps_group = parser.add_argument_group('Pipeline Steps')
    steps_group.add_argument(
        '--lint',
        action='store_true',
        help='Run linting and code style checks (black, isort, ruff)'
    )
    steps_group.add_argument(
        '--typecheck',
        action='store_true',
        help='Run static type checking with mypy'
    )
    steps_group.add_argument(
        '--test',
        action='store_true',
        help='Run tests with pytest and coverage'
    )
    steps_group.add_argument(
        '--build',
        action='store_true',
        help='Build the Docker image'
    )
    steps_group.add_argument(
        '--deploy',
        action='store_true',
        help='Deploy the application (not implemented)'
    )
    
    # If no specific steps are provided, run the default set
    parser.set_defaults(
        lint=True,
        typecheck=True,
        test=True,
        build=True,
        deploy=False
    )
    
    return parser.parse_args()

def main() -> int:
    """Main entry point for the pipeline runner."""
    args = parse_arguments()
    
    # Initialize pipeline runner
    runner = PipelineRunner(verbose=args.verbose, dry_run=args.dry_run)
    
    # Override Telegram notification setting if --no-telegram is used
    if args.no_telegram and hasattr(runner, 'telegram_notifier') and runner.telegram_notifier:
        runner.telegram_notifier.enabled = False
        print("Telegram notifications disabled by --no-telegram flag")
    
    # Define pipeline steps with descriptions
    if args.lint:
        runner.add_step(
            "lint", 
            "Run code style checks (black, isort, ruff)"
        )
    
    if args.typecheck:
        runner.add_step(
            "typecheck", 
            "Run static type checking with mypy"
        )
    
    if args.test:
        runner.add_step(
            "test", 
            "Run tests with pytest and generate coverage report"
        )
    
    if args.build:
        runner.add_step(
            "build", 
            "Build Docker image"
        )
    
    if args.deploy:
        runner.add_step(
            "deploy", 
            "Deploy the application"
        )
    
    # Check if any steps were added
    if not runner.steps:
        print("No steps to run. Use --help to see available options.")
        return 1
    
    # Run the pipeline
    success = runner.run_pipeline()
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
