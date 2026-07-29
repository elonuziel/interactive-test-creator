# Summary of Project Suggestions & Proposal Ideas

This document provides a consolidated overview of all proposals, feature suggestions, architectural designs, and maintenance improvements documented within the `suggestions/` directory.

---

## 1. Project Architecture & Maintenance

### Centralized Web Application (`web/`)
- **Current Issue:** Web application static assets (`index.html`, `style.css`, `app.js`, `run_quiz.bat`) are duplicated across individual test directories (`test_1` through `test_5`).
- **Proposed Solution:** 
  - Create a single shared root web folder (e.g., `web/` or `src/`) holding master templates.
  - Refactor test folders to only contain data (`questions.json`, `images/`).
  - Pass test identifiers dynamically via URL parameters (e.g., `index.html?test=test_5`), eliminating multi-folder code duplication and simplifying updates.

### Unified Test Launcher (`run_all.bat`)
- Replace per-directory batch files with a centralized root launcher script that presents an interactive menu to choose which test server/quiz to run.

### Pipeline & Documentation Standards
- **CSV Encoding:** Recommend `utf-8-sig` encoding in Python scripts to properly handle Windows Byte Order Marks (BOM) in Hebrew CSV files.
- **Index Mapping:** Clarify the conversion from 1-based CSV correct answer selections to 0-based `correctIndex` stored in `questions.json`.
- **Deterministic Ports:** Use `Port = 8000 + Test Number` (e.g. 8005 for `test_5`) to avoid server port collisions.
- **Vision LLM Fallbacks:** Include clear instructions for falling back to manual `Cropper.js` cropping when automated LLMs fail to transcribe complex Hebrew graph axes.

---

## 2. Interactive Web Quiz Builder ("Local-First" App)

### High-Level Architecture
- **Pure Client-Side Static App (Option A):** No backend server required. Runs 100% in the browser and can be hosted for free via GitHub Pages or run locally.
- **Privacy & Security:** Processing occurs locally on the client's machine. API keys are stored only in the browser's `localStorage` or decrypted temporarily in memory via a passcode modal (AES encryption).

### Key Features & UX Enhancements
1. **Auto-Routing PDF Parser:**
   - **Digital PDFs:** Uses `PDF.js` for sub-second, regex-based text extraction.
   - **Scanned PDFs:** Automatically detects lack of digital text, converts PDF pages to canvas images, and routes them to Gemini 1.5 Flash/Pro Vision API.
2. **"Preview and Edit" Visual Dashboard:**
   - Displays extracted question cards before final compilation.
   - Allows users to review, correct OCR/regex typos, and edit text or option selections directly on screen without touching raw JSON files.
3. **Single-File Offline Export:**
   - Compiles HTML, CSS, JS, and JSON question data into a single, downloadable `.html` file (e.g., `Exam_Moed_A.html`).
   - Enables end users to run quizzes offline by double-clicking the file in any web browser.

---

## 3. LLM-Powered Proofreading & Text Cleanup

### Optional Post-Processing Pass (`8_proofread_llm.py` / `verifyTestWithGemini`)
- **Problem Addressed:** Heuristic extraction handles ~90-95% of digital Hebrew PDFs clean, but ~5-10% of questions suffer from PyMuPDF chunk reversal (e.g., reversed RTL phrases, scrambled LTR/RTL parentheses like `(zoea)`, or merged table cells).
- **Proposed Pipeline Addition:**
  - An opt-in, batch-mode LLM pass using Gemini 1.5 Flash or GPT-4o-mini.
  - Sends all extracted questions in a single prompt call to repair word order, fix reversed parentheses, and verify option boundaries while retaining strict JSON schema compliance.
  - Verification with `7_check_json.py` ensures data integrity before final quiz generation.

---

## File Cross-Reference Matrix

| Original File | Primary Topic | Key Takeaways |
| :--- | :--- | :--- |
| [Untitled-1.md](file:///c:/Users/elon/Documents/GitHub/html-test-creator/suggestions/Untitled-1.md) | UX Ideas for Builder | Local-First design, visual card editing, single-file export, local storage key security. |
| [implementation_plan.md](file:///c:/Users/elon/Documents/GitHub/html-test-creator/suggestions/implementation_plan.md) | Technical Spec | `quiz_generator.html` UI structure, `generator.js` execution engine, PDF.js + PapaParse integration. |
| [llm_proofreader_pass.md](file:///c:/Users/elon/Documents/GitHub/html-test-creator/suggestions/llm_proofreader_pass.md) | Quality & OCR Fixes | Post-extraction LLM proofreading pass for RTL text reversal and mixed language parentheses. |
| [quiz_builder_proposal_1.md](file:///c:/Users/elon/Documents/GitHub/html-test-creator/suggestions/quiz_builder_proposal_1.md) | Architecture Tradeoffs | Comparison of Client-Side Static App vs. Python Backend Web Server (Flask/Streamlit). |
| [suggestions.md](file:///c:/Users/elon/Documents/GitHub/html-test-creator/suggestions/suggestions.md) | Project & Guide Maintenance | Centralizing `web/` assets, root test launcher, UTF-8-SIG BOM guidelines, port assignment rules. |
