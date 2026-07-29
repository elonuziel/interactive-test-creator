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

### 🧙 Interactive CLI Wizard (`start.bat`)
A step-by-step Windows wizard (`start.bat`) that automates:
1. Environment & package prerequisite verification (`pymupdf`, `pandas`, `openpyxl`).
2. Test folder creation and raw PDF / answer key drop-folder setup.
3. PDF type detection & page image rendering for Vision LLM extraction.
4. Automatic answer key merging, schema QA validation (`7_check_json.py`), and test manifest updates (`8_generate_manifest.py`).
5. Building portable single-file HTML apps or starting local web servers.

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
cli-legacy/
├── start.bat                  # Interactive Windows wizard CLI
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
Follow the interactive prompts to set up test folders, render pages for LLM processing, validate JSON outputs, build standalone HTML files, or launch the web player.

### 2. Manual Workflow & Test Creation
1. **Create a Test Folder**: Place raw source files under `tests/` (e.g. `tests/botany_2024_a/`):
   - Exam PDF: `tests/botany_2024_a/exam.pdf`
   - Answer key spreadsheet: `tests/botany_2024_a/answers.csv` or `answers.xlsx`
2. **Process PDF & Extract Questions**:
   - Follow [LLM_RUNBOOK.md](LLM_RUNBOOK.md) for Vision LLMs or check [python_scripts/README.md](python_scripts/README.md) for script usages (`1_detect_pdf_type.py` through `6_merge_json_answers.py`).
3. **Validate & Update Manifest**:
   ```bash
   python python_scripts/7_check_json.py tests/botany_2024_a/questions.json
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
