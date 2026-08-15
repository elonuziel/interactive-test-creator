# 🚀 Modernized Batch Quiz Builder & Clean Repo Architecture Walkthrough

## Repository Cleanup & Architecture Overview
The repository has been thoroughly cleaned and organized into two distinct, first-class interfaces:
1. **In-Browser Web Application (GitHub Pages root)**: Zero-backend web app running in browser with Gemini OCR and PDF.js.
2. **Native Python Desktop & Batch CLI App ([python_app/](file:///c:/Users/elon/Documents/GitHub/interactive-test-creator/python_app))**: Zero-dependency desktop GUI and high-speed batch runner.

---

## 📁 Clean Repository Layout

```
interactive-test-creator/
├── index.html            # Web Quiz Builder Interface (GitHub Pages Root)
├── generator.js          # Web OCR, Gemini API, & PDF Engine
├── quiz_player.html      # Standalone RTL Quiz Player Shell
├── app.js                # Quiz Engine & Navigation
├── style.css             # Unified RTL & Theme System
├── favicon.svg           # Application SVG Favicon
│
├── quiz_builder.py       # Root Python Entry Point (CLI & GUI wrapper)
├── start_app.bat         # Double-click Desktop GUI App Launcher
├── start_test_server.bat # Local HTTP Server & Test Menu Launcher
│
├── python_app/           # Modern Python Desktop GUI & Batch CLI App
│   ├── quiz_builder_gui.py   # Desktop GUI Application (Tkinter)
│   ├── quiz_builder_cli.py   # Batch CLI Runner & Engine
│   ├── python_scripts/       # Core pipeline scripts (1_detect.. to 9_build..)
│   ├── tests_py/             # Pytest automated test suite (57 tests)
│   ├── web/                  # Bundle templates (index.html, style.css, app.js)
│   └── start.bat             # Desktop app batch launcher
│
├── test-suite/           # In-Browser & Local Component Unit Tests
├── vendor/               # Third-party dependencies (PDF.js)
├── .github/workflows/    # Automated CI/CD Pages deployment workflow
├── tests/                # Local exam workspaces (strictly gitignored)
└── output/               # Generated standalone quizzes & portal (strictly gitignored)
```

---

## 🖥️ Modern Desktop GUI App

Launch by double-clicking **[start_app.bat](file:///c:/Users/elon/Documents/GitHub/interactive-test-creator/start_app.bat)** or via terminal:
```bash
python quiz_builder.py --gui
# or
python python_app/quiz_builder_gui.py
```

### Desktop App Highlights:
- **Zero-Dependency Native GUI**: Built with Python standard library `tkinter` + `ttk`.
- **Dark & Light Themes**: Modern slate palette (`#0f172a`, `#1e293b`) with instant theme toggle.
- **Interactive Exam Cards**: Live folder scanning, flat-file auto-grouping, and real-time status badges (`[BUILT]`, `[READY TO BUILD]`, `[NEEDS AI EXTRACTION]`, `[EMPTY]`).
- **1-Click Actions per Exam**:
  - 📋 **Copy Web Prompt**: Copies the formatted extraction prompt to OS clipboard with instant feedback.
  - 🤖 **Run CLI Agent**: Dispatches local CLI agents (`agy`, `gemini`, `claude`) in background with prompt piped.
  - 🔨 **Build HTML**: Compiles an individual test into a standalone HTML quiz.
  - 🚀 **Solve Quiz**: Launches the compiled quiz in default browser.
  - 📂 **Open Folder**: Opens test folder in Windows Explorer.
- **Top Actions Toolbar**: Run Batch All, Build Ready Quizzes, Open Master Portal, Live Search filter box, and Live Activity Log Drawer.

---

## ⌨️ High-Speed Batch CLI (`quiz_builder.py`)

Run all batch operations from repository root:
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

## 🧪 Verification & Test Results

### 1. Pytest Unit Test Suite (57/57 Passed)
```bash
python -m pytest python_app/tests_py -v
```
- **57/57 passed in 15.69s**:
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

### 3. Git Status & Privacy Verification
- `git status` confirms `tests/` and `output/` are strictly ignored.
- Dead files (`deal-with-later/`, `app-after.js`, old handoffs) have been completely removed.
