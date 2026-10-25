@echo off
title CodeGuardian.AI - Installer
color 0A
echo Installing CodeGuardian.AI...
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed on this PC!
    pause
    exit /b
)

echo [1/3] Setting up Virtual Environment...
python -m venv "%~dp0venv"

echo [2/3] Installing dependencies (Internet required)...
call "%~dp0venv\Scripts\activate"
pip install -r "%~dp0requirements.txt" -q
pip install psutil -q

echo [3/3] Creating Desktop Shortcut...
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%USERPROFILE%\Desktop\CodeGuardian.AI.lnk'); $s.TargetPath = '%~dp0venv\Scripts\pythonw.exe'; $s.Arguments = '%~dp0app_launcher.py'; $s.WorkingDirectory = '%~dp0'; $s.IconLocation = '%~dp0app.ico,0'; $s.Save()"

echo.
echo ========================================================
echo   INSTALLATION SUCCESSFUL!
echo   Desktop par CodeGuardian.AI ka icon aa gaya hai.
echo ========================================================
pause