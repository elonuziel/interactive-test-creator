@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul
title Interactive Test Creator - Server ^& Test Launcher

cd /d "%~dp0"
set PORT=8080

:MENU
cls
:: Re-check if port 8080 is currently listening
set SERVER_STARTED=0
netstat -aon | findstr :%PORT% | findstr LISTENING >nul 2>&1
if !errorlevel! equ 0 set SERVER_STARTED=1

echo ===============================================================
echo   Interactive Hebrew Test Creator - Server ^& Test Suite Launcher
echo ===============================================================
if !SERVER_STARTED! equ 1 (
    echo   Local Server Status: http://localhost:%PORT% ^(Active^)
) else (
    echo   Local Server Status: Off ^(Starts on demand when selecting 1-3^)
)
echo ===============================================================
echo.
echo   [1] Open In-Browser Component Test Runner (test_runner.html)
echo   [2] Open Web Quiz Builder (web/index.html)
echo   [3] Open Web Quiz Player (web/quiz_player.html)
echo   [4] Run Local CLI Test Suite (test-suite/run_local_tests.py)
echo   [5] Launch Python Desktop/CLI Quiz Builder (start_app.bat)
echo   [S] Start / Verify Local HTTP Server Status
echo   [Q] Stop Server ^& Quit
echo.
echo ===============================================================
set /p CHOICE="Choose an option (1-5, S, Q): "

if /i "%CHOICE%"=="1" (
    call :ENSURE_SERVER
    if !SERVER_STARTED! equ 1 (
        start "" "http://localhost:%PORT%/test-suite/test_runner.html"
    ) else (
        start "" "%~dp0test-suite\test_runner.html"
    )
    goto MENU
)
if /i "%CHOICE%"=="2" (
    call :ENSURE_SERVER
    if !SERVER_STARTED! equ 1 (
        start "" "http://localhost:%PORT%/web/index.html"
    ) else (
        start "" "%~dp0web\index.html"
    )
    goto MENU
)
if /i "%CHOICE%"=="3" (
    call :ENSURE_SERVER
    if !SERVER_STARTED! equ 1 (
        start "" "http://localhost:%PORT%/web/quiz_player.html"
    ) else (
        start "" "%~dp0web\quiz_player.html"
    )
    goto MENU
)
if /i "%CHOICE%"=="4" (
    echo.
    echo ---------------------------------------------------------------
    echo Running Local CLI Test Suite...
    echo ---------------------------------------------------------------
    set "RUN_PY="
    if exist "%~dp0.venv\Scripts\python.exe" set "RUN_PY=%~dp0.venv\Scripts\python.exe"
    if exist "%~dp0venv\Scripts\python.exe" set "RUN_PY=%~dp0venv\Scripts\python.exe"
    if exist "%~dp0desktop\.venv\Scripts\python.exe" set "RUN_PY=%~dp0desktop\.venv\Scripts\python.exe"
    if "!RUN_PY!"=="" (
        where python >nul 2>nul
        if !errorlevel! equ 0 set "RUN_PY=python"
    )
    if "!RUN_PY!"=="" (
        where py >nul 2>nul
        if !errorlevel! equ 0 set "RUN_PY=py"
    )
    
    if not "!RUN_PY!"=="" (
        !RUN_PY! test-suite\run_local_tests.py
    ) else (
        echo [X] Python runtime not found.
    )
    echo.
    pause
    goto MENU
)
if /i "%CHOICE%"=="5" (
    echo.
    echo ---------------------------------------------------------------
    echo Launching Python Desktop/CLI Builder...
    echo ---------------------------------------------------------------
    call start_app.bat
    goto MENU
)
if /i "%CHOICE%"=="S" (
    call :ENSURE_SERVER
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

:: ===============================================================
:: Subroutine: ENSURE_SERVER
:: Checks if port 8080 is listening; if not, starts HTTP server.
:: ===============================================================
:ENSURE_SERVER
netstat -aon | findstr :%PORT% | findstr LISTENING >nul 2>&1
if !errorlevel! equ 0 (
    set SERVER_STARTED=1
    exit /b 0
)

echo.
echo [INFO] Starting local HTTP server on port %PORT%...

set "SERVER_CMD="
if exist "%~dp0.venv\Scripts\python.exe" set "SERVER_CMD=%~dp0.venv\Scripts\python.exe -m http.server %PORT%"
if "!SERVER_CMD!"=="" if exist "%~dp0venv\Scripts\python.exe" set "SERVER_CMD=%~dp0venv\Scripts\python.exe -m http.server %PORT%"

if "!SERVER_CMD!"=="" (
    where python >nul 2>nul
    if !errorlevel! equ 0 set "SERVER_CMD=python -m http.server %PORT%"
)

if "!SERVER_CMD!"=="" (
    where py >nul 2>nul
    if !errorlevel! equ 0 set "SERVER_CMD=py -m http.server %PORT%"
)

if "!SERVER_CMD!"=="" (
    where npx >nul 2>nul
    if !errorlevel! equ 0 set "SERVER_CMD=npx serve -p %PORT% ."
)

if not "!SERVER_CMD!"=="" (
    echo [INFO] Detected server runtime. Executing: !SERVER_CMD! ...
    start /b "" !SERVER_CMD! >nul 2>&1
    ping 127.0.0.1 -n 3 >nul
    netstat -aon | findstr :%PORT% | findstr LISTENING >nul 2>&1
    if !errorlevel! equ 0 (
        echo [INFO] Server launched successfully on http://localhost:%PORT%
        set SERVER_STARTED=1
    ) else (
        echo [WARNING] Local HTTP server is not listening on port %PORT%.
        set SERVER_STARTED=0
    )
) else (
    echo [WARNING] Neither Python nor Node/npx was found on PATH.
    set SERVER_STARTED=0
)
exit /b 0




