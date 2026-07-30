@echo off
setlocal enabledelayedexpansion
title Interactive Test Creator - Server ^& Test Launcher

cd /d "%~dp0"

echo ===============================================================
echo   Interactive Hebrew Test Creator - Server ^& Test Suite
echo ===============================================================
echo.

set PORT=8080
set SERVER_STARTED=0

:: Check if port 8080 is already listening
netstat -aon | findstr :8080 | findstr LISTENING >nul 2>&1
if !errorlevel! equ 0 (
    echo [INFO] Local server is already running on http://localhost:%PORT%
    set SERVER_STARTED=1
) else (
    set "SERVER_CMD="
    where python >nul 2>nul
    if !errorlevel! equ 0 set "SERVER_CMD=python -m http.server %PORT%"
    
    if "!SERVER_CMD!"=="" (
        where py >nul 2>nul
        if !errorlevel! equ 0 set "SERVER_CMD=py -m http.server %PORT%"
    )
    
    if "!SERVER_CMD!"=="" (
        where npx >nul 2>nul
        if !errorlevel! equ 0 set "SERVER_CMD=npx serve -p %PORT% ."
    )
    
    if not "!SERVER_CMD!"=="" (
        echo [INFO] Detected server runtime. Starting: !SERVER_CMD! ...
        start /b "" !SERVER_CMD! >nul 2>&1
    ) else (
        echo [WARNING] Neither Python nor Node/npx was found on PATH.
    )
    
    :: Wait 2 seconds using fail-safe ping
    ping 127.0.0.1 -n 3 >nul
    
    :: Re-verify if server actually started
    netstat -aon | findstr :8080 | findstr LISTENING >nul 2>&1
    if !errorlevel! equ 0 (
        echo [INFO] Server launched successfully on http://localhost:%PORT%
        set SERVER_STARTED=1
    ) else (
        echo [WARNING] Local HTTP server is not listening on port %PORT%.
        echo Opening local files directly in default browser...
        set SERVER_STARTED=0
    )
)

:: Open Test Runner in default browser on first launch
echo [INFO] Opening Component Test Runner in browser...
if !SERVER_STARTED! equ 1 (
    start "" "http://localhost:%PORT%/test-suite/test_runner.html"
) else (
    start "" "%~dp0test-suite\test_runner.html"
)

:MENU
cls
echo ===============================================================
echo   Interactive Hebrew Test Creator - Server ^& Test Suite Launcher
echo ===============================================================
if !SERVER_STARTED! equ 1 (
    echo   Local Server: http://localhost:%PORT% ^(Active^)
) else (
    echo   Local Server: Off ^(Opening direct file:// links^)
)
echo ===============================================================
echo.
echo   [1] Open In-Browser Component Test Runner (test_runner.html)
echo   [2] Open Quiz Builder (index.html)
echo   [3] Open Quiz Player (quiz_player.html)
echo   [4] Run Local CLI Test Suite (run_local_tests.py)
echo   [Q] Stop Server ^& Quit
echo.
echo ===============================================================
set /p CHOICE="Choose an option (1-4, Q): "

if /i "%CHOICE%"=="1" (
    if !SERVER_STARTED! equ 1 (
        start "" "http://localhost:%PORT%/test-suite/test_runner.html"
    ) else (
        start "" "%~dp0test-suite\test_runner.html"
    )
    goto MENU
)
if /i "%CHOICE%"=="2" (
    if !SERVER_STARTED! equ 1 (
        start "" "http://localhost:%PORT%/index.html"
    ) else (
        start "" "%~dp0index.html"
    )
    goto MENU
)
if /i "%CHOICE%"=="3" (
    if !SERVER_STARTED! equ 1 (
        start "" "http://localhost:%PORT%/quiz_player.html"
    ) else (
        start "" "%~dp0quiz_player.html"
    )
    goto MENU
)
if /i "%CHOICE%"=="4" (
    echo.
    echo ---------------------------------------------------------------
    echo Running Local CLI Test Suite...
    echo ---------------------------------------------------------------
    where python >nul 2>nul
    if !errorlevel! equ 0 (
        python test-suite\run_local_tests.py
    ) else (
        py test-suite\run_local_tests.py
    )
    echo.
    pause
    goto MENU
)
if /i "%CHOICE%"=="Q" (
    echo.
    echo Stopping local server...
    for /f "tokens=5" %%a in ('netstat -aon ^| findstr :%PORT% ^| findstr LISTENING') do (
        taskkill /PID %%a /F >nul 2>&1
    )
    echo Goodbye!
    exit /b 0
)

goto MENU


