"""
Test script for CI pipeline authentication.

This script demonstrates how to use the authentication system in the CI pipeline.
"""
import os
import sys
import logging
from pathlib import Path

# Add parent directory to path to allow imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('test_auth')

def test_authentication():
    """Test the authentication functionality."""
    from ci.run_pipeline import TokenManager, AUTH_ENABLED, AUTH_URL, API_BASE_URL
    
    if not AUTH_ENABLED:
        logger.warning("Authentication is disabled. Set AUTH_ENABLED=true to test authentication.")
        return True
    
    logger.info("Testing authentication...")
    logger.info(f"Auth URL: {AUTH_URL}")
    logger.info(f"API Base URL: {API_BASE_URL}")
    
    try:
        # Initialize token manager
        token_manager = TokenManager()
        
        # Get auth headers (this will trigger authentication)
        headers = token_manager.get_auth_headers()
        
        if not headers:
            logger.error("Failed to get authentication headers")
            return False
            
        logger.info("Successfully authenticated")
        logger.debug(f"Access token: {token_manager.access_token}")
        logger.debug(f"Token expires at: {token_manager.token_expires}")
        
        # Test token refresh
        logger.info("Testing token refresh...")
        old_token = token_manager.access_token
        token_manager.token_expires = token_manager.token_expires - timedelta(minutes=30)  # Force refresh
        
        headers = token_manager.get_auth_headers()  # This should trigger a refresh
        
        if token_manager.access_token == old_token:
            logger.error("Token was not refreshed")
            return False
            
        logger.info("Token refresh successful")
        return True
        
    except Exception as e:
        logger.error(f"Authentication test failed: {e}", exc_info=True)
        return False

def test_protected_endpoint():
    """Test accessing a protected endpoint."""
    from ci.run_pipeline import TokenManager, AUTH_ENABLED, API_BASE_URL
    import requests
    
    if not AUTH_ENABLED:
        logger.warning("Authentication is disabled. Set AUTH_ENABLED=true to test protected endpoints.")
        return True
    
    try:
        token_manager = TokenManager()
        headers = token_manager.get_auth_headers()
        
        # Test accessing a protected endpoint
        logger.info("Testing access to protected endpoint...")
        response = requests.get(
            f"{API_BASE_URL}/reviews/recent",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            logger.info("Successfully accessed protected endpoint")
            return True
        else:
            logger.error(f"Failed to access protected endpoint: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Failed to access protected endpoint: {e}", exc_info=True)
        return False

def main():
    """Run authentication tests."""
    logger.info("Starting authentication tests")
    
    # Run tests
    auth_success = test_authentication()
    endpoint_success = test_protected_endpoint()
    
    # Print summary
    print("\n=== Test Summary ===")
    print(f"Authentication Test: {'PASSED' if auth_success else 'FAILED'}")
    print(f"Endpoint Access Test: {'PASSED' if endpoint_success else 'FAILED'}")
    
    # Return appropriate exit code
    if auth_success and endpoint_success:
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    from datetime import timedelta  # Moved here to avoid circular import
    main()
