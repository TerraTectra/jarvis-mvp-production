"""Integration tests for Docker setup."""
import os
import sys
import time
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List
import json
import pytest
import requests

# Add the src directory to the path for imports
sys.path.append(str(Path(__file__).parent.parent.parent / "src"))

from config import ScraperSettings, DatabaseSettings, TelegramSettings

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent

# Test configuration
TEST_IMAGE_NAME = "kwork-scraper-test"
TEST_CONTAINER_NAME = "kwork-scraper-test-container"
TEST_NETWORK_NAME = "kwork-scraper-test-network"
TEST_DB_VOLUME = "kwork-scraper-test-db-data"


class DockerHelper:
    """Helper class for Docker operations."""

    @staticmethod
    def run_command(cmd: List[str], cwd: Optional[str] = None) -> subprocess.CompletedProcess:
        """Run a shell command and return the result."""
        print(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            cwd=cwd or str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            print(f"Command failed with code {result.returncode}")
            print(f"STDOUT: {result.stdout}")
            print(f"STDERR: {result.stderr}")
        return result

    @classmethod
    def docker_compose(cls, *args: str) -> subprocess.CompletedProcess:
        """Run a docker-compose command."""
        return cls.run_command(["docker-compose", *args])

    @classmethod
    def docker(cls, *args: str) -> subprocess.CompletedProcess:
        """Run a docker command."""
        return cls.run_command(["docker", *args])

    @classmethod
    def build_test_image(cls) -> None:
        """Build the test Docker image."""
        # Build the image with a test tag
        result = cls.docker(
            "build",
            "-t", TEST_IMAGE_NAME,
            "-f", "Dockerfile",
            "."
        )
        assert result.returncode == 0, f"Failed to build test image: {result.stderr}"

    @classmethod
    def remove_test_resources(cls) -> None:
        """Remove any existing test containers, networks, and volumes."""
        # Stop and remove any existing test container
        cls.docker("rm", "-f", TEST_CONTAINER_NAME)
        
        # Remove test network if it exists
        cls.docker("network", "rm", TEST_NETWORK_NAME)
        
        # Remove test volume if it exists
        cls.docker("volume", "rm", "-f", TEST_DB_VOLUME)

    @classmethod
    def setup_test_network(cls) -> None:
        """Create a test Docker network."""
        # Remove any existing network first
        cls.docker("network", "rm", TEST_NETWORK_NAME)
        
        # Create a new network
        result = cls.docker("network", "create", TEST_NETWORK_NAME)
        assert result.returncode == 0, f"Failed to create test network: {result.stderr}"

    @classmethod
    def start_test_container(
        cls,
        env_vars: Optional[Dict[str, str]] = None,
        command: Optional[str] = None,
        detach: bool = True,
    ) -> str:
        """Start a test container and return its ID."""
        # Build the docker run command
        cmd = [
            "run",
            "--name", TEST_CONTAINER_NAME,
            "--network", TEST_NETWORK_NAME,
            "-v", f"{TEST_DB_VOLUME}:/data",
        ]
        
        # Add environment variables
        if env_vars:
            for key, value in env_vars.items():
                cmd.extend(["-e", f"{key}={value}"])
        
        # Add detach flag if needed
        if detach:
            cmd.append("-d")
        
        # Add the image and command
        cmd.append(TEST_IMAGE_NAME)
        
        if command:
            cmd.extend(["sh", "-c", command])
        
        # Run the container
        result = cls.docker(*cmd)
        assert result.returncode == 0, f"Failed to start test container: {result.stderr}"
        
        # Get the container ID
        result = cls.docker("ps", "-q", "-f", f"name={TEST_CONTAINER_NAME}")
        assert result.returncode == 0, f"Failed to get container ID: {result.stderr}"
        
        container_id = result.stdout.strip()
        assert container_id, "Container ID is empty"
        
        return container_id

    @classmethod
    def stop_test_container(cls) -> None:
        """Stop and remove the test container."""
        cls.docker("stop", TEST_CONTAINER_NAME)
        cls.docker("rm", TEST_CONTAINER_NAME)

    @classmethod
    def get_container_logs(cls, container_id: str) -> str:
        """Get the logs from a container."""
        result = cls.docker("logs", container_id)
        assert result.returncode == 0, f"Failed to get container logs: {result.stderr}"
        return result.stdout

    @classmethod
    def wait_for_container(cls, container_id: str, timeout: int = 30) -> bool:
        """Wait for a container to be healthy or exit."""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # Check if container is still running
            result = cls.docker("inspect", "-f", "{{.State.Running}}", container_id)
            if result.returncode != 0:
                return False
                
            if result.stdout.strip() == "false":
                # Container has exited, check exit code
                result = cls.docker("inspect", "-f", "{{.State.ExitCode}}", container_id)
                if result.returncode == 0 and result.stdout.strip() == "0":
                    return True
                return False
                
            # Check if container is healthy (if healthcheck is configured)
            result = cls.docker("inspect", "-f", "{{.State.Health.Status}}", container_id)
            if result.returncode == 0 and result.stdout.strip() == "healthy":
                return True
                
            time.sleep(1)
            
        return False


@pytest.fixture(scope="module")
def docker_helper():
    """Fixture that provides a DockerHelper instance and cleans up after tests."""
    helper = DockerHelper()
    
    # Clean up any existing test resources
    helper.remove_test_resources()
    
    # Build the test image
    helper.build_test_image()
    
    # Set up the test network
    helper.setup_test_network()
    
    yield helper
    
    # Clean up after tests
    helper.remove_test_resources()


class TestDockerIntegration:
    """Integration tests for Docker setup."""
    
    def test_docker_build(self, docker_helper):
        """Test that the Docker image builds successfully."""
        # This test just verifies that the fixture was able to build the image
        pass
    
    def test_docker_run(self, docker_helper):
        """Test that the container runs and executes the scraper."""
        # Start the container with environment variables
        env_vars = {
            "SCRAPER_HEADLESS": "true",
            "SCRAPER_MAX_PAGES": "1",
            "DATABASE_URL": f"sqlite:////data/test.db",
            "TELEGRAM_ENABLED": "false",
        }
        
        container_id = docker_helper.start_test_container(
            env_vars=env_vars,
            command="python -m src.cli run --max-pages 1"
        )
        
        try:
            # Wait for the container to finish
            assert docker_helper.wait_for_container(container_id, timeout=60), \
                "Container did not complete successfully"
            
            # Check the logs
            logs = docker_helper.get_container_logs(container_id)
            print("Container logs:", logs)
            
            # Verify the expected output
            assert "Starting Kwork scraper" in logs
            assert "Scraping completed" in logs
            
        finally:
            # Always stop and remove the container
            docker_helper.stop_test_container()
    
    def test_docker_compose(self, docker_helper):
        """Test that the docker-compose setup works."""
        # Start the services
        result = docker_helper.docker_compose(
            "-f", "docker-compose.yml",
            "-f", "docker-compose.test.yml",
            "up", "-d", "--build"
        )
        assert result.returncode == 0, f"Failed to start services: {result.stderr}"
        
        try:
            # Wait for the scraper to complete
            timeout = 120  # 2 minutes
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                # Check if the scraper container has exited
                result = docker_helper.docker_compose(
                    "-f", "docker-compose.yml",
                    "-f", "docker-compose.test.yml",
                    "ps", "--status", "exited", "--services"
                )
                
                if result.returncode == 0 and "scraper" in result.stdout:
                    break
                    
                time.sleep(5)
            else:
                pytest.fail("Scraper did not complete within the timeout")
            
            # Check the logs
            result = docker_helper.docker_compose(
                "-f", "docker-compose.yml",
                "-f", "docker-compose.test.yml",
                "logs", "scraper"
            )
            
            assert result.returncode == 0, f"Failed to get logs: {result.stderr}"
            logs = result.stdout
            
            # Verify the expected output
            assert "Starting Kwork scraper" in logs
            assert "Scraping completed" in logs
            
        finally:
            # Stop and remove the services
            docker_helper.docker_compose(
                "-f", "docker-compose.yml",
                "-f", "docker-compose.test.yml",
                "down", "-v"
            )
    
    def test_health_check(self, docker_helper):
        """Test the health check endpoint."""
        # Start the API service
        env_vars = {
            "DATABASE_URL": f"sqlite:////data/test.db",
            "API_ENABLED": "true",
            "API_HOST": "0.0.0.0",
            "API_PORT": "8000",
        }
        
        container_id = docker_helper.start_test_container(
            env_vars=env_vars,
            command="uvicorn src.api.main:app --host 0.0.0.0 --port 8000"
        )
        
        try:
            # Wait for the API to start
            time.sleep(5)
            
            # Get the container's IP address
            result = docker_helper.docker(
                "inspect",
                "-f", "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}",
                container_id
            )
            assert result.returncode == 0, f"Failed to get container IP: {result.stderr}"
            
            container_ip = result.stdout.strip()
            assert container_ip, "Container IP is empty"
            
            # Make a request to the health check endpoint
            response = requests.get(f"http://{container_ip}:8000/health")
            assert response.status_code == 200
            assert response.json() == {"status": "ok"}
            
        finally:
            # Stop and remove the container
            docker_helper.stop_test_container()


if __name__ == "__main__":
    pytest.main(["-v", "tests/integration/test_docker.py"])
