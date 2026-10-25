@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo [AI Code Guardian] Launcher starting...

REM --- 1) venv check + first-run setup ---
if not exist "venv\Scripts\python.exe" (
    echo [SETUP] venv not found. First-run setup required.
    echo [SETUP] This will create venv + venv-semgrep and pip install both.
    echo [SETUP] Requires Python 3.12 on PATH + internet access.
    set /p CONFIRM="Run first-run setup now? [y/N]: "
    if /i not "!CONFIRM!"=="y" (
        echo [SETUP] Aborted by user.
        exit /b 1
    )
    call :first_run_setup
    if errorlevel 1 exit /b 1
)

REM --- 2) Port 8000 check (fail-fast, no fallback) ---
set PORT=8000
netstat -ano | findstr ":%PORT% " | findstr "LISTENING" >nul
if not errorlevel 1 (
    echo [ERROR] Port %PORT% already in use. Stop the other process and retry.
    exit /b 1
)

REM --- 3) Portable checks (warn-only) ---
call venv\Scripts\activate.bat
python -m backend.core.portable --verify-binaries --ensure-dirs
if errorlevel 1 (
    echo [WARN] Binary verification returned non-zero. Continuing anyway, warn-only mode.
)

REM --- 4) Open browser after short delay, then start uvicorn ---
start "" /b powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 3; Start-Process 'http://127.0.0.1:%PORT%'"
echo [AI Code Guardian] Starting uvicorn on http://127.0.0.1:%PORT%
echo [AI Code Guardian] Press Ctrl+C in this window to stop.
uvicorn backend.main:app --host 127.0.0.1 --port %PORT%

echo [AI Code Guardian] Server stopped.
exit /b 0

:first_run_setup
echo [SETUP] Creating main venv...
python -m venv venv
if errorlevel 1 goto setup_fail
call venv\Scripts\activate.bat
pip install -r requirements.txt
if errorlevel 1 goto setup_fail
echo [SETUP] Creating semgrep venv...
python -m venv venv-semgrep
if errorlevel 1 goto setup_fail
call venv-semgrep\Scripts\activate.bat
pip install -r requirements-semgrep.txt
if errorlevel 1 goto setup_fail
call venv\Scripts\activate.bat
echo [SETUP] First-run setup complete.
exit /b 0

:setup_fail
echo [SETUP] Setup step failed. See message above.
exit /b 1