@echo off
title CodeGuardian.AI - Uninstaller
color 0C
echo Uninstalling CodeGuardian.AI...
del "%USERPROFILE%\Desktop\CodeGuardian.AI.lnk" /q 2>nul
echo Removing Virtual Environment (this may take a moment)...
if exist "%~dp0venv" rmdir /s /q "%~dp0venv"
echo ========================================================
echo   UNINSTALLATION SUCCESSFUL!
echo   App and Desktop icon have been removed.
echo ========================================================
pause