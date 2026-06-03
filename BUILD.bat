@echo off
title Build ShiraAI.exe
echo.
echo  ==========================================
echo   Building ShiraAI.exe (launcher only)
echo  ==========================================
echo.
echo  This compiles shira_launcher.py into a single EXE.
echo  The EXE auto-downloads shira_proxy.py from GitHub on every launch.
echo  You only need to rebuild the EXE when the LAUNCHER itself changes.
echo.

REM ── Require PyInstaller ───────────────────────────────────────────────────
where pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [!] PyInstaller not found. Run:  pip install pyinstaller
    pause
    exit /b 1
)

REM ── Clean previous build ──────────────────────────────────────────────────
if exist "dist\ShiraAI.exe" del /f /q "dist\ShiraAI.exe"
if exist "build" rmdir /s /q build
if exist "ShiraAI.spec" del /f /q ShiraAI.spec

REM ── Build ─────────────────────────────────────────────────────────────────
pyinstaller ^
    --onefile ^
    --noconsole ^
    --name ShiraAI ^
    --icon NONE ^
    shira_launcher.py

if errorlevel 1 (
    echo.
    echo [!] Build FAILED.
    pause
    exit /b 1
)

echo.
echo  ==========================================
echo   SUCCESS: dist\ShiraAI.exe is ready.
echo.
echo   Distribute ShiraAI.exe to all court PCs.
echo   No other files needed — it downloads
echo   shira_proxy.py automatically.
echo  ==========================================
echo.
pause
