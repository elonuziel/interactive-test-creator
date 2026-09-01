---
description: Rules for Super Batch exam processing, offline execution, and AI analysis for scanned PDFs
trigger: always_on
---

# Super Batch Workflow & Processing Rules

## 1. AI Analysis for Scanned PDFs
- **AI MUST analyze all scanned PDFs, unless specifically stated not to.**
- Whenever a PDF is scanned (image-only, photocopies, or classified as scanned by the detector):
  - Always render the PDF pages to high-resolution PNG images in `pages_output/` using `3_render_pdf_pages.py`.
  - Use AI multimodal Vision to read the page images and transcribe the questions into `questions.md` according to `quiz-builder-app/LLM_RUNBOOK.md`.

## 2. Twin Copying & Substitution Prompt Rule
- **Prompt the user when a digital twin is found:** If an exam folder contains both a scanned PDF and a matching digital version (twin), do **NOT** silently substitute or copy questions from the digital file.
- The system must explicitly prompt the user, stating that a digital twin was found and asking if they want to substitute the clean digital version or analyze the scanned PDF using AI Vision.
- Only substitute if the user explicitly approves.

## 3. Digital PDF Processing
- Born-digital PDFs (with readable digital text streams) should be processed automatically via the native pipeline (`2_extract_text_fitz.py` -> `5_parse_questions_md.py`) without using AI.
- **Digital PDFs should NOT normally use Vision**, unless the user explicitly requests it.
- If a digital PDF contains legacy font encoding (e.g. Word/Distiller phonetic IPA characters `0x2a0`–`0x2ba`), decode it deterministically rather than triggering AI vision.

## 4. Zero External Downloads & 100% Offline Runtime
- NEVER run `apt-get`, `pip install`, or any network-dependent commands.
- All pipeline and script executions must remain 100% offline.
- Use the bundled standalone Python 3.12 runner at `./test/py312` which includes all necessary precompiled libraries and C-extensions (`fitz`/PyMuPDF, `pandas`, `openpyxl`, `xlrd`).

## 5. Case-Insensitive PDF Discovery on Linux
- On Linux filesystems, `.PDF` and `.pdf` have different cases. When discovering PDFs in `super_batch.py` or batch scripts, always use case-insensitive matching:
  ```python
  p.is_file() and p.suffix.lower() == ".pdf"
  ```

## 6. Multi-PDF Workspace Isolation
- When an exam folder contains multiple PDFs, each exam must have an isolated workspace under `.quizbuilder/<project-slug>` to ensure `questions.md`, `pages_output/`, and `quiz.html` do not conflict.

## 7. Strict Question & Schema Validation
- Every `questions.md` must pass `strict_questions()` validation before finalizing standalone `quiz.html` or compiling `quiz_hub.html`.
- Merge official answer keys when available, ensuring the answer letter is valid for the question's options.
