# Скрипт для деплоя в staging окружение
# Требует PowerShell 7.0+

# Обработка ошибок
$ErrorActionPreference = "Stop"

# Функция для остановки сервера при завершении
function Stop-Deployment {
    param()
    
    # Проверяем, существует ли файл с PID процесса сервера
    $pidFile = Join-Path $PSScriptRoot "..\staging_server.pid"
    if (Test-Path $pidFile) {
        $processId = Get-Content -Path $pidFile -Raw -ErrorAction SilentlyContinue
        if ($processId) {
            try {
                Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
                Write-Log "Остановлен процесс сервера с ID $processId" -Level "INFO"
            } catch {
                Write-Log "Не удалось остановить процесс сервера: $_" -Level "WARNING"
            }
        }
        Remove-Item -Path $pidFile -Force -ErrorAction SilentlyContinue
    }
}

# Проверка версии PowerShell
if ($PSVersionTable.PSVersion.Major -lt 7) {
    Write-Error "Требуется PowerShell 7.0 или выше. Текущая версия: $($PSVersionTable.PSVersion)"
    exit 1
}

# Вывод информации о запуске
Write-Host "🚀 Запуск деплоя в staging окружение" -ForegroundColor Cyan
Write-Host "Текущая директория: $PWD"
Write-Host "Дата и время: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"

# Проверка наличия Python
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Error "Python не найден. Убедитесь, что Python установлен и добавлен в PATH"
    exit 1
}
Write-Host "Используется $pythonVersion"

# Пути
$projectRoot = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $projectRoot ".env"
$backupDir = Join-Path $projectRoot "backups"
$logDir = Join-Path $projectRoot "logs"
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logFile = Join-Path $logDir "deploy_${timestamp}.log"

# Создаем необходимые директории
foreach ($dir in @($backupDir, $logDir)) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "Создана директория: $dir" -ForegroundColor Green
    }
}

# Функция для логирования
function Write-Log {
    param([string]$message, [string]$level = "INFO")
    
    $levelMap = @{
        "INFO"    = "INFO"
        "WARNING" = "WARN"
        "ERROR"   = "ERROR"
        "SUCCESS" = "SUCCESS"
    }
    
    $level = $levelMap[$level] ?? "INFO"
    $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    $logMessage = "[$timestamp] [$level] $message"
    
    # Цветной вывод в консоль
    $colorMap = @{
        "INFO"    = "White"
        "WARN"    = "Yellow"
        "ERROR"   = "Red"
        "SUCCESS" = "Green"
    }
    
    $color = $colorMap[$level] ?? "White"
    Write-Host $logMessage -ForegroundColor $color
    
    # Запись в лог-файл
    try {
        Add-Content -Path $logFile -Value $logMessage -ErrorAction Stop
    } catch {
        Write-Host "Ошибка при записи в лог-файл: $_" -ForegroundColor Red
    }
}

# Проверка зависимостей
function Test-Dependencies {
    Write-Log "Проверка зависимостей..."
    
    # Проверка наличия Python-пакетов
    $requiredPackages = @(
        "uvicorn",
        "fastapi",
        "sqlalchemy",
        "python-jose"
    )
    
    foreach ($pkg in $requiredPackages) {
        $installed = python -c "import pkg_resources; print('$pkg' in [pkg.key for pkg in pkg_resources.working_set])" 2>$null
        if ($installed -ne "True") {
            Write-Log "Установка отсутствующего пакета: $pkg" -Level "WARNING"
            python -m pip install $pkg
        }
    }
}
}

try {
    # Регистрируем обработчик завершения
    $null = Register-EngineEvent -SourceIdentifier "PowerShell.Exiting" -Action {
        Stop-Deployment
    }

    Write-Log "🚀 Начало деплоя в staging окружение"
    
    # 1. Проверка наличия файла .env
    if (-not (Test-Path $envFile)) {
        throw "Файл конфигурации .env не найден в корне проекта. Создайте его на основе .env.example"
    }
    
    # 2. Загрузка переменных окружения
    Write-Log "Загрузка переменных окружения из $envFile"
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^\s*#|^\s*$') { return }
        $name, $value = $_.split('=', 2)
        if ($name) {
            $value = $value.Trim() -replace '^["\'']|["\'']$', ''
            [System.Environment]::SetEnvironmentVariable($name, $value, 'Process')
            Write-Log "Установлена переменная: $name" -Level "DEBUG"
        }
    }
    
    # 3. Создание бэкапа текущей базы данных
    $dbFile = Join-Path $projectRoot "kwork_scraper_staging.db"
    if (Test-Path $dbFile) {
        $backupFile = Join-Path $backupDir "kwork_scraper_staging_${timestamp}.db"
        try {
            Copy-Item -Path $dbFile -Destination $backupFile -Force -ErrorAction Stop
            Write-Log "✅ Создан бэкап базы данных: $backupFile" -Level "SUCCESS"
        } catch {
            Write-Log "⚠️ Не удалось создать бэкап базы данных: $_" -Level "WARNING"
        }
    } else {
        Write-Log "Файл базы данных не найден, будет создан новый" -Level "INFO"
    }
    
    # 4. Установка зависимостей
    Write-Log "Установка/обновление зависимостей Python..."
    try {
        python -m pip install --upgrade pip
        pip install -r (Join-Path $projectRoot "requirements.txt")
        Test-Dependencies
    } catch {
        throw "Ошибка при установке зависимостей: $_"
    }
    
    # 5. Запуск миграций (если используются)
    if (Test-Path (Join-Path $projectRoot "alembic.ini")) {
        Write-Log "Применение миграций базы данных..."
        try {
            Set-Location $projectRoot
            python -m alembic upgrade head
            Write-Log "✅ Миграции успешно применены" -Level "SUCCESS"
        } catch {
            Write-Log "⚠️ Ошибка при применении миграций: $_" -Level "WARNING"
        }
    }
    
    # 6. Запуск сервера
    $serverPort = [System.Environment]::GetEnvironmentVariable("PORT", "Process") ?? 8000
    $serverHost = [System.Environment]::GetEnvironmentVariable("HOST", "Process") ?? "0.0.0.0"
    
    Write-Log "Запуск сервера на $($serverHost):$serverPort..."
    
    $serverProcess = Start-Process -FilePath "python" `
        -ArgumentList "-m uvicorn src.api:app --host $serverHost --port $serverPort --reload" `
        -WorkingDirectory $projectRoot `
        -PassThru `
        -NoNewWindow `
        -RedirectStandardOutput (Join-Path $logDir "server_stdout_${timestamp}.log") `
        -RedirectStandardError (Join-Path $logDir "server_stderr_${timestamp}.log")
    
    # Сохраняем ID процесса для последующей остановки
    $script:processId = $serverProcess.Id
    $script:processId | Out-File -FilePath (Join-Path $projectRoot "staging_server.pid") -Force
    Write-Log "Сервер запущен с PID: $($script:processId)"
    
    # Даем серверу время на запуск
    $maxRetries = 10
    $retryDelay = 3 # секунды
    $serverReady = $false
    $healthCheckUrl = "http://$($serverHost):$serverPort/api/health"
    
    Write-Log "Ожидание запуска сервера (макс. $($maxRetries * $retryDelay) сек)..."
    
    for ($i = 0; $i -lt $maxRetries; $i++) {
        try {
            $response = Invoke-WebRequest -Uri $healthCheckUrl -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
            if ($response.StatusCode -eq 200) {
                $serverReady = $true
                Write-Log "✅ Сервер успешно запущен и доступен по адресу $healthCheckUrl" -Level "SUCCESS"
                break
            }
        } catch {
            Write-Log "Попытка $($i+1)/$maxRetries: сервер ещё не готов, повторная попытка через $retryDelay сек..." -Level "INFO"
            Start-Sleep -Seconds $retryDelay
        }
    }
    
    if (-not $serverReady) {
        throw "Не удалось подключиться к серверу по адресу $healthCheckUrl после $maxRetries попыток"
    }
    
    # 7. Запуск smoke-тестов
    Write-Log "Запуск smoke-тестов..."
    $testResult = $false
    
    try {
        $testProcess = Start-Process -FilePath "python" `
            -ArgumentList "-m tests.smoke_test" `
            -WorkingDirectory $projectRoot `
            -NoNewWindow `
            -Wait `
            -PassThru `
            -RedirectStandardOutput (Join-Path $logDir "smoke_test_stdout_${timestamp}.log") `
            -RedirectStandardError (Join-Path $logDir "smoke_test_stderr_${timestamp}.log")
        
        if ($testProcess.ExitCode -eq 0) {
            Write-Log "✅ Smoke-тесты успешно пройдены" -Level "SUCCESS"
            $testResult = $true
        } else {
            $errorContent = Get-Content -Path (Join-Path $logDir "smoke_test_stderr_${timestamp}.log") -Raw -ErrorAction SilentlyContinue
            throw "Smoke-тесты не пройдены. Код выхода: $($testProcess.ExitCode). Ошибка: $errorContent"
        }
    } catch {
        throw "Ошибка при выполнении smoke-тестов: $_"
    }
    
    # 8. Проверка доступа к Web UI
    $uiUrl = "http://$($serverHost):$serverPort/ci/ui"
    $apiDocsUrl = "http://$($serverHost):$serverPort/api/docs"
    
    Write-Log ""
    Write-Log "=" * 60
    Write-Log "🚀 Деплой успешно завершен!" -Level "SUCCESS"
    Write-Log "Сервер доступен по следующим адресам:"
    Write-Log "- Web UI: $uiUrl"
    Write-Log "- API Docs: $apiDocsUrl"
    Write-Log "- Журналы: $logDir"
    Write-Log "=" * 60
    
    # Открываем Web UI в браузере по умолчанию
    try {
        Start-Process $uiUrl
    } catch {
        Write-Log "Не удалось открыть Web UI автоматически: $_" -Level "WARNING"
    }
    
    # Ожидание нажатия клавиши для завершения
    Write-Host "`nНажмите любую клавишу для остановки сервера..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    
} catch {
    Write-Log "❌ Ошибка при деплое: $_" -Level "ERROR"
    
    # Пытаемся записать стек вызовов в лог
    $errorMessage = $_.Exception.Message
    $stackTrace = $_.ScriptStackTrace -replace "`n", "`n    "
    Write-Log "Стек вызовов:`n    $stackTrace" -Level "ERROR"
    
    exit 1
} finally {
    # Останавливаем сервер при завершении
    Stop-Deployment
}
