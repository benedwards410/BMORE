@echo off
REM KCE Document Intake Pipeline launcher.
REM Handles the two things that trip up a bare "python -m kce_pipeline":
REM   1. "python" on this machine hits the Microsoft Store alias -- use the py launcher.
REM   2. -m kce_pipeline must run with the kce-pipeline folder as the working directory.
REM
REM Usage from anywhere:
REM   kce.cmd --check-api
REM   kce.cmd "C:\path\to\a_project_folder"
setlocal
cd /d "%~dp0" || exit /b 1
py -m kce_pipeline %*
exit /b %ERRORLEVEL%
