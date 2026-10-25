@echo off
setlocal EnableDelayedExpansion
set PORT=8000

echo [AI Code Guardian] Stopping server on port %PORT%...

set PID=
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%PORT% " ^| findstr "LISTENING"') do (
    set PID=%%a
    goto :found
)

echo [INFO] No server found listening on port %PORT%. Already stopped.
exit /b 0

:found
echo [INFO] Found server PID=!PID!

REM --- Graceful attempt (taskkill without /F) ---
taskkill /PID !PID! >nul 2>&1
timeout /t 3 /nobreak >nul

netstat -ano | findstr ":%PORT% " | findstr "LISTENING" >nul
if errorlevel 1 (
    echo [OK] Server stopped gracefully.
    exit /b 0
)

echo [WARN] Graceful stop did not work. Forcing stop...
taskkill /PID !PID! /F >nul 2>&1
timeout /t 1 /nobreak >nul
netstat -ano | findstr ":%PORT% " | findstr "LISTENING" >nul
if errorlevel 1 (
    echo [OK] Server force-stopped.
    exit /b 0
)

echo [ERROR] Could not stop server on port %PORT%. Manual action required.
exit /b 1