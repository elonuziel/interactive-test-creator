@echo off
setlocal enabledelayedexpansion

:: ===========================================================================
:: start.bat - Interactive Quiz Builder Wizard
:: Interactive workflow for converting Hebrew exam PDFs into interactive quizzes.
:: ===========================================================================

cd /d "%~dp0"

:: Initialize ANSI color escape sequences
for /f "delims=" %%A in ('powershell -NoProfile -Command "[char]27"') do set "ESC=%%A"
set "C_RESET=!ESC![0m"
set "C_BOLD=!ESC![1m"
set "C_GREEN=!ESC![32m"
set "C_YELLOW=!ESC![33m"
set "C_CYAN=!ESC![36m"
set "C_RED=!ESC![31m"
set "C_GRAY=!ESC![90m"

set "FORM_NUMBER="

title Interactive Hebrew Quiz Builder

cls
echo.
echo !C_CYAN!!C_BOLD!===========================================================================!C_RESET!
echo !C_CYAN!!C_BOLD!  INTERACTIVE HEBREW QUIZ BUILDER!C_RESET!
echo !C_GRAY!  Transform PDF Exams into Self-Contained Interactive Quizzes!C_RESET!
echo !C_CYAN!!C_BOLD!===========================================================================!C_RESET!
echo.

:: ---------------------------------------------------------------------------
:: STEP 1: Check Prerequisites
:: ---------------------------------------------------------------------------
echo  !C_BOLD![Step 1/6] Checking Prerequisites...!C_RESET!
echo  !C_GRAY!---------------------------------------------------------------------------!C_RESET!

python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  !C_RED!!C_BOLD![X] ERROR: Python is not installed or not in your system PATH.!C_RESET!
    echo      Please install Python from https://python.org
    echo      Be sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo   !C_GREEN![OK]!C_RESET! Python Environment: %PYVER%

set "MISSING_PKGS="
python -c "import fitz" >nul 2>&1
if errorlevel 1 set "MISSING_PKGS=!MISSING_PKGS! pymupdf"

python -c "import pandas" >nul 2>&1
if errorlevel 1 set "MISSING_PKGS=!MISSING_PKGS! pandas"

python -c "import openpyxl" >nul 2>&1
if errorlevel 1 set "MISSING_PKGS=!MISSING_PKGS! openpyxl"

if not "!MISSING_PKGS!"=="" (
    echo.
    echo   !C_YELLOW![!] NOTICE: Missing required Python packages:!MISSING_PKGS!!C_RESET!
    echo.
    set /p INSTALL_CHOICE="   !C_CYAN![?] Install missing packages now? (Y/n): !C_RESET!"
    if /i "!INSTALL_CHOICE!"=="n" (
        echo.
        echo   !C_YELLOW![!] Skipping package installation. Note: Some pipeline steps may fail.!C_RESET!
    ) else (
        echo.
        echo   !C_CYAN![i] Installing dependencies...!C_RESET!
        pip install !MISSING_PKGS! --quiet
        if errorlevel 1 (
            echo   !C_RED![!] WARNING: Automatic package installation failed.!C_RESET!
            echo       Please manually run: pip install!MISSING_PKGS!
        ) else (
            echo   !C_GREEN![OK] All required packages installed successfully!!C_RESET!
        )
    )
) else (
    echo   !C_GREEN![OK]!C_RESET! Python Packages: All required libraries are ready
)

echo.

:: ---------------------------------------------------------------------------
:: STEP 2: Select or Create Test Folder
:: ---------------------------------------------------------------------------
:select_test_step
echo  !C_BOLD![Step 2/6] Test Workspace Setup!C_RESET!
echo  !C_GRAY!---------------------------------------------------------------------------!C_RESET!
echo.

if not exist "tests" (
    echo   !C_CYAN![i] Creating tests\ directory...!C_RESET!
    mkdir "tests"
    echo   !C_GREEN![OK] tests\ folder created.!C_RESET!
    echo.
)

set "HAS_TESTS=0"
set "HAS_READY_TESTS=0"
set "TEST_COUNT=0"

echo   Available Test Workspaces:
for /d %%d in (tests\*) do (
    set /a TEST_COUNT+=1
    set "TEST_OPT_PATH_!TEST_COUNT!=%%d"
    set "TEST_OPT_NAME_!TEST_COUNT!=%%~nxd"
    set "HAS_TESTS=1"
    
    if exist "%%d\questions.json" (
        set "TEST_OPT_READY_!TEST_COUNT!=1"
        set "HAS_READY_TESTS=1"
        echo     [!TEST_COUNT!] %%~nxd  !C_GREEN![OK READY - questions.json present]!C_RESET!
    ) else (
        set "TEST_OPT_READY_!TEST_COUNT!=0"
        echo     [!TEST_COUNT!] %%~nxd  !C_YELLOW![... PENDING - needs processing]!C_RESET!
    )
)

if !TEST_COUNT!==0 (
    echo     (No existing test folders found in tests\)
)

echo.
echo   What would you like to do?
if !TEST_COUNT! GTR 0 (
    echo     [1-!TEST_COUNT!] Select an existing test workspace above
)
echo     [N] Create a NEW test workspace
if !HAS_READY_TESTS!==1 (
    echo     [B] BUILD a standalone HTML quiz from a ready test
    echo     [S] START the local web server to browse tests
)
echo     [Q] Quit
echo.

:get_action_choice
set "ACTION="
set /p ACTION="   !C_CYAN![?] Your choice > !C_RESET!"

if "!ACTION!"=="" goto :invalid_choice
set "ACTION=!ACTION: =!"

if /i "!ACTION!"=="q" goto :end
if /i "!ACTION!"=="n" goto :create_test
if /i "!ACTION!"=="s" goto :start_server
if /i "!ACTION!"=="b" goto :build_html

set "IS_NUMERIC=1"
for /f "delims=0123456789" %%i in ("!ACTION!") do set "IS_NUMERIC=0"

if !IS_NUMERIC!==1 (
    if !ACTION! GEQ 1 if !ACTION! LEQ !TEST_COUNT! (
        for %%a in (!ACTION!) do (
            set "TEST_DIR=!TEST_OPT_PATH_%%a!"
            set "TEST_NAME=!TEST_OPT_NAME_%%a!"
            set "IS_READY=!TEST_OPT_READY_%%a!"
        )
        
        echo.
        echo   Workspace Selected: !C_BOLD!!TEST_NAME!!C_RESET!
        if !IS_READY!==1 (
            echo   Status: !C_GREEN!READY (questions.json present)!C_RESET!
            echo.
            echo   Select an action for !TEST_NAME!:
            echo     [1] Build standalone HTML quiz file
            echo     [2] Re-process with AI agent ^(re-extract / proofread^)
            echo     [B] Back to main menu
            echo.
            set "EXISTING_CHOICE="
            set /p EXISTING_CHOICE="   !C_CYAN![?] Your choice (1/2/B) [Default: 1]: !C_RESET!"
            if defined EXISTING_CHOICE set "EXISTING_CHOICE=!EXISTING_CHOICE: =!"
            if "!EXISTING_CHOICE!"=="1" goto :build_single
            if "!EXISTING_CHOICE!"=="2" goto :drop_files_check
            if /i "!EXISTING_CHOICE!"=="b" goto :select_test_step
            goto :build_single
        ) else (
            echo   Status: !C_YELLOW!PENDING (requires processing)!C_RESET!
            goto :drop_files_check
        )
    )
)

:invalid_choice
echo.
echo  !C_RED![X] Invalid input: '!ACTION!'!C_RESET!
if !TEST_COUNT! GTR 0 (
    echo      Please enter a number ^(1-!TEST_COUNT!^), 'N', 'S', or 'Q'.
) else (
    echo      Please enter 'N', 'S', or 'Q'.
)
echo.
goto :get_action_choice


:: ===========================================================================
:: STEP 3: Create New Test Workspace
:: ===========================================================================
:create_test
echo.
echo  !C_BOLD![Step 3/6] Create New Test Workspace!C_RESET!
echo  !C_GRAY!---------------------------------------------------------------------------!C_RESET!
echo.
echo   Enter a short identifier name for your test folder.
echo   Examples: 2024_moed_a, botany_final, bio_exam_3
echo.
set /p TEST_NAME="   !C_CYAN![?] Test workspace name [Default: test_1]: !C_RESET!"

if "!TEST_NAME!"=="" (
    set "TEST_NAME=test_1"
)

set "TEST_NAME=!TEST_NAME: =_!"
set "TEST_DIR=tests\!TEST_NAME!"

if exist "!TEST_DIR!" (
    echo.
    echo   !C_CYAN![i] NOTE: Folder !TEST_DIR! already exists.!C_RESET!
    if exist "!TEST_DIR!\questions.json" (
        echo   !C_GREEN![OK] questions.json already present. Proceeding to build options.!C_RESET!
        goto :post_process
    )
    echo   !C_CYAN![i] Continuing with existing folder...!C_RESET!
) else (
    mkdir "!TEST_DIR!"
    echo.
    echo   !C_GREEN![OK] Workspace directory created: !TEST_DIR!\!C_RESET!
)

:: ---------------------------------------------------------------------------
:: Check for Source Files (PDF / Answer Key)
:: ---------------------------------------------------------------------------
:drop_files_check
set "HAS_PDF=0"
set "HAS_ANSWERS=0"
set "PDF_NAME="
set "PDF_FULL_PATH="
set "ANSWERS_NAME="
set "PDF_COUNT=0"

for %%f in ("!TEST_DIR!\*.pdf") do (
    set /a PDF_COUNT+=1
    set "HAS_PDF=1" & set "PDF_NAME=%%~nxf" & set "PDF_FULL_PATH=%%~ff"
)
for %%f in ("!TEST_DIR!\*.csv") do set "HAS_ANSWERS=1" & set "ANSWERS_NAME=%%~nxf"
for %%f in ("!TEST_DIR!\*.xlsx") do set "HAS_ANSWERS=1" & set "ANSWERS_NAME=%%~nxf"
for %%f in ("!TEST_DIR!\*.xls") do set "HAS_ANSWERS=1" & set "ANSWERS_NAME=%%~nxf"

if !HAS_PDF!==1 (
    echo.
    if !PDF_COUNT! GTR 1 (
        echo   !C_YELLOW![!] WARNING: Multiple PDF files found in !TEST_DIR! ^(!PDF_COUNT! files^). Using: !PDF_NAME!!C_RESET!
        echo       Remove extra PDFs if this is not the desired exam file.
    ) else (
        echo   !C_GREEN![OK] PDF File Detected: !PDF_NAME!!C_RESET!
    )
    if !HAS_ANSWERS!==1 (
        echo   !C_GREEN![OK] Answer Key Detected: !ANSWERS_NAME!!C_RESET!
    ) else (
        echo   !C_CYAN![i] NOTE: No answer key file ^(CSV/Excel^) detected in workspace.!C_RESET!
    )
    echo.
    echo   !C_CYAN![i] Proceeding to document pre-processing...!C_RESET!
    echo.
    goto :pre_processing_step
)

echo.
echo !C_YELLOW!!C_BOLD!===========================================================================!C_RESET!
echo !C_YELLOW!!C_BOLD!                     ACTION REQUIRED: PLACE EXAM FILES!C_RESET!
echo !C_YELLOW!!C_BOLD!===========================================================================!C_RESET!
echo.
echo   Please place your exam source files into: !C_BOLD!!TEST_DIR!\!C_RESET!
echo   Opening workspace folder in Explorer...
echo.
echo   Required files:
echo     1. exam.pdf    - Your exam PDF file
echo     2. answers.csv - Answer key ^(CSV or Excel .xlsx / .xls^) [Optional]
echo.
echo   Press any key after copying your files to continue.
echo !C_YELLOW!!C_BOLD!===========================================================================!C_RESET!
echo.

start "" explorer "!TEST_DIR!"
pause

set "HAS_PDF=0"
set "HAS_ANSWERS=0"
set "PDF_NAME="
set "PDF_FULL_PATH="
set "ANSWERS_NAME="
set "PDF_COUNT=0"

for %%f in ("!TEST_DIR!\*.pdf") do (
    set /a PDF_COUNT+=1
    set "HAS_PDF=1" & set "PDF_NAME=%%~nxf" & set "PDF_FULL_PATH=%%~ff"
)
for %%f in ("!TEST_DIR!\*.csv") do set "HAS_ANSWERS=1" & set "ANSWERS_NAME=%%~nxf"
for %%f in ("!TEST_DIR!\*.xlsx") do set "HAS_ANSWERS=1" & set "ANSWERS_NAME=%%~nxf"
for %%f in ("!TEST_DIR!\*.xls") do set "HAS_ANSWERS=1" & set "ANSWERS_NAME=%%~nxf"

if !HAS_PDF!==0 (
    echo   !C_YELLOW![!] WARNING: No PDF file found in !TEST_DIR!\!C_RESET!
    echo       The extraction step will rely entirely on external inputs or manual JSON.
)
if !HAS_ANSWERS!==0 (
    echo   !C_CYAN![i] NOTE: No answer key spreadsheet found.!C_RESET!
    echo       Questions will be extracted with placeholder answers until merged.
)
if !HAS_PDF!==1 echo   !C_GREEN![OK] PDF File Found: !PDF_NAME!!C_RESET!
if !HAS_ANSWERS!==1 echo   !C_GREEN![OK] Answer Key Found: !ANSWERS_NAME!!C_RESET!
echo.

:pre_processing_step
:: ---------------------------------------------------------------------------
:: STEP 4: Document Pre-processing & Analysis
:: ---------------------------------------------------------------------------
echo  !C_BOLD![Step 4/6] Document Pre-processing ^& Analysis!C_RESET!
echo  !C_GRAY!---------------------------------------------------------------------------!C_RESET!
echo.

set "IS_DIGITAL=0"
if !HAS_PDF!==1 (
    echo   [1/2] Analyzing PDF format ^(Digital vs Scanned^)...
    python python_scripts\1_detect_pdf_type.py "!PDF_FULL_PATH!" > "!TEST_DIR!\pdf_type_result.txt"
    type "!TEST_DIR!\pdf_type_result.txt"
    
    findstr /C:"DIGITAL PDF detected" "!TEST_DIR!\pdf_type_result.txt" >nul
    if not errorlevel 1 set "IS_DIGITAL=1"
    echo.
)

if !HAS_ANSWERS!==1 (
    echo !C_CYAN!!C_BOLD!===========================================================================!C_RESET!
    echo !C_CYAN!!C_BOLD!   [2/2] ANSWER KEY FORM SETUP!C_RESET!
    echo   Enter the Form Number corresponding to this answer key.
    echo   ^(e.g., 32, 76, 1, 0^). Refer to your PDF title page if unsure.
    echo !C_CYAN!!C_BOLD!===========================================================================!C_RESET!
    set "FORM_NUMBER="
    set /p FORM_NUMBER="   !C_CYAN![?] Form Number [Default: 1]: !C_RESET!"
    if "!FORM_NUMBER!"=="" (
        set "FORM_NUMBER=1"
    )
    echo.
    echo   !C_CYAN![i] Extracting answers for Form !FORM_NUMBER!...!C_RESET!
    python python_scripts\4_extract_csv_answers.py "!TEST_DIR!\!ANSWERS_NAME!" "!FORM_NUMBER!" -o "!TEST_DIR!\answers.json"
    echo.
) else (
    echo !C_CYAN!!C_BOLD!===========================================================================!C_RESET!
    echo !C_CYAN!!C_BOLD!   [2/2] FORM NUMBER SETUP ^(No answer spreadsheet found^)!C_RESET!
    echo   Is this Form 0 ^(Master Exam where option 1/א is always the answer^)?
    echo   - Enter '0' to auto-generate Form Zero answer key
    echo   - Enter Form Number ^(e.g., 1, 32^) if adding answers manually later
    echo !C_CYAN!!C_BOLD!===========================================================================!C_RESET!
    set "FORM_NUMBER="
    set /p FORM_NUMBER="   !C_CYAN![?] Form Number [Default: 0 for Form Zero]: !C_RESET!"
    if "!FORM_NUMBER!"=="" set "FORM_NUMBER=0"
    
    if "!FORM_NUMBER!"=="0" (
        echo.
        echo   !C_GREEN![OK] Form 0 selected! Auto-generating baseline answer key...!C_RESET!
        python python_scripts\4_extract_csv_answers.py "none" "0" -o "!TEST_DIR!\answers.json"
        set "HAS_ANSWERS=1"
    )
)

set "SKIP_STEP3="
set /p SKIP_STEP3="   !C_CYAN![?] Press Enter to run page rendering/text extraction, or 's' to skip > !C_RESET!"
if /i "!SKIP_STEP3!"=="s" goto :agent_extraction_step

echo.
if !HAS_PDF!==1 (
    echo   Page Cleaning Options:
    echo     • Press [Enter] for Standard cleaning ^(skips cover/instructions pages 1-4, 6,8,10...^)
    echo     • Type custom pages to discard ^(e.g., '1-3, 5'^)
    echo     • Type 'none' to preserve all pages
    echo.
    set "DISCARD_PAGES="
    set /p DISCARD_PAGES="   !C_CYAN![?] Discard pages [Default: standard]: !C_RESET!"
    if "!DISCARD_PAGES!"=="" set "DISCARD_PAGES=std"
    
    echo.
    echo   !C_CYAN![i] Rendering clean PDF pages...!C_RESET!
    python python_scripts\3_render_pdf_pages.py "!PDF_FULL_PATH!" -o "!TEST_DIR!\pages_output" --discard-pages "!DISCARD_PAGES!" --merged-pdf "!TEST_DIR!\!TEST_NAME!_clean.pdf"
    
    if !IS_DIGITAL!==1 (
        echo.
        echo   !C_GREEN![OK] DIGITAL PDF DETECTED: Extracting text automatically...!C_RESET!
        python python_scripts\2_extract_text_fitz.py "!PDF_FULL_PATH!" -o "!TEST_DIR!\raw_text.md" --extract-images "!TEST_DIR!\images" --page-map "!TEST_DIR!\page_map.json"
        python python_scripts\5_parse_questions_md.py "!TEST_DIR!\raw_text.md" -o "!TEST_DIR!\questions.json" --image-dir "!TEST_DIR!\images" --page-map "!TEST_DIR!\page_map.json"
        
        if errorlevel 1 (
            echo.
            echo   !C_YELLOW![!] WARNING: Automatic parsing encountered issues. questions.json may need AI review.!C_RESET!
        ) else (
            echo   !C_GREEN![OK] Automated extraction finished successfully!!C_RESET!
        )
    )
)

echo.
echo   !C_GREEN![OK] Pre-processing complete!!C_RESET!
echo.

:agent_extraction_step
:: ---------------------------------------------------------------------------
:: STEP 5: Launch AI Agent / Proofreading
:: ---------------------------------------------------------------------------
echo  !C_BOLD![Step 5/6] AI Agent Question Extraction ^& Proofreading!C_RESET!
echo  !C_GRAY!---------------------------------------------------------------------------!C_RESET!
echo.
set "SKIP_STEP4="
set /p SKIP_STEP4="   !C_CYAN![?] Press Enter to launch AI extraction pass, or 's' to skip to building > !C_RESET!"
if /i "!SKIP_STEP4!"=="s" goto :post_process
echo.
if exist "!TEST_DIR!\questions.json" (
    echo   !C_CYAN![i] Automated text extraction is complete!!C_RESET!
    echo   Hebrew text extraction may benefit from an AI proofreading pass to fix reversed words.
    echo.
    set /p PROOF_CHOICE="   !C_CYAN![?] Run AI proofreading pass on questions.json? (Y/n) [Default: Y]: !C_RESET!"
    if /i "!PROOF_CHOICE!"=="n" (
        goto :post_process
    )
    echo.
    echo   !C_CYAN![i] Preparing AI proofreading prompt...!C_RESET!
) else (
    echo   !C_CYAN![i] AI Agent pass needed to extract questions from rendered pages into questions.json.!C_RESET!
)
echo.

python python_scripts\generate_prompts.py "!TEST_DIR!" "!TEST_NAME!" "!FORM_NUMBER!" "!HAS_ANSWERS!" >nul 2>&1

if exist "!TEST_DIR!\prompt_local_agent.txt" (
    type "!TEST_DIR!\prompt_local_agent.txt" | clip
)

set "AGENT_FOUND=0"
set "AGENT_LAUNCHED=0"

where agy >nul 2>&1
if not errorlevel 1 (
    set "AGENT_FOUND=1"
    echo   !C_GREEN![OK] Detected CLI Agent: agy (Gemini CLI)!C_RESET!
    echo.
    set /p USE_AGY="   !C_CYAN![?] Launch agy automatically? (Y/n) [Default: Y]: !C_RESET!"
    if /i not "!USE_AGY!"=="n" (
        echo.
        echo !C_CYAN!!C_BOLD!===========================================================================!C_RESET!
        echo !C_CYAN!!C_BOLD!            LAUNCHING AGENT: agy (Gemini CLI)!C_RESET!
        echo !C_CYAN!!C_BOLD!===========================================================================!C_RESET!
        echo   1. Opening agy in a new window with full prompt piped.
        echo   2. The agent will output/update questions.json automatically.
        echo   3. Once finished, return here and press any key to continue.
        echo !C_CYAN!!C_BOLD!===========================================================================!C_RESET!
        echo.
        start "" cmd /k "cd /d "%~dp0" && type "!TEST_DIR!\prompt_local_agent.txt" | agy"
        set "AGENT_LAUNCHED=1"
        goto :wait_for_questions
    )
)

where gemini >nul 2>&1
if not errorlevel 1 if !AGENT_LAUNCHED!==0 (
    set "AGENT_FOUND=1"
    echo   !C_GREEN![OK] Detected CLI Agent: gemini CLI!C_RESET!
    echo.
    set /p USE_GEMINI="   !C_CYAN![?] Launch gemini CLI automatically? (Y/n) [Default: Y]: !C_RESET!"
    if /i not "!USE_GEMINI!"=="n" (
        echo.
        echo !C_CYAN!!C_BOLD!===========================================================================!C_RESET!
        echo !C_CYAN!!C_BOLD!            LAUNCHING AGENT: gemini CLI!C_RESET!
        echo !C_CYAN!!C_BOLD!===========================================================================!C_RESET!
        echo   1. Opening gemini in a new window with full prompt piped.
        echo   2. The agent will output/update questions.json automatically.
        echo   3. Once finished, return here and press any key to continue.
        echo !C_CYAN!!C_BOLD!===========================================================================!C_RESET!
        echo.
        start "" cmd /k "cd /d "%~dp0" && type "!TEST_DIR!\prompt_local_agent.txt" | gemini"
        set "AGENT_LAUNCHED=1"
        goto :wait_for_questions
    )
)

where claude >nul 2>&1
if not errorlevel 1 if !AGENT_LAUNCHED!==0 (
    set "AGENT_FOUND=1"
    echo   !C_GREEN![OK] Detected CLI Agent: claude CLI!C_RESET!
    echo.
    set /p USE_CLAUDE="   !C_CYAN![?] Launch claude CLI automatically? (Y/n) [Default: Y]: !C_RESET!"
    if /i not "!USE_CLAUDE!"=="n" (
        echo.
        echo !C_CYAN!!C_BOLD!===========================================================================!C_RESET!
        echo !C_CYAN!!C_BOLD!            LAUNCHING AGENT: claude CLI!C_RESET!
        echo !C_CYAN!!C_BOLD!===========================================================================!C_RESET!
        echo   1. Opening claude in a new window with full prompt piped.
        echo   2. The agent will output/update questions.json automatically.
        echo   3. Once finished, return here and press any key to continue.
        echo !C_CYAN!!C_BOLD!===========================================================================!C_RESET!
        echo.
        start "" cmd /k "cd /d "%~dp0" && type "!TEST_DIR!\prompt_local_agent.txt" | claude"
        set "AGENT_LAUNCHED=1"
        goto :wait_for_questions
    )
)

:prompt_menu
echo.
echo !C_CYAN!!C_BOLD!===========================================================================!C_RESET!
echo !C_CYAN!!C_BOLD!                 AI PROMPT ASSISTANT!C_RESET!
echo !C_CYAN!!C_BOLD!===========================================================================!C_RESET!
echo.
echo   Prompt files generated:
echo     • Local Prompt: !TEST_DIR!\prompt_local_agent.txt
echo     • Web AI Prompt: !TEST_DIR!\prompt_web_ai.txt
echo.
echo   !C_GREEN![OK] Local prompt has been copied to your Windows Clipboard!!C_RESET!
echo.
echo   Select a prompt helper option:
echo     [1] LOCAL AGENT (agy, gemini, claude, Cursor, Antigravity, VS Code)
echo         Copies local prompt to clipboard.
echo.
echo     [2] WEB AI (ChatGPT, Claude.ai, Gemini Web, Google AI Studio)
echo         Copies web prompt to clipboard ^& opens AI website.
echo.
echo     [3] Print both prompts to console
echo     [S] Skip prompt helper
echo.
set /p PROMPT_CHOICE="   !C_CYAN![?] Your choice (1/2/3/S) [Default: 1]: !C_RESET!"

if /i "!PROMPT_CHOICE!"=="1" goto :copy_local_prompt
if /i "!PROMPT_CHOICE!"=="2" goto :copy_web_prompt
if /i "!PROMPT_CHOICE!"=="3" goto :show_both_prompts
if /i "!PROMPT_CHOICE!"=="s" goto :wait_for_questions
goto :copy_local_prompt

:copy_local_prompt
type "!TEST_DIR!\prompt_local_agent.txt" | clip
echo.
echo   !C_GREEN![OK] Local Agent prompt copied to clipboard!!C_RESET!
echo.
echo   !C_GRAY!--- LOCAL PROMPT PREVIEW ---!C_RESET!
type "!TEST_DIR!\prompt_local_agent.txt"
echo.
echo   !C_GRAY!----------------------------!C_RESET!
goto :wait_for_questions

:copy_web_prompt
type "!TEST_DIR!\prompt_web_ai.txt" | clip
echo.
echo   !C_GREEN![OK] Web AI prompt copied to clipboard!!C_RESET!
echo.
echo   !C_GRAY!--- WEB AI PROMPT PREVIEW ---!C_RESET!
type "!TEST_DIR!\prompt_web_ai.txt"
echo.
echo   !C_GRAY!-----------------------------!C_RESET!
echo.
echo   Open a Web AI assistant in browser?
echo     [1] ChatGPT (chatgpt.com)
echo     [2] Gemini Web (gemini.google.com)
echo     [3] Claude Web (claude.ai)
echo     [4] Google AI Studio (aistudio.google.com)
echo     [N] Skip opening browser
echo.
set /p WEB_CHOICE="   !C_CYAN![?] Your choice (1/2/3/4/N): !C_RESET!"
if "!WEB_CHOICE!"=="1" start https://chatgpt.com
if "!WEB_CHOICE!"=="2" start https://gemini.google.com
if "!WEB_CHOICE!"=="3" start https://claude.ai
if "!WEB_CHOICE!"=="4" start https://aistudio.google.com
echo.
echo   INSTRUCTIONS:
echo     1. Upload clean PDF: !TEST_DIR!\!TEST_NAME!_clean.pdf
echo     2. Paste the prompt ^(already copied to clipboard!^).
echo     3. Save output as: !TEST_DIR!\questions.json
echo.
goto :wait_for_questions

:show_both_prompts
echo.
echo !C_CYAN!!C_BOLD!===========================================================================!C_RESET!
echo  PROMPT 1: LOCAL AGENT
echo !C_CYAN!!C_BOLD!===========================================================================!C_RESET!
type "!TEST_DIR!\prompt_local_agent.txt"
echo.
echo !C_CYAN!!C_BOLD!===========================================================================!C_RESET!
echo  PROMPT 2: WEB AI
echo !C_CYAN!!C_BOLD!===========================================================================!C_RESET!
type "!TEST_DIR!\prompt_web_ai.txt"
echo.
echo !C_CYAN!!C_BOLD!===========================================================================!C_RESET!
echo.
goto :prompt_menu

:wait_for_questions
echo.
echo   !C_CYAN![i] Waiting for AI agent to create/update questions.json...!C_RESET!
echo       Press any key once the agent has completed the task.
echo.
pause

:check_questions_exist
if exist "!TEST_DIR!\questions.json" (
    echo.
    echo   !C_GREEN![OK] Verified: questions.json found in !TEST_DIR!!C_RESET!
    goto :post_process
)

for %%f in ("!TEST_DIR!\final_questions.json" "!TEST_DIR!\output.json" "!TEST_DIR!\response.json" "!TEST_DIR!\gemini-code-*" "!TEST_DIR!\gemini_code_*" "!TEST_DIR!\gemini-*" "!TEST_DIR!\gemini_*" "!TEST_DIR!\questions.txt" "!TEST_DIR!\questions.json.txt" "!TEST_DIR!\data.json") do (
    if exist "%%~f" (
        echo.
        echo   !C_CYAN![i] Found %%~nxf. Renaming to questions.json...!C_RESET!
        move "%%~f" "!TEST_DIR!\questions.json" >nul
        goto :post_process
    )
)

set "JSON_COUNT=0"
for %%f in ("!TEST_DIR!\*.json" "!TEST_DIR!\*.txt") do (
    set "FNAME=%%~nxf"
    if /i not "!FNAME!"=="answers.json" if /i not "!FNAME!"=="page_map.json" if /i not "!FNAME!"=="questions.json" if /i not "!FNAME!"=="pdf_type_result.txt" if /i not "!FNAME!"=="prompt_local_agent.txt" if /i not "!FNAME!"=="prompt_web_ai.txt" (
        set /a JSON_COUNT+=1
        set "JSON_FILE_!JSON_COUNT!=%%~nxf"
        set "JSON_PATH_!JSON_COUNT!=%%~ff"
    )
)

if !JSON_COUNT! GTR 0 (
    echo.
    echo   Found !JSON_COUNT! candidate file^(s^) in !TEST_DIR!:
    for /l %%i in (1,1,!JSON_COUNT!) do (
        echo     [%%i] !JSON_FILE_%%i!
    )
    echo.
    set "CHOSEN_JSON_INDEX="
    set /p CHOSEN_JSON_INDEX="   !C_CYAN![?] Select file to use as questions.json (1-!JSON_COUNT! or Enter to skip): !C_RESET!"
    if defined CHOSEN_JSON_INDEX set "CHOSEN_JSON_INDEX=!CHOSEN_JSON_INDEX: =!"
    if not "!CHOSEN_JSON_INDEX!"=="" (
        for %%a in (!CHOSEN_JSON_INDEX!) do (
            if defined JSON_PATH_%%a (
                echo.
                echo   !C_GREEN![OK] Selected '!JSON_FILE_%%a!'. Renaming to questions.json...!C_RESET!
                move "!JSON_PATH_%%a!" "!TEST_DIR!\questions.json" >nul
                goto :post_process
            )
        )
    )
)

echo.
echo   !C_YELLOW![!] WARNING: questions.json not found in !TEST_DIR!!C_RESET!
echo       If your file was saved under a different name, please rename it to 'questions.json'.
echo.
pause
goto :check_questions_exist


:: ===========================================================================
:: STEP 6: Post-Processing & Output Generation
:: ===========================================================================
:post_process
echo.
echo  !C_BOLD![Step 6/6] Automated Post-Processing ^& Validation!C_RESET!
echo  !C_GRAY!---------------------------------------------------------------------------!C_RESET!
if exist "!TEST_DIR!\questions.json" (
    if !HAS_ANSWERS!==1 (
        echo.
        echo   !C_CYAN![i] Merging answer key into questions.json...!C_RESET!
        python python_scripts\6_merge_json_answers.py "!TEST_DIR!"
    )
    echo.
    echo   !C_CYAN![i] Running QA validation checks...!C_RESET!
    python python_scripts\7_check_json.py "!TEST_DIR!"
) else (
    echo.
    echo   !C_YELLOW![!] Skipping answer merge and QA (questions.json not present).!C_RESET!
)

echo.
echo   !C_CYAN![i] Updating manifest.json...!C_RESET!
python python_scripts\8_generate_manifest.py

echo.
echo   !C_CYAN![i] Cleaning temporary files...!C_RESET!
if exist "!TEST_DIR!\answers_extracted.json" del /q "!TEST_DIR!\answers_extracted.json"
if exist "!TEST_DIR!\prompt_local_agent.txt" del /q "!TEST_DIR!\prompt_local_agent.txt"
if exist "!TEST_DIR!\prompt_web_ai.txt" del /q "!TEST_DIR!\prompt_web_ai.txt"
if exist "!TEST_DIR!\pdf_type_result.txt" del /q "!TEST_DIR!\pdf_type_result.txt"
if exist "!TEST_DIR!\raw_text.md" del /q "!TEST_DIR!\raw_text.md"
if exist "!TEST_DIR!\page_map.json" del /q "!TEST_DIR!\page_map.json"
echo   !C_GREEN![OK] Workspace cleanup complete!!C_RESET!

echo.
echo !C_CYAN!!C_BOLD!===========================================================================!C_RESET!
echo !C_CYAN!!C_BOLD! OUTPUT OPTIONS!C_RESET!
echo !C_CYAN!!C_BOLD!===========================================================================!C_RESET!
echo.
echo   [H] Build STANDALONE HTML file ^(single self-contained file, no server needed^)
echo   [S] Start LOCAL WEB SERVER ^(browse all tests interactively in browser^)
echo   [B] Do BOTH ^(Build HTML + Start Server^)
echo   [M] Return to MAIN MENU
echo   [Q] Quit
echo.
set /p POST_CHOICE="   !C_CYAN![?] Your choice (H/S/B/M/Q) [Default: H]: !C_RESET!"

if /i "!POST_CHOICE!"=="s" goto :start_server
if /i "!POST_CHOICE!"=="b" goto :build_and_serve
if /i "!POST_CHOICE!"=="m" goto :select_test_step
if /i "!POST_CHOICE!"=="q" goto :end
goto :build_single


:build_single
echo.
echo   !C_CYAN![i] Building standalone HTML quiz file...!C_RESET!
set "OUTPUT_FILE=!TEST_DIR!\!TEST_NAME!_quiz.html"
python python_scripts\9_build_single_html.py "!TEST_DIR!" -o "!OUTPUT_FILE!"

if exist "!OUTPUT_FILE!" (
    echo.
    echo !C_GREEN!!C_BOLD!===========================================================================!C_RESET!
    echo !C_GREEN!!C_BOLD!                    [OK] BUILD COMPLETE!!C_RESET!
    echo !C_GREEN!!C_BOLD!===========================================================================!C_RESET!
    echo.
    echo   Quiz File: !C_BOLD!!OUTPUT_FILE!!C_RESET!
    echo.
    echo   Double-click to open in any web browser.
    echo   Can be shared via email, USB drive, or WhatsApp.
    echo.
    set /p OPEN_FILE="   !C_CYAN![?] Open the quiz now in browser? (Y/n) [Default: Y]: !C_RESET!"
    if /i not "!OPEN_FILE!"=="n" (
        start "" "!OUTPUT_FILE!"
    )
) else (
    echo   !C_RED![X] ERROR: HTML Build failed. Check the error log above.!C_RESET!
)
echo.
echo   Press any key to return to main menu...
pause >nul
exit /b 0


:build_html
echo.
echo   Select a test folder to build:
echo.
set "IDX=0"
for /d %%d in (tests\*) do (
    if exist "%%d\questions.json" (
        set /a IDX+=1
        set "TEST_OPTION_!IDX!=%%d"
        set "TEST_OPTNAME_!IDX!=%%~nxd"
        echo     [!IDX!] %%~nxd
    )
)
if !IDX!==0 (
    echo   !C_YELLOW![!] No test folders with questions.json found.!C_RESET!
    echo.
    echo   Press any key to return to main menu...
    pause >nul
    goto :select_test_step
)
echo.
set /p BUILD_CHOICE="   !C_CYAN![?] Enter number (1-!IDX!): !C_RESET!"

set "TEST_DIR="
set "TEST_NAME="
for %%a in (!BUILD_CHOICE!) do (
    set "TEST_DIR=!TEST_OPTION_%%a!"
    set "TEST_NAME=!TEST_OPTNAME_%%a!"
)
if "!TEST_DIR!"=="" (
    echo   !C_RED![X] ERROR: Invalid selection.!C_RESET!
    echo.
    echo   Press any key to return to main menu...
    pause >nul
    goto :select_test_step
)
goto :build_single


:build_and_serve
call :build_single
goto :start_server


:start_server
echo.
echo   !C_CYAN![i] Generating web app manifest...!C_RESET!
python python_scripts\8_generate_manifest.py
echo.
echo   !C_CYAN![i] Starting local web server on port 8000...!C_RESET!
echo   Opening: http://localhost:8000/web/index.html
echo.
start /b python -m http.server 8000
timeout /t 2 /nobreak >nul
start http://localhost:8000/web/index.html
python -m http.server 8000 >nul 2>&1
echo.
echo   !C_CYAN![i] Server stopped. Returning to main menu...!C_RESET!
goto :select_test_step


:end
echo.
echo  !C_CYAN!!C_BOLD!===========================================================================!C_RESET!
echo  !C_CYAN!!C_BOLD! Thank you for using Interactive Hebrew Quiz Builder! Goodbye.!C_RESET!
echo  !C_CYAN!!C_BOLD!===========================================================================!C_RESET!
echo.
pause
endlocal
