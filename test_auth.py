import uvicorn
import requests
import logging
import time
import sys
from typing import Tuple, Optional, Any

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('auth_test.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Configuration
BASE_URL = "http://localhost:8000"
TIMEOUT = 5  # seconds

def check_server_health() -> bool:
    """Check if the server is responding to health check."""
    try:
        url = f"{BASE_URL}/api/health"
        logger.info(f"Checking server health at {url}")
        response = requests.get(url, timeout=TIMEOUT)
        if response.status_code == 200:
            logger.info("Server is healthy")
            return True
        logger.warning(f"Server health check failed with status {response.status_code}")
        return False
    except requests.exceptions.RequestException as e:
        logger.error(f"Server health check failed: {str(e)}")
        return False

def test_invalid_credentials() -> Tuple[Optional[int], Any]:
    """Test authentication with invalid credentials."""
    if not check_server_health():
        return None, "Server is not healthy"

    url = f"{BASE_URL}/api/auth/token"
    test_cases = [
        {"username": "nonexistent", "password": "password"},
        {"username": "admin", "password": "wrongpassword"},
        {"username": "", "password": ""},
        {},
        None
    ]
    
    results = []
    for i, test_case in enumerate(test_cases, 1):
        try:
            logger.info(f"Test case {i}: {test_case}")
            if test_case is None:
                response = requests.post(url, timeout=TIMEOUT)
            else:
                data = {
                    "username": test_case.get("username", ""),
                    "password": test_case.get("password", ""),
                    "grant_type": "password"
                }
                response = requests.post(
                    url, 
                    data=data, 
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=TIMEOUT
                )
            
            result = {
                "test_case": test_case,
                "status_code": response.status_code,
                "response": response.json() if response.content else {}
            }
            results.append(result)
            
            if response.status_code == 200:
                logger.warning(f"Unexpected success for test case {i}")
            else:
                logger.info(f"Expected failure for test case {i}: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error in test case {i}: {str(e)}")
            results.append({"test_case": test_case, "error": str(e)})
    
    return 200 if all(r.get("status_code", 200) != 200 for r in results if "error" not in r) else 400, results

def test_invalid_refresh_token() -> Tuple[Optional[int], Any]:
    """Test refresh token with invalid tokens."""
    if not check_server_health():
        return None, "Server is not healthy"

    url = f"{BASE_URL}/api/auth/refresh"
    test_cases = [
        {"refresh_token": "invalid.token.here"},
        {"refresh_token": ""},
        {"wrong_key": "some_value"},
        {},
        None
    ]
    
    results = []
    for i, test_case in enumerate(test_cases, 1):
        try:
            logger.info(f"Refresh test case {i}: {test_case}")
            if test_case is None:
                response = requests.post(url, timeout=TIMEOUT)
            else:
                response = requests.post(
                    url, 
                    json=test_case,
                    headers={"Content-Type": "application/json"},
                    timeout=TIMEOUT
                )
            
            result = {
                "test_case": test_case,
                "status_code": response.status_code,
                "response": response.json() if response.content else {}
            }
            results.append(result)
            
            if response.status_code == 200:
                logger.warning(f"Unexpected success for refresh test case {i}")
            else:
                logger.info(f"Expected failure for refresh test case {i}: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error in refresh test case {i}: {str(e)}")
            results.append({"test_case": test_case, "error": str(e)})
    
    return 200 if all(r.get("status_code", 200) != 200 for r in results if "error" not in r) else 400, results

def test_auth() -> Tuple[Optional[int], Any]:
    """Run all authentication tests."""
    test_results = {}
    
    # Test successful authentication and token refresh
    logger.info("Running positive authentication test...")
    status, auth_result = _test_positive_auth()
    test_results["positive_auth"] = {
        "status": "success" if status == 200 else "failed",
        "result": auth_result
    }
    
    # Test invalid credentials
    logger.info("\nRunning invalid credentials test...")
    status, invalid_creds_result = test_invalid_credentials()
    test_results["invalid_credentials"] = {
        "status": "success" if status == 200 else "failed",
        "result": invalid_creds_result
    }
    
    # Test invalid refresh tokens
    logger.info("\nRunning invalid refresh token test...")
    status, invalid_refresh_result = test_invalid_refresh_token()
    test_results["invalid_refresh"] = {
        "status": "success" if status == 200 else "failed",
        "result": invalid_refresh_result
    }
    
    # Determine overall test status
    all_passed = all(
        test_results[test]["status"] == "success" 
        for test in test_results
    )
    
    return 200 if all_passed else 400, test_results

def _test_positive_auth() -> Tuple[Optional[int], Any]:
    """Test successful authentication and token refresh."""
    if not check_server_health():
        return None, "Server is not healthy"

    try:
        # Test successful authentication
        url = f"{BASE_URL}/api/auth/token"
        data = {
            "username": "admin",
            "password": "admin",
            "grant_type": "password"
        }
        
        logger.info(f"Testing authentication endpoint at {url}")
        response = requests.post(
            url, 
            data=data, 
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=TIMEOUT
        )
        
        if response.status_code != 200:
            error_msg = f"Authentication failed: {response.text}"
            logger.error(error_msg)
            return response.status_code, error_msg
            
        tokens = response.json()
        if not all(k in tokens for k in ["access_token", "refresh_token"]):
            error_msg = "Missing tokens in response"
            logger.error(error_msg)
            return 400, error_msg
            
        logger.info("Authentication successful")
        
        # Test refresh token
        refresh_url = f"{BASE_URL}/api/auth/refresh"
        refresh_data = {"refresh_token": tokens["refresh_token"]}
        
        logger.info(f"Testing refresh token endpoint at {refresh_url}")
        refresh_response = requests.post(
            refresh_url, 
            json=refresh_data, 
            headers={"Content-Type": "application/json"},
            timeout=TIMEOUT
        )
        
        logger.info(f"Refresh status code: {refresh_response.status_code}")
        
        if refresh_response.status_code != 200:
            error_msg = f"Token refresh failed: {refresh_response.text}"
            logger.error(error_msg)
            return refresh_response.status_code, error_msg
        
        logger.info("Token refresh successful")
        return 200, {
            "message": "Authentication and token refresh successful",
            "access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"]
        }
            
    except requests.exceptions.Timeout:
        error_msg = "Request timed out. Is the server running and accessible?"
        logger.error(error_msg)
        return None, error_msg
    except requests.exceptions.RequestException as e:
        error_msg = f"Request failed: {str(e)}"
        logger.error(error_msg)
        return None, error_msg
    except Exception as e:
        error_msg = f"Unexpected error during authentication test: {str(e)}"
        logger.error(error_msg)
        return None, error_msg

def print_test_summary(test_results: dict) -> None:
    """Print a summary of test results."""
    print("\n" + "=" * 80)
    print("TEST SUMMARY".center(80))
    print("=" * 80)
    
    total_tests = len(test_results)
    passed_tests = sum(1 for r in test_results.values() if r["status"] == "success")
    failed_tests = total_tests - passed_tests
    
    print(f"\nTotal Tests: {total_tests}")
    print(f"✅ Passed: {passed_tests}")
    print(f"❌ Failed: {failed_tests}")
    
    if failed_tests > 0:
        print("\nFailed Tests:")
        for name, result in test_results.items():
            if result["status"] != "success":
                error_msg = result.get('error', 'Unknown error')
                if isinstance(error_msg, dict):
                    error_msg = error_msg.get('detail', str(error_msg))
                print(f"- {name}: {error_msg}")
    
    print("\nDetailed Results:")
    for name, result in test_results.items():
        status = "✅ PASSED" if result["status"] == "success" else "❌ FAILED"
        print(f"\n{name.upper()} - {status}")
        if "result" in result and result["result"]:
            if isinstance(result["result"], (list, dict)):
                import json
                print(json.dumps(result["result"], indent=2, default=str))
            else:
                print(result["result"])
    
    print("\n" + "=" * 80)
    print("END OF TEST SUMMARY".center(80))
    print("=" * 80)

if __name__ == "__main__":
    import os
    import sys
    from dotenv import load_dotenv
    
    # Load environment variables
    load_dotenv()
    
    # Set environment variables if not set
    os.environ.setdefault("JWT_ALGORITHM", "HS256")
    os.environ.setdefault("SECRET_KEY", "test_secret_key_123")
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('auth_test.log'),
            logging.StreamHandler()
        ]
    )
    
    # Check if we should start the server or connect to an existing one
    START_SERVER = os.getenv("START_SERVER", "true").lower() == "true"
    
    server_process = None
    
    try:
        if START_SERVER:
            # Start the server in a subprocess
            import subprocess
            logger.info("Starting server...")
            server_process = subprocess.Popen(
                ["python", "-m", "uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait for the server to start
            logger.info("Waiting for server to start...")
            time.sleep(3)
        
        # Run the tests
        logger.info("Starting authentication tests...")
        status_code, test_results = test_auth()
        
        # Print test summary
        if isinstance(test_results, dict):
            print_test_summary(test_results)
        else:
            logger.error(f"Unexpected test results format: {type(test_results)}")
        
        # Exit with appropriate status code
        if status_code == 200:
            logger.info("✅ All tests completed successfully!")
            sys.exit(0)
        else:
            logger.error("❌ Some tests failed. Check the logs for details.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"❌ Unexpected error during testing: {str(e)}")
        sys.exit(1)
    finally:
        if server_process:
            logger.info("Stopping server...")
            server_process.terminate()
            try:
                server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("Server did not terminate gracefully, forcing kill...")
                server_process.kill()
            logger.info("Server stopped")
