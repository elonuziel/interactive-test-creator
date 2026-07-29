@echo off
setlocal enabledelayedexpansion

:: ===========================================================================
:: start.bat - Interactive Quiz Builder Wizard
:: Walks users through the entire workflow: setup, extraction, and building.
:: ===========================================================================

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

:: Check if tests\ exists, create if not
if not exist "tests" (
    echo   Creating tests\ directory...
    mkdir "tests"
    echo   OK - tests\ created
    echo.
)

:select_test_step
:: List existing test folders
set "HAS_TESTS=0"
set "HAS_READY_TESTS=0"
set "TEST_COUNT=0"

echo   Existing test folders:
for /d %%d in (tests\*) do (
    set /a TEST_COUNT+=1
    set "TEST_OPT_PATH_!TEST_COUNT!=%%d"
    set "TEST_OPT_NAME_!TEST_COUNT!=%%~nxd"
    set "HAS_TESTS=1"
    
    if exist "%%d\questions.json" (
        set "TEST_OPT_READY_!TEST_COUNT!=1"
        set "HAS_READY_TESTS=1"
        echo     !TEST_COUNT!. %%~nxd  [READY - questions.json exists]
    ) else (
        set "TEST_OPT_READY_!TEST_COUNT!=0"
        echo     !TEST_COUNT!. %%~nxd  [PENDING - needs processing]
    )
)

if !TEST_COUNT!==0 (
    echo     (none^)
)

echo.
echo   What would you like to do?
if !TEST_COUNT! GTR 0 (
    echo     [1-!TEST_COUNT!] Select an existing test folder above
)
echo     [N] Create a NEW test folder
if !HAS_READY_TESTS!==1 (
    echo     [B] BUILD a single HTML from a ready test
    echo     [S] START the server with all tests
)
echo     [Q] Quit
echo.

:get_action_choice
set "ACTION="
set /p ACTION="   Your choice: "

if "!ACTION!"=="" goto :invalid_choice
if /i "!ACTION!"=="q" goto :end
if /i "!ACTION!"=="n" goto :create_test
if /i "!ACTION!"=="s" goto :start_server
if /i "!ACTION!"=="b" goto :build_html

:: Check if user entered a number corresponding to an existing test folder
set "IS_NUMERIC=1"
for /f "delims=0123456789" %%i in ("!ACTION!") do set "IS_NUMERIC=0"

if !IS_NUMERIC!==1 (
    if !ACTION! GEQ 1 if !ACTION! LEQ !TEST_COUNT! (
        set "TEST_DIR=!TEST_OPT_PATH_%ACTION%!"
        set "TEST_NAME=!TEST_OPT_NAME_%ACTION%!"
        set "IS_READY=!TEST_OPT_READY_%ACTION%!"
        
        echo.
        echo   Selected: !TEST_NAME!
        if !IS_READY!==1 (
            echo   Status: READY ^(questions.json exists^)
            echo.
            echo   What would you like to do with !TEST_NAME!?
            echo     [1] Build single HTML quiz
            echo     [2] Re-process with AI agent ^(re-extract^)
            echo     [B] Back to main menu
            echo.
            set /p EXISTING_CHOICE="   Choice (1/2/b): "
            if "!EXISTING_CHOICE!"=="1" goto :build_single
            if "!EXISTING_CHOICE!"=="2" goto :drop_files_check
            if /i "!EXISTING_CHOICE!"=="b" goto :select_test_step
            goto :build_single
        ) else (
            echo   Status: PENDING ^(needs processing^)
            goto :drop_files_check
        )
    )
)

:invalid_choice
echo.
echo  ===========================================================
echo    ERROR: '!ACTION!' is not a valid choice.
if !TEST_COUNT! GTR 0 (
    echo    Please enter a number (1-!TEST_COUNT!), 'N', 'S', or 'Q'.
) else (
    echo    Please enter 'N', 'S', or 'Q'.
)
echo  ===========================================================
echo.
goto :get_action_choice


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
:: STEP 3b: Check or Drop files
:: ---------------------------------------------------------------------------
:drop_files_check
set "HAS_PDF=0"
set "HAS_ANSWERS=0"
set "PDF_NAME="
set "ANSWERS_NAME="

for %%f in ("!TEST_DIR!\*.pdf") do (
    set "HAS_PDF=1"
    set "PDF_NAME=%%~nxf"
    set "PDF_FULL_PATH=%%~ff"
)
for %%f in ("!TEST_DIR!\*.csv") do (
    set "HAS_ANSWERS=1"
    set "ANSWERS_NAME=%%~nxf"
)
for %%f in ("!TEST_DIR!\*.xlsx") do (
    set "HAS_ANSWERS=1"
    set "ANSWERS_NAME=%%~nxf"
)
for %%f in ("!TEST_DIR!\*.xls") do (
    set "HAS_ANSWERS=1"
    set "ANSWERS_NAME=%%~nxf"
)

if !HAS_PDF!==1 (
    echo.
    echo   OK - Found PDF file: !PDF_NAME!
    if !HAS_ANSWERS!==1 (
        echo   OK - Found answer key file: !ANSWERS_NAME!
    ) else (
        echo   NOTE: No answer key spreadsheet found (CSV/Excel^).
    )
    echo.
    echo   Proceeding directly to pre-processing...
    echo.
    goto :pre_processing_step
)

:: If NO PDF file is found, prompt user to drop files
echo.
echo  ===========================================================
echo                     DROP YOUR FILES
echo  ===========================================================
echo.
echo   Folder !TEST_DIR!\ does not contain a PDF file yet.
echo   Opening folder in Explorer...
echo.
echo   Please drop these files into it:
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
for %%f in ("!TEST_DIR!\*.pdf") do (
    set "HAS_PDF=1"
    set "PDF_FULL_PATH=%%~ff"
)
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

:pre_processing_step
:: ---------------------------------------------------------------------------
:: STEP 3: PRE-PROCESSING (Automated)
:: ---------------------------------------------------------------------------
echo  [Step 3/5] Running automated pre-processing steps...
echo  -------------------------------------
echo.
if !HAS_PDF!==1 (
    echo   Detecting PDF type...
    python python_scripts\1_detect_pdf_type.py "!PDF_FULL_PATH!" > "!TEST_DIR!\pdf_type_result.txt"
    type "!TEST_DIR!\pdf_type_result.txt"
    
    set "IS_DIGITAL=0"
    findstr /C:"DIGITAL PDF detected" "!TEST_DIR!\pdf_type_result.txt" >nul
    if not errorlevel 1 set "IS_DIGITAL=1"
    
    echo.
    echo   Rendering PDF pages (auto-discarding blank pages & creating clean merged PDF)...
    python python_scripts\3_render_pdf_pages.py "!PDF_FULL_PATH!" -o "!TEST_DIR!\pages_output" --merged-pdf "!TEST_DIR!\!TEST_NAME!_clean.pdf"
    
    if !IS_DIGITAL!==1 (
        echo.
        echo   DIGITAL PDF detected! Automating text extraction...
        python python_scripts\2_extract_text_fitz.py "!PDF_FULL_PATH!" -o "!TEST_DIR!\raw_text.md" --extract-images "!TEST_DIR!\images" --page-map "!TEST_DIR!\page_map.json"
        python python_scripts\5_parse_questions_md.py "!TEST_DIR!\raw_text.md" -o "!TEST_DIR!\questions.json" --image-dir "!TEST_DIR!\images" --page-map "!TEST_DIR!\page_map.json"
        echo   Automated extraction complete!
    )
)

if !HAS_ANSWERS!==1 (
    echo.
    echo   Please enter the Form Number for the answer key ^(e.g., 076, 76, 1^).
    echo   This is required to extract the correct answers from the CSV/Excel.
    echo.
    set /p FORM_NUMBER="   Form Number: "
    if "!FORM_NUMBER!"=="" set "FORM_NUMBER=1"
    echo.
    echo   Extracting answers from CSV...
    python python_scripts\4_extract_csv_answers.py "!TEST_DIR!" "!FORM_NUMBER!"
) else (
    set "FORM_NUMBER=1"
)
echo.
echo   Pre-processing complete!
echo.

:agent_extraction_step
:: ---------------------------------------------------------------------------
:: STEP 4: Launch AI Agent
:: ---------------------------------------------------------------------------
echo  [Step 4/5] Launching AI agent for extraction
echo  -------------------------------------
echo.
if exist "!TEST_DIR!\questions.json" (
    echo   We auto-extracted questions from your digital PDF!
    echo   However, sometimes Hebrew extraction has reversed words or formatting quirks.
    echo.
    set /p PROOF_CHOICE="   Would you like an AI agent to proofread and fix the JSON? (Y/n): "
    if /i "!PROOF_CHOICE!"=="n" (
        goto :post_process
    )
    echo.
    echo   The AI agent will now perform a proofreading pass...
) else (
    echo   The extraction pipeline needs an AI agent to read the rendered images
    echo   and extract the multiple-choice questions into questions.json.
)
echo.

:: Generate prompt files (prompt_local_agent.txt & prompt_web_ai.txt)
python python_scripts\generate_prompts.py "!TEST_DIR!" "!TEST_NAME!" "!FORM_NUMBER!" "!HAS_ANSWERS!" >nul 2>&1

:: Read AGENT_PROMPT from prompt_local_agent.txt and pre-load into Windows Clipboard
if exist "!TEST_DIR!\prompt_local_agent.txt" (
    set /p AGENT_PROMPT=<"!TEST_DIR!\prompt_local_agent.txt"
    type "!TEST_DIR!\prompt_local_agent.txt" | clip
)

:: Try to detect available agents
set "AGENT_FOUND=0"
set "AGENT_LAUNCHED=0"

:: Check for agy (Gemini CLI)
where agy >nul 2>&1
if not errorlevel 1 (
    set "AGENT_FOUND=1"
    echo   FOUND: agy (Gemini CLI^)
    echo.
    set /p USE_AGY="   Launch agy to process the test automatically? (Y/n): "
    if /i not "!USE_AGY!"=="n" (
        echo.
        echo  ===========================================================
        echo            LAUNCHING AGENT: agy (Gemini CLI^)
        echo  ===========================================================
        echo.
        echo   Auto-injecting prompt into agy...
        echo   Command: agy -i "!AGENT_PROMPT!"
        echo.
        echo   What is happening now:
        echo     1. agy is starting in a NEW window with prompt auto-injected.
        echo     2. It will automatically read the images and output questions.json.
        echo     3. Once questions.json is ready, come back here to continue.
        echo.
        echo  ===========================================================
        echo.
        start "" cmd /k "cd /d "%~dp0" && agy -i "!AGENT_PROMPT!""
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
    set /p USE_GEMINI="   Launch gemini to process the test automatically? (Y/n): "
    if /i not "!USE_GEMINI!"=="n" (
        echo.
        echo  ===========================================================
        echo            LAUNCHING AGENT: gemini CLI
        echo  ===========================================================
        echo.
        echo   Command: gemini "!AGENT_PROMPT!"
        echo.
        echo   Starting gemini in a new window with prompt injected...
        echo  ===========================================================
        echo.
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
    set /p USE_CLAUDE="   Launch claude to process the test automatically? (Y/n): "
    if /i not "!USE_CLAUDE!"=="n" (
        echo.
        echo  ===========================================================
        echo            LAUNCHING AGENT: claude CLI
        echo  ===========================================================
        echo.
        echo   Command: claude "!AGENT_PROMPT!"
        echo.
        echo   Starting claude in a new window with prompt injected...
        echo  ===========================================================
        echo.
        start "" cmd /k "cd /d "%~dp0" && claude "!AGENT_PROMPT!""
        set "AGENT_LAUNCHED=1"
        goto :wait_for_questions
    )
)

:: Show interactive prompt selection menu if CLI agent was NOT launched
:prompt_menu
echo.
echo  ===========================================================
echo                 AI AGENT PROMPT ASSISTANT
echo  ===========================================================
echo.
echo   Prompt files generated:
echo     - !TEST_DIR!\prompt_local_agent.txt
echo     - !TEST_DIR!\prompt_web_ai.txt
echo.
echo   Local prompt has been pre-copied to clipboard!
echo.
echo   Which prompt would you like to copy/open?
echo.
echo     [1] LOCAL AGENT PROMPT (agy, gemini, claude, Cursor, VS Code, Antigravity^)
echo         Copies local prompt to clipboard.
echo.
echo     [2] WEB AI PROMPT (ChatGPT, Claude.ai, Gemini Web, AI Studio^)
echo         Copies web prompt to clipboard ^& offers to open browser.
echo.
echo     [3] Display BOTH prompts on screen
echo     [S] Skip prompt assistant
echo.
set /p PROMPT_CHOICE="   Your choice (1/2/3/s): "

if /i "!PROMPT_CHOICE!"=="1" goto :copy_local_prompt
if /i "!PROMPT_CHOICE!"=="2" goto :copy_web_prompt
if /i "!PROMPT_CHOICE!"=="3" goto :show_both_prompts
if /i "!PROMPT_CHOICE!"=="s" goto :wait_for_questions
:: Default to copy local prompt
goto :copy_local_prompt

:copy_local_prompt
type "!TEST_DIR!\prompt_local_agent.txt" | clip
echo.
echo   OK - Copied LOCAL AGENT PROMPT to clipboard!
echo.
echo   --- PROMPT PREVIEW ---
type "!TEST_DIR!\prompt_local_agent.txt"
echo.
echo   ----------------------
goto :wait_for_questions

:copy_web_prompt
type "!TEST_DIR!\prompt_web_ai.txt" | clip
echo.
echo   OK - Copied WEB AI PROMPT to clipboard!
echo.
echo   --- PROMPT PREVIEW ---
type "!TEST_DIR!\prompt_web_ai.txt"
echo.
echo   ----------------------
echo.
echo   Would you like to open a Web AI service in your browser now?
echo     [1] ChatGPT (chatgpt.com^)
echo     [2] Gemini Web (gemini.google.com^)
echo     [3] Claude (claude.ai^)
echo     [4] Google AI Studio (aistudio.google.com^)
echo     [N] No, I will paste manually
echo.
set /p WEB_CHOICE="   Your choice (1/2/3/4/n): "
if "!WEB_CHOICE!"=="1" start https://chatgpt.com
if "!WEB_CHOICE!"=="2" start https://gemini.google.com
if "!WEB_CHOICE!"=="3" start https://claude.ai
if "!WEB_CHOICE!"=="4" start https://aistudio.google.com
echo.
echo   INSTRUCTIONS FOR WEB AI / AI STUDIO:
echo     1. Upload your exam PDF (or rendered images in !TEST_DIR!\pages_output\^).
echo     2. Press Ctrl+V to paste the copied prompt.
echo     3. Save the generated JSON response directly to: !TEST_DIR!\questions.json
echo.
goto :wait_for_questions

:show_both_prompts
echo.
echo  ===========================================================
echo  PROMPT 1: LOCAL AI AGENT (agy / gemini / claude / IDEs^)
echo  ===========================================================
type "!TEST_DIR!\prompt_local_agent.txt"
echo.
echo  ===========================================================
echo  PROMPT 2: WEB AI (ChatGPT / Claude.ai / Gemini Web^)
echo  ===========================================================
type "!TEST_DIR!\prompt_web_ai.txt"
echo.
echo  ===========================================================
echo.
goto :prompt_menu

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
:: POST-PROCESS: Automated Steps and Build HTML
:: ===========================================================================
:post_process
echo.
echo  [Step 5/5] Running automated post-processing...
echo  -------------------------------------
if !HAS_ANSWERS!==1 (
    echo.
    echo   Merging answers into questions.json...
    python python_scripts\6_merge_json_answers.py "!TEST_DIR!"
)

echo.
echo   Running QA checks...
python python_scripts\7_check_json.py "!TEST_DIR!"

echo.
echo   Updating manifest...
python python_scripts\8_generate_manifest.py

echo.
echo   Cleaning up temporary files...
if exist "!TEST_DIR!\answers_extracted.json" del /q "!TEST_DIR!\answers_extracted.json"
if exist "!TEST_DIR!\prompt_local_agent.txt" del /q "!TEST_DIR!\prompt_local_agent.txt"
if exist "!TEST_DIR!\prompt_web_ai.txt" del /q "!TEST_DIR!\prompt_web_ai.txt"
if exist "!TEST_DIR!\pdf_type_result.txt" del /q "!TEST_DIR!\pdf_type_result.txt"
if exist "!TEST_DIR!\raw_text.md" del /q "!TEST_DIR!\raw_text.md"
if exist "!TEST_DIR!\page_map.json" del /q "!TEST_DIR!\page_map.json"
echo   Cleanup complete!

echo.
echo  What would you like to do with the quiz?
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
set "OUTPUT_FILE=!TEST_DIR!\!TEST_NAME!_quiz.html"
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
echo.
echo   Press any key to return to the main menu...
pause >nul
goto :select_test_step


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
    echo.
    echo   Press any key to return to the main menu...
    pause >nul
    goto :select_test_step
)
echo.
set /p BUILD_CHOICE="   Enter number: "
set "TEST_DIR=!TEST_OPTION_%BUILD_CHOICE%!"
set "TEST_NAME=!TEST_OPTNAME_%BUILD_CHOICE%!"
if "!TEST_DIR!"=="" (
    echo   ERROR: Invalid selection.
    echo.
    echo   Press any key to return to the main menu...
    pause >nul
    goto :select_test_step
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
echo.
echo   Server stopped. Returning to main menu...
goto :select_test_step


:: ===========================================================================
:end
echo.
echo  Done. Goodbye!
echo.
pause
endlocal
