@echo off
title Build ShiraAI.exe
echo.
echo  ==========================================
echo   Building ShiraAI.exe
echo  ==========================================
echo.
echo  The EXE bundles Python + all libraries.
echo  On every launch it downloads the latest
echo  shira_proxy.py from update_url.txt and
echo  runs it — no Python needed on user PCs.
echo.

where pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [!] PyInstaller not found. Installing...
    pip install pyinstaller
)

if exist "dist\ShiraAI.exe" del /f /q "dist\ShiraAI.exe"
if exist "build" rmdir /s /q build
if exist "ShiraAI.spec" del /f /q ShiraAI.spec

pyinstaller ^
    --onefile ^
    --console ^
    --name ShiraAI ^
    --hidden-import flask ^
    --hidden-import flask_cors ^
    --hidden-import requests ^
    --hidden-import requests_negotiate_sspi ^
    --hidden-import pdfplumber ^
    --hidden-import docx ^
    --hidden-import bs4 ^
    --hidden-import lxml ^
    --hidden-import lxml.etree ^
    --hidden-import pywintypes ^
    --hidden-import win32security ^
    --hidden-import win32timezone ^
    --hidden-import sspi ^
    --hidden-import sspicon ^
    --hidden-import httpx ^
    --hidden-import google.generativeai ^
    --collect-all pdfplumber ^
    --collect-all requests_negotiate_sspi ^
    shira_launcher.py

if errorlevel 1 (
    echo.
    echo [!] Build FAILED.
    pause
    exit /b 1
)

copy /Y dist\ShiraAI.exe ShiraAI.exe

echo.
echo  ==========================================
echo   SUCCESS: ShiraAI.exe is ready.
echo.
echo   Distribute ShiraAI.exe + update_url.txt
echo   to all court computers.
echo   No Python installation needed.
echo  ==========================================
echo.
pause
