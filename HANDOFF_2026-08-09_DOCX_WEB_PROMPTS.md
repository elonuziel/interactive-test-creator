# Handoff Summary (2026-08-09)

## Scope Completed

### 1) CLI now accepts DOCX intake and converts to PDF before pipeline
- Implemented in [cli-legacy/quiz_builder_cli.py](cli-legacy/quiz_builder_cli.py).
- Added converter detection:
  - LibreOffice soffice backend.
  - Microsoft Word COM backend (PowerShell on Windows).
- Added ask-once prompt when DOCX files are found:
  - Convert all DOCX to PDF now?
- Added ask-once overwrite behavior:
  - Overwrite matching existing PDFs or skip.
- Added manual fallback if no converter is detected:
  - User exports DOCX to PDF manually and continues.
- Downstream processing remains PDF-native and unchanged.

### 2) Web flow has safer DOCX behavior + better prompt text
- Implemented in [generator.js](generator.js).
- If user selects DOCX in the PDF picker, web now shows a clear message to convert DOCX to PDF first instead of failing deep in PDF parsing.
- Default AI extraction prompt in web now includes explicit image-based options handling rules.

### 3) Enhanced prompt generation for complex image-heavy exams
- Implemented in [cli-legacy/python_scripts/generate_prompts.py](cli-legacy/python_scripts/generate_prompts.py).
- Script now generates both standard and enhanced prompts:
  - prompt_local_agent.txt
  - prompt_web_ai.txt
  - prompt_local_agent_enhanced.txt
  - prompt_web_ai_enhanced.txt
- Enhanced prompts explicitly instruct:
  - Use placeholders for image-only options.
  - Keep schema compatible with current pipeline.
  - Preserve/assign pageImage for visual questions.

### 4) CLI cleanup/autodetect updated for enhanced prompt files
- Implemented in [cli-legacy/quiz_builder_cli.py](cli-legacy/quiz_builder_cli.py).
- Enhanced prompt files are excluded from markdown autodetection and included in scratch cleanup handling.

### 5) Tests added for new CLI DOCX flow
- Added [cli-legacy/tests_py/test_quiz_builder_cli_docx.py](cli-legacy/tests_py/test_quiz_builder_cli_docx.py).
- Covers:
  - Existing-PDF skip without overwrite.
  - Overwrite path calls converter.
  - No-converter fallback behavior.
  - Converted-PDF preference behavior.

## Current Modified Files (not committed yet)
- [cli-legacy/python_scripts/generate_prompts.py](cli-legacy/python_scripts/generate_prompts.py)
- [cli-legacy/quiz_builder_cli.py](cli-legacy/quiz_builder_cli.py)
- [generator.js](generator.js)

## Workspace Validation Done
- Python syntax compile passed for:
  - [cli-legacy/python_scripts/generate_prompts.py](cli-legacy/python_scripts/generate_prompts.py)
  - [cli-legacy/quiz_builder_cli.py](cli-legacy/quiz_builder_cli.py)
- Editor diagnostics showed no errors in changed files.
- Note: full pytest run was previously blocked on missing pytest in environment.

## Prompt Generation Validation Done
Validated in folder:
- [cli-legacy/tests/2026_chemistry_a](cli-legacy/tests/2026_chemistry_a)

Found generated prompt files:
- [cli-legacy/tests/2026_chemistry_a/prompt_local_agent.txt](cli-legacy/tests/2026_chemistry_a/prompt_local_agent.txt)
- [cli-legacy/tests/2026_chemistry_a/prompt_web_ai.txt](cli-legacy/tests/2026_chemistry_a/prompt_web_ai.txt)
- [cli-legacy/tests/2026_chemistry_a/prompt_local_agent_enhanced.txt](cli-legacy/tests/2026_chemistry_a/prompt_local_agent_enhanced.txt)
- [cli-legacy/tests/2026_chemistry_a/prompt_web_ai_enhanced.txt](cli-legacy/tests/2026_chemistry_a/prompt_web_ai_enhanced.txt)

## Quality Check Snapshot (latest run)
- Questions file checked: [cli-legacy/tests/2026_chemistry_a/questions.json](cli-legacy/tests/2026_chemistry_a/questions.json)
- QA script: [cli-legacy/python_scripts/7_check_json.py](cli-legacy/python_scripts/7_check_json.py)
- Result: schema check passed (no errors/warnings).
- Important content warning:
  - Extracted questions count was only 3 while [cli-legacy/tests/2026_chemistry_a/pages_output](cli-legacy/tests/2026_chemistry_a/pages_output) contains 12 page images.
  - This likely indicates under-extraction for this exam.

## What Must Be Tested Next (Resume Checklist)

### A) Prompt effectiveness on all 3 converted PDFs
1. Run extraction using enhanced prompt files for each exam workspace.
2. Confirm all pages were processed, not only the first few.
3. Confirm image-based options use placeholders consistently.
4. Confirm visual questions include pageImage.

### B) Content completeness checks
1. Question count per exam should be plausible for full paper length.
2. Spot-check random pages against extracted questions.
3. Verify no large page ranges are missing from extraction.

### C) Pipeline integration checks
1. Run merge step and verify correctIndex behavior (Form 0 / all answers = 1 path when applicable).
2. Build standalone HTML and open quiz.
3. Confirm visual questions are answerable with page image context.

### D) Regression checks
1. Ensure old PDF-only workflow still behaves identically.
2. Ensure DOCX conversion prompt appears only when DOCX exists.
3. Ensure overwrite prompt appears only when matching PDF exists.

## Suggested Commands to Continue
- Run CLI workflow:
  - python cli-legacy/quiz_builder_cli.py
- Validate questions file:
  - python cli-legacy/python_scripts/7_check_json.py cli-legacy/tests/<workspace>/questions.json
- Build standalone HTML:
  - python cli-legacy/python_scripts/9_build_single_html.py cli-legacy/tests/<workspace>
- Run tests (after installing pytest):
  - python -m pip install pytest
  - python -m pytest cli-legacy/tests_py -q

## Open Risks / Known Gaps
1. Option-level images are still not first-class schema fields in player rendering.
2. Current practical strategy is placeholder options + pageImage context.
3. Extraction quality depends on LLM compliance with enhanced prompt and full page coverage.
4. Coverage warning is not yet automated in QA script (possible future improvement).

## Recommended Next Implementation (if continuing development)
1. Add optional coverage warning in [cli-legacy/python_scripts/7_check_json.py](cli-legacy/python_scripts/7_check_json.py):
   - warn when extracted question count is suspiciously low relative to rendered page count.
2. Add optional image-option schema extension later (only if needed):
   - requires updates in player render path and single-file builder.
3. Keep md-first extraction for complex image-heavy exams, then normalize to JSON.
