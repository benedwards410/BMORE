@echo off
REM ===================================================================
REM  KCE Document Intake Pipeline
REM
REM  EASIEST WAY TO USE THIS:
REM     Drag a project folder onto this file and let go.
REM
REM  Or just double-click it and paste/type the folder path when asked.
REM
REM  From a script or a scheduled task:
REM     "RUN A PROJECT.cmd" "C:\path\to\project" [--no-pause]
REM  Exit code follows the Python CLI:  0 clean, 1 critical flags outstanding,
REM  2 the launcher or the tool itself failed. The window is held open only
REM  when a person launched it (double-click / drag-and-drop), so a script
REM  gets the real code instead of the 255 a "pause" with no console left.
REM ===================================================================
setlocal EnableDelayedExpansion
title KCE Document Intake Pipeline
set "RESULT=2"

cd /d "%~dp0" 2>nul
if errorlevel 1 (
  echo.
  echo  ERROR: cannot change into the folder this file lives in.
  echo  Keep "RUN A PROJECT.cmd" in the same folder as "kce_pipeline".
  echo.
  goto :finish
)

REM --- Python check -------------------------------------------------
py --version >nul 2>&1
if errorlevel 1 (
  echo.
  echo  ERROR: Python was not found.
  echo  Install Python 3.11 or newer from python.org, then run this again.
  echo.
  goto :finish
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
if defined TARGET set "TARGET=%TARGET:"=%"

if "%TARGET%"=="" (
  echo.
  echo  Nothing entered. Exiting.
  echo.
  goto :finish
)

if not exist "%TARGET%\" (
  echo.
  echo  ERROR: that folder does not exist:
  echo     %TARGET%
  echo.
  echo  Make sure you dragged a FOLDER, not a single PDF.
  echo.
  goto :finish
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
) else if "%RESULT%"=="1" (
  echo  ---------------------------------------------------------
  echo   Finished. Some items need a person to decide - see the
  echo   critical list above and open the report.
  echo  ---------------------------------------------------------
) else (
  echo  ---------------------------------------------------------
  echo   The tool itself failed ^(exit code %RESULT%^).
  echo   Double-click "CHECK SETUP.cmd" to see what is missing.
  echo  ---------------------------------------------------------
)

:finish
REM Hold the window open only for a person. Both tests must pass:
REM  1. cmd was started to run THIS file: double-click / drag-and-drop put the
REM     script's own name into CMDCMDLINE; an open console window does not.
REM  2. stdin is a real console: "timeout" fails when input is redirected or
REM     absent, which is exactly when "pause" used to hit end-of-input and kill
REM     cmd before "exit /b" could report RESULT.
REM "--no-pause" as the 2nd argument, or KCE_NO_PAUSE=1, skips the pause outright
REM (for a scheduler that runs with a hidden console).
if defined KCE_NO_PAUSE goto :done
if /i "%~2"=="--no-pause" goto :done
echo %CMDCMDLINE% | findstr /i /c:"%~nx0" >nul || goto :done
timeout /t 0 >nul 2>&1 || goto :done
echo.
pause
:done
exit /b %RESULT%
