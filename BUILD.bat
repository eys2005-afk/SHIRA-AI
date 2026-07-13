@echo off
echo ============================================
echo  ShiraAI - Building EXE...
echo ============================================
echo.
for /f "tokens=3 delims= " %%a in ('findstr "VERSION = " shira_proxy.py') do set VER=%%a
echo Current VERSION in code: %VER%
echo Make sure this matches what you will enter in update_server.bat!
echo.
pause

:: Kill running instance
taskkill /f /im ShiraAI.exe >nul 2>&1

:: Build
pyinstaller --onefile --noconsole --name "ShiraAI" ^
  --hidden-import win32timezone ^
  --hidden-import pdfminer ^
  --hidden-import pdfminer.high_level ^
  --hidden-import pdfminer.layout ^
  --hidden-import pdfminer.converter ^
  --hidden-import pdfminer.pdfinterp ^
  --hidden-import pdfminer.pdfdevice ^
  --exclude-module torch ^
  --exclude-module scipy ^
  --exclude-module numpy ^
  --exclude-module pandas ^
  --exclude-module pyarrow ^
  --exclude-module numba ^
  --exclude-module PIL ^
  --exclude-module matplotlib ^
  --exclude-module sklearn ^
  --exclude-module tensorflow ^
  shira_proxy.py

if %errorlevel% == 0 (
    copy /y "update_url.txt" "dist\update_url.txt" >nul 2>&1
    echo.
    echo ============================================
    echo  SUCCESS! EXE is ready at: dist\ShiraAI.exe
    echo ============================================
) else (
    echo.
    echo ============================================
    echo  BUILD FAILED - check errors above
    echo ============================================
)
pause
