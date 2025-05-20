#!/usr/bin/env python3
"""
CI/CD Pipeline Visualization

This script generates a visualization of the CI/CD pipeline using Graphviz.
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional
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

def check_graphviz_installed() -> bool:
    """Check if Graphviz is installed."""
    try:
        subprocess.run(
            ["dot", "-V"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )
        return True
    except (subprocess.SubprocessError, FileNotFoundError):
        return False

def generate_pipeline_graph(output_format: str = "png") -> bool:
    """Generate a visualization of the CI/CD pipeline."""
    print(colorize("\n📊 Generating CI/CD pipeline visualization...", "header"))
    
    # Check if Graphviz is installed
    if not check_graphviz_installed():
        print(colorize(
            "Graphviz is not installed. Please install it first:\n"
            "  - Ubuntu/Debian: sudo apt-get install graphviz\n"
            "  - macOS: brew install graphviz\n"
            "  - Windows: choco install graphviz",
            "warning"
        ))
        return False
    
    # Define the pipeline stages and jobs
    pipeline = {
        "stages": [
            {
                "name": "Setup",
                "jobs": ["Install Dependencies", "Setup Environment"]
            },
            {
                "name": "Lint & Format",
                "jobs": ["Black", "isort", "Ruff", "mypy"]
            },
            {
                "name": "Test",
                "jobs": [
                    "Unit Tests",
                    "Integration Tests",
                    "Coverage Report"
                ]
            },
            {
                "name": "Build",
                "jobs": ["Build Docker Image", "Test Docker Image"]
            },
            {
                "name": "Deploy",
                "jobs": ["Deploy to Staging", "Run E2E Tests", "Deploy to Production"]
            },
            {
                "name": "Notify",
                "jobs": ["Send Notifications"]
            }
        ],
        "dependencies": {
            "Setup Environment": ["Install Dependencies"],
            "Black": ["Setup Environment"],
            "isort": ["Setup Environment"],
            "Ruff": ["Setup Environment"],
            "mypy": ["Setup Environment"],
            "Unit Tests": ["Black", "isort", "Ruff", "mypy"],
            "Integration Tests": ["Unit Tests"],
            "Coverage Report": ["Unit Tests", "Integration Tests"],
            "Build Docker Image": ["Coverage Report"],
            "Test Docker Image": ["Build Docker Image"],
            "Deploy to Staging": ["Test Docker Image"],
            "Run E2E Tests": ["Deploy to Staging"],
            "Deploy to Production": ["Run E2E Tests"],
            "Send Notifications": ["Deploy to Production"]
        }
    }
    
    # Generate DOT file
    dot_content = [
        'digraph G {',
        '    rankdir=LR;',
        '    node [shape=box, style=rounded, fontname="Arial", fontsize=10];',
        '    edge [fontname="Arial", fontsize=8];',
        '    
    # Define stages',
    ]
    
    # Add stages as subgraphs
    for i, stage in enumerate(pipeline["stages"]):
        stage_name = stage["name"]
        dot_content.append(f'    subgraph cluster_{i} {{')
        dot_content.append(f'        label = "{stage_name}";')
        dot_content.append('        style = filled;')
        dot_content.append('        color = lightgrey;')
        dot_content.append('        node [style=filled, color=white];')
        
        for job in stage["jobs"]:
            dot_content.append(f'        "{job}";')
        
        dot_content.append('    }')
    
    # Add dependencies
    dot_content.append('\n    # Define dependencies')
    for job, deps in pipeline["dependencies"].items():
        for dep in deps:
            dot_content.append(f'    "{dep}" -> "{job}";')
    
    dot_content.append('}')
    
    # Create output directory if it doesn't exist
    output_dir = PROJECT_ROOT / "ci" / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Write DOT file
    dot_file = output_dir / "pipeline.dot"
    with open(dot_file, "w", encoding="utf-8") as f:
        f.write("\n".join(dot_content))
    
    # Generate visualization
    output_file = output_dir / f"pipeline.{output_format}"
    try:
        subprocess.run(
            ["dot", f"-T{output_format}", "-o", str(output_file), str(dot_file)],
            check=True
        )
        print(colorize(f"✓ Pipeline visualization saved to: {output_file}", "okgreen"))
        return True
    except subprocess.CalledProcessError as e:
        print(colorize(f"❌ Failed to generate pipeline visualization: {e}", "fail"))
        return False

def main() -> int:
    """Main entry point for the pipeline visualization script."""
    parser = argparse.ArgumentParser(description='Generate a visualization of the CI/CD pipeline')
    parser.add_argument(
        '--format',
        default='png',
        choices=['png', 'svg', 'pdf', 'jpg'],
        help='Output format (default: png)'
    )
    
    args = parser.parse_args()
    
    print(colorize("\n🚀 Jarvis MVP CI/CD Pipeline Visualization\n", "header"))
    
    if generate_pipeline_graph(args.format):
        return 0
    return 1

if __name__ == "__main__":
    sys.exit(main())
