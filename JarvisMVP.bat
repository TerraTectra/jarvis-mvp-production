@echo off
title Jarvis MVP - Автоматический запуск
color 0A
cls

echo ===============================================
echo  🚀 Jarvis MVP - Запуск системы
  echo  %date% %time:~0,8%
echo ===============================================
echo.

REM Проверяем наличие Python
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ❌ ОШИБКА: Python не найден в системе!
    echo Убедитесь, что Python установлен и добавлен в PATH
    pause
    exit /b 1
)

REM Проверяем наличие виртуального окружения
if not exist "venv\Scripts\activate.bat" (
    echo ⚠️ Виртуальное окружение не обнаружено
    echo Создаем виртуальное окружение...
    python -m venv venv
    if %ERRORLEVEL% NEQ 0 (
        echo ❌ Не удалось создать виртуальное окружение
        pause
        exit /b 1
    )
    
    echo Устанавливаем зависимости...
    call venv\Scripts\activate.bat
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    if %ERRORLEVEL% NEQ 0 (
        echo ❌ Ошибка при установке зависимостей
        pause
        exit /b 1
    )
)

echo.
echo ✅ Все проверки пройдены

REM Активируем виртуальное окружение
call venv\Scripts\activate.bat

REM Устанавливаем переменные окружения
set PYTHONPATH=%~dp0
set PATH=%~dp0venv\Scripts;%PATH%

REM Запускаем приложение
echo.
echo 🚀 Запускаю Jarvis MVP...
python run.py all

REM Обработка завершения
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ❌ Произошла ошибка при выполнении программы
) else (
    echo.
    echo ✅ Программа завершила работу успешно
)

pause
