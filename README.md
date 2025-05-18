# 🚀# 🚀 Jarvis MVP - Production Deployment

## 🌟 Особенности

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
