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

## 🗺️ Yandex Maps Moscow organization scraper

The project includes a Playwright-based scraper for collecting Moscow organizations from Yandex Maps:

```bash
python -m src.automation.yandex_maps_scraper --target-per-category 150
```

### Search categories

The scraper searches these category synonym groups and stores the source query with every record:

1. `Компьютерные клубы`, `Киберарена`
2. `Дизайн-студии интерьеров`, `Архитектурное бюро`
3. `Студии видеомонтажа`, `Видеопродакшн`

For each category it tries to collect up to 150 organizations. If fewer visible Moscow results are available, it saves all organizations it can load.

### Dependencies

Install Python dependencies and the Chromium browser used by Playwright:

```bash
pip install -r requirements.txt
playwright install chromium
```

### Output files

Progress is saved incrementally after every organization so interrupted runs can be resumed:

- JSON Lines progress: `data/yandex_maps_progress.jsonl`
- CSV checkpoint: `data/yandex_maps_progress.csv`
- Final deduplicated Excel export: `data/yandex_maps_moscow_organizations.xlsx`

The final export is deduplicated by stable Yandex Maps URL when available, then normalized phone number, then normalized organization name plus address.

### Useful command examples

Run with a visible browser so you can manually observe CAPTCHA or layout changes:

```bash
python -m src.automation.yandex_maps_scraper --no-headless --target-per-category 100
```

Use shorter test limits while validating selectors:

```bash
python -m src.automation.yandex_maps_scraper --target-per-category 5 --min-delay 2 --max-delay 3
```

Write outputs to custom paths:

```bash
python -m src.automation.yandex_maps_scraper \
  --progress-path data/custom_yandex_progress.jsonl \
  --csv-path data/custom_yandex_progress.csv \
  --excel-path data/custom_yandex_export.xlsx
```

### Anti-bot and data availability limitations

Yandex Maps may show CAPTCHA or other anti-bot challenges, throttle requests, change result-card selectors, or hide fields such as phone, website, rating, or reviews. The scraper detects likely CAPTCHA pages, no-result pages, repeated unchanged sidebar counts, navigation timeouts, and missing fields gracefully. When a CAPTCHA appears, stop the run, solve it manually in a visible browser if appropriate, then rerun; already collected organizations remain in `data/yandex_maps_progress.jsonl`.
