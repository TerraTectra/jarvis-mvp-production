#!/bin/bash

# Set environment variables if needed
# export PATH=$PATH:/path/to/venv/bin

# Get the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR" || exit 1

# Activate virtual environment if exists
if [ -f "../venv/bin/activate" ]; then
    source ../venv/bin/activate
fi

# Run the analytics report generation
python3 -c "
import analytics
report = analytics.generate_daily_report()
print('Generated daily report:')
print(report)
"

# Send Telegram notification if configured
if [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -n "$TELEGRAM_CHAT_ID" ]; then
    python3 -c "
import os
import requests
import json
from datetime import datetime

# Generate report
import analytics
report = analytics.generate_daily_report()

# Format message
message = f"📊 *Ежедневный отчёт CI/CD*\n" \
         f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n" \
         f"🔹 Всего запусков: {report['total_runs']}" \
         f" (✅ {report['successful']} | ❌ {report['failed']})\n" \
         f"🔹 Успешность: {report['success_rate']:.1f}%\n" \
         f"🔹 Средняя длительность: {report['avg_duration_seconds']:.1f} сек\n\n"

# Add top errors if any
if report['top_errors']:
    message += "🔴 *Топ ошибок:*\n"
    for error, count in report['top_errors'].items():
        message += f"• {error}: {count}\n"

# Send to Telegram
url = f"https://api.telegram.org/bot{os.getenv('TELEGRAM_BOT_TOKEN')}/sendMessage"
params = {
    'chat_id': os.getenv('TELEGRAM_CHAT_ID'),
    'text': message,
    'parse_mode': 'Markdown'
}

response = requests.post(url, json=params)
if response.status_code != 200:
    print(f"Failed to send Telegram notification: {response.text}")
"
fi

echo "Daily cron job completed at $(date)" >> "$SCRIPT_DIR/cron.log"
