# 📝 Interactive Hebrew Quiz Creator & Player (`html-test-creator` - CLI Legacy)

A modern, end-to-end framework and wizard for transforming Hebrew exam PDFs (digital or scanned) and answer key spreadsheets into fully interactive, RTL-optimized web quizzes and portable single-file HTML applications.

---

## 🌟 Key Features

### 📱 Premium RTL Interactive Web Quiz (`web/`)
The web application (`web/index.html`, `web/app.js`, `style.css` in `web/`) offers a responsive and accessible quiz interface:
- **Native RTL & Hebrew Support**: Built specifically for Hebrew text formatting and right-to-left layout.
- **Built-in Image Cropper & Viewer**: Powered by Cropper.js (`web/cropper.min.js`), allowing users to view and crop diagrams, tables, and graphs embedded in full-page exam scans directly inside questions.
- **Immediate Feedback Mode**: Toggle optional instant answer checking.
- **Keyboard Shortcuts**:
  - `1` – `4`: Select answer options.
  - `←` / `→`: Navigate between questions.
  - `Esc`: Close image viewer/cropper modal.
- **Progress Tracking & Jump Bar**: Real-time progress bar with visual question status indicators and quick-jump navigation.
- **Dynamic Shuffling & Auto-Save**: Randomize question choices per run and save test state automatically to `LocalStorage` (scoped per test).
- **Rich Review Screen**: Detailed score breakdown with filters for **All**, **Wrong Only**, or **Unanswered** questions.
- **Dark & Light Themes**: Responsive toggle for visual comfort.

---

### 🧙 Interactive CLI (`quizbuilder`, `start.bat` / `start.sh`)
A command-oriented CLI with an optional guided wizard automates:
1. Environment & package prerequisite verification (`pymupdf`, `pandas`, `openpyxl`).
2. Test folder creation and exam source drop-folder setup (`.pdf` or `.docx`) plus answer-key sheets.
3. PDF type detection & page image rendering for Vision LLM extraction.
4. Automatic answer key merging, schema QA validation (`7_check_json.py`), and test manifest updates (`8_generate_manifest.py`).
5. Building portable single-file HTML apps or starting local web servers.
6. Detecting an installed `freebuff` or `freebuff-cli` command and offering it as a prompt-helper destination.

Install the CLI from this directory with `python -m pip install -e .` (or `python -m pip install -e '.[test]'` for tests). Copy `quizbuilder.toml.example` to `quizbuilder.toml` to customize defaults. On Linux/macOS, run `bash start.sh` (or `./start.sh` after making it executable). The launcher resolves its own directory and uses `python3`, falling back to `python`.

If `.docx` files are detected, the wizard asks once whether to convert all DOCX files to PDF. If matching PDFs already exist, it also asks once whether to overwrite them. If a local converter backend is available, conversion is attempted automatically. If not, the wizard provides manual export-to-PDF steps and resumes after you place PDFs in the same folder.

---

### 📦 Portable Single-File HTML Exporter
Build completely **self-contained HTML files** for any test that run by double-clicking without needing a web server or backend:
```bash
python python_scripts/9_build_single_html.py tests/2022_moed_a -o "botany_2022a.html"
```
Inlines CSS, JS, question data, and images (as base64 data URIs) into a single portable `.html` file suitable for offline distribution, email, or messaging apps.

---

### 🤖 LLM & Vision Extraction Workflow
Designed for AI agents (such as Antigravity, Gemini, ChatGPT, Claude) to extract questions from scanned or digital exam PDFs:
- **[LLM Runbook](LLM_RUNBOOK.md)**: Detailed instructions and schema for AI agents processing exam page scans.
- **[Prompt Generator](python_scripts/generate_prompts.py)**: Helper script to generate standardized LLM extraction prompts.

---

## 📁 Directory Structure

```
quiz-builder-app/
├── start.bat                  # Interactive Windows wizard CLI
├── start.sh                   # Linux/macOS wizard launcher
├── LLM_RUNBOOK.md             # AI Agent instructions for PDF extraction
├── README.md                  # Legacy CLI project documentation
├── web/                       # Legacy Web Quiz App
│   ├── index.html             # Main quiz HTML structure
│   ├── app.js                 # Quiz logic, navigation, cropper & state
│   ├── style.css              # Custom styling & dark mode system
│   ├── cropper.min.js         # Image cropper library
│   └── cropper.min.css        # Image cropper stylesheet
├── python_scripts/            # Pipeline utility scripts
│   ├── 1_detect_pdf_type.py   # PDF text vs scan detector
│   ├── 2_extract_text_fitz.py # Text & image extraction via PyMuPDF
│   ├── 3_render_pdf_pages.py  # Render PDF pages to PNG for LLMs
│   ├── 4_extract_csv_answers.py# Extract answer keys from CSV/XLSX
│   ├── 5_parse_questions_md.py# Heuristic Markdown question parser
│   ├── 6_merge_json_answers.py# Merge answer keys with questions JSON
│   ├── 7_check_json.py        # QA validator for question JSON schema
│   ├── 8_generate_manifest.py # Auto-generate tests menu manifest
│   ├── 9_build_single_html.py # Pack single-file standalone HTML quiz
│   ├── generate_prompts.py    # Generate LLM extraction prompts
│   └── README.md              # Documentation for Python scripts
├── servers/                   # Local web server launchers
│   ├── run_server.bat         # Windows Python HTTP server runner
│   └── run_server.sh          # Linux/macOS Python HTTP server runner
└── tests_py/                  # Pytest test suite for Python pipeline
```

---

## 🚀 Quick Start

### 1. Using the Interactive Wizard (Windows)
Double-click `start.bat` or run from terminal:
```cmd
start.bat
```

### 2. Using the Interactive CLI (Linux/macOS)
```bash
bash start.sh
# Or, once executable:
./start.sh
```

Useful commands include:
```bash
python -m pip install -e ".[gui]"
python -m quizbuilder gui
python -m quizbuilder --help
python -m quizbuilder detect
python -m quizbuilder serve --port 8000
python -m quizbuilder init biology_101
python -m quizbuilder process tests/biology_101
python -m quizbuilder prompt tests/biology_101 --kind local
python -m quizbuilder validate tests/biology_101/questions.md
python -m quizbuilder build tests/biology_101
python -m quizbuilder clean tests/biology_101
python -m quizbuilder wizard
python -m quizbuilder --config quizbuilder.toml detect
```

The desktop GUI lets you choose a projects folder, edit a test's `questions.md`
with RTL-aware fields, save changes, and export a standalone HTML quiz. Markdown is
now the default human-editable question format; legacy `questions.json` files remain
readable for compatibility. Select one
test for a normal run, or check multiple tests and enable mixed mode to create a
derived quiz without changing the source projects. Generated runs are placed in
the folder's `runs/` directory.

To build a portable desktop bundle, install the GUI and packaging extras and run
`python build_gui.py` from this directory. PyInstaller builds for the operating
system it is run on; create the Windows bundle on Windows and the Linux bundle on
Linux.

The prompt-helper menu includes hosted Freebuff Chat, which opens `https://freebuff.com/chat` in the browser after generating the web prompt. If `freebuff` or `freebuff-cli` is installed on `PATH` (or configured through `freebuff_commands`), it also includes Freebuff CLI and pipes the generated local prompt to the command through standard input.

Follow the interactive prompts to set up test folders, render pages for LLM processing, validate JSON outputs, build standalone HTML files, or launch the web player.

### 3. Configuration

Copy `quizbuilder.toml.example` to `quizbuilder.toml` and customize workspace defaults. Pass a different file with `--config path/to/config.toml`.

### 4. Manual Workflow & Test Creation
1. **Create a Test Folder**: Place raw source files under `tests/` (e.g. `tests/botany_2024_a/`):
   - Exam source: `tests/botany_2024_a/exam.pdf` or `tests/botany_2024_a/exam.docx`
   - Answer key spreadsheet: `tests/botany_2024_a/answers.csv` or `answers.xlsx`
   - Note: The processing pipeline remains PDF-native. DOCX files should be converted to PDF before extraction (wizard can attempt this automatically when a converter is available).
2. **Process PDF & Extract Questions**:
   - Follow [LLM_RUNBOOK.md](LLM_RUNBOOK.md) for Vision LLMs or check [python_scripts/README.md](python_scripts/README.md) for script usages (`1_detect_pdf_type.py` through `6_merge_json_answers.py`).
3. **Validate & Update Manifest**:
   ```bash
   python python_scripts/7_check_json.py tests/botany_2024_a/questions.md
   python python_scripts/8_generate_manifest.py
   ```
4. **Launch Local Web App**:
   ```bash
   # On Windows:
   servers\run_server.bat
   # On Linux/macOS:
   bash servers/run_server.sh
   ```

---

## 🧪 Testing

Run the Python pytest suite covering question parsing, answer merging, and QA validations:

```bash
pip install pytest
pytest tests_py/ -v
```

---

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](../LICENSE) file for details.
