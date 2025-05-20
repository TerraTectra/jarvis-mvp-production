# Authentication & Authorization

This document describes how to authenticate with the Code Review API.

## Overview

The API uses JWT (JSON Web Tokens) for authentication. All protected endpoints require a valid JWT token in the `Authorization` header.

## Getting Started

### 1. Obtain an Access Token

To get an access token, make a POST request to `/ci/api/auth/token` with your username and password:

```bash
curl -X 'POST' \
  'http://localhost:8000/ci/api/auth/token' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'grant_type=password&username=admin&password=admin'
```

Example response:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### 2. Use the Access Token

Include the access token in the `Authorization` header for all protected endpoints:

```
Authorization: Bearer <your_access_token>
```

Example with curl:

```bash
curl -X 'GET' \
  'http://localhost:8000/ci/api/review/list' \
  -H 'accept: application/json' \
  -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...'
```

## Refreshing Tokens

## Защита Telegram-бота

### Настройка доступа

1. Укажите ID администраторов в файле `.env`:
   ```
   TELEGRAM_ADMIN_ID=123456789,987654321  # ID администраторов через запятую
   ```

2. Перезапустите бота для применения изменений

### Защищенные команды

Все команды бота доступны только пользователям, чьи ID указаны в `TELEGRAM_ADMIN_ID`:

- `/start` - Показать приветственное сообщение
- `/status` - Показать статус системы
- `/orders` - Показать последние заказы
- `/logs` - Показать логи системы

### Принцип работы защиты

1. При получении команды бот проверяет ID отправителя
2. Если ID отправителя отсутствует в списке администраторов:
   - Пользователь получает сообщение "⛔ Доступ запрещен."
   - В логах фиксируется попытка доступа
3. Доступ к функционалу предоставляется только авторизованным пользователям

Access tokens have a short lifespan (default: 30 minutes). To get a new access token without requiring the user to log in again, use the refresh token.

### Refresh Token Endpoint

```bash
POST /api/auth/refresh
Content-Type: application/json

{
  "refresh_token": "your_refresh_token_here"
}
```

Example with curl:

```bash
curl -X 'POST' \
  'http://localhost:8000/api/auth/refresh' \
  -H 'Content-Type: application/json' \
  -d '{"refresh_token": "your_refresh_token_here"}'
```

Successful response:

```json
{
  "access_token": "new_access_token_here",
  "refresh_token": "new_refresh_token_here",
  "token_type": "bearer"
}
```

### Refresh Token Security

- Refresh tokens have a longer lifespan (default: 7 days)
- Each time you refresh, you get a new refresh token (refresh token rotation)
- The old refresh token becomes invalid after use
- Refresh tokens should be stored securely (e.g., HTTP-only cookies for web apps)

## Token Expiration and Renewal Flow

1. Client authenticates with username/password to get access_token and refresh_token
2. Access token is used until it expires (30 minutes by default)
3. When access token expires, client uses refresh token to get a new access token
4. The refresh token is also renewed with each refresh
5. If refresh token expires, user must log in again

## Available Scopes

- `admin`: Full access to all endpoints
- `review:read`: Read access to review data
- `review:write`: Write access to create/update reviews

## Token Expiration

Access tokens expire after 30 minutes by default. You'll need to obtain a new token after expiration.

## Example: Complete Authentication Flow

1. **Get an access token:**

```bash
# Get token
TOKEN=$(curl -s -X 'POST' \
  'http://localhost:8000/ci/api/auth/token' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'grant_type=password&username=admin&password=admin' | jq -r '.access_token')

echo "Token: $TOKEN"
```

2. **Use the token to access protected endpoints:**

```bash
# List recent reviews
curl -s -X 'GET' \
  'http://localhost:8000/ci/api/review/list' \
  -H 'accept: application/json' \
  -H "Authorization: Bearer $TOKEN" | jq .

# Trigger a new review
curl -X 'POST' \
  'http://localhost:8000/ci/api/review/trigger' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "repo_path": "/path/to/repo",
    "branch": "main",
    "notify": true
  }'
```

## Error Handling

### Invalid Token

```http
HTTP/1.1 401 Unauthorized
{
  "detail": "Could not validate credentials"
}
```

### Insufficient Permissions

```http
HTTP/1.1 403 Forbidden
{
  "detail": "Not enough permissions"
}
```

### Expired Token

```http
HTTP/1.1 401 Unauthorized
{
  "detail": "Token has expired"
}
```

## Security Considerations

- Always use HTTPS in production
- Store tokens securely and never commit them to version control
- Use appropriate token expiration times
- Implement proper user authentication and password policies
- Rotate secrets and keys periodically
