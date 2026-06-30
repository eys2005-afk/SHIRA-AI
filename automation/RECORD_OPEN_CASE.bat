@echo off
title Shira AI - Record Open Case
color 1F
echo.
echo  ==========================================
echo   Shira AI - Recording: Open Case
echo  ==========================================
echo.
echo  [*] Starting Playwright recorder...
echo  [*] Use TEST DATA ONLY during recording!
echo  [*] Close the browser window when finished.
echo  ==========================================
echo.

cd /d "%~dp0"
python record_open_case.py

echo.
echo [!] Recording session ended.
pause
