#!/usr/bin/env python3
"""
CI Tools Setup Script

This script sets up the development environment with all necessary tools
for running CI checks locally.
"""

import os
import sys
import subprocess
import platform
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import json
import venv

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

def run_command(
    cmd: List[str], 
    cwd: Optional[Path] = None,
    env: Optional[Dict[str, str]] = None,
    capture: bool = True,
    verbose: bool = False
) -> Tuple[bool, str]:
    """Run a shell command and return (success, output)."""
    if verbose:
        print(f"Running: {' '.join(cmd)}")
    
    try:
        env = env or os.environ.copy()
        result = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            env=env,
            check=False,
            capture_output=capture,
            text=True,
            encoding='utf-8',
        )
        
        output = ""
        if capture:
            if result.stdout:
                output += result.stdout
            if result.stderr:
                output += "\n" + result.stderr
        
        return result.returncode == 0, output.strip()
        
    except Exception as e:
        error_msg = f"Error running command: {e}"
        if verbose:
            error_msg += f"\nCommand: {' '.join(cmd)}"
        return False, error_msg

def check_tool_installed(tool: str, version_arg: str = "--version") -> bool:
    """Check if a tool is installed and available in PATH."""
    try:
        subprocess.run(
            [tool, version_arg],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True
        )
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False

def install_python_dependencies(verbose: bool = False) -> bool:
    """Install Python dependencies."""
    print(colorize("\n📦 Installing Python dependencies...", "header"))
    
    # Check if pip is installed
    if not check_tool_installed("pip"):
        print(colorize("❌ pip is not installed. Please install pip first.", "fail"))
        return False
    
    # Upgrade pip
    success, output = run_command(
        [sys.executable, "-m", "pip", "install", "--upgrade", "pip"],
        verbose=verbose
    )
    if not success:
        print(colorize(f"❌ Failed to upgrade pip: {output}", "fail"))
        return False
    
    # Install dependencies
    requirements_files = ["requirements.txt", "requirements-dev.txt"]
    
    for req_file in requirements_files:
        if not (PROJECT_ROOT / req_file).exists():
            print(colorize(f"⚠️  {req_file} not found, skipping...", "warning"))
            continue
            
        print(f"Installing from {req_file}...")
        success, output = run_command(
            [sys.executable, "-m", "pip", "install", "-r", req_file],
            verbose=verbose
        )
        
        if not success:
            print(colorize(f"❌ Failed to install from {req_file}: {output}", "fail"))
            return False
    
    print(colorize("✓ Python dependencies installed successfully", "okgreen"))
    return True

def setup_pre_commit_hooks(verbose: bool = False) -> bool:
    """Set up pre-commit hooks."""
    print(colorize("\n🔧 Setting up pre-commit hooks...", "header"))
    
    if not check_tool_installed("pre-commit"):
        print(colorize("❌ pre-commit is not installed. Please install it first.", "fail"))
        return False
    
    # Install pre-commit hooks
    success, output = run_command(
        ["pre-commit", "install"],
        verbose=verbose
    )
    
    if not success:
        print(colorize(f"❌ Failed to install pre-commit hooks: {output}", "fail"))
        return False
    
    # Install the hooks
    success, output = run_command(
        ["pre-commit", "install-hooks"],
        verbose=verbose
    )
    
    if not success:
        print(colorize(f"❌ Failed to install pre-commit hooks: {output}", "fail"))
        return False
    
    print(colorize("✓ pre-commit hooks installed successfully", "okgreen"))
    return True

def setup_virtualenv(venv_path: Path, verbose: bool = False) -> bool:
    """Set up a Python virtual environment."""
    print(colorize(f"\n🐍 Setting up Python virtual environment at {venv_path}...", "header"))
    
    if venv_path.exists():
        print(colorize(f"✓ Virtual environment already exists at {venv_path}", "okgreen"))
        return True
    
    try:
        venv.create(venv_path, with_pip=True)
        print(colorize("✓ Virtual environment created successfully", "okgreen"))
        return True
    except Exception as e:
        print(colorize(f"❌ Failed to create virtual environment: {e}", "fail"))
        return False

def main() -> int:
    """Main entry point for the setup script."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Set up the CI environment')
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    parser.add_argument(
        '--venv',
        type=Path,
        default=PROJECT_ROOT / '.venv',
        help='Path to the virtual environment (default: .venv)'
    )
    
    args = parser.parse_args()
    
    print(colorize("\n🚀 Setting up Jarvis MVP CI Environment\n", "header"))
    
    # Create logs directory
    (PROJECT_ROOT / "ci" / "logs").mkdir(parents=True, exist_ok=True)
    
    # Set up virtual environment
    if not setup_virtualenv(args.venv, args.verbose):
        return 1
    
    # Activate virtual environment
    if os.name == 'nt':  # Windows
        activate_script = args.venv / "Scripts" / "activate"
        python_exec = args.venv / "Scripts" / "python.exe"
    else:  # Unix/Linux/MacOS
        activate_script = args.venv / "bin" / "activate"
        python_exec = args.venv / "bin" / "python"
    
    # Update PATH to include virtual environment
    os.environ["PATH"] = f"{args.venv / 'bin'}{os.pathsep}{os.environ['PATH']}"
    
    # Install Python dependencies
    if not install_python_dependencies(args.verbose):
        return 1
    
    # Set up pre-commit hooks
    if not setup_pre_commit_hooks(args.verbose):
        return 1
    
    print(colorize("\n✅ Setup completed successfully!", "okgreen"))
    print("\nNext steps:")
    print(f"1. Activate the virtual environment: source {activate_script}")
    print("2. Run 'make check' to verify everything is working")
    print("3. Commit your changes: git add . && git commit -m 'chore: set up CI environment'")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
