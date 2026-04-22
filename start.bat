@echo off
setlocal
cd /d "%~dp0"

echo ==========================================
echo   Smart Presence Kiosk - Starting System
echo ==========================================

if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found.
    echo Please create it first with:
    echo python -m venv .venv
    pause
    exit /b 1
)

if not exist "scripts\start_backend.bat" (
    echo [ERROR] Missing scripts\start_backend.bat
    pause
    exit /b 1
)

if not exist "scripts\start_kiosk.bat" (
    echo [ERROR] Missing scripts\start_kiosk.bat
    pause
    exit /b 1
)

start "Presence Backend" cmd /k "scripts\start_backend.bat"

:: Wait 22 seconds to let TensorFlow and Face Embeddings load fully
timeout /t 22 /nobreak > nul

start "Presence Kiosk" cmd /k "scripts\start_kiosk.bat"

:: Wait 3 more seconds before opening the dashboard
timeout /t 3 /nobreak > nul

start "" "http://127.0.0.1:8000"
echo Backend, kiosk, and dashboard launched.
endlocal