@echo off
setlocal enabledelayedexpansion

:: ══════════════════════════════════════════════════════════════════════════════
:: start.bat - Interactive Quiz Builder Wizard
:: Walks users through the entire workflow: setup, extraction, and building.
:: ══════════════════════════════════════════════════════════════════════════════

:: Navigate to repo root (in case script is double-clicked from Explorer)
cd /d "%~dp0"

title Interactive Quiz Builder

echo.
echo  ===========================================================
echo     Interactive Hebrew Quiz Builder - Setup Wizard
echo  ===========================================================
echo.

:: ---------------------------------------------------------------------------
:: STEP 1: Check Python
:: ---------------------------------------------------------------------------
echo  [Step 1/5] Checking prerequisites...
echo  -------------------------------------

python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  ERROR: Python is not installed or not on PATH.
    echo     Please install Python from https://python.org
    echo     Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo   OK - %PYVER% found

:: ---------------------------------------------------------------------------
:: STEP 1b: Check and install pip packages
:: ---------------------------------------------------------------------------
set "MISSING_PKGS="

python -c "import fitz" >nul 2>&1
if errorlevel 1 set "MISSING_PKGS=!MISSING_PKGS! pymupdf"

python -c "import pandas" >nul 2>&1
if errorlevel 1 set "MISSING_PKGS=!MISSING_PKGS! pandas"

python -c "import openpyxl" >nul 2>&1
if errorlevel 1 set "MISSING_PKGS=!MISSING_PKGS! openpyxl"

if not "!MISSING_PKGS!"=="" (
    echo.
    echo   WARNING: Missing packages:!MISSING_PKGS!
    echo.
    set /p INSTALL_CHOICE="   Install them now? (Y/n): "
    if /i "!INSTALL_CHOICE!"=="n" (
        echo.
        echo   Skipping package installation. Some pipeline steps may fail.
    ) else (
        echo.
        echo   Installing packages...
        pip install !MISSING_PKGS! --quiet
        if errorlevel 1 (
            echo   WARNING: Some packages failed to install. You may need to run:
            echo      pip install!MISSING_PKGS!
        ) else (
            echo   OK - All packages installed successfully
        )
    )
) else (
    echo   OK - All required packages are installed
)

echo.

:: ---------------------------------------------------------------------------
:: STEP 2: Create or select a test folder
:: ---------------------------------------------------------------------------
echo  [Step 2/5] Test folder setup
echo  -------------------------------------
echo.

:: Check if tests/ exists, create if not
if not exist "tests" (
    echo   Creating tests\ directory...
    mkdir "tests"
    echo   OK - tests\ created
    echo.
)

:: List existing test folders
set "HAS_TESTS=0"
for /d %%d in (tests\*) do (
    if exist "%%d\questions.json" (
        set "HAS_TESTS=1"
    )
)

:: Show existing tests if any
set "TEST_COUNT=0"
echo   Existing test folders:
for /d %%d in (tests\*) do (
    set /a TEST_COUNT+=1
    if exist "%%d\questions.json" (
        echo     !TEST_COUNT!. %%~nxd  [READY - questions.json exists]
    ) else (
        echo     !TEST_COUNT!. %%~nxd  [PENDING - needs processing]
    )
)

if !TEST_COUNT!==0 (
    echo     (none^)
)

echo.
echo   What would you like to do?
echo     [N] Create a NEW test folder
if !HAS_TESTS!==1 (
    echo     [B] BUILD a single HTML from an existing test
    echo     [S] START the server with all tests
)
echo     [Q] Quit
echo.
set /p ACTION="   Your choice: "

if /i "!ACTION!"=="q" goto :end
if /i "!ACTION!"=="s" goto :start_server
if /i "!ACTION!"=="b" goto :build_html
if /i "!ACTION!"=="n" goto :create_test
:: Default to creating a new test
goto :create_test


:: ===========================================================================
:: CREATE NEW TEST
:: ===========================================================================
:create_test
echo.
echo  [Step 3/5] Creating new test
echo  -------------------------------------
echo.
echo   Enter a name for your test folder.
echo   Examples: 2024_moed_a, botany_final, bio_exam_3
echo.
set /p TEST_NAME="   Test name: "

if "!TEST_NAME!"=="" (
    echo   No name entered. Using 'test_1'.
    set "TEST_NAME=test_1"
)

:: Clean the name (replace spaces with underscores)
set "TEST_NAME=!TEST_NAME: =_!"
set "TEST_DIR=tests\!TEST_NAME!"

if exist "!TEST_DIR!" (
    echo.
    echo   NOTE: Folder !TEST_DIR! already exists.
    if exist "!TEST_DIR!\questions.json" (
        echo   OK - questions.json already exists. Skipping to build step.
        goto :post_process
    )
    echo   Continuing with existing folder...
) else (
    mkdir "!TEST_DIR!"
    echo.
    echo   OK - Created: !TEST_DIR!\
)

:: ---------------------------------------------------------------------------
:: STEP 3b: Drop files
:: ---------------------------------------------------------------------------
echo.
echo  ===========================================================
echo                     DROP YOUR FILES
echo  ===========================================================
echo.
echo   A folder will open in Explorer.
echo   Please drop these files into it:
echo.
echo     1. exam.pdf    - Your exam PDF file
echo     2. answers.csv - Answer key (CSV or Excel .xlsx^)
echo.
echo   Then come back here and press any key to continue.
echo  ===========================================================
echo.

:: Open the folder in Explorer
start "" explorer "!TEST_DIR!"

pause

:: Verify files were dropped
set "HAS_PDF=0"
set "HAS_ANSWERS=0"
for %%f in ("!TEST_DIR!\*.pdf") do set "HAS_PDF=1"
for %%f in ("!TEST_DIR!\*.csv") do set "HAS_ANSWERS=1"
for %%f in ("!TEST_DIR!\*.xlsx") do set "HAS_ANSWERS=1"
for %%f in ("!TEST_DIR!\*.xls") do set "HAS_ANSWERS=1"

if !HAS_PDF!==0 (
    echo   WARNING: No PDF file found in !TEST_DIR!
    echo     The AI agent will still try to process the folder.
)
if !HAS_ANSWERS!==0 (
    echo   NOTE: No answer key file found (CSV/Excel^).
    echo     The agent can still extract questions without answers.
)
if !HAS_PDF!==1 echo   OK - PDF file found
if !HAS_ANSWERS!==1 echo   OK - Answer key file found
echo.

:: ---------------------------------------------------------------------------
:: STEP 4: Launch AI Agent
:: ---------------------------------------------------------------------------
echo  [Step 4/5] Launching AI agent for extraction
echo  -------------------------------------
echo.
echo   The extraction pipeline needs an AI agent to read the PDF
echo   and run the steps in LLM_RUNBOOK.md.
echo.

:: Build the prompt for the agent
set "AGENT_PROMPT=Read LLM_RUNBOOK.md and follow it to process the test in !TEST_DIR!/ -- extract questions from the PDF, parse them into questions.json, and merge the answer key. Work through all steps."

:: Try to detect available agents
set "AGENT_FOUND=0"
set "AGENT_LAUNCHED=0"

:: Check for agy (Gemini CLI)
where agy >nul 2>&1
if not errorlevel 1 (
    set "AGENT_FOUND=1"
    echo   FOUND: agy (Gemini CLI^)
    echo.
    set /p USE_AGY="   Launch agy to process the test? (Y/n): "
    if /i not "!USE_AGY!"=="n" (
        echo.
        echo   Starting agy...
        echo   -------------------------------------
        start "" cmd /k "cd /d "%~dp0" && agy "!AGENT_PROMPT!""
        set "AGENT_LAUNCHED=1"
        goto :wait_for_questions
    )
)

:: Check for gemini CLI
where gemini >nul 2>&1
if not errorlevel 1 if !AGENT_LAUNCHED!==0 (
    set "AGENT_FOUND=1"
    echo   FOUND: gemini CLI
    echo.
    set /p USE_GEMINI="   Launch gemini to process the test? (Y/n): "
    if /i not "!USE_GEMINI!"=="n" (
        echo.
        echo   Starting gemini...
        start "" cmd /k "cd /d "%~dp0" && gemini "!AGENT_PROMPT!""
        set "AGENT_LAUNCHED=1"
        goto :wait_for_questions
    )
)

:: Check for claude CLI
where claude >nul 2>&1
if not errorlevel 1 if !AGENT_LAUNCHED!==0 (
    set "AGENT_FOUND=1"
    echo   FOUND: claude CLI
    echo.
    set /p USE_CLAUDE="   Launch claude to process the test? (Y/n): "
    if /i not "!USE_CLAUDE!"=="n" (
        echo.
        echo   Starting claude...
        start "" cmd /k "cd /d "%~dp0" && claude "!AGENT_PROMPT!""
        set "AGENT_LAUNCHED=1"
        goto :wait_for_questions
    )
)

:: Check for VS Code
where code >nul 2>&1
if not errorlevel 1 (
    set "AGENT_FOUND=1"
    echo   FOUND: VS Code (use Copilot Chat inside^)
)

:: Check for Cursor
where cursor >nul 2>&1
if not errorlevel 1 (
    set "AGENT_FOUND=1"
    echo   FOUND: Cursor IDE
)

:: Show manual instructions
echo.
echo  ===========================================================
echo               AI AGENT INSTRUCTIONS
echo  ===========================================================
echo.
echo   Open this project in an AI-powered IDE or CLI:
echo.
echo     - agy (Gemini CLI^)
echo     - gemini CLI
echo     - claude CLI
echo     - VS Code with Copilot
echo     - Cursor IDE
echo     - Antigravity IDE
echo     - Google AI Studio
echo.
echo   Then paste this prompt:
echo.
echo   ---
echo   %AGENT_PROMPT%
echo   ---
echo.

:: Copy prompt to clipboard
echo %AGENT_PROMPT%| clip
echo   OK - Prompt copied to clipboard!
echo.

:wait_for_questions
echo   Waiting for the AI agent to create questions.json...
echo   (Press any key once the agent has finished processing^)
echo.
pause

:: Check if questions.json was created
if exist "!TEST_DIR!\questions.json" (
    echo.
    echo   OK - questions.json found in !TEST_DIR!
    goto :post_process
)

:: Also check for final_questions.json
if exist "!TEST_DIR!\final_questions.json" (
    echo.
    echo   OK - final_questions.json found. Renaming to questions.json...
    move "!TEST_DIR!\final_questions.json" "!TEST_DIR!\questions.json" >nul
    goto :post_process
)

echo.
echo   WARNING: questions.json not found yet in !TEST_DIR!
echo   The agent may still be working. You can:
echo     1. Wait and press any key when the agent is done
echo     2. Press Ctrl+C to exit and run start.bat again later
echo.
pause

if exist "!TEST_DIR!\questions.json" goto :post_process
if exist "!TEST_DIR!\final_questions.json" (
    move "!TEST_DIR!\final_questions.json" "!TEST_DIR!\questions.json" >nul
    goto :post_process
)

echo   ERROR: questions.json still not found. Please run start.bat again
echo      after the agent completes processing.
goto :end


:: ===========================================================================
:: POST-PROCESS: Build HTML or start server
:: ===========================================================================
:post_process
echo.
echo  [Step 5/5] What would you like to do with the quiz?
echo  -------------------------------------
echo.
echo   [H] Build a SINGLE HTML file (double-click to open, no server^)
echo   [S] Start the SERVER (opens all tests in browser^)
echo   [B] Do BOTH
echo   [Q] Quit
echo.
set /p POST_CHOICE="   Your choice: "

if /i "!POST_CHOICE!"=="s" goto :start_server
if /i "!POST_CHOICE!"=="b" goto :build_and_serve
if /i "!POST_CHOICE!"=="q" goto :end
:: Default to build single
goto :build_single


:build_single
echo.
echo   Building single-file HTML...
set "OUTPUT_FILE=!TEST_NAME!_quiz.html"
python python_scripts\9_build_single_html.py "!TEST_DIR!" -o "!OUTPUT_FILE!"

if exist "!OUTPUT_FILE!" (
    echo.
    echo  ===========================================================
    echo                    BUILD COMPLETE
    echo  ===========================================================
    echo.
    echo   Your quiz is ready: !OUTPUT_FILE!
    echo.
    echo   Double-click the file to start the quiz.
    echo   You can share it via email, USB, or WhatsApp.
    echo.
    set /p OPEN_FILE="   Open the quiz now? (Y/n): "
    if /i not "!OPEN_FILE!"=="n" (
        start "" "!OUTPUT_FILE!"
    )
) else (
    echo   ERROR: Build failed. Check the error messages above.
)
goto :end


:build_html
echo.
echo   Which test folder would you like to build?
echo.
set "IDX=0"
for /d %%d in (tests\*) do (
    if exist "%%d\questions.json" (
        set /a IDX+=1
        set "TEST_OPTION_!IDX!=%%d"
        set "TEST_OPTNAME_!IDX!=%%~nxd"
        echo     !IDX!. %%~nxd
    )
)
if !IDX!==0 (
    echo   No test folders with questions.json found.
    goto :end
)
echo.
set /p BUILD_CHOICE="   Enter number: "
set "TEST_DIR=!TEST_OPTION_%BUILD_CHOICE%!"
set "TEST_NAME=!TEST_OPTNAME_%BUILD_CHOICE%!"
if "!TEST_DIR!"=="" (
    echo   ERROR: Invalid selection.
    goto :end
)
goto :build_single


:build_and_serve
call :build_single
goto :start_server


:start_server
echo.
echo   Generating test manifest...
python python_scripts\8_generate_manifest.py
echo.
echo   Starting server...
echo   Opening http://localhost:8000/web/index.html
echo.
start http://localhost:8000/web/index.html
python -m http.server 8000
goto :end


:: ===========================================================================
:end
echo.
echo  Done. Goodbye!
echo.
pause
endlocal
