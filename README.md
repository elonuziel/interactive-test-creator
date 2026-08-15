# 📝 Interactive Hebrew Quiz Generator & Player

> **Try it live:** [elonuziel.github.io/interactive-test-creator](https://elonuziel.github.io/interactive-test-creator/)

Turn scanned or digital Hebrew exam PDFs into fully interactive, self-grading digital quizzes right in your browser — zero backend required. Upload a PDF, extract questions with Gemini OCR, attach an answer key, proofread side-by-side, and export a standalone, portable HTML quiz file.

---

## 🎯 Quiz Generator (`index.html`)

**`index.html`** + **`generator.js`** — the main builder & creator UI (GitHub Pages root landing page).

### Generator Features
1. **Upload PDF or questions.json**: Select a digital/scanned exam PDF, or upload a `questions.json` file.
2. **Attach Answer Key** *(Optional)*: Upload a CSV, XLS, or XLSX answer key and select your form number.
3. **Clean PDF & Select Pages**: Discard blank or cover pages using standard presets ("ניקוי סטנדרטי", "עמודים זוגיים") and download a clean PDF.
4. **Clean PDF API Integration**: Automatically sends only selected pages to Gemini API / OCR processing to eliminate cover sheet noise.
5. **Configure Gemini OCR or External LLM**: Use a free Gemini API key with direct structured JSON schema extraction, or copy the extraction prompt to ChatGPT/Claude.
6. **Edit & Proofread**: Adjust text, options, answer keys, or compare side-by-side with original PDF page snapshots in **Proof Mode**.
7. **Image Compression Export Toggle**: Compress embedded question diagrams to WebP @ 75% quality, reducing exported HTML file sizes by 80%+ while preserving crisp visual quality.
8. **Export & Take**: Click **הורד מבחן עצמאי** to download a single-file HTML quiz, or **פתור מבחן כעת** to start immediately.

---

## 📝 Quiz Taker (`quiz_player.html`)

**`quiz_player.html`** + **`app.js`** + **`style.css`** — The standalone, RTL-native quiz player.

### Player Features
- **Native RTL Hebrew**: Purpose-built right-to-left UI with modern Rubik typography.
- **Question Flagging / Star (⭐)**: Bookmark challenging questions during a test with real-time star badges on the jump bar.
- **Mix & Match Custom Practice**: Combine categories (`Wrong`, `Unanswered`, `Starred`) and manually cherry-pick question cards in the Review List to launch targeted practice sessions.
- **Keyboard Navigation**:
  - `1`–`9`: Select answer choices.
  - `←` / `→`: Navigate between questions.
  - `Esc`: Close image zoom overlay.
- **Immediate Feedback**: Optional toggle to check answers instantaneously.
- **Progress Jump Bar**: Auto-centering single-line or multi-row jump toolbar showing real-time answered/correct status.
- **Auto-Save & Resume**: Per-quiz `LocalStorage` persistence saving answers and starred flags to resume uncompleted sessions.
- **Answer Shuffling**: Randomized options per session for exams without explicit answer keys.
- **Image Cropper & Fullscreen Zoom**: Crop embedded graphs or tables directly in the quiz card.
- **Results Dashboard & Review**: Score calculation with filters for **All**, **Wrong Only**, **Unanswered**, or **Starred** questions.
- **Dark & Light Themes**: Seamless theme switching with system preference support.

---

## 🖥️ Python Desktop GUI & Batch CLI Builder (`python_app/`)

- **Root CLI & Batch Runner (`quiz_builder.py`)**:
  - Run `python quiz_builder.py` to scan exam folders, auto-group flat files, auto-convert DOCX, and dispatch terminal agents.
  - Run `python quiz_builder.py --gui` or double-click **`start_app.bat`** to launch the Desktop GUI app.
  - Run `python quiz_builder.py --build` to compile all ready tests into `output/` with a **Master Quiz Portal** (`output/index.html`).
  - Run `python quiz_builder.py --watch` for live auto-recompilation on save.
- **Desktop GUI Application (`python_app/quiz_builder_gui.py` / `start_app.bat`)**:
  - Native, zero-dependency desktop app with Dark/Light themes, visual exam cards, 1-click prompt copy, agent dispatch, and live activity log.

---

## 🧪 Development Server & Component Test Suite

- **Desktop App Launcher (`start_app.bat`)**: Double-click to launch the native Python Desktop GUI.
- **Local Dev Server & Test Menu (`start_test_server.bat`)**: Double-click to launch a local HTTP server on port 8080, open the browser, and present an interactive menu.
- **Python Pytest Suite (`python_app/tests_py/`)**: Run `python -m pytest python_app/tests_py -v` (57 automated unit tests).
- **Local Component Test Suite (`test-suite/run_local_tests.py`)**: Run `python test-suite/run_local_tests.py` (10 automated component tests).
- **In-Browser Test Runner (`test-suite/test_runner.html`)**: Real-time browser component tests with performance metrics.

---

## 📁 Repository Structure

```
interactive-test-creator/
├── index.html            # Web Quiz Builder Interface (GitHub Pages Root)
├── generator.js          # OCR, Gemini API, & PDF Parser Engine
├── quiz_player.html      # Standalone Quiz Player Shell
├── app.js                # Quiz Engine & Navigation
├── style.css             # Unified RTL & Theme System
├── favicon.svg           # Application SVG Favicon
│
├── quiz_builder.py       # Root Python Entry Point (CLI & GUI wrapper)
├── start_app.bat         # Double-click Desktop GUI App Launcher
├── start_test_server.bat # Local HTTP Server & Test Launcher
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
├── tests/                # Local exam workspaces (gitignored)
└── output/               # Generated standalone quizzes & portal (gitignored)
```

---

## 🔑 Gemini API Keys

| Type | Prefix | How to Get |
|---|---|---|
| Gemini Free Tier | `AIza...` | [Google AI Studio](https://aistudio.google.com/apikey) |
| Gemini Cloud | `AQ...` | [Google Cloud Console](https://console.cloud.google.com/apis/credentials) |

---

## 📄 License

MIT — see [LICENSE](LICENSE).
