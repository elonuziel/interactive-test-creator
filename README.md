# 📝 Interactive Hebrew Quiz Generator & Player Suite

> **Try the Web App Live:** [elonuziel.github.io/interactive-test-creator](https://elonuziel.github.io/interactive-test-creator/)

Turn scanned or digital Hebrew exam PDFs & Word DOCX documents into fully interactive, self-grading digital quizzes. The project is organized into two distinct, first-class platforms:
1. **🌐 In-Browser Web Application (`web/`)**: Zero-backend web builder running in your browser with Gemini OCR and PDF.js.
2. **🖥️ Python Desktop GUI & Batch CLI App (`desktop/`)**: Zero-dependency native desktop GUI with batch folder processing, DOCX conversion, and AI agent dispatch.

---

## 🌐 In-Browser Web Application (`web/`)

- **Web Quiz Generator (`web/index.html` + `web/generator.js`)**:
  - Upload exam PDFs or `questions.json` files.
  - Attach CSV, XLS, or XLSX answer keys with Form number support.
  - Page cleaning & selection presets ("ניקוי סטנדרטי", "עמודים זוגיים").
  - Client-side Gemini OCR integration with structured JSON schema.
  - Side-by-side Proof Mode with page snapshots.
  - Export standalone, single-file HTML quizzes.
- **Standalone RTL Quiz Player (`web/quiz_player.html` + `web/app.js`)**:
  - Native Right-to-Left (RTL) design with modern typography.
  - Keyboard shortcuts (`1`–`9` choices, `←` / `→` navigation).
  - Question bookmarking / Star (⭐), instant feedback toggle, and score breakdown.
  - Targeted review practice sessions (Wrong, Unanswered, Starred).
  - Image cropper & fullscreen diagram zoom.
  - Dark & Light themes with LocalStorage session resume.

---

## 🖥️ Python Desktop GUI & Batch CLI Builder (`desktop/`)

- **1-Click Launchers**:
  - Double-click **`start_app.bat`** in the root directory to open the Desktop GUI.
  - Run **`python quiz_builder.py --gui`** from the terminal.
- **Desktop GUI Highlights (`desktop/quiz_builder_gui.py`)**:
  - Zero external dependencies (powered by Python standard library `tkinter` + `ttk`).
  - Dark & Light slate themes with 1-click toggle.
  - Interactive exam cards with real-time status badges (`[BUILT]`, `[READY TO BUILD]`, `[NEEDS AI EXTRACTION]`, `[EMPTY]`).
  - 1-Click action buttons: Copy Web Prompt to clipboard, Run Local CLI Agent (`agy`, `gemini`, `claude`), Build Standalone HTML, Solve Quiz, or Open Folder.
- **High-Speed Batch CLI (`quiz_builder.py` / `desktop/quiz_builder_cli.py`)**:
  - **Flat-File Auto-Grouping**: Drop raw PDFs, DOCXs, and CSV answer keys into `./tests` (or custom folder) — it pairs and groups them into workspaces automatically.
  - **DOCX-to-PDF Conversion**: Automatic headless conversion via LibreOffice or Microsoft Word COM.
  - **Quick Build**: `python quiz_builder.py --build` compiles all ready workspaces into `output/` and generates a **Master Quiz Portal** (`output/index.html`).
  - **Live Watch Mode**: `python quiz_builder.py --watch` automatically recompiles quizzes upon saving `questions.md` or `questions.json`.

---

## ⚡ Fast 1-Click Root Launchers

| Launcher | What it Does |
|---|---|
| **`start_app.bat`** | 🚀 Launches the **Python Desktop GUI Application** |
| **`start_web.bat`** | 🌐 Starts a local HTTP server and opens the **Web Quiz Builder** |
| **`start_test_server.bat`** | 🧪 Interactive menu to launch web server, run tests, or open builder |
| **`quiz_builder.py`** | ⌨️ Root Python CLI entry point (`--help`, `--build`, `--watch`, `--gui`) |

---

## 📁 Repository Structure

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
└── walkthrough.md                     # Comprehensive architecture guide
```

---

## 🧪 Verification & Test Suites

- **Python Pytest Suite**: `python -m pytest desktop/tests_py -v` (57 unit tests)
- **Local Component Suite**: `python test-suite/run_local_tests.py` (10 component tests)
- **In-Browser Test Runner**: Open `test-suite/test_runner.html` for real-time visual test metrics

---

## 🔑 Gemini API Keys

| Type | Prefix | How to Get |
|---|---|---|
| Gemini Free Tier | `AIza...` | [Google AI Studio](https://aistudio.google.com/apikey) |
| Gemini Cloud | `AQ...` | [Google Cloud Console](https://console.cloud.google.com/apis/credentials) |

---

## 📄 License

MIT — see [LICENSE](LICENSE).
