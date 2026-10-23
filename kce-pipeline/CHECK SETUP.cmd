@echo off
REM ===================================================================
REM  Double-click this to check the tool is set up correctly.
REM  It never displays your API key.
REM
REM  Exit code: 0 = live extraction works, anything else = read the output.
REM  The window is held open only when a person launched it, so a script that
REM  calls "CHECK SETUP.cmd" [--no-pause] gets the real exit code.
REM ===================================================================
title KCE Pipeline - Setup Check
set "RESULT=2"

cd /d "%~dp0" 2>nul
if errorlevel 1 (
  echo  ERROR: cannot change into the folder this file lives in.
  goto :finish
)

py --version >nul 2>&1
if errorlevel 1 (
  echo.
  echo  [FAIL] Python was not found.
  echo         Install Python 3.11+ from python.org and tick
  echo         "Add Python to PATH" during setup.
  echo.
  goto :finish
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

:finish
REM Hold the window open only for a person -- see RUN A PROJECT.cmd for the why.
if defined KCE_NO_PAUSE goto :done
if /i "%~1"=="--no-pause" goto :done
echo %CMDCMDLINE% | findstr /i /c:"%~nx0" >nul || goto :done
timeout /t 0 >nul 2>&1 || goto :done
echo.
pause
:done
exit /b %RESULT%
