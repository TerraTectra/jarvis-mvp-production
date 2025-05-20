"""
Test script to verify the authentication flow and protected endpoints.
"""
import os
import sys
import json
import requests
from typing import Dict, Any, Optional

# Configuration
BASE_URL = "http://localhost:8000"
AUTH_URL = f"{BASE_URL}/ci/api/auth/token"
REVIEWS_URL = f"{BASE_URL}/ci/api/review/list"

# Test credentials
TEST_USER = "admin"
TEST_PASSWORD = "admin"


def get_access_token() -> str:
    """Get an access token using the test credentials."""
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
        response.raise_for_status()
        return response.json()["access_token"]
    except requests.exceptions.RequestException as e:
        print(f"Error getting access token: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            print(f"Response body: {e.response.text}")
        sys.exit(1)


def test_protected_endpoint(token: str, endpoint: str, method: str = "GET", json_data: Optional[Dict] = None) -> Dict[str, Any]:
    """Test a protected endpoint with the given token."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        if method.upper() == "GET":
            response = requests.get(endpoint, headers=headers)
        elif method.upper() == "POST":
            response = requests.post(endpoint, headers=headers, json=json_data or {})
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
            
        response.raise_for_status()
        return response.json()
        
    except requests.exceptions.RequestException as e:
        print(f"Error calling {endpoint}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response status: {e.response.status_code}")
            print(f"Response body: {e.response.text}")
        return {}


def main():
    print("🚀 Starting authentication flow test...\n")
    
    # Step 1: Get access token
    print("🔑 Step 1: Getting access token...")
    token = get_access_token()
    print(f"✅ Successfully obtained access token: {token[:20]}...\n")
    
    # Step 2: Test protected endpoint
    print("🔒 Step 2: Testing protected endpoint...")
    reviews = test_protected_endpoint(token, REVIEWS_URL)
    print(f"✅ Successfully accessed protected endpoint")
    print(f"📊 Reviews count: {len(reviews) if isinstance(reviews, list) else 'N/A'}\n")
    
    # Step 3: Print token info (for debugging)
    print("🔍 Token information:")
    print(f"- Token length: {len(token)} characters")
    print(f"- Sample: {token[:20]}...{token[-20:]}")
    
    print("\n🎉 All tests completed successfully!")


if __name__ == "__main__":
    main()
