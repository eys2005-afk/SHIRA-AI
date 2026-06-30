@echo off
title Shira AI - Automation Setup
cd /d "%~dp0"

echo ==========================================
echo  Shira AI - Automation Setup
echo ==========================================
echo.
echo [*] Installing Python packages...
pip install -r requirements.txt
if errorlevel 1 goto :error

echo.
echo [*] Installing Playwright browser (Edge)...
python -m playwright install msedge
if errorlevel 1 goto :error

echo.
echo [OK] Setup complete.
echo Next steps:
echo   1. Copy config.example.json to config.json and edit it.
echo   2. Run RECORD_OPEN_CASE.bat
pause
exit /b 0

:error
echo.
echo [!] Setup failed - see the error above.
pause
exit /b 1
