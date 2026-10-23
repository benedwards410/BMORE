@echo off
rem Pull new documents from Outlook + the drop folder, file them per MTX, then
rem run the pipeline on every project whose inputs changed. Safe to run from
rem Task Scheduler: it holds a lock, never pauses, and returns the pipeline's
rem exit-code convention (0 clean, 1 critical flags outstanding, 2+ tool failure).
setlocal
cd /d "%~dp0"
py -m kce_intake sync
set "SYNC=%ERRORLEVEL%"
py -m kce_intake run-changed
set "RUN=%ERRORLEVEL%"
if %SYNC% GEQ 2 exit /b %SYNC%
exit /b %RUN%
