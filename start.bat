@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title Interactive Hebrew Quiz Builder - Desktop GUI

cd /d "%~dp0"

set "RUN_PY="
if exist "%~dp0quiz-builder-app\.venv\Scripts\python.exe" set "RUN_PY=%~dp0quiz-builder-app\.venv\Scripts\python.exe"
if "!RUN_PY!"=="" if exist "%~dp0.venv\Scripts\python.exe" set "RUN_PY=%~dp0.venv\Scripts\python.exe"
if "!RUN_PY!"=="" if exist "%~dp0venv\Scripts\python.exe" set "RUN_PY=%~dp0venv\Scripts\python.exe"
if "!RUN_PY!"=="" (
    where python >nul 2>nul
    if !errorlevel! equ 0 set "RUN_PY=python"
)
if "!RUN_PY!"=="" (
    where py >nul 2>nul
    if !errorlevel! equ 0 set "RUN_PY=py"
)

if not "!RUN_PY!"=="" (
    set "PYTHONPATH=%~dp0quiz-builder-app\src;!PYTHONPATH!"
    start "" "!RUN_PY!" -m quizbuilder.gui %*
) else (
    echo [ERROR] Python runtime was not found. Please install Python 3.11+ or create a virtual environment.
    pause
)

