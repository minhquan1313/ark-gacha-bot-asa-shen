@echo off
cd /d "%~dp0"

if not exist "venv\Scripts\pythonw.exe" (
  echo Virtual environment not found, please run setup.bat first!
  pause
  exit /b 1
)

start "" /d "%~dp0" "%~dp0venv\Scripts\pythonw.exe" "%~dp0main.py" --app-id ShenGBot
exit /b
