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

start "Presence Backend" cmd /k "%~dp0scripts\start_backend.bat"

timeout /t 4 /nobreak > nul

start "Presence Kiosk" cmd /k "%~dp0scripts\start_kiosk.bat"

timeout /t 2 /nobreak > nul

start "" "http://127.0.0.1:8000"

echo Backend, kiosk, and dashboard launched.
endlocal
