# 🚀 Jarvis MVP - Production Deployment

[![CI/CD](https://github.com/TerraTectra/jarvis-mvp-production/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/TerraTectra/jarvis-mvp-production/actions/workflows/ci-cd.yml)
[![Monitoring](https://img.shields.io/badge/monitor-grafana-FFA500)](http://localhost:3000)
[![Telegram](https://img.shields.io/badge/chat-telegram-0088cc)](https://t.me/your_telegram_channel)

## 🛠 CI/CD Pipeline

### Branch Strategy
- `main` - Production environment (protected)
- `develop` - Staging environment
- `feature/*` - Feature branches

### Workflow
1. Push to `develop` → Auto-deploy to staging
2. Create PR to `main` → Code review required
3. Merge to `main` → Manual approval for production deploy

### Monitoring
- **Prometheus**: Metrics collection
- **Grafana**: Dashboards and visualization
- **Telegram Alerts**: Instant notifications

## 🌟 Features

- **Полная автоматизация** - автоответчик, API и бот в одном процессе
- **Масштабируемость** - готово к работе на облачной платформе
- **Надежность** - автоматические перезапуски при сбоях
- **Безопасность** - защищенные переменные окружения

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

## ⚙️ Настройка окружения

Скопируйте `.env.template` в `.env` и настройте:

```env
# Основные настройки
DEBUG=False

# Telegram бот
TELEGRAM_TOKEN=your_telegram_bot_token
TELEGRAM_ADMIN_ID=6904521519

# Kwork
KEYWORDS=python,парсинг,автоматизация
POLL_INTERVAL=300

# Уведомления
NOTIFICATIONS_ENABLED=true
NOTIFY_NEW_ORDER=true
NOTIFY_REPLY_RESULT=true
NOTIFY_ERRORS=true
```

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

## 🚀 Quick Start

### Local Development

```bash
# Clone the repository
git clone https://github.com/TerraTectra/jarvis-mvp-production.git
cd jarvis-mvp-production

# Set up Python environment
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt

# Start the application
python run.py
```

### Monitoring Stack

```bash
# Start monitoring services
docker-compose -f docker-compose.monitoring.yml up -d

# Access dashboards:
# - Grafana: http://localhost:3000 (admin/admin)
# - Prometheus: http://localhost:9090
```

## 📚 Documentation

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
