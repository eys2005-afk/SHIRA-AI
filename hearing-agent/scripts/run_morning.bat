@echo off
rem ריצת הבוקר: קריאת היומן משירה וקביעת הדיונים ב-Verbit
cd /d "%~dp0.."
call .venv\Scripts\activate.bat
python -m agent.morning >> data\morning.log 2>&1
