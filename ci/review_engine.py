#!/usr/bin/env python3
"""
AI Code Inspector - Automated Code Review Engine

This module provides automated code review capabilities for the CI/CD pipeline.
It analyzes code quality, potential bugs, and adherence to standards.
"""

import ast
import subprocess
import json
import re
import os
import sys
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger('code_review')

@dataclass
class CodeIssue:
    """Represents an issue found during code review."""
    file_path: str
    line: int
    column: int
    code: str
    message: str
    severity: str  # 'info', 'warning', 'error'
    tool: str  # 'flake8', 'mypy', 'bandit', etc.
    category: str  # 'style', 'bug', 'security', 'performance', 'complexity'

    def to_dict(self) -> dict:
        return asdict(self)

class CodeReviewer:
    """Main class for performing code reviews."""
    
    def __init__(self, repo_path: str):
        self.repo_path = Path(repo_path).resolve()
        self.issues: List[CodeIssue] = []
        self.temp_dir = Path(tempfile.mkdtemp(prefix='code_review_'))
        
    def __del__(self):
        """Clean up temporary files."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def run_flake8(self) -> List[CodeIssue]:
        """Run flake8 for style and syntax checking."""
        try:
            result = subprocess.run(
                ['flake8', '--format=json', '--max-line-length=120', str(self.repo_path)],
                capture_output=True,
                text=True,
                cwd=str(self.repo_path)
            )
            
            issues = []
            for item in json.loads(result.stdout or '[]'):
                issue = CodeIssue(
                    file_path=item['filename'],
                    line=item['line_number'],
                    column=item['column_number'],
                    code=item['code'],
                    message=item['text'],
                    severity='warning' if item['code'].startswith('E') else 'info',
                    tool='flake8',
                    category='style'
                )
                issues.append(issue)
            return issues
            
        except Exception as e:
            logger.error(f"Error running flake8: {e}")
            return []
    
    def run_mypy(self) -> List[CodeIssue]:
        """Run mypy for static type checking."""
        try:
            result = subprocess.run(
                ['mypy', '--no-error-summary', '--no-pretty', '--show-column-numbers',
                 '--hide-error-context', '--hide-error-codes', '--no-color-output',
                 '--no-incremental', '--cache-dir=/dev/null', str(self.repo_path)],
                capture_output=True,
                text=True,
                cwd=str(self.repo_path)
            )
            
            issues = []
            pattern = r'^(.*?):(\d+):(\d+): (error|note|warning): (.*?)(?:\s+\[.*?\])?$'
            
            for line in result.stderr.splitlines():
                if match := re.match(pattern, line):
                    file_path, line_no, col_no, severity, message = match.groups()
                    issue = CodeIssue(
                        file_path=file_path,
                        line=int(line_no),
                        column=int(col_no),
                        code='mypy',
                        message=message,
                        severity=severity,
                        tool='mypy',
                        category='type'
                    )
                    issues.append(issue)
            return issues
            
        except Exception as e:
            logger.error(f"Error running mypy: {e}")
            return []
    
    def run_bandit(self) -> List[CodeIssue]:
        """Run bandit for security issues."""
        try:
            result = subprocess.run(
                ['bandit', '-r', '-f', 'json', str(self.repo_path)],
                capture_output=True,
                text=True,
                cwd=str(self.repo_path)
            )
            
            issues = []
            report = json.loads(result.stdout or '{}')
            
            for issue in report.get('results', []):
                code_issue = CodeIssue(
                    file_path=issue['filename'],
                    line=issue['line_number'],
                    column=issue['col_offset'],
                    code=issue['test_id'],
                    message=issue['issue_text'],
                    severity=issue['issue_severity'].lower(),
                    tool='bandit',
                    category='security'
                )
                issues.append(code_issue)
            return issues
            
        except Exception as e:
            logger.error(f"Error running bandit: {e}")
            return []
    
    def analyze_ast(self) -> List[CodeIssue]:
        """Analyze code using AST for complex patterns."""
        issues = []
        
        for py_file in self.repo_path.rglob('*.py'):
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                # Skip empty files
                if not content.strip():
                    continue
                    
                # Check for common issues using AST
                tree = ast.parse(content, str(py_file))
                
                # Example: Check for functions that are too long
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        # Check function length
                        func_lines = node.end_lineno - node.lineno if hasattr(node, 'end_lineno') else 0
                        if func_lines > 50:  # More than 50 lines is too long
                            issue = CodeIssue(
                                file_path=str(py_file.relative_to(self.repo_path)),
                                line=node.lineno,
                                column=node.col_offset,
                                code='AST001',
                                message=f"Function '{node.name}' is too long ({func_lines} lines). Consider refactoring.",
                                severity='warning',
                                tool='ast',
                                category='complexity'
                            )
                            issues.append(issue)
                            
            except Exception as e:
                logger.warning(f"Error analyzing {py_file} with AST: {e}")
                continue
                
        return issues
    
    def run_all_checks(self) -> Dict[str, Any]:
        """Run all code quality checks and return a report."""
        logger.info("Starting code review...")
        
        # Run all checks in parallel
        import concurrent.futures
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = [
                executor.submit(self.run_flake8),
                executor.submit(self.run_mypy),
                executor.submit(self.run_bandit),
                executor.submit(self.analyze_ast)
            ]
            
            # Collect results
            self.issues = []
            for future in concurrent.futures.as_completed(futures):
                try:
                    self.issues.extend(future.result())
                except Exception as e:
                    logger.error(f"Error in code review: {e}")
        
        # Generate summary
        summary = {
            'total_issues': len(self.issues),
            'by_severity': {
                'error': sum(1 for i in self.issues if i.severity == 'error'),
                'warning': sum(1 for i in self.issues if i.severity == 'warning'),
                'info': sum(1 for i in self.issues if i.severity == 'info')
            },
            'by_tool': {},
            'by_category': {}
        }
        
        # Count issues by tool and category
        for issue in self.issues:
            summary['by_tool'][issue.tool] = summary['by_tool'].get(issue.tool, 0) + 1
            summary['by_category'][issue.category] = summary['by_category'].get(issue.category, 0) + 1
        
        # Convert issues to dict for JSON serialization
        issues_dict = [issue.to_dict() for issue in self.issues]
        
        # Create final report
        report = {
            'summary': summary,
            'issues': issues_dict,
            'timestamp': str(datetime.datetime.utcnow()),
            'repo_path': str(self.repo_path)
        }
        
        return report

def save_report(report: Dict[str, Any], output_file: str) -> None:
    """Save the review report to a file."""
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

def format_report_for_console(report: Dict[str, Any]) -> str:
    """Format the report for console output."""
    summary = report.get('summary', {})
    
    # Emoji mapping for severity
    severity_emoji = {
        'error': '🔴',
        'warning': '🟠',
        'info': '🔵'
    }
    
    # Build the report
    lines = [
        "\n📋 Code Review Report",
        "=" * 80,
        f"📁 Repository: {report.get('repo_path', 'N/A')}",
        f"🕒 Timestamp: {report.get('timestamp', 'N/A')}",
        "\n📊 Summary:",
        f"   • Total issues: {summary.get('total_issues', 0)}",
    ]
    
    # Add severity breakdown
    if 'by_severity' in summary:
        lines.append("\n🚨 Severity:")
        for severity, count in summary['by_severity'].items():
            emoji = severity_emoji.get(severity, '⚪')
            lines.append(f"   • {emoji} {severity.capitalize()}: {count}")
    
    # Add tool breakdown
    if 'by_tool' in summary:
        lines.append("\n🛠️ By Tool:")
        for tool, count in summary['by_tool'].items():
            lines.append(f"   • {tool}: {count}")
    
    # Add category breakdown
    if 'by_category' in summary:
        lines.append("\n📌 By Category:")
        for category, count in summary['by_category'].items():
            lines.append(f"   • {category}: {count}")
    
    # Add top issues
    issues = report.get('issues', [])
    if issues:
        lines.append("\n🔍 Top Issues:")
        for i, issue in enumerate(issues[:5], 1):
            lines.append(
                f"{i}. {issue.get('file_path')}:{issue.get('line')} - "
                f"{issue.get('message')} ({issue.get('tool')} - {issue.get('severity')})"
            )
    
    lines.append("\n" + "=" * 80)
    return "\n".join(lines)

def format_report_for_telegram(report: Dict[str, Any]) -> str:
    """Format the report for Telegram message."""
    summary = report.get('summary', {})
    
    # Emoji mapping for severity
    severity_emoji = {
        'error': '🔴',
        'warning': '🟠',
        'info': '🔵'
    }
    
    # Build the message
    message = [
        "*📋 Code Review Report*\n",
        f"*Repository:* {report.get('repo_path', 'N/A')}",
        f"*Timestamp:* {report.get('timestamp', 'N/A')}\n",
        f"*Total Issues:* {summary.get('total_issues', 0)}",
    ]
    
    # Add severity breakdown
    if 'by_severity' in summary:
        message.append("\n*Severity:*")
        for severity, count in summary['by_severity'].items():
            emoji = severity_emoji.get(severity, '⚪')
            message.append(f"{emoji} *{severity.capitalize()}*: {count}")
    
    # Add a summary of issues by category
    if 'by_category' in summary:
        message.append("\n*Issues by Category:*")
        for category, count in summary['by_category'].items():
            message.append(f"• *{category.capitalize()}*: {count}")
    
    # Add a quick assessment
    if summary.get('total_issues', 0) == 0:
        message.append("\n✅ *Code quality is excellent!*")
    elif summary.get('by_severity', {}).get('error', 0) > 0:
        message.append("\n❌ *Critical issues found! Please review them immediately.*")
    elif summary.get('by_severity', {}).get('warning', 0) > 0:
        message.append("\n⚠️ *Some warnings found. Consider addressing them when possible.*")
    else:
        message.append("\nℹ️ *Minor issues found. Review them when possible.*")
    
    return "\n".join(message)

def main():
    """Command-line interface for the code reviewer."""
    import argparse
    
    parser = argparse.ArgumentParser(description='AI Code Inspector - Automated Code Review')
    parser.add_argument('path', help='Path to the repository or file to review')
    parser.add_argument('--output', '-o', help='Output file for the report (JSON)')
    parser.add_argument('--format', '-f', choices=['json', 'console', 'telegram'], 
                       default='console', help='Output format')
    
    args = parser.parse_args()
    
    # Check if path exists
    path = Path(args.path)
    if not path.exists():
        print(f"Error: Path '{path}' does not exist.", file=sys.stderr)
        sys.exit(1)
    
    # Create reviewer and run checks
    reviewer = CodeReviewer(str(path))
    report = reviewer.run_all_checks()
    
    # Save report if output file is specified
    if args.output:
        save_report(report, args.output)
    
    # Print report in the requested format
    if args.format == 'json':
        print(json.dumps(report, indent=2))
    elif args.format == 'telegram':
        print(format_report_for_telegram(report))
    else:  # console
        print(format_report_for_console(report))
    
    # Exit with appropriate status code
    if report.get('summary', {}).get('by_severity', {}).get('error', 0) > 0:
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
