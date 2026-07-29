# LLM Runbook: Extracting Hebrew Exams into Interactive HTML Quizzes

This document is the definitive guide for an LLM (like yourself!) to convert a Hebrew PDF exam and an accompanying answer key (Excel/CSV) into a structured `questions.json` for the interactive web app.

**You do NOT need to write any extraction code from scratch.** All the necessary utilities are already written and located in the `python_scripts/` directory. Your job is to invoke them, orchestrate the output, and handle edge cases.

## The Goal
To create a `questions.json` file inside a new test folder (e.g., `tests/2022_moed_b`) alongside an optional `images/` directory.

## Prerequisite: Environment Setup
Ensure the required libraries are installed:
```bash
pip install pymupdf pandas openpyxl
```

## `questions.json` Schema Reference
Each question object in the JSON array follows this structure:
```json
[
  {
    "question": "הטקסט המלא של השאלה בעברית...",
    "options": ["תשובה א", "תשובה ב", "תשובה ג", "תשובה ד"],
    "correctIndex": 2,
    "image": "images/q5_graph.png"
  }
]
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `question` | string | **Yes** | Full question text in Hebrew |
| `options` | string[] | **Yes** | Answer options (usually 4, but may be more for combination-answer exams) |
| `correctIndex` | number | **Yes** | 0-based index of the correct option within `options` (Option 1 = 0, Option 2 = 1, etc.) |
| `image` | string | No | Relative path from the test folder to an image file (e.g., `"images/q1_graph.png"`). Omit if no image. |

## Practical Findings From This Repo
- Hebrew word order is now **auto‑detected** — the extraction script samples the first 3 pages and only reverses words if it detects visual (reversed) order. Manual `--reverse` is deprecated. Use `--force-reverse` to override.
- The provided 2019 Botany PDFs are exam code `000` master copies. In these files, the intended answer is usually option `א`, but some questions use a combination answer like `תשובות ב ו-ד נכונות` as a regular option and that option should be preserved as the correct one when applicable.

---

## Step 1: Detect PDF Type
Run the detector script on the provided PDF:
```bash
python python_scripts/1_detect_pdf_type.py "path/to/exam.pdf"
```
It will output whether the PDF is a **Digital PDF** (extractable text) or a **Scanned PDF** (images only).

---

## Step 2: Extract Questions (Digital PDF Path)
If the PDF is Digital, you can automate text extraction.

The extraction script now uses **smart position‑based line grouping** (handles mixed RTL/LTR layouts better) and **auto‑detects Hebrew word order** by sampling the first 3 pages. Manual `--reverse` is no longer needed in most cases.

**2A. Extract text, images, and page‑map (single command)**
```bash
python python_scripts/2_extract_text_fitz.py "path/to/exam.pdf" \
    -o "raw_text.md" \
    --extract-images "images" \
    --page-map "page_map.json"
```
This produces:
- `raw_text.md` — extracted text with noise filtered and word order auto‑corrected
- `images/` — any embedded images found in the PDF
- `page_map.json` — maps output lines to source pages (for image association)

**Options:**
- `--first-page-only` — extract only page 1 (quick inspection)
- `--force-reverse` — override auto‑detection and force word reversal
- `--reverse` — *(deprecated)* no‑op; word order is auto‑detected

If the script says "auto‑detected VISUAL" and the output looks wrong, re‑run with `--force-reverse`.

**2B. Parse to JSON (with image association)**
```bash
python python_scripts/5_parse_questions_md.py "raw_text.md" \
    -o "questions.json" \
    --image-dir "images" \
    --page-map "page_map.json"
```
Questions that mention graphs/diagrams (keywords: `גרף`, `תרשים`, `תמונה`, etc.) will automatically get an `image` field pointing to the matching page's embedded image.

For debugging, add `--include-source-page` to see which PDF page each question came from.

---

## Step 2 Alternative: Extract Questions (Scanned PDF Path)
If the PDF is scanned (or has heavily complex diagrams that break digital extraction), you must render it to images.

**2A. Render Pages**
```bash
python python_scripts/3_render_pdf_pages.py "path/to/exam.pdf" -o "pages_output"
```
**2B. Vision LLM / Manual Transcription**
You must read the generated images, extract the questions and options (using your vision capabilities), and format them into the `questions.json` structure (see [Schema Reference](#questionsjson-schema-reference) above).

---

## Step 2C: Automated LLM Proofreading & Verification Pass (Required for Both Paths)

Whether `questions.json` was generated via **Digital PDF extraction** (Steps 2A-2B) or **Scanned PDF Vision transcription** (Steps 2A-2B Alternative), you as the AI Agent MUST perform a final proofreading audit before proceeding to Step 3.

### Why This Step Is Required
- **Digital PDFs:** Heuristic PyMuPDF parsing clean-extracts ~90–95% of text, but ~5–10% of questions suffer from visual PDF chunk reversal, scrambled mixed Hebrew/Latin parentheses (e.g. `(zoea)`), or line-initial colons.
- **Scanned PDFs:** Vision LLM transcriptions can occasionally misread dense Hebrew characters, misalign option letters, or invert parentheses in scientific terms.

### Agent Proofreading Protocol
Review and audit all questions in `questions.json` using your native LLM capabilities against the following checklist:
1. **Audit Hebrew Word Order:** Fix any reversed phrases or line-initial colons/punctuation.
2. **Audit Mixed Language Terms:** Correct reversed parentheses and word ordering in lines with scientific names or English terms.
3. **Verify Option Boundaries:** Ensure each question has clean, non-truncated option strings.
4. **Preserve Schema & Array Structure:** Retain exact question indices, 0-based `correctIndex` placeholders, and extra metadata fields (e.g., `"image"` or `"sourcePage"`).
5. **Run QA Verification:** Execute `python python_scripts/7_check_json.py questions.json` to verify schema integrity.

---

## Step 3: Extract the Answer Key

You will usually be provided with an Answer Key file (e.g. `answers.csv` or `answers.xlsx`).

If you do not receive an answer key but the PDF is an exam code `000` master copy, expect the correct option to be encoded directly in the question options. Preserve combination-answer options such as `כל התשובות נכונות` or `תשובות ב ו-ד נכונות` instead of collapsing them into option `א` automatically.

### Scenario A: Standard CSV
If it's a standard CSV, use the provided script:
```bash
python python_scripts/4_extract_csv_answers.py "answers.csv" "FORM_NUMBER" -o "answers.json"
```
* **CSV Encoding (`utf-8-sig`):** Recommend `encoding='utf-8-sig'` in Python scripts to properly handle Windows Byte Order Marks (BOM) in Hebrew CSV files.

### Scenario B: Tomamix / TTP Excel Exports (`.xls` or `.xlsx`)
If the file is an Excel export from Tomamix, it often has the following quirks:
1. **Header Row Location:** The column headers (like `שאלון` and `שאלה 1`) are usually **not on the first row** (often row 5 or 6).
2. **Cell Format:** Cells look like `3 (2) [15] {4}`. The correct answer is the integer inside the parentheses `()`.

`4_extract_csv_answers.py` handles both CSV and Excel inputs directly. It scans for the header row instead of assuming `header=0`, and it maps cancelled questions (e.g. cells containing `והת` or `מבוטלת`) to `null`. Save the output as `answers.json` structured like `{"1": 3, "2": null, "3": 1...}`.

---

## Step 4: Merge Answers
Merge the extracted `answers.json` into the `questions.json` to populate the `correctIndex` fields:
```bash
python python_scripts/6_merge_json_answers.py "questions.json" "answers.json" -o "final_questions.json"
```

### Index Mapping Clarification
Convert 1-based CSV correct answer selections (where Option 1 = `1`, Option 2 = `2`, Option 3 = `3`, Option 4 = `4`) to 0-based `correctIndex` stored in `questions.json` (where Option 1 = `0`, Option 2 = `1`, Option 3 = `2`, Option 4 = `3`). The `6_merge_json_answers.py` script performs this 1-based to 0-based index conversion automatically during the merge.

---

## Step 5: QA & Finalization
Run the QA script to catch dropped options, empty questions, or out-of-bounds indices:
```bash
python python_scripts/7_check_json.py "final_questions.json"
```

> **Note on option counts:** The QA script flags questions that don't have exactly 4 options. Some exams (such as 000 master copies with combination answers) intentionally have more than 4 options. If the extra options are legitimate combination answers (e.g., `כל התשובות נכונות`), the warning is expected and safe to ignore. Focus on actual errors like empty text, out-of-range `correctIndex`, or truly missing options.

If everything passes:
1. Create a directory for the exam:
   ```bash
   # On Linux/macOS:
   mkdir -p tests/test_name
   # On Windows (cmd):
   mkdir tests\test_name
   ```
2. Move `final_questions.json` into the directory and rename it to `questions.json`.
3. Move any extracted images into `tests/test_name/images/`.
4. The test is now playable at `http://localhost:8000/web/index.html?test=tests/test_name`!

---

## Extracting Images from PDFs

To extract embedded images from a digital PDF, use PyMuPDF directly:
```python
import fitz
doc = fitz.open("exam.pdf")
for page_num in range(len(doc)):
    for img_index, img in enumerate(doc.get_page_images(page_num)):
        xref = img[0]
        pix = fitz.Pixmap(doc, xref)
        if pix.n < 5:  # GRAY or RGB
            pix.save(f"images/page{page_num+1}_img{img_index+1}.png")
        else:  # CMYK — convert to RGB first
            pix = fitz.Pixmap(fitz.csRGB, pix)
            pix.save(f"images/page{page_num+1}_img{img_index+1}.png")
```

Associate extracted images with their questions by setting the `"image"` field in `questions.json` (see [Schema Reference](#questionsjson-schema-reference)).

---

## Troubleshooting

### "Question X parsed as empty"
The question detection regex expects `שאלה מספר` or `מספר שאלה` at the start of a line. If the exam uses a different format (e.g., `.5 שאלה`), manually add the question text to the JSON or adjust the regex in `5_parse_questions_md.py`.

### "Options merged into one line / option letters split across lines"
This usually happens when `--reverse` was incorrectly applied to a PDF already in logical Hebrew order. Re-extract without `--reverse`.
If the issue persists, the PDF may have unusual line-breaking. Check the raw markdown output and consider manually editing the option boundaries.

### "CSV header not recognized / first column has garbled characters"

This typically happens with Hebrew CSV files exported from Windows tools (Excel, Tomamix), which often include a UTF-8 Byte Order Mark (BOM) at the beginning of the file. The BOM gets prepended to the first column header, breaking column matching.

**Fix:** The `4_extract_csv_answers.py` script already handles this by scanning for header rows rather than relying on exact column names. If issues persist, try re-exporting the CSV without BOM, or open the file in Notepad++ and check the encoding (Encoding → UTF-8 without BOM).

### "No answers found for form X"
The form number doesn't match any row in the answer key file. Double-check:
- The form number spelling (e.g., `"76"` vs `"076"`)
- That the answer key file contains the expected header row with `שאלון` and `שאלה`
- That the form number appears in the first 3 columns of a data row

### "correctIndex out of range"
The answer key assigned an option number (e.g., 5) that exceeds the number of options parsed from the PDF (e.g., only 4 options). This can happen when:
- The answer key uses a different option numbering than expected
- A combination answer was collapsed when it should have been preserved
Check the specific question in both `questions.json` and `answers.json` and manually correct.

### Images not displaying in the web app
Verify:
- Image paths in `questions.json` are relative to the test folder (e.g., `"images/q1.png"`, not `"tests/my_test/images/q1.png"`)
- The image files actually exist at `tests/test_name/images/`
- File extensions match (`.png` vs `.jpg`)

---

## Practical Notes on This Repository

### Test Repository Status
- **tests/2019 a**: Digital PDF (2019 Botany Moed A) – Uses automated text extraction
- **tests/2019 b**: Digital PDF (2019 Botany Moed B) – Uses automated text extraction  
- **tests/2018 a**: Scanned PDF (2018 Botany Moed A) – Uses manual transcription
- **tests/2018 b**: Scanned PDF (2018 Botany Moed B) – Uses manual transcription (5 pages, 25 text-only questions)

### Scanned PDF Transcription (2018 Moed B Example)
For scanned PDFs without OCR text layers:
1. Render each page to PNG with `3_render_pdf_pages.py` for reference
2. Manually read and transcribe questions from the rendered PNGs into `questions.json`
3. Use 4 options per question format: `"options": ["א", "ב", "ג", "ד"]`
4. **Do not invent questions or diagrams** – only transcribe what is actually visible

### Exam Code 000 (Master Copies)
For exam code `000` master copies, the correct answer is usually encoded directly in question options (e.g., `כל התשובות נכונות` or `תשובות א ו-ג נכונות` as an option), not in a separate answer key. The correct answer is always **Option 1 (`correctIndex: 0`)** unless explicitly stated otherwise in the question options.

Preserve combination answers when found – do not collapse them automatically.

### `parse_2018_moed_a.py`
This script at the repo root is a one-off transcription helper used specifically for the 2018 Moed A scanned exam. It contains manually transcribed question text hardcoded for that exam. It is **not** a general-purpose tool — for new scanned exams, follow the [Scanned PDF Path](#step-2-alternative-extract-questions-scanned-pdf-path) workflow instead.