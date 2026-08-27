@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
cd /d "%~dp0"

title Interactive Hebrew Quiz Builder

:: 1. Check if compiled standalone executable exists
if exist "%~dp0dist\quiz_builder.exe" (
    "%~dp0dist\quiz_builder.exe" %*
    exit /b !errorlevel!
)

if exist "%~dp0..\dist\quiz_builder.exe" (
    "%~dp0..\dist\quiz_builder.exe" %*
    exit /b !errorlevel!
)

:: 2. Detect Python executable (virtual environment or system python / py)
set "PYTHON_EXE="

if exist "%~dp0.venv\Scripts\python.exe" set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if "!PYTHON_EXE!"=="" if exist "%~dp0venv\Scripts\python.exe" set "PYTHON_EXE=%~dp0venv\Scripts\python.exe"
if "!PYTHON_EXE!"=="" if exist "%~dp0..\.venv\Scripts\python.exe" set "PYTHON_EXE=%~dp0..\.venv\Scripts\python.exe"

if "!PYTHON_EXE!"=="" (
    where python >nul 2>nul
    if !errorlevel! equ 0 set "PYTHON_EXE=python"
)

if "!PYTHON_EXE!"=="" (
    where py >nul 2>nul
    if !errorlevel! equ 0 set "PYTHON_EXE=py"
)

:: 3. Execute Python CLI wizard script
if not "!PYTHON_EXE!"=="" (
    set "PYTHONPATH=%~dp0src;!PYTHONPATH!"
    "!PYTHON_EXE!" -m quizbuilder %*
    if !errorlevel! neq 0 (
        echo.
        echo [X] Execution failed with error code !errorlevel!. Press any key to exit.
        pause >nul
    )
) else (
    echo.
    echo [X] Python was not found on system PATH or in a local .venv folder.
    echo     Please install Python 3.8+ or set up a virtual environment.
    echo.
    pause
)

