@echo off
cd /d "%~dp0\.."

if not exist ".venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found at .venv\Scripts\activate.bat
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
uvicorn app.main:app --reload
