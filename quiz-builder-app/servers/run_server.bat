@echo off
setlocal
cd /d "%~dp0\.."
set "PYTHONPATH=%~dp0..\src;%PYTHONPATH%"

where python >nul 2>nul
if errorlevel 1 (
    echo Error: Python 3 is required but was not found on PATH.
    exit /b 1
)

python -m quizbuilder serve --port 8000
