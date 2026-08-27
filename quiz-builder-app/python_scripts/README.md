# Python Utilities for PDF to HTML Interactive Quiz

This folder contains the Python pipeline for extracting Hebrew exam PDFs into the interactive HTML format used by this project.

## Prerequisites
```bash
pip install pymupdf pandas openpyxl
```

`pandas` and `openpyxl` are only needed if you plan to read Excel answer keys with `4_extract_csv_answers.py`.

## Drop Folder Location & Input Files

Drop your raw PDFs (e.g. `exam.pdf`) and answer key spreadsheets (e.g. `answers.csv` or `answers.xlsx`) directly into a dedicated folder under `tests/` (e.g., `tests/test_1/`, `tests/test_2/`).

> 🔒 **Git Note**: Files inside `tests/` are matched by `.gitignore` (`test*/`) and will not be uploaded to GitHub.

## The Workflow

The scripts are numbered in the order you would typically use them.

### 1. `1_detect_pdf_type.py`
Determines if a PDF is a Digital PDF (has extractable text) or a Scanned PDF (images only). 
**Usage:** `python 1_detect_pdf_type.py "tests/test_1/exam.pdf"`

### 2. Digital PDF Path (if Step 1 is Digital)
Use these scripts to extract text, images, and parse it:

**A. `2_extract_text_fitz.py`**
Extracts text using PyMuPDF with smart position‑based line grouping (handles mixed RTL/LTR layouts better than raw `get_text()`).
Hebrew word‑order is **auto‑detected** — the script samples the first 3 pages and only reverses words if it detects visual (reversed) order.
Also supports embedded image extraction and page‑to‑line mapping for image association.

**Usage:**
```bash
# Extract text only (default — auto‑detects word order):
python 2_extract_text_fitz.py "exam.pdf" -o "raw_text.md"

# Extract text + embedded images + page‑map (for full pipeline):
python 2_extract_text_fitz.py "exam.pdf" -o "raw_text.md" \
    --extract-images "images" --page-map "page_map.json"

# Inspect first page only (quick check):
python 2_extract_text_fitz.py "exam.pdf" --first-page-only
```

**Options:**
| Flag | Description |
|------|-------------|
| `-o`, `--output FILE` | Output markdown file (default: `<pdf>_extracted.md`) |
| `--extract-images DIR` | Extract embedded images from the PDF into `DIR` |
| `--page-map FILE` | Write a JSON mapping `line_N → page_number` for image association |
| `--first-page-only` | Extract only page 1 (quick inspection) |
| `--force-reverse` | Force Hebrew word‑order reversal (overrides auto‑detection) |
| `--reverse` | *(deprecated)* No‑op — word order is auto‑detected now |

**B. `5_parse_questions_md.py`**
Parses the generated Markdown file into the default editable `questions.md` format.
Uses robust regex patterns that handle multiple question/answer formats including LTR‑grouped Hebrew text.
Supports image association via keyword detection (`גרף`, `תרשים`, etc.) and page‑map from step 2.

**Usage:**
```bash
# Parse text only:
python 5_parse_questions_md.py "raw_text.md" -o "questions.md"

# Parse with image association:
python 5_parse_questions_md.py "raw_text.md" -o "questions.md" \
    --image-dir "images" --page-map "page_map.json"

# Include source page in output (for debugging):
python 5_parse_questions_md.py "raw_text.md" -o "questions.md" \
    --include-source-page
```

**Options:**
| Flag | Description |
|------|-------------|
| `-o`, `--output FILE` | Output Markdown file (default: `questions.md`) |
| `--image-dir DIR` | Directory with extracted images for keyword‑based association |
| `--page-map FILE` | JSON file from `2_extract_text_fitz.py --page-map` |
| `--include-source-page` | Add `sourcePage` field to each question for debugging |

### 3. Scanned PDF Path (if Step 1 is Scanned)
Use these scripts to render the PDF to images and extract text manually (via Vision LLMs or manual transcription).

**A. `3_render_pdf_pages.py`**
Renders a PDF to PNG images per page.
**Usage:** `python 3_render_pdf_pages.py "exam.pdf" -o "pages"`

*After rendering, use an LLM or manual transcription to create `questions.md` with the text and options.*

### 4. Answer Extraction and Merging

**A. `4_extract_csv_answers.py`**
Extracts the correct answers for a specific exam form from the master student answers CSV or Excel export.
The script scans for the row containing `שאלון` and handles the `3 (2) [15] {4}`-style cell format. Recommend using `encoding='utf-8-sig'` when reading CSV files to properly process Windows Byte Order Marks (BOM) in Hebrew CSVs.
**Usage:** `python 4_extract_csv_answers.py "answers.xlsx" "76" -o "answers.json"`
*(Where "76" is the test form number)*

**B. `6_merge_json_answers.py`**
Merges the extracted answers from the CSV with the Markdown question source and maps 1-based CSV selections (1, 2, 3, 4) to 0-based `correctIndex` values (0, 1, 2, 3) stored in `questions.md`.
**Usage:** `python 6_merge_json_answers.py "questions.md" "answers.json" -o "questions.md"`

### 5. Quality Assurance

**`7_check_json.py`**
Checks the final Markdown question file for dropped options, empty questions, duplicate option text, or out-of-bounds `correctIndex` values. Run this before deploying!
**Usage:** `python 7_check_json.py "final_questions.json"`
**Options:** `--expected-options N` (default: 4; mismatched counts produce a warning instead of an error)

### 6. Auto-Generate Test Manifest

**`8_generate_manifest.py`**
Scans the `tests/` directory for subdirectories containing `questions.md` (or legacy `questions.json`) and generates a `manifest.json` file that the web app uses to populate the test selection menu.

**Usage:**
```bash
# Default: scan tests/ and write tests/manifest.json
python 8_generate_manifest.py

# Custom tests directory
python 8_generate_manifest.py --tests-dir path/to/tests

# Custom output path
python 8_generate_manifest.py -o custom_manifest.json
```

> **Note:** This script is automatically run by `run_server.bat` and `run_server.sh` before starting the HTTP server.

### 7. Build Single-File HTML

**`9_build_single_html.py`**
Builds a **completely self-contained HTML quiz file** that works by double-clicking — no server needed. Inlines CSS, JS, questions, and optionally images (as base64 data URIs) into a single `.html` file.

**Usage:**
```bash
# Basic usage
python 9_build_single_html.py "tests/2019_a" -o "botany_2019a.html"

# Without images (smaller file size)
python 9_build_single_html.py "tests/2019_a" --no-images

# With custom title
python 9_build_single_html.py "tests/2019_a" --title "בוטניקה 2019 מועד א"
```

**Options:**
| Flag | Description |
|------|-------------|
| `-o`, `--output FILE` | Output HTML file path (default: `<test_name>_quiz.html`) |
| `--no-images` | Skip embedding images (reduces file size) |
| `--title TEXT` | Custom page title |
