# 🚀 Dual-Platform Architecture & Organization Walkthrough

## Overview of Organization
The repository has been structured into two clean, self-contained root application folders:
1. **🌐 `web/`**: In-Browser Client-Side Web Application (HTML, JS, CSS, PDF.js vendor assets).
2. **🖥️ `desktop/`**: Native Python Desktop GUI & High-Speed Batch CLI Suite (Tkinter app, CLI engine, scripts, tests_py).
3. **⚡ Root**: Direct 1-click launchers for both platforms (`start_app.bat`, `start_web.bat`, `start_test_server.bat`, `quiz_builder.py`).

---

## 📁 Clean Repository Layout

```
interactive-test-creator/
├── web/                               # 🌐 IN-BROWSER WEB APPLICATION
│   ├── index.html                     # Web Quiz Builder Interface
│   ├── generator.js                   # Client-side OCR & Gemini API Engine
│   ├── quiz_player.html               # Standalone Quiz Player Shell
│   ├── app.js                         # Quiz Engine & Navigation
│   ├── style.css                      # Unified RTL & Theme System
│   ├── favicon.svg                    # Application Favicon
│   └── vendor/                        # Third-party libraries (PDF.js)
│
├── desktop/                           # 🖥️ PYTHON DESKTOP GUI & BATCH CLI APP
│   ├── quiz_builder_gui.py            # Native Tkinter Desktop Application
│   ├── quiz_builder_cli.py            # High-Speed Batch CLI Engine
│   ├── python_scripts/                # Core pipeline scripts (1_detect.. to 9_build..)
│   ├── tests_py/                      # Pytest automated test suite (57 tests)
│   ├── web/                           # Standalone HTML bundle templates
│   ├── build_exe.py                   # PyInstaller compiler
│   └── start.bat                      # Desktop app batch launcher
│
├── test-suite/                        # 🧪 INTEGRATED TEST SUITE
│   ├── test_runner.html               # Browser component test runner
│   ├── run_tests.js                   # Node test runner (CI)
│   └── run_local_tests.py             # Python local test runner
│
├── .github/workflows/
│   └── deploy-pages.yml               # Automated GitHub Pages deployment from web/
│
├── start_app.bat                      # ⚡ 1-Click Desktop GUI App Launcher
├── start_web.bat                      # ⚡ 1-Click Web App Launcher
├── start_test_server.bat              # ⚡ Dev Server & Test Menu Launcher
├── quiz_builder.py                    # ⚡ Root Python CLI/GUI Entry Point Wrapper
├── .gitignore                         # Strictly ignores tests/, output/, caches, build/
└── README.md                          # Comprehensive dual-platform documentation
```

---

## 🖥️ Modern Desktop GUI App (`desktop/quiz_builder_gui.py`)

Launch with double-clicking **[start_app.bat](file:///c:/Users/elon/Documents/GitHub/interactive-test-creator/start_app.bat)** or via terminal:
```bash
python quiz_builder.py --gui
# or
python desktop/quiz_builder_gui.py
```

### Desktop App Features:
- **Zero-Dependency Native GUI**: Built using standard library `tkinter` and `ttk`.
- **Dark & Light Slate Themes**: Toggle between dark and light themes with 1 click.
- **Interactive Exam Cards**:
  - Live folder scanning and flat-file auto-grouping (pairing PDFs, DOCXs, and CSV answer keys).
  - Status badges: `[BUILT]` (Green), `[READY TO BUILD]` (Blue), `[NEEDS AI EXTRACTION]` (Amber), `[EMPTY]` (Gray).
  - Question counters and metadata chips.
- **1-Click Card Actions**:
  - 📋 **Copy Web Prompt**: Copies the formatted extraction prompt to OS clipboard with instant feedback.
  - 🤖 **Run CLI Agent**: Dispatches local CLI agents (`agy`, `gemini`, `claude`) in background with prompt piped.
  - 🔨 **Build HTML**: Compiles an individual test into a standalone HTML quiz.
  - 🚀 **Solve Quiz**: Launches the compiled quiz in default browser.
  - 📂 **Open Folder**: Opens test folder in Windows Explorer.
- **Top Batch Actions Toolbar**: Run Batch All, Build Ready Quizzes, Open Master Portal (`output/index.html`), Live Search filter box, and Live Activity Log Drawer.

---

## ⌨️ High-Speed Batch CLI (`quiz_builder.py`)

Run all batch operations from root:
```bash
# 1. Run Batch on tests/ (or any folder)
python quiz_builder.py
python quiz_builder.py path/to/my_exams/

# 2. Fast Build Only (Compile All Ready Tests into output/)
python quiz_builder.py --build

# 3. Live Watch Mode (Auto-Recompile on Save)
python quiz_builder.py --watch

# 4. Non-Interactive Batch (for CI/Scripts)
python quiz_builder.py --yes --output output
```

---

## 🌐 In-Browser Web App (`web/`)

- Double-click **[start_web.bat](file:///c:/Users/elon/Documents/GitHub/interactive-test-creator/start_web.bat)** to start a local HTTP server and open the web app.
- GitHub Pages automatically deploys from `web/` via `.github/workflows/deploy-pages.yml` with 100% path compatibility.

---

## 🧪 Verification & Test Results

### 1. Pytest Unit Test Suite (57/57 Passed)
```bash
python -m pytest desktop/tests_py -v
```
- **57/57 passed in 8.64s**:
  - `test_quiz_builder_gui.py`: Theme structure, palette keys, and headless initialization.
  - `test_quiz_builder_batch.py`: Flat-file grouping, stem normalization, status analysis, master portal generation.
  - `test_quiz_builder_cli_docx.py`: DOCX conversion, fallback, and preference handling.
  - `test_parse_questions.py`, `test_check_json.py`, `test_merge_answers.py`, `test_discard_blank_pages.py`.

### 2. Local Component Test Suite (10/10 Passed)
```bash
python test-suite/run_local_tests.py
```
- **10/10 passed successfully**:
  - Whitespace normalization, markdown parsing, CSV answer extraction, Form 0 merging, Gemini cleanup, diagram matching.

### 3. GitHub Pages Deployment Compatibility
- Verified `.github/workflows/deploy-pages.yml` packages `web/` contents directly into the site root artifact.
