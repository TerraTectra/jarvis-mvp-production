# Скрипт для отправки отчета о тестах в Telegram

param (
    [string]$TestResult,
    [string]$ChatId = $env:TELEGRAM_CHAT_ID,
    [string]$BotToken = $env:TELEGRAM_BOT_TOKEN
)

# Проверяем наличие обязательных параметров
if (-not $ChatId -or -not $BotToken) {
    Write-Error "Необходимо указать TELEGRAM_CHAT_ID и TELEGRAM_BOT_TOKEN"
    exit 1
}

# Формируем сообщение
$message = "🔄 *Отчет о тестировании Web UI* 🚀
"
$message += "\n📋 *Результаты тестов:*\n"

# Анализируем результаты тестов
if ($LASTEXITCODE -eq 0) {
    $message += "✅ Все тесты успешно пройдены!"
} else {
    $message += "❌ Обнаружены ошибки в тестах!"
}

# Добавляем дополнительную информацию, если есть
if ($TestResult) {
    $message += "\n\n📊 Детали тестов:\n"
    $message += $TestResult
}

# Отправляем сообщение в Telegram
$url = "https://api.telegram.org/bot$BotToken/sendMessage"
$body = @{
    chat_id = $ChatId
    text = $message
    parse_mode = "Markdown"
    disable_web_page_preview = $true
}

try {
    $response = Invoke-RestMethod -Uri $url -Method Post -Body $body -ContentType "application/json"
    if ($response.ok) {
        Write-Host "✅ Отчет успешно отправлен в Telegram" -ForegroundColor Green
    } else {
        Write-Error "❌ Ошибка при отправке отчета в Telegram: $($response.description)"
        exit 1
    }
} catch {
    Write-Error "❌ Ошибка при отправке отчета в Telegram: $_"
    exit 1
}
