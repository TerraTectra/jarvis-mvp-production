# Скрипт для запуска smoke-тестов Web UI

# Установка переменных окружения
$env:PYTHONPATH = "$PSScriptRoot/.."
$env:UI_ADMIN_TOKEN = "test_token"  # Тестовый токен для тестов

# Запуск тестов
Write-Host "Запуск smoke-тестов Web UI..." -ForegroundColor Cyan

# Проверяем, установлен ли pytest
$pytestInstalled = pip list | Select-String "pytest"
if (-not $pytestInstalled) {
    Write-Host "Установка pytest..." -ForegroundColor Yellow
    pip install pytest
}

# Запускаем тесты
$testResult = pytest -v "$PSScriptRoot/../tests/test_web_ui.py" | Out-String

# Выводим результаты
if ($LASTEXITCODE -eq 0) {
    Write-Host $testResult -ForegroundColor Green
    Write-Host "`n✅ Все smoke-тесты Web UI успешно пройдены" -ForegroundColor Green
} else {
    Write-Host $testResult -ForegroundColor Red
    Write-Host "`n❌ Обнаружены ошибки в smoke-тестах Web UI" -ForegroundColor Red
    exit 1
}
