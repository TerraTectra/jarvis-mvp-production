# AI-Powered Code Review System

An automated code review system that integrates with your CI/CD pipeline to provide intelligent code analysis and feedback.

## Features

- **Automated Code Analysis**: Runs multiple static analysis tools (flake8, mypy, bandit) and custom AST analysis
- **Web Interface**: Dashboard to view and manage code reviews
- **RESTful API**: Full-featured API for integration with other tools
- **Database Storage**: Persistent storage for review results
- **Authentication**: JWT-based authentication with role-based access control
- **Telegram Notifications**: Get notified about review results

## Quick Start

### Prerequisites

- Python 3.8+
- SQLite (for development)

### Installation

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Initialize the database:
   ```bash
   python -m ci.init_db
   ```

3. Start the API server:
   ```bash
   uvicorn ci.review_api:app --reload
   ```

4. Access the web interface at `http://localhost:8000`

## API Documentation

Once the server is running, you can access the interactive API documentation at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Running Tests

```bash
pytest tests/
```

## Configuration

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

## Database Schema

The system uses SQLAlchemy ORM with the following main tables:

### review_tasks
- `id`: UUID primary key
- `repository_path`: Path to the repository
- `branch`: Git branch
- `commit_hash`: Git commit hash
- `status`: Review status (pending, in_progress, completed, failed)
- `created_at`: Timestamp when the review was created
- `started_at`: When the review started
- `completed_at`: When the review completed
- `metadata`: JSON field for additional data

### review_issues
- `id`: UUID primary key
- `task_id`: Foreign key to review_tasks
- `file_path`: Path to the file with the issue
- `line`: Line number
- `column`: Column number
- `message`: Issue description
- `severity`: Issue severity (info, warning, error, critical)
- `type`: Issue type (style, type, security, bug, performance)
- `tool`: Tool that found the issue
- `code`: Error code (e.g., E501)
- `context`: Additional context about the issue

### pipeline_contexts
- `id`: UUID primary key
- `review_task_id`: Foreign key to review_tasks
- `pipeline_name`: Name of the pipeline
- `trigger`: What triggered the pipeline
- `branch`: Git branch
- `commit_hash`: Git commit hash
- `commit_message`: Git commit message
- `environment`: Environment name (e.g., development, production)
- `variables`: JSON field for pipeline variables
- `artifacts`: JSON array of artifact paths

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## License

MIT
