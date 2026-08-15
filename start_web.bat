@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
cd /d "%~dp0"

title Interactive Hebrew Quiz Builder — Web App

echo ===============================================================
echo   Launching Interactive Hebrew Quiz Builder (Web App)
echo ===============================================================

:: Detect Python executable to serve via HTTP
set "PYTHON_EXE="
if exist "%~dp0.venv\Scripts\python.exe" set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if exist "%~dp0venv\Scripts\python.exe" set "PYTHON_EXE=%~dp0venv\Scripts\python.exe"
if exist "%~dp0desktop\.venv\Scripts\python.exe" set "PYTHON_EXE=%~dp0desktop\.venv\Scripts\python.exe"

if "!PYTHON_EXE!"=="" (
    where python >nul 2>nul
    if !errorlevel! equ 0 set "PYTHON_EXE=python"
)

if "!PYTHON_EXE!"=="" (
    where py >nul 2>nul
    if !errorlevel! equ 0 set "PYTHON_EXE=py"
)

if not "!PYTHON_EXE!"=="" (
    echo Starting local web server at http://localhost:8080 ...
    start "" "http://localhost:8080/web/index.html"
    "!PYTHON_EXE!" -m http.server 8080 --directory "%~dp0."
) else (
    echo Opening web app directly in default browser...
    start "" "%~dp0web\index.html"
)
