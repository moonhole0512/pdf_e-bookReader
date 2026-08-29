@echo off
setlocal enabledelayedexpansion

echo ========================================================
echo   E-Book Reader Local Server Launcher
echo ========================================================

cd /d "%~dp0"

REM 1. Check for standard .venv
if exist ".venv\Scripts\activate.bat" (
    echo [INFO] Activating .venv virtual environment...
    call .venv\Scripts\activate.bat
    goto RUN_SERVER
)

REM 2. Check for local venv folder (Conda or existing venv)
if exist "venv\Scripts\activate.bat" (
    echo [INFO] Activating venv virtual environment...
    call venv\Scripts\activate.bat
    goto RUN_SERVER
)

if exist "venv\python.exe" (
    echo [INFO] Found local portable Python in venv...
    set "PATH=%~dp0venv;%~dp0venv\Scripts;%PATH%"
    goto RUN_SERVER
)

REM 3. If no virtualenv found, automatically create .venv
echo [INFO] Virtual environment not found. Creating .venv...
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Please install Python 3.10+ from https://www.python.org/
    pause
    exit /b 1
)

python -m venv .venv
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to create .venv virtual environment.
    pause
    exit /b 1
)

echo [INFO] Activating newly created .venv...
call .venv\Scripts\activate.bat

echo [INFO] Installing required dependencies from requirements.txt...
pip install --upgrade pip
pip install -r requirements.txt
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

:RUN_SERVER
echo.
echo [INFO] Starting E-Book Reader server at http://localhost:8000
echo [INFO] Press Ctrl+C to stop the server.
echo.

where waitress-serve >nul 2>nul
if %ERRORLEVEL% equ 0 (
    waitress-serve --host 0.0.0.0 --port 8000 app:app
) else (
    python -m waitress --host 0.0.0.0 --port 8000 app:app
)

if %ERRORLEVEL% neq 0 (
    echo [WARNING] Waitress failed, falling back to direct Python run...
    python app.py
)

pause
