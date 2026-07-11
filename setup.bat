@echo off
cd /d "%~dp0"

cd

:: check if python is installed
>nul 2>nul assoc .py

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

:: Check if Git is installed
where git >nul 2>&1

if errorlevel 1 (
  echo Git not installed, downloading installer...
  powershell -c "$release = Invoke-RestMethod -Uri 'https://api.github.com/repos/git-for-windows/git/releases/latest'; $asset = $release.assets | Where-Object { $_.name -match '^Git-.*-64-bit\.exe$' } | Select-Object -First 1; if (-not $asset) { throw 'Git installer asset not found.' }; Invoke-WebRequest -Uri $asset.browser_download_url -OutFile '%TEMP%\git-installer.exe'"
  
  if errorlevel 1 (
    echo Failed to download Git installer.
    pause
    exit /b 1
  )
  
  echo Installing Git...
  "%TEMP%\git-installer.exe" /VERYSILENT /NORESTART
  if errorlevel 1 (
    echo Failed to install Git.
    pause
    exit /b 1
  )
  
  del "%TEMP%\git-installer.exe" >nul 2>&1
  echo Git installed successfully.
  ) else (
  echo Git is already installed.
)

:: get depedencies, not worth checking worst case they are already installed.
echo Installing dependencies...
py -m pip install -r requirements.txt

echo Finished installing dependencies.

echo Setup finished.
pause
