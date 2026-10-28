@echo off
setlocal EnableExtensions
setlocal EnableDelayedExpansion

set "MODE=%~1"
if /I "%MODE%"=="" set "MODE=/update"
if /I "%~2"=="__logged" goto :execute
if not exist "%~dp0source\logs" mkdir "%~dp0source\logs"
set "UPDATE_LOG=%~dp0source\logs\updater.log"
echo Update log: "%UPDATE_LOG%"
set "UPDATE_OUTPUT=%TEMP%\gbot-update-%RANDOM%-%RANDOM%.log"
>>"%UPDATE_LOG%" echo [%DATE% %TIME%] [UPDATE] Starting %MODE%
call "%~f0" "%MODE%" __logged >"%UPDATE_OUTPUT%" 2>&1
set "UPDATE_EXIT=!ERRORLEVEL!"
type "%UPDATE_OUTPUT%"
type "%UPDATE_OUTPUT%" >>"%UPDATE_LOG%"
>>"%UPDATE_LOG%" echo [%DATE% %TIME%] [UPDATE] Finished %MODE%, exit code !UPDATE_EXIT!
del /q "%UPDATE_OUTPUT%"
exit /b %UPDATE_EXIT%

:execute
cd /d "%~dp0"
:: Trust this installation for all child Git commands, without changing global config.
if not defined GIT_CONFIG_COUNT set "GIT_CONFIG_COUNT=0"
set "GIT_CONFIG_KEY_%GIT_CONFIG_COUNT%=safe.directory"
set "GIT_CONFIG_VALUE_%GIT_CONFIG_COUNT%=%CD:\=/%"
set /a GIT_CONFIG_COUNT+=1 >nul
set "BRANCH=stable_before_qml"
set "REMOTE_URL=https://github.com/minhquan1313/ark-gacha-bot-asa-shen.git"

if not exist ".git\" (
  echo Git repository not found.
  echo Initializing repository...
  git init
  if errorlevel 1 goto :git_error
  git remote add origin "%REMOTE_URL%"
  if errorlevel 1 goto :git_error
  git fetch origin %BRANCH%
  if errorlevel 1 goto :git_error
  git checkout -f -B %BRANCH% origin/%BRANCH%
  if errorlevel 1 goto :git_error
)

echo Checking update...
git fetch origin "%BRANCH%"
if errorlevel 1 goto :git_error

set "UPDATE_COUNT="
for /f %%C in ('git rev-list --count HEAD..origin/%BRANCH%') do set "UPDATE_COUNT=%%C"
if not defined UPDATE_COUNT goto :git_error

if /I "%MODE%"=="/check" (
  echo UPDATE_MANIFEST_BEGIN
  git show origin/%BRANCH%:manifest.json
  if errorlevel 1 goto :git_error
  echo UPDATE_MANIFEST_END
)

if not "!UPDATE_COUNT!"=="0" (
  if /I "%MODE%"=="/check" (
    echo UPDATE_AVAILABLE
    endlocal & exit /b 10
  )
  
  if /I not "%MODE%"=="/update" goto :usage_error
  :: Save local edits as a backup; leave the stash unapplied to keep the latest code.
  echo Backing up local changes, if any...
  git stash push --include-untracked -m "GBot updater backup"
  if errorlevel 1 goto :git_error
  
  echo Downloading update...
  git merge --ff-only origin/%BRANCH%
  
  if errorlevel 1 goto :git_error
  echo Update complete.
  
  goto :setup_and_restart
)

if /I "%MODE%"=="/check" (
  echo UP_TO_DATE
  endlocal & exit /b 0
)
if /I not "%MODE%"=="/update" goto :usage_error
echo Up to date!
goto :setup_and_restart

:setup_and_restart
echo Installing dependencies before restart...
call "%~dp0setup.bat" /update
if errorlevel 1 (
  echo Setup failed. The app was not restarted. See the update log and rerun updater.bat.
  endlocal & exit /b 1
)
call "%~dp0run.bat"
set "RESTART_EXIT=!ERRORLEVEL!"
endlocal & exit /b %RESTART_EXIT%

:usage_error
echo Usage: updater.bat /check or updater.bat /update
endlocal & exit /b 1

:git_error
echo.
echo Git update operation failed. See the error above.
endlocal & exit /b 1
