# 🚀 Kwork Scraper - Automated Project Parser

A high-performance, async web scraper for Kwork.ru that extracts project data with browser automation and stores it in a database.

## 🌟 Features

- **CI/CD Integration**
  - Automated testing on every push to main/develop branches
  - Code coverage reporting
  - Automated deployment to staging
  - GitHub Actions workflow for Kwork integration tests

- **Monitoring & Alerts**
  - Real-time error tracking
  - Performance metrics
  - Telegram notifications for critical issues
  - Prometheus alerts for Kwork API status

- **Kwork Integration**: Automated monitoring and response to Kwork orders
  - Real-time order monitoring
  - Smart filtering by keywords, categories, and price
  - Automated responses with customizable templates
  - Telegram notifications for new orders
  - Blacklist to avoid duplicate responses

- **Async Browser Pool**: Concurrent scraping with configurable pool size
- **Robust Parsing**: Handles various page layouts and data formats
- **Database Integration**: SQLite storage with SQLAlchemy ORM
- **CLI Interface**: Easy-to-use command line tools
- **Telegram Notifications**: Daily reports and error alerts
- **Resumable Sessions**: Continue from where you left off
- **Headless Mode**: Works on servers without GUI

## 🛠 CI/CD Pipeline

### Kwork Integration Tests

Our CI pipeline automatically runs integration tests for Kwork functionality on every push to `main` or `develop` branches. The pipeline includes:

1. **Test Environment Setup**
   - PostgreSQL database
   - Python 3.10
   - All required dependencies

2. **Test Execution**
   ```bash
   python -m pytest tests/test_order_processing_simple.py -v --cov=src --cov-report=xml
   ```

3. **Code Coverage**
   - Minimum 80% code coverage required
   - Reports uploaded to Codecov

### Staging Deployment

1. **Environment**
   - Uses `staging.env` configuration
   - Separate PostgreSQL database
   - Real Kwork API (with test token)

2. **Deployment Steps**
   ```bash
   # Copy staging config
   cp staging.env .env
   
   # Install dependencies
   pip install -r requirements.txt
   
   # Run in staging mode
   python -m src.main
   ```

## 📊 Monitoring

### Alerting Rules

We use Prometheus for monitoring with the following alert rules:

1. **Kwork Processing Errors**
   - Triggered when any processing errors occur
   - Severity: Warning

2. **High Error Rate**
   - Triggered when error rate exceeds 10%
   - Severity: Critical

3. **Kwork API Status**
   - Monitors API availability
   - Severity: Critical

4. **No New Orders**
   - Triggered when no orders processed in 2 hours
   - Severity: Warning

### Telegram Notifications

- Real-time alerts for critical issues
- Daily summary reports
- Deployment notifications

## 🚀 Quick Start

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Initialize the database**
   ```bash
   python -m src.cli initdb --yes
   ```

3. **Run the scraper**
   ```bash
   python -m src.cli scrape --max-pages 5 --category web-programming --price-min 1000
   ```

## 🚀 Быстрый старт

### 1. Настройка окружения

```bash
# Клонируем репозиторий (если еще не сделали)
git clone https://github.com/yourusername/jarvis-mvp.git
cd jarvis-mvp

# Устанавливаем зависимости
pip install -r requirements.txt
pip install -r requirements-kwork.txt

# Запускаем интерактивную настройку
python run_jarvis.py setup

# Следуем инструкциям для настройки:
# 1. Укажите Kwork API токен
# 2. Настройте Telegram бота
# 3. Проверьте настройки
```

### 2. Запуск системы

```bash
# Запуск всех компонентов
python run_jarvis.py start

# Или вручную:
# python -m src.bot.telegram_bot &
# python scripts/manage_kwork.py start
```

### 3. Проверка работы

1. Проверьте статус в Telegram: `/status`
2. Просмотрите логи: `tail -f logs/jarvis.log`
3. Убедитесь, что приходят уведомления о новых заказах

## 🔧 Kwork Integration

### Настройка фильтров

```bash
# Интерактивная настройка фильтра
python scripts/setup_kwork_filter.py

# Или через CLI
python scripts/manage_kwork.py create-filter \
  --name "Web Development" \
  --keyword python --keyword django \
  --min-price 1000 --max-price 50000

# Список фильтров
python scripts/manage_kwork.py list-filters
```

### Ручное управление

```bash
# Запуск только Kwork Poller
python scripts/manage_kwork.py start --interval 300

# Тестирование соединения
python scripts/manage_kwork.py test-connection

# Интерактивная консоль
python scripts/kwork_console.py
```

Подробнее в [документации по Kwork интеграции](docs/kwork_integration.md).

## 🛠 Staging Deployment

### Prerequisites
- Python 3.8+
- PowerShell 7.0+ (для Windows)
- Учетные данные для доступа к staging окружению

### Deployment Steps

1. **Настройка окружения**
   ```bash
   # Скопируйте пример конфигурации
   cp .env.staging .env
   
   # Отредактируйте .env, указав актуальные настройки
   # ОБЯЗАТЕЛЬНО измените значения по умолчанию для SECRET_KEY и паролей!
   ```

2. **Запуск деплоя**
   ```powershell
   # Windows (PowerShell)
   .\scripts\deploy_staging.ps1
   
   # Linux/macOS
   # python -m tests.smoke_test
   ```

3. **Проверка работоспособности**
   После успешного деплоя откройте в браузере:
   - Web UI: http://localhost:8000/ci/ui
   - API Docs: http://localhost:8000/api/docs

4. **Остановка сервера**
   Нажмите любую клавишу в окне терминала, чтобы остановить сервер.

### Smoke Testing

Для ручного запуска smoke-тестов:
```bash
python -m tests.smoke_test
```

### Troubleshooting

1. **Ошибка порта**
   Если порт 8000 занят, измените `WEBHOOK_PORT` в `.env` файле.

2. **Проблемы с аутентификацией**
   - Проверьте правильность `CI_USERNAME` и `CI_PASSWORD`
   - Убедитесь, что пользователь имеет необходимые права доступа

3. **Логи**
   Логи сервера и тестов сохраняются в папке `logs/`

## 🔐 Authentication

The API uses JWT (JSON Web Tokens) for authentication. All protected endpoints require a valid JWT token in the `Authorization` header.

### Authentication Flow

1. **Obtain Access and Refresh Tokens**
   ```bash
   curl -X 'POST' \
     'http://localhost:8000/api/auth/token' \
     -H 'Content-Type: application/x-www-form-urlencoded' \
     -d 'username=admin&password=admin'
   ```

   Response:
   ```json
   {
     "access_token": "eyJhbGciOiJIUzI1NiIs...",
     "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
     "token_type": "bearer"
   }
   ```

2. **Use the Access Token**
   Include the token in the `Authorization` header:
   ```
   Authorization: Bearer <your_access_token>
   ```

3. **Refresh the Access Token** (when it expires)
   ```bash
   curl -X 'POST' \
     'http://localhost:8000/api/auth/refresh' \
     -H 'Content-Type: application/json' \
     -d '{"refresh_token": "your_refresh_token_here"}'
   ```

### Token Expiration

- **Access Token**: 30 minutes (configurable via `ACCESS_TOKEN_EXPIRE_MINUTES`)
- **Refresh Token**: 7 days (configurable via `REFRESH_TOKEN_EXPIRE_DAYS`)

### CI Authentication

The CI system includes built-in support for JWT authentication. To enable:

1. Set up a service account in your authentication system
2. Configure the following environment variables:
   ```
   AUTH_ENABLED=true
   AUTH_URL=http://your-api-url/api/auth
   API_BASE_URL=http://your-api-url/api
   CI_USERNAME=your_ci_username
   CI_PASSWORD=your_ci_password
   ```

3. The CI system will automatically handle token management and refresh

### Testing Authentication

A test script is available to verify authentication:

```bash
python -m ci.test_auth
```

### Security Best Practices

1. Always use HTTPS in production
2. Store tokens securely (never commit them to version control)
3. Use strong, unique passwords for service accounts
4. Regularly rotate your `SECRET_KEY` in production
5. Limit token lifetimes based on your security requirements
6. Use the principle of least privilege for API tokens

For more details, see the [Authentication Documentation](docs/AUTHENTICATION.md).

### Testing Authentication

To test the authentication flow, use the test script:

```bash
# Install test dependencies
pip install -r scripts/requirements-test.txt

# Run the test script
python scripts/test_auth.py
```

This will test:
1. Unauthenticated access (should fail)
2. Getting an access token
3. Accessing protected endpoints with the token

## 🚀 API Documentation

Once the server is running, you can access the interactive API documentation at:
- Swagger UI: http://localhost:8000/api/docs
- ReDoc: http://localhost:8000/api/redoc

## 📊 CLI Usage

### Scrape Projects
```bash
# Basic usage
python -m src.cli scrape --max-pages 10

# With filters
python -m src.cli scrape \
  --category web-programming \
  --category design \
  --price-min 1000 \
  --price-max 50000 \
  --max-pages 5 \
  --output projects.json

# Run in verbose mode
python -m src.cli -v scrape --max-pages 3
```

### List Projects
```bash
# Show recent projects
python -m src.cli list-projects

# Save to file
python -m src.cli list-projects --limit 20 --output latest_projects.json
```

### Database Management
```bash
# Initialize/Reset database (WARNING: Drops all data!)
python -m src.cli initdb

# Send daily report to Telegram
python -m src.cli send-report --chat-id YOUR_CHAT_ID --token YOUR_BOT_TOKEN
```

## 🚀 Развертывание на Railway

1. **Клонируйте репозиторий**
   ```bash
   git clone https://github.com/yourusername/jarvis-mvp-railway.git
   cd jarvis-mvp-railway
   ```

2. **Настройте Railway**
   - Перейдите в [Railway Dashboard](https://railway.app/dashboard)
   - Нажмите "New Project" → "Deploy from GitHub repo"
   - Выберите ваш репозиторий

3. **Настройте переменные окружения**
   - В разделе `Variables` добавьте все переменные из `.env.template`
   - Установите `DEBUG=False` для продакшена

4. **Деплой**
   - При пуше в ветку `main` автоматически запустится деплой
   - Или нажмите "Manual Trigger" для ручного деплоя

## ⚙️ Configuration

Copy `.env.example` to `.env` and configure:

```env
# Database
DATABASE_URL=sqlite+aiosqlite:///./kwork_scraper.db

# Telegram Bot (for reports)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# Scraper Settings
HEADLESS=true
BROWSER_POOL_SIZE=3
MAX_PAGES=10
REQUEST_DELAY=2.0  # seconds between requests
```

## 🏗️ Architecture

### Components

1. **Browser Pool**
   - Manages multiple Chrome instances
   - Handles connection pooling and timeouts
   - Configurable browser options

2. **Scraper**
   - Async page navigation and data extraction
   - Handles pagination and rate limiting
   - Robust error handling and retries

3. **Database**
   - SQLite with SQLAlchemy ORM
   - Models for projects, snapshots, and sessions
   - Async operations with aiosqlite

4. **CLI**
   - User-friendly command interface
   - Progress reporting and logging
   - Data export options

## 📈 Monitoring

### Logs
Logs are written to stderr with different levels:
- INFO: Progress and status updates
- WARNING: Non-critical issues
- ERROR: Critical errors that need attention

### Metrics
- Pages scraped
- Projects found
- New projects added
- Error rate

## 🤖 Telegram Integration

Configure Telegram bot token and chat ID to receive:
- Daily summary reports
- Error notifications
- System status updates

## 🛠 Development

### Setup
1. Install development dependencies:
   ```bash
   pip install -r requirements-dev.txt
   ```

2. Run tests:
   ```bash
   pytest tests/
   ```

3. Run with debug logging:
   ```bash
   LOG_LEVEL=DEBUG python -m src.cli scrape --max-pages 2
   ```

### Project Structure
```
src/
  ├── integrations/     # Scraper implementation
  │   ├── browser_pool.py
  │   ├── kwork_parser.py
  │   ├── kwork_price_parser.py
  │   └── pagination.py
  │
  ├── database/        # Database models and CRUD
  │   ├── kwork_models.py
  │   ├── kwork_crud.py
  │   └── session.py
  │
  └── cli.py          # Command line interface
```

## 📝 License

MIT License

---
<div align="center">
  <p>Developed for automation and data collection</p>
  <p>Kwork Scraper © 2024</p>
</div>

## 📱 Команды бота

- `/start` - Проверка работы бота
- `/status` - Статус системы
- `/orders [N]` - Последние N заказов
- `/logs [N]` - Последние N логов

## 🔍 Мониторинг

- **Логи**: Доступны в разделе `Logs` в Railway Dashboard
- **Метрики**: Мониторинг в реальном времени
- **Оповещения**: Настройте уведомления в Telegram

## 🔄 Автоматизация

- **GitHub Actions**: Автоматические тесты и деплой
- **Railway**: Автоматические обновления и перезапуски
- **Cron Jobs**: Планировщик задач встроен в приложение

## 📚 Документация

- [API Documentation](https://your-railway-url.railway.app/docs)
- [Telegram Bot Guide](https://core.telegram.org/bots/api)
- [Railway Docs](https://docs.railway.app/)

## 📝 Лицензия

MIT License

---
<div align="center">
  <p>Разработано для автоматизации рутины</p>
  <p>Jarvis MVP © 2024</p>
</div>
