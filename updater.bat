@echo off
setlocal EnableExtensions EnableDelayedExpansion

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
set "BRANCH=stable_to_play"
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

set "UPDATE_COUNT=0"
for /f %%C in ('git rev-list --count HEAD..origin/%BRANCH%') do set "UPDATE_COUNT=%%C"

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
  ::Revert local changes so git can update smoothly
  for /f "delims=" %%F in ('git diff --name-only') do (
    git diff --quiet HEAD..origin/%BRANCH% -- "%%F"
    if errorlevel 1 (
      echo Restoring conflicting local file: %%F
      git restore --worktree --staged -- "%%F"
      if errorlevel 1 goto :git_error
    )
  )
  
  echo Downloading update...
  git pull origin "%BRANCH%"
  
  if errorlevel 1 goto :git_error
  echo Update complete.
  
  endlocal & exit /b 0
)

if /I "%MODE%"=="/check" (
  echo UP_TO_DATE
  endlocal & exit /b 0
)
if /I not "%MODE%"=="/update" goto :usage_error
echo Up to date!
endlocal & exit /b 0

:usage_error
echo Usage: updater.bat /check or updater.bat /update
endlocal & exit /b 1

:git_error
echo.
echo Update check failed.
endlocal & exit /b 1
