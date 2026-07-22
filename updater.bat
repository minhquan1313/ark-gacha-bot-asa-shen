@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "MODE=%~1"
if /I "%MODE%"=="" set "MODE=/update"
set "BRANCH=stable_to_play"

if not exist ".git\" (
  echo Git repository not found.
  echo Initializing repository...
  git init
  if errorlevel 1 goto :git_error
  git remote add origin https://github.com/minhquan1313/ark-gacha-bot-asa-shen.git >nul 2>&1
  if errorlevel 1 goto :git_error
  git fetch origin %BRANCH%
  if errorlevel 1 goto :git_error
  git checkout -f -B %BRANCH% origin/%BRANCH%
  if errorlevel 1 goto :git_error
)

echo Checking update...
git fetch origin "%BRANCH%" >nul 2>&1
if errorlevel 1 goto :git_error

set "UPDATE_COUNT=0"
for /f %%C in ('git rev-list --count HEAD..origin/%BRANCH%') do set "UPDATE_COUNT=%%C"

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
