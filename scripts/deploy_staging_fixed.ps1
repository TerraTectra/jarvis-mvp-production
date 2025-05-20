# Скрипт для деплоя в staging окружение
# Требует PowerShell 7.0+

# Обработка ошибок
$ErrorActionPreference = "Stop"

# Функция для логирования
function Write-Log {
    param(
        [string]$Message,
        [ValidateSet('DEBUG', 'INFO', 'WARNING', 'ERROR', 'SUCCESS')]
        [string]$Level = 'INFO'
    )
    
    $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    $logMessage = "[$timestamp] [$Level] $Message"
    
    # Цветной вывод в консоль
    $colorMap = @{
        'DEBUG'   = 'Gray'
        'INFO'    = 'White'
        'WARNING' = 'DarkYellow'
        'ERROR'   = 'Red'
        'SUCCESS' = 'Green'
    }
    
    $color = if ($colorMap.ContainsKey($Level)) { $colorMap[$Level] } else { 'White' }
    Write-Host $logMessage -ForegroundColor $color
    
    # Запись в лог-файл
    try {
        Add-Content -Path $script:logFile -Value $logMessage -ErrorAction Stop
    } catch {
        Write-Host "Ошибка при записи в лог-файл: $_" -ForegroundColor Red
    }
}

# Функция для остановки сервера
function Stop-Deployment {
    $pidFile = Join-Path $script:projectRoot "staging_server.pid"
    if (Test-Path $pidFile) {
        $processId = Get-Content -Path $pidFile -ErrorAction SilentlyContinue
        if ($processId) {
            try {
                Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
                Write-Log "Остановлен процесс сервера с ID $processId" -Level 'INFO'
            } catch {
                Write-Log "Не удалось остановить процесс сервера: $_" -Level 'WARNING'
            }
        }
        Remove-Item -Path $pidFile -Force -ErrorAction SilentlyContinue
    }
}

# Функция для проверки зависимостей
function Test-Dependencies {
    Write-Log "Проверка зависимостей..." -Level 'INFO'
    
    $requiredPackages = @(
        "uvicorn",
        "fastapi",
        "sqlalchemy",
        "python-jose"
    )
    
    foreach ($pkg in $requiredPackages) {
        $installed = python -c "import pkg_resources; print('$pkg' in [pkg.key for pkg in pkg_resources.working_set])" 2>$null
        if ($installed -ne "True") {
            Write-Log "Установка отсутствующего пакета: $pkg" -Level 'WARNING'
            python -m pip install $pkg
        }
    }
}

# Основной код
function Start-Deployment {
    try {
        # Инициализация путей
        $script:projectRoot = Split-Path -Parent $PSScriptRoot
        $envFile = Join-Path $script:projectRoot ".env"
        $backupDir = Join-Path $script:projectRoot "backups"
        $logDir = Join-Path $script:projectRoot "logs"
        $script:logFile = Join-Path $logDir ("deploy_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".log")
        
        # Создаем необходимые директории
        foreach ($dir in @($backupDir, $logDir)) {
            if (-not (Test-Path $dir)) {
                New-Item -ItemType Directory -Path $dir -Force | Out-Null
                Write-Host "Создана директория: $dir" -ForegroundColor Green
            }
        }
        
        Write-Log "🚀 Начало деплоя в staging окружение" -Level 'INFO'
        
        # 1. Проверка наличия файла .env
        if (-not (Test-Path $envFile)) {
            throw "Файл конфигурации .env не найден в корне проекта. Создайте его на основе .env.example"
        }
        
        # 2. Загрузка переменных окружения
        Write-Log "Загрузка переменных окружения из $envFile" -Level 'INFO'
        Get-Content $envFile | ForEach-Object {
            if ($_ -match '^\s*#|^\s*$') { return }
            $name, $value = $_.split('=', 2)
            if ($name) {
                $value = $value.Trim() -replace '^["\'']|["\'']$', ''
                [System.Environment]::SetEnvironmentVariable($name, $value, 'Process')
                Write-Log "Установлена переменная: $name" -Level 'DEBUG'
            }
        }
        
        # 3. Создание бэкапа базы данных
        $dbFile = Join-Path $script:projectRoot "kwork_scraper_staging.db"
        if (Test-Path $dbFile) {
            $backupFile = Join-Path $backupDir ("kwork_scraper_staging_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".db")
            try {
                Copy-Item -Path $dbFile -Destination $backupFile -Force -ErrorAction Stop
                Write-Log "✅ Создан бэкап базы данных: $backupFile" -Level 'SUCCESS'
            } catch {
                Write-Log "⚠️ Не удалось создать бэкап базы данных: $_" -Level 'WARNING'
            }
        } else {
            Write-Log "Файл базы данных не найден, будет создан новый" -Level 'INFO'
        }
        
        # 4. Установка зависимостей
        Write-Log "Установка/обновление зависимостей Python..." -Level 'INFO'
        try {
            python -m pip install --upgrade pip
            pip install -r (Join-Path $script:projectRoot "requirements.txt")
            Test-Dependencies
        } catch {
            throw "Ошибка при установке зависимостей: $_"
        }
        
        # 5. Запуск миграций
        if (Test-Path (Join-Path $script:projectRoot "alembic.ini")) {
            Write-Log "Применение миграций базы данных..." -Level 'INFO'
            try {
                Set-Location $script:projectRoot
                python -m alembic upgrade head
                Write-Log "✅ Миграции успешно применены" -Level 'SUCCESS'
            } catch {
                Write-Log "⚠️ Ошибка при применении миграций: $_" -Level 'WARNING'
            }
        }
        
        # 6. Запуск сервера
        $serverPort = [System.Environment]::GetEnvironmentVariable("PORT", "Process") ?? 8000
        $serverHost = [System.Environment]::GetEnvironmentVariable("HOST", "Process") ?? "0.0.0.0"
        
        Write-Log "Запуск сервера на ${serverHost}:${serverPort}..." -Level 'INFO'
        
        $serverProcess = Start-Process -FilePath "python" `
            -ArgumentList "-m uvicorn src.api:app --host ${serverHost} --port ${serverPort} --reload" `
            -WorkingDirectory $script:projectRoot `
            -PassThru `
            -NoNewWindow `
            -RedirectStandardOutput (Join-Path $logDir ("server_stdout_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".log")) `
            -RedirectStandardError (Join-Path $logDir ("server_stderr_" + (Get-Date -Format "yyyyMMdd_HHmmss") + ".log"))
        
        # Сохраняем ID процесса для последующей остановки
        $script:processId = $serverProcess.Id
        $script:processId | Out-File -FilePath (Join-Path $script:projectRoot "staging_server.pid") -Force
        Write-Log "Сервер запущен с PID: $($script:processId)" -Level 'INFO'
        
        # 7. Проверка доступности сервера
        $maxRetries = 10
        $retryDelay = 3
        $serverReady = $false
        $healthCheckUrl = "http://${serverHost}:${serverPort}/api/health"
        
        Write-Log "Ожидание запуска сервера (макс. $($maxRetries * $retryDelay) сек)..." -Level 'INFO'
        
        for ($i = 0; $i -lt $maxRetries; $i++) {
            try {
                $response = Invoke-WebRequest -Uri $healthCheckUrl -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
                if ($response.StatusCode -eq 200) {
                    $serverReady = $true
                    Write-Log "✅ Сервер успешно запущен и доступен по адресу $healthCheckUrl" -Level 'SUCCESS'
                    break
                }
            } catch {
                $attempt = $i + 1
                Write-Log "Попытка ${attempt}/${maxRetries}: сервер ещё не готов, повторная попытка через ${retryDelay} сек..." -Level 'INFO'
                Start-Sleep -Seconds $retryDelay
            }
        }
        
        if (-not $serverReady) {
            throw "Не удалось подключиться к серверу по адресу $healthCheckUrl после $maxRetries попыток"
        }
        
        # 8. Запуск smoke-тестов
        Write-Log "Запуск smoke-тестов..." -Level 'INFO'
        $testResult = $false
        $testTimestamp = Get-Date -Format "yyyyMMdd_HHmmss"
        
        try {
            $testProcess = Start-Process -FilePath "python" `
                -ArgumentList "-m tests.smoke_test" `
                -WorkingDirectory $script:projectRoot `
                -NoNewWindow `
                -Wait `
                -PassThru `
                -RedirectStandardOutput (Join-Path $logDir "smoke_test_stdout_${testTimestamp}.log") `
                -RedirectStandardError (Join-Path $logDir "smoke_test_stderr_${testTimestamp}.log")
            
            if ($testProcess.ExitCode -eq 0) {
                Write-Log "✅ Smoke-тесты успешно пройдены" -Level 'SUCCESS'
                $testResult = $true
            } else {
                $errorContent = Get-Content -Path (Join-Path $logDir "smoke_test_stderr_${testTimestamp}.log") -Raw -ErrorAction SilentlyContinue
                throw "Smoke-тесты не пройдены. Код выхода: $($testProcess.ExitCode). Ошибка: $errorContent"
            }
        } catch {
            throw "Ошибка при выполнении smoke-тестов: $_"
        }
        
        # 9. Отображение информации о развертывании
        $uiUrl = "http://${serverHost}:${serverPort}/ci/ui"
        $apiDocsUrl = "http://${serverHost}:${serverPort}/api/docs"
        
        Write-Log "" -Level 'INFO'
        Write-Log ("=" * 60) -Level 'INFO'
        Write-Log "🚀 Деплой успешно завершен!" -Level 'SUCCESS'
        Write-Log "Сервер доступен по следующим адресам:" -Level 'INFO'
        Write-Log "- Web UI: $uiUrl" -Level 'INFO'
        Write-Log "- API Docs: $apiDocsUrl" -Level 'INFO'
        Write-Log "- Журналы: $logDir" -Level 'INFO'
        Write-Log ("=" * 60) -Level 'INFO'
        
        # Открываем Web UI в браузере по умолчанию
        try {
            Start-Process $uiUrl
        } catch {
            Write-Log "Не удалось открыть Web UI автоматически: $_" -Level 'WARNING'
        }
        
        # Ожидание нажатия клавиши для завершения
        Write-Host "`nНажмите любую клавишу для остановки сервера..."
        $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
        
    } catch {
        Write-Log "❌ Ошибка при деплое: $_" -Level 'ERROR'
        
        # Пытаемся записать стек вызовов в лог
        $errorMessage = $_.Exception.Message
        $stackTrace = $_.ScriptStackTrace -replace "`n", "`n    "
        Write-Log "Стек вызовов:`n    $stackTrace" -Level 'ERROR'
        
        # Пытаемся остановить сервер при ошибке
        if ($script:processId) {
            try {
                Stop-Process -Id $script:processId -Force -ErrorAction SilentlyContinue
                Write-Log "Остановлен процесс сервера с ID $($script:processId)" -Level 'INFO'
            } catch {
                Write-Log "Не удалось остановить процесс сервера: $_" -Level 'WARNING'
            }
        }
        
        exit 1
    } finally {
        # Всегда останавливаем сервер при завершении
        Stop-Deployment
    }
}

# Регистрируем обработчик завершения
$null = Register-EngineEvent -SourceIdentifier "PowerShell.Exiting" -Action {
    Stop-Deployment
}

# Запускаем деплой
Start-Deployment
