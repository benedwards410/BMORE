@echo off
REM ===================================================================
REM  KCE Document Intake Pipeline
REM
REM  EASIEST WAY TO USE THIS:
REM     Drag a project folder onto this file and let go.
REM
REM  Or just double-click it and paste/type the folder path when asked.
REM ===================================================================
setlocal EnableDelayedExpansion
title KCE Document Intake Pipeline

cd /d "%~dp0" 2>nul
if errorlevel 1 (
  echo.
  echo  ERROR: cannot change into the folder this file lives in.
  echo  Keep "RUN A PROJECT.cmd" in the same folder as "pipeline".
  echo.
  pause
  exit /b 1
)

REM --- Python check -------------------------------------------------
py --version >nul 2>&1
if errorlevel 1 (
  echo.
  echo  ERROR: Python was not found.
  echo  Install Python 3.11 or newer from python.org, then run this again.
  echo.
  pause
  exit /b 1
)

REM --- Which folder? ------------------------------------------------
set "TARGET=%~1"
if "%TARGET%"=="" (
  echo.
  echo  ==========================================================
  echo    KCE Document Intake Pipeline
  echo  ==========================================================
  echo.
  echo   TIP: next time, just drag the project folder onto this
  echo        file instead of typing the path.
  echo.
  set /p "TARGET=  Paste the project folder path here: "
)

REM Strip surrounding quotes if the user pasted a quoted path.
set "TARGET=%TARGET:"=%"

if "%TARGET%"=="" (
  echo.
  echo  Nothing entered. Exiting.
  echo.
  pause
  exit /b 1
)

if not exist "%TARGET%\" (
  echo.
  echo  ERROR: that folder does not exist:
  echo     %TARGET%
  echo.
  echo  Make sure you dragged a FOLDER, not a single PDF.
  echo.
  pause
  exit /b 1
)

echo.
echo  Reading documents in:
echo     %TARGET%
echo.
echo  This takes about 10-30 seconds per document. Please wait...

py -m kce_pipeline "%TARGET%"
set "RESULT=%ERRORLEVEL%"

echo.
if "%RESULT%"=="0" (
  echo  ---------------------------------------------------------
  echo   Finished. No blocking issues.
  echo  ---------------------------------------------------------
) else (
  echo  ---------------------------------------------------------
  echo   Finished. Some items need a person to decide - see the
  echo   critical list above and open the report.
  echo  ---------------------------------------------------------
)
echo.
pause
exit /b %RESULT%
