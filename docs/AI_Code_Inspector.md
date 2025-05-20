# AI Code Inspector

An automated code review system that integrates with your CI/CD pipeline to provide intelligent code analysis and feedback.

## Features

- **Automated Code Review**: Runs multiple static analysis tools (flake8, mypy, bandit) and custom AST analysis
- **Integration with CI/CD**: Easy to integrate with any CI/CD pipeline
- **Web Interface**: Dashboard to view and manage code reviews
- **API-First**: All functionality available via REST API
- **Security**: JWT-based authentication and role-based access control
- **Extensible**: Plugin architecture for adding new analyzers

## Getting Started

### Prerequisites

- Python 3.8+
- pip
- SQLite (for development)

### Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd <repository-name>
   ```

2. Create a virtual environment and activate it:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: .\\venv\\Scripts\\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Initialize the database:
   ```bash
   python -m ci.init_db
   ```

### Configuration

Copy `.env.example` to `.env` and update the values:

```env
# Application
ENV=development
SECRET_KEY=your-secret-key
DATABASE_URL=sqlite:///reviews.db

# JWT Authentication
JWT_SECRET_KEY=your-jwt-secret
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30

# Telegram Notifications (optional)
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
TELEGRAM_CHAT_ID=your-chat-id
```

## API Reference

### Authentication

Most endpoints require authentication. Include the JWT token in the `Authorization` header:

```
Authorization: Bearer <token>
```

To get a token:

```bash
curl -X POST "http://localhost:8000/api/auth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=admin"
```

### Endpoints

#### Code Reviews

- `POST /api/reviews/` - Create a new code review
- `GET /api/reviews/` - List all code reviews
- `GET /api/reviews/{review_id}` - Get a specific code review
- `GET /api/reviews/{review_id}/report` - Get the full review report
- `POST /api/reviews/{review_id}/notify` - Send notification about review

Example: Create a new code review

```bash
curl -X POST "http://localhost:8000/api/reviews/" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"repository_path": "/path/to/repo", "branch": "main"}'
```

## CLI Usage

Run a code review from the command line:

```bash
python -m ci.review_engine --path ./src --output report.json
```

Options:
- `--path`: Path to the code to review (required)
- `--output`: Output file for the report (default: review_report.json)
- `--format`: Output format (json, html, text)
- `--exclude`: Comma-separated list of paths to exclude

## CI/CD Integration

### GitHub Actions

```yaml
name: Code Review

on: [push, pull_request]

jobs:
  code-review:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
    
    - name: Run code review
      run: |
        python -m ci.review_engine --path . --output review.json
        # Upload report as artifact
        echo "REVIEW_REPORT=$(cat review.json | jq -c '.')" >> $GITHUB_ENV
    
    - name: Upload review report
      uses: actions/upload-artifact@v2
      with:
        name: code-review-report
        path: review.json
```

## Report Structure

```json
{
  "id": "uuid",
  "status": "completed",
  "repository_path": "/path/to/repo",
  "branch": "main",
  "commit_hash": "abc123",
  "started_at": "2023-01-01T00:00:00Z",
  "completed_at": "2023-01-01T00:01:00Z",
  "summary": {
    "total_issues": 5,
    "by_severity": {
      "error": 2,
      "warning": 3,
      "info": 0
    },
    "by_type": {
      "style": 3,
      "type": 1,
      "security": 1
    }
  },
  "issues": [
    {
      "id": "issue-1",
      "file_path": "src/main.py",
      "line": 10,
      "column": 5,
      "message": "Line too long (120 > 79 characters)",
      "severity": "warning",
      "type": "style",
      "tool": "flake8",
      "code": "E501",
      "context": {
        "snippet": "print('This is a very long line that exceeds the maximum allowed line length')"
      }
    }
  ]
}
```

## Telegram Notifications

To receive notifications in Telegram:

1. Create a bot using [@BotFather](https://t.me/botfather)
2. Get your chat ID using `@userinfobot`
3. Set the `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` environment variables

Example notification:

```
🔍 *Code Review Completed*: `main` @ `abc123`

📊 *Issues Found*: 5
  • ⚠️ Warnings: 3
  • ❌ Errors: 2
  • ℹ️  Info: 0

🔗 [View Full Report](http://ci.example.com/reviews/123)
```

## Development

### Running Tests

```bash
pytest tests/
```

### Adding a New Analyzer

1. Create a new file in `ci/analyzers/`
2. Implement the `analyze` function
3. Register the analyzer in `ci/review_engine.py`

### Code Style

- Follow PEP 8
- Use type hints
- Write docstrings for all public functions and classes
- Keep functions small and focused

## License

[MIT](LICENSE)
