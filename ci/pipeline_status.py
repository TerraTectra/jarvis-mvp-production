#!/usr/bin/env python3
"""
CI/CD Pipeline Status

This script checks the status of the CI/CD pipeline and provides a summary.
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import subprocess

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

def get_git_info() -> Dict[str, str]:
    """Get Git repository information."""
    def run_git_command(cmd: List[str]) -> str:
        try:
            result = subprocess.run(
                ["git"] + cmd,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return ""
    
    branch = run_git_command(["rev-parse", "--abbrev-ref", "HEAD"])
    commit_hash = run_git_command(["rev-parse", "HEAD"])
    commit_message = run_git_command(["log", "-1", "--pretty=%B"]).split("\n")[0]
    commit_author = run_git_command(["log", "-1", "--pretty=%an"])
    commit_date = run_git_command(["log", "-1", "--pretty=%cd", "--date=iso"])
    
    return {
        "branch": branch,
        "commit_hash": commit_hash,
        "commit_message": commit_message,
        "commit_author": commit_author,
        "commit_date": commit_date
    }

def check_python_environment() -> Dict[str, Any]:
    """Check Python environment and dependencies."""
    try:
        import platform
        import sys
        import pkg_resources
        
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        
        # Check installed packages
        installed_packages = {}
        for pkg in pkg_resources.working_set:
            installed_packages[pkg.key] = pkg.version
        
        return {
            "python_version": python_version,
            "installed_packages": installed_packages,
            "status": "success"
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

def check_docker_environment() -> Dict[str, Any]:
    """Check Docker environment."""
    try:
        # Check if Docker is installed
        docker_version = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            text=True
        )
        
        if docker_version.returncode != 0:
            return {
                "status": "error",
                "error": "Docker is not installed or not in PATH"
            }
        
        # Check if Docker daemon is running
        docker_info = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True
        )
        
        if docker_info.returncode != 0:
            return {
                "status": "error",
                "error": "Docker daemon is not running"
            }
        
        # Get Docker version
        version_output = docker_version.stdout.strip()
        
        # Get container status
        containers = subprocess.run(
            ["docker", "ps", "-a", "--format", "{{.Names}}|{{.Status}}"],
            capture_output=True,
            text=True
        )
        
        container_status = []
        if containers.returncode == 0:
            for line in containers.stdout.strip().split("\n"):
                if line:
                    name, status = line.split("|", 1)
                    container_status.append({"name": name, "status": status})
        
        return {
            "status": "success",
            "version": version_output,
            "containers": container_status
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

def check_ci_status() -> Dict[str, Any]:
    """Check CI/CD pipeline status."""
    # This is a placeholder for actual CI status check
    # In a real implementation, this would query your CI server's API
    
    # For now, we'll simulate some data
    return {
        "status": "success",
        "last_run": (datetime.now() - timedelta(hours=2)).isoformat(),
        "last_status": "passed",
        "duration": "5m 23s",
        "jobs": [
            {"name": "lint", "status": "passed", "duration": "1m 12s"},
            {"name": "test", "status": "passed", "duration": "2m 45s"},
            {"name": "build", "status": "passed", "duration": "1m 26s"}
        ]
    }

def generate_status_report() -> Dict[str, Any]:
    """Generate a comprehensive status report."""
    print(colorize("\n🔍 Gathering system information...", "header"))
    
    git_info = get_git_info()
    python_info = check_python_environment()
    docker_info = check_docker_environment()
    ci_status = check_ci_status()
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "git": git_info,
        "python": python_info,
        "docker": docker_info,
        "ci_status": ci_status
    }
    
    return report

def print_status_report(report: Dict[str, Any]) -> None:
    """Print a formatted status report to the console."""
    print("\n" + "=" * 80)
    print(colorize("🚀 Jarvis MVP CI/CD Pipeline Status", "header") + "\n")
    
    # Git information
    print(colorize("📦 Git Repository", "okblue") + "\n" + "-" * 40)
    print(f"Branch:       {report['git']['branch']}")
    print(f"Commit:       {report['git']['commit_hash'][:7]}")
    print(f"Message:      {report['git']['commit_message']}")
    print(f"Author:       {report['git']['commit_author']}")
    print(f"Date:         {report['git']['commit_date']}")
    
    # Python environment
    print("\n" + colorize("🐍 Python Environment", "okblue") + "\n" + "-" * 40)
    if report["python"]["status"] == "success":
        print(f"Python:       {report['python']['python_version']}")
        print(f"Packages:     {len(report['python']['installed_packages'])} installed")
    else:
        print(colorize(f"Error: {report['python']['error']}", "fail"))
    
    # Docker environment
    print("\n" + colorize("🐳 Docker Environment", "okblue") + "\n" + "-" * 40)
    if report["docker"]["status"] == "success":
        print(f"Version:      {report['docker']['version']}")
        print(f"Containers:   {len(report['docker']['containers'])} found")
        
        if report["docker"]["containers"]:
            print("\n  Containers:")
            for container in report["docker"]["containers"]:
                status = (
                    colorize(container["status"], "okgreen") 
                    if "Up" in container["status"] 
                    else colorize(container["status"], "warning")
                )
                print(f"    {container['name']}: {status}")
    else:
        print(colorize(f"Error: {report['docker']['error']}", "fail"))
    
    # CI/CD status
    print("\n" + colorize("🔄 CI/CD Pipeline Status", "okblue") + "\n" + "-" * 40)
    print(f"Last Run:     {report['ci_status']['last_run']}")
    
    status_display = (
        colorize(report['ci_status']['last_status'].upper(), "okgreen")
        if report['ci_status']['last_status'] == "passed"
        else colorize(report['ci_status']['last_status'].upper(), "fail")
    )
    print(f"Status:       {status_display}")
    print(f"Duration:     {report['ci_status']['duration']}")
    
    if "jobs" in report["ci_status"]:
        print("\n  Jobs:")
        for job in report["ci_status"]["jobs"]:
            job_status = (
                colorize("PASSED", "okgreen")
                if job["status"] == "passed"
                else colorize("FAILED", "fail")
            )
            print(f"    {job['name'].ljust(10)} {job_status}  {job['duration']}")
    
    print("\n" + "=" * 80)

def main() -> int:
    """Main entry point for the pipeline status script."""
    parser = argparse.ArgumentParser(description='Check the status of the CI/CD pipeline')
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output the status report in JSON format'
    )
    
    args = parser.parse_args()
    
    report = generate_status_report()
    
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_status_report(report)
    
    # Return non-zero exit code if there are any errors
    if any([
        report["python"]["status"] != "success",
        report["docker"]["status"] != "success",
        report["ci_status"]["last_status"] != "passed"
    ]):
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
