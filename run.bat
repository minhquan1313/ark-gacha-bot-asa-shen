@echo off
setlocal EnableExtensions EnableDelayedExpansion

:: Specify the required Python version
set "PYTHON_VERSION=3.11"

:: Check if Python 3.11 is installed
echo Checking for Python %PYTHON_VERSION%...
py -%PYTHON_VERSION% --version >nul 2>&1
if errorlevel 1 (
  :: python is not installed
  echo Python not installed, downloading installer...
  powershell -c "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.1/python-3.11.1-amd64.exe' -OutFile '%USERPROFILE%\AppData\Local\Temp\python-3.11.1.exe'"
  echo Launching installer, please make sure to follow the correct setup instructions Adding python to environment variables!
  echo:
  
  "%USERPROFILE%\AppData\Local\Temp\python-3.11.1.exe"
  pause
  echo Please press any button once you have completed the python setup, so we can continue installing the depedencies.
  
  ) else (
  echo Python is already installed. Please make sure its of version 3.10 or higher, using an older version will NOT work!
)

:: Check if virtual environment exists
if not exist "venv" (
  echo Virtual environment not found. Creating a new one using Python %PYTHON_VERSION%...
  py -%PYTHON_VERSION% -m venv venv
  if errorlevel 1 (
    echo Failed to create virtual environment with Python %PYTHON_VERSION%. Ensure Python is installed and accessible.
    pause
    exit /b
  )
  echo Virtual environment created successfully.
  
  :: Install dependencies immediately after creating the venv
  echo Installing dependencies from requirements.txt...
  call venv\Scripts\activate.bat
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt
)

:: Activate the virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat
if errorlevel 1 (
  echo Failed to activate virtual environment. Please activate it manually using:
  echo venv\Scripts\activate
  pause
  exit /b
)

:: Run the main Python script
echo Installing/updating dependencies from requirements.txt...
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo Failed to install dependencies from requirements.txt.
  pause
  deactivate
  exit /b
)

cls

:: Prepare to pull update
set "SHOULD_UPDATE=1"
if "%SHOULD_UPDATE%"=="0" goto :git_done

set "BRANCH=stable_to_play"
if not exist ".git\" (
  echo Git repository not found.
  echo Initializing repository...
  
  git init
  if errorlevel 1 goto :git_error
  
  git remote add origin https://github.com/minhquan1313/ark-gacha-bot-asa-shen.git  >nul 2>&1
  if errorlevel 1 goto :git_error
  
  git fetch origin %BRANCH%
  if errorlevel 1 goto :git_error
  
  git checkout -f -B %BRANCH% origin/%BRANCH%
  if errorlevel 1 goto :git_error
  
  git pull origin %BRANCH%
  if errorlevel 1 goto :git_error
)

:: Pull updates from Git
echo Checking update...
git fetch origin "%BRANCH%" >nul 2>&1
if errorlevel 1  goto :git_error

for /f %%C in ('git rev-list --count HEAD..origin/%BRANCH%') do (
  set "UPDATE_COUNT=%%C"
)

if not "!UPDATE_COUNT!"=="0" (
  echo Downloading update...
  git pull origin %BRANCH%
  if errorlevel 1  goto :git_error
  ) else (
  echo Up to date!
)

goto :git_done

:git_error
echo.
echo Update failed.
pause
exit /b 1

:git_done

set "APP_ID=ShenGBot"
echo Starting GBot...
python main.py --app-id "%APP_ID%"

:: Deactivate virtual environment
echo Deactivating virtual environment...
call deactivate

echo Killing remaining Shen GBot processes...
powershell.exe -NoProfile -Command "$appId = '%APP_ID%'; Get-CimInstance Win32_Process | Where-Object { ($_.Name -eq 'python.exe' -or $_.Name -eq 'pythonw.exe') -and $_.CommandLine -like ('*--app-id ' + $appId + '*') } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
@REM taskkill /F /IM python.exe /T
@REM taskkill /F /IM pythonw.exe /T
