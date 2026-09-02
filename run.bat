@echo off
cd /d "%~dp0"

:: check if python is installed
echo Checking Python...
python --version >nul 2>&1

if errorlevel 1 (
  py --version >nul 2>&1
)

if errorlevel 1 (
  :: python is not installed
  echo Python not installed, please run setup.bat first!
  pause
  exit /b 1
)

:: Check if virtual environment exists
if not exist "venv" (
  echo Virtual environment not found, please run setup.bat first!
  pause
  exit /b 1
)

:: Activate the virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

if errorlevel 1 (
  echo Failed to activate virtual environment!
  pause
  exit /b 1
)

:: Run the main Python script
set "APP_ID=ShenGBot"
echo Starting GBot...
python main.py --app-id "%APP_ID%"

:: Deactivate virtual environment
echo Deactivating virtual environment...
call deactivate

echo Killing remaining Shen GBot processes...
powershell.exe -NoProfile -Command "$appId = '%APP_ID%'; Get-CimInstance Win32_Process | Where-Object { ($_.Name -eq 'python.exe' -or $_.Name -eq 'pythonw.exe') -and $_.CommandLine -like ('*--app-id ' + $appId + '*') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"

if exist ".update_restart.request" (
  del /q ".update_restart.request" >nul 2>&1
  start "" /d "%~dp0" "%~f0"
)
