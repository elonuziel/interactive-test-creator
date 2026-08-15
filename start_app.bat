@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
cd /d "%~dp0"

title Interactive Hebrew Quiz Builder — Desktop App

:: Detect Python executable
set "PYTHON_EXE="
if exist "%~dp0.venv\Scripts\python.exe" set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if "!PYTHON_EXE!"=="" if exist "%~dp0venv\Scripts\python.exe" set "PYTHON_EXE=%~dp0venv\Scripts\python.exe"
if "!PYTHON_EXE!"=="" if exist "%~dp0cli-legacy\.venv\Scripts\python.exe" set "PYTHON_EXE=%~dp0cli-legacy\.venv\Scripts\python.exe"

if "!PYTHON_EXE!"=="" (
    where python >nul 2>nul
    if !errorlevel! equ 0 set "PYTHON_EXE=python"
)

if "!PYTHON_EXE!"=="" (
    where py >nul 2>nul
    if !errorlevel! equ 0 set "PYTHON_EXE=py"
)

if not "!PYTHON_EXE!"=="" (
    "!PYTHON_EXE!" "%~dp0cli-legacy\quiz_builder_gui.py" %*
    if !errorlevel! neq 0 (
        echo.
        echo [X] Desktop app closed with code !errorlevel!. Press any key to exit.
        pause >nul
    )
) else (
    echo.
    echo [X] Python 3 was not found on your PATH or in a local virtual environment.
    echo     Please install Python 3.8+ to run the Desktop Quiz Builder App.
    echo.
    pause
)
