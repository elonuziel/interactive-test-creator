@echo off
setlocal
cd /d "%~dp0"

title Interactive Hebrew Quiz Builder

:: Check if compiled standalone executable exists
if exist "%~dp0dist\quiz_builder.exe" (
    "%~dp0dist\quiz_builder.exe" %*
    exit /b %errorlevel%
)

if exist "%~dp0..\dist\quiz_builder.exe" (
    "%~dp0..\dist\quiz_builder.exe" %*
    exit /b %errorlevel%
)

:: Otherwise execute Python CLI wizard script
python "%~dp0quiz_builder_cli.py" %*
if errorlevel 1 (
    echo.
    echo [X] Execution failed or Python is missing. Press any key to exit.
    pause >nul
)
