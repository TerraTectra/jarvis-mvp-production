# Скрипт для полной проверки Web UI

# Установка переменных окружения
$env:PYTHONPATH = "$PSScriptRoot/.."

# 1. Запускаем smoke-тесты
Write-Host "🚀 Запуск smoke-тестов Web UI..." -ForegroundColor Cyan
$testOutput = & "$PSScriptRoot/test_web_ui.ps1" 2>&1 | Out-String

# 2. Отправляем отчет в Telegram, если указаны учетные данные
if ($env:TELEGRAM_BOT_TOKEN -and $env:TELEGRAM_CHAT_ID) {
    Write-Host "\n📤 Отправка отчета в Telegram..." -ForegroundColor Cyan
    & "$PSScriptRoot/send_telegram_report.ps1" -TestResult $testOutput
}

# 3. Выводим результаты
if ($LASTEXITCODE -eq 0) {
    Write-Host "\n✅ Проверка Web UI успешно завершена" -ForegroundColor Green
    exit 0
} else {
    Write-Host "\n❌ Проверка Web UI завершилась с ошибками" -ForegroundColor Red
    exit 1
}
