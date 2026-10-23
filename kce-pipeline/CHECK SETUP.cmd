@echo off
REM ===================================================================
REM  Double-click this to check the tool is set up correctly.
REM  It never displays your API key.
REM ===================================================================
title KCE Pipeline - Setup Check

cd /d "%~dp0" 2>nul
if errorlevel 1 (
  echo  ERROR: cannot change into the folder this file lives in.
  pause
  exit /b 1
)

py --version >nul 2>&1
if errorlevel 1 (
  echo.
  echo  [FAIL] Python was not found.
  echo         Install Python 3.11+ from python.org and tick
  echo         "Add Python to PATH" during setup.
  echo.
  pause
  exit /b 1
)
for /f "delims=" %%v in ('py --version 2^>^&1') do echo  [ok]   %%v

echo.
py -m kce_pipeline --check-api
set "RESULT=%ERRORLEVEL%"

echo.
if not "%RESULT%"=="0" (
  echo  ---------------------------------------------------------------
  echo   Something above needs fixing before NEW documents can be read.
  echo.
  echo   Projects already run before will still work offline.
  echo  ---------------------------------------------------------------
)
echo.
pause
exit /b %RESULT%
