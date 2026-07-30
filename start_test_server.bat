@echo off
setlocal enabledelayedexpansion
title Interactive Test Creator - Server & Test Launcher

cd /d "%~dp0"

echo ===============================================================
echo   Interactive Hebrew Test Creator - Server & Test Suite
echo ===============================================================
echo.

:: Detect Python or Node/Npx
where python >nul 2>nul
if %errorlevel% equ 0 (
    echo [INFO] Detected Python. Starting local server on http://localhost:8080 ...
    start /b "" python -m http.server 8080 >nul 2>&1
    set SERVER_STARTED=1
) else (
    where npx >nul 2>nul
    if !errorlevel! equ 0 (
        echo [INFO] Detected Node/npx. Starting serve on http://localhost:8080 ...
        start /b "" npx serve -p 8080 . >nul 2>&1
        set SERVER_STARTED=1
    ) else (
        echo [WARNING] Neither Python nor Node/npx was found on PATH.
        echo Opening local files directly in default browser...
    )
)

:: Wait 1.5s for server startup
timeout /t 2 /nobreak >nul

:: Open Test Runner in default browser
echo [INFO] Opening Component Test Runner in browser...
start http://localhost:8080/test-suite/test_runner.html

:MENU
cls
echo ===============================================================
echo   Interactive Hebrew Test Creator - Server & Test Suite Launcher
echo ===============================================================
echo   Local Server: http://localhost:8080
echo ===============================================================
echo.
echo   [1] Open In-Browser Component Test Runner (test_runner.html)
echo   [2] Open Quiz Builder (index.html)
echo   [3] Open Quiz Player (quiz_player.html)
echo   [4] Re-open Test Runner
echo   [Q] Stop Server & Quit
echo.
echo ===============================================================
set /p CHOICE="Choose an option (1-4, Q): "

if /i "%CHOICE%"=="1" (
    start http://localhost:8080/test-suite/test_runner.html
    goto MENU
)
if /i "%CHOICE%"=="2" (
    start http://localhost:8080/index.html
    goto MENU
)
if /i "%CHOICE%"=="3" (
    start http://localhost:8080/quiz_player.html
    goto MENU
)
if /i "%CHOICE%"=="4" (
    start http://localhost:8080/test-suite/test_runner.html
    goto MENU
)
if /i "%CHOICE%"=="Q" (
    echo.
    echo Stopping local server...
    taskkill /FI "WINDOWTITLE eq Interactive Test Creator*" /F >nul 2>&1
    for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8080 ^| findstr LISTENING') do (
        taskkill /PID %%a /F >nul 2>&1
    )
    echo Goodbye!
    exit /b 0
)

goto MENU
