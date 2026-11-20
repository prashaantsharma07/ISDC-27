@echo off
rem Start TeamMARS object detection and open it in the browser (Windows).
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (echo Run setup.bat first & pause & exit /b 1)
start "" /b cmd /c "timeout /t 8 >nul & start http://127.0.0.1:8765"
.venv\Scripts\python -I server.py
