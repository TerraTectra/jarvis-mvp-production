"""Integration tests for the code review engine."""
import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from ci.review_engine import CodeReviewer

@pytest.fixture
def sample_python_file():
    """Create a temporary Python file with sample code for testing."""
    code = """
    def example_function():
        # This function has a style issue (line too long)
        long_line = "This is a very long line that exceeds the maximum allowed line length of 79 characters and should trigger a flake8 E501 error."
        
        # This has a type issue (mypy will catch this)
        result = 1 + "1"  # type: ignore
        
        # This has a security issue (bandit will catch this)
        password = "secret"  # nosec
        
        return result
    
    if __name__ == "__main__":
        print(example_function())
    """
    
    with tempfile.NamedTemporaryFile(suffix='.py', delete=False) as f:
        f.write(code.encode('utf-8'))
        file_path = f.name
    
    yield file_path
    
    # Clean up
    if os.path.exists(file_path):
        os.unlink(file_path)

class TestCodeReviewerIntegration:
    """Integration tests for the CodeReviewer class."""
    
    def test_review_python_file(self, sample_python_file):
        """Test reviewing a Python file with various issues."""
        # Create a reviewer for the directory containing our test file
        test_dir = os.path.dirname(sample_python_file)
        reviewer = CodeReviewer(test_dir)
        
        # Run the review
        report = reviewer.run_all_checks()
        
        # Verify the report structure
        assert isinstance(report, dict)
        assert "summary" in report
        assert "issues" in report
        assert "timestamp" in report
        
        # Check that we found some issues
        assert len(report["issues"]) > 0
        
        # Check that we have the expected issue types
        issue_types = {issue["type"] for issue in report["issues"]}
        assert "style" in issue_types  # From flake8
        assert "type" in issue_types   # From mypy
        assert "security" in issue_types  # From bandit
        
        # Check that the issue locations are correct
        for issue in report["issues"]:
            assert "file_path" in issue
            assert "line" in issue
            assert "message" in issue
            assert "severity" in issue
            assert "tool" in issue
    
    @patch("subprocess.run")
    def test_flake8_integration(self, mock_run):
        """Test integration with flake8."""
        # Mock the subprocess.run output
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = b"test.py:2:1: E302 expected 2 blank lines, found 1\ntest.py:5:80: E501 line too long (89 > 79 characters)"
        mock_run.return_value = mock_result
        
        # Create a reviewer
        reviewer = CodeReviewer("/path/to/code")
        
        # Run flake8 check
        issues = reviewer.run_flake8()
        
        # Verify the issues
        assert len(issues) == 2
        assert issues[0]["type"] == "style"
        assert "E302" in issues[0]["message"]
        assert issues[1]["type"] == "style"
        assert "E501" in issues[1]["message"]
    
    @patch("subprocess.run")
    def test_mypy_integration(self, mock_run):
        """Test integration with mypy."""
        # Mock the subprocess.run output
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = b"test.py:5: error: Unsupported operand types for + (\"int\" and \"str\")  [operator]"
        mock_run.return_value = mock_result
        
        # Create a reviewer
        reviewer = CodeReviewer("/path/to/code")
        
        # Run mypy check
        issues = reviewer.run_mypy()
        
        # Verify the issues
        assert len(issues) == 1
        assert issues[0]["type"] == "type"
        assert "Unsupported operand types" in issues[0]["message"]
        assert issues[0]["severity"] == "error"
    
    @patch("subprocess.run")
    def test_bandit_integration(self, mock_run):
        """Test integration with bandit."""
        # Mock the subprocess.run output
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = json.dumps({
            "results": [
                {
                    "filename": "test.py",
                    "issue_confidence": "MEDIUM",
                    "issue_severity": "MEDIUM",
                    "issue_text": "Possible hardcoded password",
                    "line_number": 8,
                    "line_range": [8],
                    "test_id": "B105",
                    "test_name": "hardcoded_password_string",
                    "more_info": "https://bandit.readthedocs.io/en/latest/plugins/b105_hardcoded_password_string.html"
                }
            ],
            "metrics": {}
        }).encode()
        mock_run.return_value = mock_result
        
        # Create a reviewer
        reviewer = CodeReviewer("/path/to/code")
        
        # Run bandit check
        issues = reviewer.run_bandit()
        
        # Verify the issues
        assert len(issues) == 1
        assert issues[0]["type"] == "security"
        assert "hardcoded password" in issues[0]["message"].lower()
        assert issues[0]["severity"] == "medium"
    
    def test_ast_analysis(self, tmp_path):
        """Test AST-based code analysis."""
        # Create a test file with some code to analyze
        test_file = tmp_path / "test_ast.py"
        test_file.write_text("""
        def complex_function(a, b, c, d, e, f, g, h, i, j):
            # Too many arguments
            return a + b + c + d + e + f + g + h + i + j
            
        def long_function():
            # Too many lines
            a = 1
            b = 2
            c = 3
            d = 4
            e = 5
            f = 6
            g = 7
            h = 8
            i = 9
            j = 10
            k = 11
            l = 12
            m = 13
            n = 14
            o = 15
            p = 16
            q = 17
            r = 18
            s = 19
            t = 20
            u = 21
            v = 22
            w = 23
            x = 24
            y = 25
            z = 26
            return a + z
        """)
        
        # Create a reviewer
        reviewer = CodeReviewer(str(tmp_path))
        
        # Run AST analysis
        issues = reviewer.analyze_ast()
        
        # Verify we found the expected issues
        issue_messages = [issue["message"] for issue in issues]
        assert any("too many arguments" in msg.lower() for msg in issue_messages)
        assert any("function is too complex" in msg.lower() for msg in issue_messages)
