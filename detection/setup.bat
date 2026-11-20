@echo off
rem One-time install (Windows). Needs Python 3.10+ from python.org ("Add to PATH" ticked).
cd /d "%~dp0"
if not exist .venv python -m venv .venv
.venv\Scripts\python -m pip install -q --upgrade pip
.venv\Scripts\pip install -q --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt
echo Ready. Start with start.bat
pause
