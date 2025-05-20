# Jarvis MVP API

A FastAPI-based API for the Jarvis MVP project, providing endpoints for order management and automated responses.

## Features

- **Order Management**: Fetch and manage orders from various sources
- **Automated Responses**: Generate context-aware responses to orders
- **Authentication**: JWT-based authentication for secure access
- **Documentation**: Interactive API documentation with Swagger UI and ReDoc
- **Health Monitoring**: Built-in health check endpoints

## Quick Start

### Prerequisites

- Python 3.8+
- pip
- Virtual environment (recommended)

### Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd jarvis-mvp
   ```

2. Set up the environment:
   ```powershell
   # On Windows
   .\setup.ps1
   ```
   
   Or manually:
   ```bash
   # Create and activate virtual environment
   python -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\Activate.ps1
   
   # Install dependencies
   pip install -r requirements.txt
   
   # Copy and configure environment variables
   cp .env.example .env
   # Edit .env with your configuration
   ```

### Running the API

```bash
# Development (with auto-reload)
uvicorn src.api:app --reload --port 8000

# Or use the provided script (Windows)
.\start_api.ps1
```

### Testing the API

1. Start the API server
2. Open a new terminal and run:
   ```bash
   # Windows
   .\test_api.ps1
   
   # Or manually test with curl
   curl http://localhost:8000/api/health
   ```

## Authentication

The API uses JWT (JSON Web Tokens) for authentication. Here's how to authenticate:

### 1. Get Access Token

```bash
curl -X POST http://localhost:8000/api/auth/token \
  -d "username=admin&password=admin&grant_type=password" \
  -H "Content-Type: application/x-www-form-urlencoded"
```

Response:
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "refresh_token": "eyJ..."
}
```

### 2. Using the Access Token

Include the token in the `Authorization` header for protected endpoints:
```
Authorization: Bearer <your_access_token>
```

### 3. Refresh Token

When the access token expires, use the refresh token to get a new one:

```bash
curl -X POST http://localhost:8000/api/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "your_refresh_token"}'
```

## API Documentation

Once the API is running, you can access the interactive documentation:

- **Swagger UI**: http://localhost:8000/api/docs
- **ReDoc**: http://localhost:8000/api/redoc
- **OpenAPI Schema**: http://localhost:8000/api/openapi.json

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | Database connection URL | `sqlite+aiosqlite:///./kwork_scraper.db` |
| `SECRET_KEY` | Secret key for JWT token generation | `your_secure_jwt_secret_key` |
| `JWT_ALGORITHM` | Algorithm for JWT | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token lifetime | `30` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token lifetime | `7` |
| `ALLOWED_HOSTS` | Comma-separated list of allowed hosts | `localhost,127.0.0.1` |

## Development

### Running Tests

```bash
pytest tests/
```

### Code Style

This project uses:
- **Black** for code formatting
- **isort** for import sorting
- **Flake8** for linting

Run the linters:
```bash
black .
isort .
flake8
```

## Deployment

For production deployment, it's recommended to use a production-grade ASGI server like Uvicorn with Gunicorn:

```bash
# Install production dependencies
pip install gunicorn uvicorn[standard]

# Run with Gunicorn
gunicorn src.api:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
