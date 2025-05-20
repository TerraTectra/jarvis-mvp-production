#!/usr/bin/env python3
"""
CI Environment Cleanup Script

This script cleans up the CI environment by removing temporary files,
Docker containers, and other artifacts.
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

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

def run_command(cmd: List[str], cwd: Optional[Path] = None) -> bool:
    """Run a shell command and return success status."""
    try:
        subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return True
    except subprocess.CalledProcessError as e:
        print(colorize(f"Error running command: {' '.join(cmd)}", "fail"))
        print(colorize(f"Error: {e.stderr}", "fail"))
        return False
    except Exception as e:
        print(colorize(f"Unexpected error: {e}", "fail"))
        return False

def remove_directory(path: Path, name: str) -> bool:
    """Remove a directory if it exists."""
    if not path.exists():
        print(f"{name} directory does not exist: {path}")
        return True
    
    try:
        shutil.rmtree(path)
        print(f"Removed {name} directory: {path}")
        return True
    except Exception as e:
        print(colorize(f"Failed to remove {name} directory: {e}", "fail"))
        return False

def clean_python_artifacts() -> bool:
    """Clean up Python artifacts."""
    print(colorize("\n🧹 Cleaning Python artifacts...", "header"))
    success = True
    
    # Remove __pycache__ directories
    for pycache in PROJECT_ROOT.rglob("__pycache__"):
        success &= remove_directory(pycache, "__pycache__")
    
    # Remove .pytest_cache
    pytest_cache = PROJECT_ROOT / ".pytest_cache"
    success &= remove_directory(pytest_cache, ".pytest_cache")
    
    # Remove .mypy_cache
    mypy_cache = PROJECT_ROOT / ".mypy_cache"
    success &= remove_directory(mypy_cache, ".mypy_cache")
    
    # Remove build, dist, and egg-info directories
    build_dir = PROJECT_ROOT / "build"
    dist_dir = PROJECT_ROOT / "dist"
    egg_info = PROJECT_ROOT.glob("*.egg-info")
    
    success &= remove_directory(build_dir, "build")
    success &= remove_directory(dist_dir, "dist")
    
    for egg in egg_info:
        if egg.is_dir():
            success &= remove_directory(egg, "egg-info")
    
    # Remove coverage files
    coverage_files = list(PROJECT_ROOT.glob(".coverage*"))
    for cov_file in coverage_files:
        try:
            cov_file.unlink()
            print(f"Removed coverage file: {cov_file}")
        except Exception as e:
            print(colorize(f"Failed to remove coverage file {cov_file}: {e}", "fail"))
            success = False
    
    return success

def clean_docker() -> bool:
    """Clean up Docker containers and images."""
    print(colorize("\n🐳 Cleaning Docker artifacts...", "header"))
    
    if not shutil.which("docker"):
        print("Docker is not installed, skipping Docker cleanup")
        return True
    
    success = True
    
    # Stop and remove all containers
    try:
        print("Stopping and removing all containers...")
        containers = subprocess.check_output(
            ["docker", "ps", "-aq"],
            stderr=subprocess.PIPE,
            text=True
        ).strip()
        
        if containers:
            subprocess.run(
                ["docker", "rm", "-f"] + containers.split("\n"),
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            print("Removed all containers")
        else:
            print("No containers to remove")
    except subprocess.CalledProcessError as e:
        print(colorize(f"Failed to remove containers: {e.stderr}", "fail"))
        success = False
    
    # Remove all unused images
    try:
        print("Removing unused images...")
        subprocess.run(
            ["docker", "image", "prune", "-f"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        print("Removed unused images")
    except subprocess.CalledProcessError as e:
        print(colorize(f"Failed to remove unused images: {e.stderr}", "fail"))
        success = False
    
    # Remove all unused volumes
    try:
        print("Removing unused volumes...")
        subprocess.run(
            ["docker", "volume", "prune", "-f"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        print("Removed unused volumes")
    except subprocess.CalledProcessError as e:
        print(colorize(f"Failed to remove unused volumes: {e.stderr}", "fail"))
        success = False
    
    # Remove all unused networks
    try:
        print("Removing unused networks...")
        subprocess.run(
            ["docker", "network", "prune", "-f"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        print("Removed unused networks")
    except subprocess.CalledProcessError as e:
        print(colorize(f"Failed to remove unused networks: {e.stderr}", "fail"))
        success = False
    
    return success

def clean_ci_logs() -> bool:
    """Clean up CI log files."""
    print(colorize("\n📋 Cleaning CI logs...", "header"))
    logs_dir = PROJECT_ROOT / "ci" / "logs"
    
    if not logs_dir.exists():
        print("No CI logs directory found")
        return True
    
    return remove_directory(logs_dir, "CI logs")

def clean_virtualenv(venv_path: Path) -> bool:
    """Clean up the virtual environment."""
    print(colorize(f"\n🧹 Cleaning virtual environment at {venv_path}...", "header"))
    
    if not venv_path.exists():
        print(f"Virtual environment not found at {venv_path}")
        return True
    
    return remove_directory(venv_path, "virtual environment")

def main() -> int:
    """Main entry point for the cleanup script."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Clean up the CI environment')
    parser.add_argument(
        '--all',
        action='store_true',
        help='Clean all artifacts (Python, Docker, logs, etc.)'
    )
    parser.add_argument(
        '--python',
        action='store_true',
        help='Clean Python artifacts (__pycache__, .pytest_cache, etc.)'
    )
    parser.add_argument(
        '--docker',
        action='store_true',
        help='Clean Docker containers, images, and volumes'
    )
    parser.add_argument(
        '--logs',
        action='store_true',
        help='Clean CI logs'
    )
    parser.add_argument(
        '--venv',
        type=Path,
        default=PROJECT_ROOT / '.venv',
        help='Path to the virtual environment to clean (default: .venv)'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force cleanup without confirmation'
    )
    
    args = parser.parse_args()
    
    # If no specific options are provided, clean everything
    if not any([args.all, args.python, args.docker, args.logs]):
        args.all = True
    
    print(colorize("\n🧹 Jarvis MVP CI Environment Cleanup\n", "header"))
    
    if not args.force:
        confirm = input("Are you sure you want to proceed? This cannot be undone. [y/N] ")
        if confirm.lower() != 'y':
            print("Cleanup cancelled")
            return 0
    
    success = True
    
    # Clean Python artifacts
    if args.all or args.python:
        success &= clean_python_artifacts()
    
    # Clean Docker artifacts
    if args.all or args.docker:
        success &= clean_docker()
    
    # Clean CI logs
    if args.all or args.logs:
        success &= clean_ci_logs()
    
    # Clean virtual environment if --all is specified
    if args.all:
        success &= clean_virtualenv(args.venv)
    
    if success:
        print(colorize("\n✅ Cleanup completed successfully!", "okgreen"))
        return 0
    else:
        print(colorize("\n❌ Cleanup completed with errors", "fail"))
        return 1

if __name__ == "__main__":
    sys.exit(main())
