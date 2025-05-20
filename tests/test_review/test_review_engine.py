"""Unit tests for the code review engine."""
import os
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from ci.review_engine import CodeReviewer

@pytest.fixture
def sample_code_file(tmp_path):
    """Create a sample Python file for testing."""
    code = """
    def hello():
        print('Hello, World!')
    """
    file_path = tmp_path / "sample.py"
    file_path.write_text(code)
    return file_path

class TestCodeReviewer:
    def test_init_with_valid_path(self, sample_code_file):
        """Test CodeReviewer initialization with valid path."""
        reviewer = CodeReviewer(str(sample_code_file.parent))
        assert reviewer.path == str(sample_code_file.parent)
        assert isinstance(reviewer.issues, list)

    @patch('subprocess.run')
    def test_run_flake8(self, mock_run, sample_code_file):
        """Test flake8 execution."""
        # Mock subprocess output
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = b""
        mock_run.return_value = mock_result

        reviewer = CodeReviewer(str(sample_code_file.parent))
        issues = reviewer.run_flake8()
        
        assert isinstance(issues, list)
        mock_run.assert_called_once()

    @patch('subprocess.run')
    def test_run_mypy(self, mock_run, sample_code_file):
        """Test mypy execution."""
        # Mock subprocess output
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = b""
        mock_run.return_value = mock_result

        reviewer = CodeReviewer(str(sample_code_file.parent))
        issues = reviewer.run_mypy()
        
        assert isinstance(issues, list)
        mock_run.assert_called_once()

    @patch('subprocess.run')
    def test_run_bandit(self, mock_run, sample_code_file):
        """Test bandit execution."""
        # Mock subprocess output
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            'results': [],
            'metrics': {}
        }).encode()
        mock_run.return_value = mock_result

        reviewer = CodeReviewer(str(sample_code_file.parent))
        issues = reviewer.run_bandit()
        
        assert isinstance(issues, list)
        mock_run.assert_called_once()

    def test_analyze_ast(self, sample_code_file):
        """Test AST analysis."""
        reviewer = CodeReviewer(str(sample_code_file.parent))
        issues = reviewer.analyze_ast()
        
        assert isinstance(issues, list)

    @patch('ci.review_engine.CodeReviewer.run_flake8')
    @patch('ci.review_engine.CodeReviewer.run_mypy')
    @patch('ci.review_engine.CodeReviewer.run_bandit')
    @patch('ci.review_engine.CodeReviewer.analyze_ast')
    def test_run_all_checks(self, mock_ast, mock_bandit, mock_mypy, mock_flake8, sample_code_file):
        """Test running all checks in parallel."""
        # Setup mocks
        mock_flake8.return_value = [{"type": "style", "message": "test"}]
        mock_mypy.return_value = []
        mock_bandit.return_value = []
        mock_ast.return_value = []

        reviewer = CodeReviewer(str(sample_code_file.parent))
        report = reviewer.run_all_checks()
        
        assert "summary" in report
        assert "issues" in report
        assert len(report["issues"]) > 0
        
        # Verify all checks were called
        mock_flake8.assert_called_once()
        mock_mypy.assert_called_once()
        mock_bandit.assert_called_once()
        mock_ast.assert_called_once()

    def test_generate_report(self, sample_code_file):
        """Test report generation."""
        reviewer = CodeReviewer(str(sample_code_file.parent))
        report = reviewer.generate_report()
        
        assert isinstance(report, dict)
        assert "timestamp" in report
        assert "summary" in report
        assert "issues" in report
        assert "metrics" in report

    def test_save_report(self, sample_code_file, tmp_path):
        """Test saving report to file."""
        output_file = tmp_path / "report.json"
        reviewer = CodeReviewer(str(sample_code_file.parent))
        
        # Mock the report data
        test_report = {"test": "report"}
        with patch.object(reviewer, 'generate_report', return_value=test_report):
            result = reviewer.save_report(str(output_file))
            
        assert result == str(output_file)
        assert output_file.exists()
        assert json.loads(output_file.read_text()) == test_report
