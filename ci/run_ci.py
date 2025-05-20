#!/usr/bin/env python3
"""
Local CI runner for Jarvis MVP.

This script runs various code quality checks locally, similar to what would happen in CI.
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import json
import platform

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent
os.chdir(PROJECT_ROOT)

# ANSI color codes
COLORS = {
    'HEADER': '\033[95m',
    'OKBLUE': '\033[94m',
    'OKCYAN': '\033[96m',
    'OKGREEN': '\033[92m',
    'WARNING': '\033[93m',
    'FAIL': '\033[91m',
    'ENDC': '\033[0m',
    'BOLD': '\033[1m',
    'UNDERLINE': '\033[4m',
}

def colorize(text: str, color: str) -> str:
    """Apply ANSI color to text if output is a terminal."""
    if sys.stdout.isatty() and color in COLORS:
        return f"{COLORS[color]}{text}{COLORS['ENDC']}"
    return text

@dataclass
class CheckResult:
    """Result of a single check."""
    name: str
    success: bool
    output: str = ""
    duration: float = 0.0
    fix_suggestion: str = ""

    def __str__(self) -> str:
        status = colorize("PASS", "OKGREEN") if self.success else colorize("FAIL", "FAIL")
        return f"[{status}] {self.name:<20} {self.duration:.2f}s"

class CheckRunner:
    """Runs various code quality checks."""
    
    def __init__(self, verbose: bool = False, fix: bool = False):
        self.verbose = verbose
        self.fix = fix
        self.results: List[CheckResult] = []
        self.start_time: float = 0.0
        
    def log(self, message: str, level: str = "INFO") -> None:
        """Log a message with the specified log level."""
        if level == "ERROR":
            prefix = colorize("[ERROR]", "FAIL")
        elif level == "WARNING":
            prefix = colorize("[WARN] ", "WARNING")
        elif level == "INFO" and self.verbose:
            prefix = colorize("[INFO] ", "OKBLUE")
        elif level == "SUCCESS":
            prefix = colorize("[ OK ]", "OKGREEN")
        else:
            return
            
        print(f"{prefix} {message}")
    
    def run_command(
        self, 
        cmd: List[str], 
        cwd: Optional[Path] = None,
        env: Optional[Dict[str, str]] = None,
        capture: bool = True
    ) -> Tuple[bool, str]:
        """Run a shell command and return (success, output)."""
        if self.verbose:
            self.log(f"Running: {' '.join(cmd)}")
        
        try:
            env = env or os.environ.copy()
            result = subprocess.run(
                cmd,
                cwd=cwd or PROJECT_ROOT,
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
            if self.verbose:
                error_msg += f"\nCommand: {' '.join(cmd)}"
            return False, error_msg
    
    def run_check(self, name: str, func, *args, **kwargs) -> bool:
        """Run a check function and record the result."""
        self.log(f"Running check: {name}")
        start_time = getattr(self, 'start_time', 0.0)
        
        try:
            result = func(*args, **kwargs)
            duration = getattr(self, 'start_time', 0.0) - start_time
            
            if isinstance(result, CheckResult):
                result.duration = duration
                self.results.append(result)
                return result.success
            else:
                success = bool(result)
                self.results.append(CheckResult(name, success, duration=duration))
                return success
                
        except Exception as e:
            error_msg = f"Error in check {name}: {e}"
            if self.verbose:
                import traceback
                error_msg += f"\n{traceback.format_exc()}"
            self.results.append(CheckResult(name, False, error_msg))
            return False
    
    def check_black(self) -> CheckResult:
        """Check code formatting with black."""
        cmd = ["black", "--check", "--diff", "--color", "src", "tests"]
        success, output = self.run_command(cmd)
        
        fix_cmd = "black src tests"
        return CheckResult(
            "black", 
            success, 
            output,
            fix_suggestion=f"Run '{fix_cmd}' to fix formatting issues."
        )
    
    def check_isort(self) -> CheckResult:
        """Check import sorting with isort."""
        cmd = ["isort", "--check-only", "--diff", "src", "tests"]
        success, output = self.run_command(cmd)
        
        fix_cmd = "isort src tests"
        return CheckResult(
            "isort", 
            success, 
            output,
            fix_suggestion=f"Run '{fix_cmd}' to fix import ordering."
        )
    
    def check_ruff(self) -> CheckResult:
        """Run ruff linter."""
        cmd = ["ruff", "check", "--fix", "src", "tests"]
        success, output = self.run_command(cmd)
        return CheckResult("ruff", success, output)
    
    def check_mypy(self) -> CheckResult:
        """Run static type checking with mypy."""
        cmd = ["mypy", "--strict", "src", "tests"]
        success, output = self.run_command(cmd)
        return CheckResult("mypy", success, output)
    
    def check_pytest(self) -> CheckResult:
        """Run tests with pytest."""
        cmd = ["pytest", "-v", "--cov=src", "--cov-report=term-missing", "tests"]
        success, output = self.run_command(cmd)
        return CheckResult("pytest", success, output)
    
    def check_docker(self) -> CheckResult:
        """Check Docker build."""
        # First, check if Docker is installed and running
        docker_installed, _ = self.run_command(["docker", "--version"], capture=False)
        if not docker_installed:
            return CheckResult("docker", False, "Docker is not installed or not in PATH")
        
        # Try to build the Docker image
        build_cmd = ["docker", "build", "-t", "jarvis-mvp-ci-test", "."]
        success, output = self.run_command(build_cmd)
        
        if not success:
            return CheckResult("docker-build", False, output)
        
        # Test running the container
        run_cmd = ["docker", "run", "--rm", "jarvis-mvp-ci-test", "--help"]
        success, output = self.run_command(run_cmd)
        
        return CheckResult("docker-run", success, output)
    
    def check_telegram(self) -> CheckResult:
        """Check Telegram notification configuration."""
        # This is a placeholder for actual Telegram notification testing
        # In a real scenario, you would test sending a test message
        self.log("Skipping Telegram notification test in local mode", "WARNING")
        return CheckResult("telegram", True, "Skipped in local mode")
    
    def run_all_checks(self) -> bool:
        """Run all checks and return overall success."""
        import time
        
        # List of checks to run (name, function)
        checks = [
            ("black", self.check_black),
            ("isort", self.check_isort),
            ("ruff", self.check_ruff),
            ("mypy", self.check_mypy),
            ("pytest", self.check_pytest),
            ("docker", self.check_docker),
            ("telegram", self.check_telegram),
        ]
        
        # Run all checks
        all_success = True
        for name, check_func in checks:
            self.start_time = time.time()
            success = self.run_check(name, check_func)
            all_success = all_success and success
            
            # If a check fails and we're not in verbose mode, show the error
            if not success and not self.verbose:
                result = next(r for r in self.results if r.name == name)
                if result.output:
                    print(result.output)
                if result.fix_suggestion:
                    print(f"  {colorize('Hint:', 'OKCYAN')} {result.fix_suggestion}")
        
        return all_success
    
    def print_summary(self) -> None:
        """Print a summary of all check results."""
        print("\n" + "=" * 80)
        print(f"{'CHECK':<25} {'STATUS':<10} TIME")
        print("-" * 80)
        
        for result in self.results:
            print(str(result))
            
        print("=" * 80)
        
        # Count successes and failures
        success_count = sum(1 for r in self.results if r.success)
        total = len(self.results)
        
        print(f"\n{success_count} of {total} checks passed")
        
        # Show fix suggestions for failed checks
        failed_checks = [r for r in self.results if not r.success]
        if failed_checks:
            print("\nFix suggestions for failed checks:")
            for check in failed_checks:
                if check.fix_suggestion:
                    print(f"  {check.name}: {check.fix_suggestion}")


def main() -> int:
    """Main entry point for the CI runner."""
    parser = argparse.ArgumentParser(description="Run local CI checks")
    parser.add_argument(
        "-v", "--verbose", 
        action="store_true", 
        help="Enable verbose output"
    )
    parser.add_argument(
        "--fix", 
        action="store_true", 
        help="Automatically fix fixable issues"
    )
    
    args = parser.parse_args()
    
    print(colorize("\n🚀 Starting Jarvis MVP CI Checks\n", "HEADER"))
    
    runner = CheckRunner(verbose=args.verbose, fix=args.fix)
    success = runner.run_all_checks()
    runner.print_summary()
    
    if not success:
        print(colorize("\n❌ Some checks failed. Please fix the issues above.", "FAIL"))
        return 1
    
    print(colorize("\n✅ All checks passed!", "OKGREEN"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
