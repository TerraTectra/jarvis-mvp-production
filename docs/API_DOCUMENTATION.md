# API Documentation

## Table of Contents
- [Overview](#overview)
- [Authentication](#authentication)
- [Endpoints](#endpoints)
  - [Health Check](#health-check)
  - [Get Orders](#get-orders)
  - [Generate Reply](#generate-reply)
- [Error Handling](#error-handling)
- [Rate Limiting](#rate-limiting)
- [Examples](#examples)

## Overview

The API provides a set of endpoints to interact with the order management system, including fetching orders and generating automated responses.

## Authentication

Most endpoints require authentication using JWT (JSON Web Tokens).

### Authentication Flow

1. **Obtain Access Token**
   ```http
   POST /api/auth/token
   Content-Type: application/x-www-form-urlencoded
   
   username=user&password=pass&grant_type=password
   ```

2. **Using the Access Token**
   Include the token in the `Authorization` header for protected endpoints:
   ```
   Authorization: Bearer <your_access_token>
   ```

3. **Refresh Token (when access token expires)**
   ```http
   POST /api/auth/refresh
   Content-Type: application/json
   
   {
     "refresh_token": "your_refresh_token"
   }
   ```

### Token Details
- **Access Token**: Short-lived (default: 30 minutes)
- **Refresh Token**: Long-lived (default: 7 days)
- **Token Type**: Bearer

## Web UI Protection

The Web UI is protected by a token-based authentication system. Access to all Web UI pages (except the login page) requires a valid token.

### Access Flow

1. **Access Web UI**
   - Navigate to any Web UI page (e.g., `/`, `/form`)
   - You will be automatically redirected to the login page if not authenticated

2. **Login**
   - Submit the admin token on the login page
   - On successful authentication, you'll receive a session cookie
   - The cookie is valid for 1 hour

3. **Logout**
   - Access the `/logout` endpoint to invalidate the session

### Environment Variables

Set the following environment variable in your `.env` file:

```
UI_ADMIN_TOKEN=your_secure_token_here  # Token for accessing the web UI
```

### Security Notes
- The token is stored in an HTTP-only cookie
- The cookie has the `SameSite=Lax` attribute for CSRF protection
- Token should be rotated regularly in production
- All Web UI routes are protected by the authentication middleware

### Environment Variables
```
ACCESS_TOKEN_EXPIRE_MINUTES=30  # Access token lifetime in minutes
REFRESH_TOKEN_EXPIRE_DAYS=7      # Refresh token lifetime in days
SECRET_KEY=your-secret-key-here  # For JWT signing
ALGORITHM=HS256                 # JWT hashing algorithm
```

## Endpoints

### Health Check

```http
GET /api/health
```

**Response**
```json
{
  "status": "ok"
}
```

### Get Orders

```http
GET /orders?source=local&limit=10
```

**Parameters**
- `source` (optional): Source of orders (`kwork` or `local`)
- `limit` (optional, default=10): Maximum number of orders to return (max 50)

**Response**
```json
[
  {
    "id": "1",
    "title": "Need Python developer",
    "reply": "...",
    "source": "local",
    "url": "",
    "sent": false,
    "submission": null
  }
]
```

### Generate Reply

```http
POST /generate-reply
Content-Type: application/json

{
  "id": "order123",
  "title": "Need a Python developer for web scraping",
  "source": "local",
  "url": "https://example.com/order123",
  "send": false
}
```

**Request Body**
- `id`: Order ID (required)
- `title`: Order title (required)
- `source`: Source of the order (optional, default="local")
- `url`: URL of the order (optional)
- `send`: Whether to send the reply (optional, default=false)

**Response**
```json
{
  "id": "order123",
  "title": "Need a Python developer for web scraping",
  "reply": "...",
  "source": "local",
  "url": "https://example.com/order123",
  "sent": false,
  "submission": {
    "status": "not_sent",
    "message": "Sending was not requested (send=False)",
    "reason": null
  },
  "analysis": {
    "keywords": ["python", "developer", "web", "scraping"],
    "sentiment": "neutral"
  }
}
```

## Error Handling

### Error Responses

| Status Code | Error Code | Description |
|------------|------------|-------------|
| 400 | bad_request | Invalid request parameters |
| 401 | unauthorized | Authentication required |
| 403 | forbidden | Insufficient permissions |
| 404 | not_found | Resource not found |
| 422 | validation_error | Request validation failed |
| 429 | too_many_requests | Rate limit exceeded |
| 500 | server_error | Internal server error |

### Example Error Response
```json
{
  "detail": "Could not validate credentials",
  "status": 401,
  "error": "unauthorized"
}
```

## Rate Limiting

The API implements rate limiting to prevent abuse. By default, the limits are:
- 100 requests per minute per IP address
- 1000 requests per hour per user (when authenticated)

## Examples

### Python Example

```python
import requests
from datetime import datetime, timedelta

# Configuration
BASE_URL = "http://localhost:8000"
CREDENTIALS = {
    "username": "user",
    "password": "pass"
}

def get_auth_tokens():
    """Get new access and refresh tokens."""
    response = requests.post(
        f"{BASE_URL}/api/auth/token",
        data={"username": CREDENTIALS["username"], 
              "password": CREDENTIALS["password"],
              "grant_type": "password"},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    response.raise_for_status()
    return response.json()

def refresh_token(refresh_token: str):
    """Refresh access token using refresh token."""
    response = requests.post(
        f"{BASE_URL}/api/auth/refresh",
        json={"refresh_token": refresh_token}
    )
    response.raise_for_status()
    return response.json()

# Get initial tokens
tokens = get_auth_tokens()
access_token = tokens["access_token"]
refresh_token = tokens["refresh_token"]

# Example API call with token refresh
def make_authenticated_request():
    global access_token, refresh_token
    
    try:
        # Try to make request with current access token
        response = requests.get(
            f"{BASE_URL}/orders?source=local&limit=5",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        
        # If token expired, refresh and retry
        if response.status_code == 401:
            print("Token expired, refreshing...")
            new_tokens = refresh_token(refresh_token)
            access_token = new_tokens["access_token"]
            
            # Retry with new token
            response = requests.get(
                f"{BASE_URL}/orders?source=local&limit=5",
                headers={"Authorization": f"Bearer {access_token}"}
            )
        
        return response.json()
    except Exception as e:
        print(f"Request failed: {str(e)}")
        raise

# Example usage
print("Making authenticated request...")
data = make_authenticated_request()
print("Orders:", data)
```

### cURL Examples

#### 1. Get Access Token
```bash
# Get access and refresh tokens
curl -X POST http://localhost:8000/api/auth/token \
  -d "username=user&password=pass&grant_type=password" \
  -H "Content-Type: application/x-www-form-urlencoded"

# Expected response:
# {
#   "access_token": "eyJ...",
#   "token_type": "bearer",
#   "refresh_token": "eyJ..."
# }
```

#### 2. Refresh Access Token
```bash
# Refresh access token using refresh token
curl -X POST http://localhost:8000/api/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "your_refresh_token_here"}'

# Response includes new access_token and refresh_token
```

#### 3. Make Authenticated Requests
```bash
# Get orders with access token
ACCESS_TOKEN="your_access_token_here"
curl -X GET "http://localhost:8000/orders?limit=2" \
  -H "Authorization: Bearer $ACCESS_TOKEN"

# Generate reply
curl -X POST http://localhost:8000/generate-reply \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"id":"test123","title":"Need Python developer","send":false}'
```

#### 4. Error Handling Example
```bash
# Example of handling 401 Unauthorized
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer $EXPIRED_TOKEN" \
  http://localhost:8000/orders)

if [ "$RESPONSE" -eq 401 ]; then
    echo "Token expired, refreshing..."
    # Add refresh token logic here
fi
```
