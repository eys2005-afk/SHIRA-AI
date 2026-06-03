@echo off
echo ============================================
echo  ShiraAI - Publish Update
echo ============================================
echo.

:: Read current version from shira_proxy.py (match exact line: VERSION = "x.x")
for /f "tokens=3 delims=^= " %%a in ('findstr /r "^VERSION = " shira_proxy.py') do set VER=%%a

:: Strip surrounding quotes from version
set VER=%VER:"=%

echo Current VERSION in code: %VER%
echo.

if "%VER%"=="" (
    echo [!] Could not read VERSION from shira_proxy.py
    pause
    exit /b 1
)

:: Check EXE exists
if not exist "dist\ShiraAI.exe" (
    echo [!] dist\ShiraAI.exe not found. Run BUILD.bat first.
    pause
    exit /b 1
)

:: Copy EXE to update_files
set UPDATE_DIR=C:\Users\elchanans\Documents\AI\AI\SHIRA1\update_files
if not exist "%UPDATE_DIR%" mkdir "%UPDATE_DIR%"
copy /y "dist\ShiraAI.exe" "%UPDATE_DIR%\ShiraAI.exe" >nul
echo [*] Copied ShiraAI.exe to update_files.

:: Write version cleanly (no extra characters)
> "%UPDATE_DIR%\version.txt" echo %VER%
echo [*] version.txt set to %VER%.

:: Verify what was written
echo [*] Contents of version.txt:
type "%UPDATE_DIR%\version.txt"
echo.

:: Get local IP
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /r "IPv4"') do (
    set IP=%%a
    goto :found
)
:found
set IP=%IP: =%

echo.
echo ============================================
echo  Update server running at: http://%IP%:8081
echo  Press Ctrl+C to stop
echo ============================================
echo.

cd "%UPDATE_DIR%"
python -m http.server 8081
