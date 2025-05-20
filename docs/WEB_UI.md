# Web UI Documentation

## Overview

The Web UI provides a user-friendly interface for interacting with the application. It's protected by token-based authentication to ensure secure access to all features.

## Features

- Secure token-based authentication
- User-friendly interface for order management
- Real-time feedback and responses
- Responsive design for all devices

## Setup

### Prerequisites

- Python 3.8+
- Dependencies from `requirements.txt`
- Environment variables set in `.env`

### Environment Variables

Add these to your `.env` file:

```
# Web UI Configuration
UI_ADMIN_TOKEN=your_secure_token_here  # Token for accessing the web UI
```

### Running the Application

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set up environment variables in `.env`

3. Run the application:
   ```bash
   uvicorn src.main:app --reload
   ```

4. Access the Web UI at `http://localhost:8000`

## Authentication

### Login

1. Navigate to `http://localhost:8000`
2. You'll be redirected to the login page
3. Enter the admin token from your `.env` file
4. You'll be redirected to the main interface on successful login

### Logout

- Click the logout button or navigate to `/logout`
- This will clear your session and require re-authentication

## API Endpoints

### Web UI Routes

- `GET /` - Main interface
- `GET /login` - Login page
- `POST /login` - Process login
- `GET /logout` - Logout and clear session
- `GET /form` - Order form
- `POST /form` - Process order form

## Security

### Token Management

- Tokens should be strong and kept confidential
- Rotate tokens regularly in production
- Never commit tokens to version control

### Session Security

- Sessions use HTTP-only cookies
- CSRF protection with SameSite=Lax
- 1-hour session timeout
- Automatic redirection to login for unauthenticated users

## Testing

Run the test suite to verify Web UI functionality:

```bash
# Run all tests
pytest tests/

# Run Web UI tests specifically
pytest tests/test_web_ui.py -v

# Or use the test script
./scripts/test_web_ui.ps1
```

## Troubleshooting

### Common Issues

1. **Login Fails**
   - Verify `UI_ADMIN_TOKEN` in `.env` matches the token you're using
   - Check server logs for authentication errors

2. **Session Expires Quickly**
   - Default session timeout is 1 hour
   - Ensure your system time is synchronized

3. **CORS Errors**
   - Verify `ALLOWED_HOSTS` in `.env` includes your domain
   - Check browser console for specific error messages

## Best Practices

1. **Development**
   - Use different tokens for development and production
   - Never commit `.env` to version control
   - Use environment-specific configuration files

2. **Production**
   - Enable HTTPS
   - Set `DEBUG=False` in production
   - Implement rate limiting
   - Monitor authentication logs

## Support

For assistance, please contact your system administrator or open an issue in the project repository.
