"""Integration tests for the code review API."""
import json
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from ci.review_api import app, router
from ci.review_engine import CodeReviewer

client = TestClient(app)

class TestReviewAPI:
    def test_trigger_code_review_success(self):
        """Test successful code review trigger."""
        with patch('ci.review_api.run_code_review') as mock_review:
            mock_review.return_value = {"status": "completed", "issues": []}
            
            response = client.post(
                "/ci/api/review/trigger",
                json={"path": ".", "notify": False}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "review_id" in data
            assert "status" in data
            assert data["status"] == "started"

    def test_get_review_status_not_found(self):
        """Test getting status of non-existent review."""
        response = client.get("/ci/api/review/nonexistent")
        assert response.status_code == 404

    @patch('ci.review_api.review_results')
    def test_get_review_status(self, mock_results):
        """Test getting status of existing review."""
        test_result = {"status": "completed", "issues": []}
        mock_results["test_id"] = test_result
        
        response = client.get("/ci/api/review/test_id")
        
        assert response.status_code == 200
        assert response.json() == test_result

    @patch('ci.review_api.review_results')
    @patch('ci.review_api.send_telegram_notification')
    def test_get_telegram_notification(self, mock_send, mock_results):
        """Test sending telegram notification."""
        test_result = {
            "status": "completed",
            "summary": {"total_issues": 1},
            "issues": [{"type": "style", "message": "test"}]
        }
        mock_results["test_id"] = test_result
        mock_send.return_value = {"status": "success"}
        
        response = client.get("/ci/api/review/test_id/telegram")
        
        assert response.status_code == 200
        assert "notification_sent" in response.json()
        mock_send.assert_called_once()

    def test_get_review_report_not_found(self):
        """Test getting report for non-existent review."""
        response = client.get("/ci/api/review/nonexistent/report")
        assert response.status_code == 404

    @patch('ci.review_api.review_results')
    def test_get_review_report(self, mock_results):
        """Test getting review report."""
        test_result = {
            "status": "completed",
            "summary": {"total_issues": 0},
            "issues": []
        }
        mock_results["test_id"] = test_result
        
        response = client.get("/ci/api/review/test_id/report")
        
        assert response.status_code == 200
        assert response.json() == test_result

    @patch('ci.review_api.background_tasks')
    @patch('ci.review_api.run_code_review')
    def test_background_task_processing(self, mock_review, mock_tasks):
        """Test background task processing."""
        from ci.review_api import run_code_review
        
        # Mock the background task
        mock_tasks.add_task = MagicMock()
        
        # Trigger the review
        response = client.post(
            "/ci/api/review/trigger",
            json={"path": ".", "notify": False}
        )
        
        # Verify background task was added
        assert response.status_code == 200
        mock_tasks.add_task.assert_called_once()
        
        # Get the function and args passed to add_task
        task_func = mock_tasks.add_task.call_args[1]['function']
        task_kwargs = mock_tasks.add_task.call_args[1]['kwargs']
        
        # Call the function directly to test it
        with patch('ci.review_api.review_results', {}) as mock_results:
            review_id = task_kwargs['review_id']
            mock_review.return_value = {"status": "completed"}
            
            task_func()
            
            # Verify the review was run and results were stored
            mock_review.assert_called_once()
            assert review_id in mock_results
            assert mock_results[review_id]["status"] == "completed"
