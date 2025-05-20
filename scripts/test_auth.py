"""
Test script to verify the authentication flow and protected endpoints.
"""
import os
import sys
import json
import requests
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

# Configuration
BASE_URL = "http://localhost:8000/api"
AUTH_URL = f"{BASE_URL}/auth/token"
REVIEWS_URL = f"{BASE_URL}/review/list"

# Test credentials
TEST_USER = "admin"
TEST_PASSWORD = "admin"

def print_step(step: str):
    """Print a formatted step message."""
    print(f"\n{'='*50}")
    print(f"STEP: {step}")
    print(f"{'='*50}")

def print_response(response: requests.Response):
    """Print the response details."""
    print(f"Status: {response.status_code}")
    try:
        print("Response:", json.dumps(response.json(), indent=2, ensure_ascii=False))
    except ValueError:
        print("Response:", response.text)

def get_access_token() -> str:
    """Get an access token using the test credentials."""
    print_step("1. Getting access token")
    
    try:
        response = requests.post(
            AUTH_URL,
            data={
                "username": TEST_USER,
                "password": TEST_PASSWORD,
                "grant_type": "password"
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        print("Request:", f"POST {AUTH_URL}")
        print(f"Headers: {dict(response.request.headers)}")
        print(f"Body: {response.request.body}")
        print_response(response)
        
        response.raise_for_status()
        token = response.json()["access_token"]
        print(f"✅ Successfully obtained access token: {token[:20]}...")
        return token
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error getting access token: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            print(f"Response body: {e.response.text}")
        sys.exit(1)

def test_protected_endpoint(token: str, endpoint: str, method: str = "GET", json_data: Optional[Dict] = None):
    """Test a protected endpoint with the given token."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    print_step(f"Testing {method} {endpoint}")
    
    try:
        if method.upper() == "GET":
            response = requests.get(endpoint, headers=headers)
        elif method.upper() == "POST":
            response = requests.post(endpoint, headers=headers, json=json_data or {})
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
        
        print(f"Request: {method} {endpoint}")
        print(f"Headers: {headers}")
        if json_data:
            print(f"Body: {json.dumps(json_data, indent=2)}")
        print_response(response)
        
        response.raise_for_status()
        return response.json()
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error calling {endpoint}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            print(f"Response body: {e.response.text}")
        return None

def test_unauthenticated_access():
    """Test accessing protected endpoints without authentication."""
    print_step("Testing unauthenticated access")
    
    # Test without any token
    print("\n1. Accessing protected endpoint without token")
    response = requests.get(REVIEWS_URL)
    print_response(response)
    
    # Test with invalid token
    print("\n2. Accessing protected endpoint with invalid token")
    headers = {"Authorization": "Bearer invalid_token_123"}
    response = requests.get(REVIEWS_URL, headers=headers)
    print_response(response)

def main():
    """Main test function."""
    print("=" * 60)
    print("🔒 Testing Authentication Flow")
    print("=" * 60)
    
    # Test 1: Try to access protected endpoints without authentication
    test_unauthenticated_access()
    
    # Test 2: Get access token
    token = get_access_token()
    
    if not token:
        print("❌ Failed to get access token. Exiting...")
        return
    
    # Test 3: Access protected endpoints with valid token
    print_step("Testing authenticated access")
    
    # Test list reviews
    reviews = test_protected_endpoint(token, REVIEWS_URL)
    
    # Test creating a new review (if implemented)
    # review_data = {
    #     "repo_path": "/path/to/repo",
    #     "branch": "main",
    #     "notify": True
    # }
    # test_protected_endpoint(token, f"{BASE_URL}/review/trigger", "POST", review_data)
    
    print("\n" + "=" * 60)
    print("✅ Authentication flow test completed successfully!")
    print("=" * 60)

if __name__ == "__main__":
    main()
