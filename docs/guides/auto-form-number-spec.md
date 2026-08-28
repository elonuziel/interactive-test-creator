# Automatic PDF Form-Number Detection Specification

## Status

Draft implementation specification. This document records the requested behavior and clarified decisions. **No implementation is included in this change.**

## Request summary

When the application obtains or generates `questions.md` from an exam PDF, it should automatically detect the exam/form number from the PDF rather than requiring the user to type it manually. The detected form must drive answer-key selection and answer-column/row lookup when the test is understood, built, merged, or exported.

The same behavior must be shared across:

- The root website builder and player.
- The legacy/Python web application.
- The Python CLI and scripts.
- The desktop GUI, including regular extraction, Web AI Batch, and Super Batch.
- All generated local/web/AI prompts and runbooks.
- Standalone HTML and hub builds where metadata/runtime behavior matters.

The existing repository tests and fixtures under `tests/` must be used to verify the implementation, with additional focused tests added under the project’s existing test locations as appropriate.

## Goals

1. Detect a form number from PDF content as the primary source.
2. Support Hebrew, English, numeric, and common exam-specific labels.
3. Correctly recognize examples such as `מבחן מס' 063`, including any three-digit value from `000` through `999`.
4. Preserve the displayed/raw value, including leading zeroes, while using a normalized numeric value for matching.
5. Use the PDF-derived form to select the correct answer-key row/column.
6. Treat Form 0 as a meaningful zero-test mode, not merely as an arbitrary default.
7. Replace manual form entry in normal flows with automatic detection, while allowing a clearly warned override.
8. Make the logic consistent across all application surfaces and prompts.
9. Require user confirmation when detection is missing, ambiguous, or conflicts with other metadata.
10. Preserve compatibility with existing `questions.md`, legacy JSON, answer-key formats, and existing runtime behavior.

## Non-goals

- Do not redesign the entire question Markdown schema.
- Do not remove support for manually supplied answer keys.
- Do not force migration of every existing `questions.md` file immediately.
- Do not physically randomize/rewrite answer choices during build solely because a test is Form 0.
- Do not silently choose an answer-key column when the PDF-derived value is unavailable or ambiguous.
- Do not require an online third-party service for deterministic form detection or answer-key matching.

## Decisions from interview

### Detection source and precedence

- Inspect PDF content first, using locally extracted text for digital PDFs and OCR/vision context for scanned PDFs.
- Filename and folder metadata may be used as fallback or supporting evidence, but must not outrank a high-confidence labeled value found in PDF content.
- Detection should support a broad heuristic set: Hebrew, English, numeric, and exam-specific labels.
- The common expected label is `מבחן מס' 063`, but the detector must also understand variants such as:
  - `מבחן מס 063`
  - `מבחן מספר 063`
  - `מספר מבחן: 063`
  - `שאלון 063`
  - `Form 063`
  - `Test 063`
  - `Exam No. 063`
  - Similar punctuation, spacing, apostrophe, quote, and RTL/LTR arrangements.
- Accept one or more digits where the source uses them. Three-digit values, including `000`, must be supported explicitly.
- Preserve the raw/display form (`063`) and normalize it to a numeric lookup identity (`63`) for matching. Form `000` normalizes to numeric form `0` but retains `000` for display and provenance.

### Candidate selection and confidence

- Rank candidates using confidence scoring.
- Prefer a number adjacent to a recognized label such as `מבחן מס'`, `שאלון`, `Form`, or `Exam No.`.
- Candidate evidence should record source, raw text, normalized value, location/context where available, and confidence.
- If multiple candidates are close in confidence, do not silently choose. Require confirmation.
- A candidate found only in an unrelated filename token or page number should have low confidence and must not override labeled PDF content.

### Persistence and Markdown

- Newly generated `questions.md` files must contain a visible form metadata line before the question sections.
- Use a canonical visible line such as:

  `Form number: 063`

- The exact final localized wording may follow existing product language conventions, but it must be machine-recognizable and stable across all generated prompts/builders.
- Newly generated files only are required to use the standardized metadata heading/line.
- Existing files without metadata must remain readable and must not be rewritten merely because they were opened or inspected.
- Legacy files may be upgraded when they are rebuilt or regenerated.
- The metadata should include enough provenance for diagnostics, preferably including normalized form, source (`pdf-content`, `ocr`, `filename`, `manual-override`, etc.), and confidence without making the visible document unnecessarily noisy.
- If the implementation uses an additional machine-readable representation, it must not break the existing Markdown parser. The visible heading remains mandatory for newly generated output.

### Manual override and conflicts

- The PDF-derived form is authoritative for automatic answer-key lookup.
- Users may override it in GUI and website flows, but the UI must show a prominent warning that the override changes answer-key selection.
- A conflict between the PDF form and an answer-key form should default to the PDF-derived value for lookup, while clearly displaying the conflicting values and offering the warned override path.
- If a user confirms an override, record it in metadata/provenance and include it in diagnostics/prompts.
- If no form can be detected, or multiple candidates are unresolved, pause and ask the user rather than silently falling back.

### Form 0 behavior

- Form 0 is valid and has a specific meaning: all source correct answers are option 1 (the first option, represented internally as `correctIndex: 0`).
- Form `000` is numerically equivalent to Form 0 for answer-key matching, while the displayed raw value remains `000`.
- Form 0 must not cause the AI to solve answers.
- Prompts must explicitly state that Form 0 means every source answer is option 1 and that the player/runtime should scramble displayed choices while preserving correctness.
- The source question data should retain `correctIndex: 0` and a clear shuffle contract, such as `shuffleOptions: true`, rather than physically rewriting option order during build.
- The shared quiz runtime must perform the shuffling and correct-index remapping consistently for website, GUI-generated exports, standalone HTML, and any other player path.
- Official answer-key merging for a confirmed nonzero form must disable shuffling according to current behavior; Form 0 remains the explicit zero-test/shuffle case.

### Answer-key formats

Apply automatic form selection to all supported answer-key sources where the format permits it:

- CSV.
- XLS.
- XLSX.
- Markdown/text answer keys.
- Legacy JSON, where form metadata or form-specific mappings exist.

The implementation must reuse and consolidate current parsing/matching behavior rather than creating separate incompatible rules for each surface.

For tabular answer keys:

- Locate the row/column associated with the normalized PDF form number.
- Preserve leading-zero display text for UI and diagnostics but compare normalized numeric identities (`063` == `63`).
- Support current answer representations including numeric selections, parenthesized selections, English letters, Hebrew letters, and existing Form 0 bracket conventions.
- Reject or ask for confirmation when a matching form is absent, duplicated, or structurally ambiguous.
- Do not use a generic/default form merely because `Config.default_form` is currently `0` when a PDF-derived value exists.

## Proposed shared data model

Introduce or consolidate a reusable form metadata model in the shared core. The exact class/module location should follow existing project conventions, but it should expose at least:

```text
raw_value: string              # e.g. "063"
normalized_value: string       # canonical numeric identity, e.g. "63"
is_form_zero: bool             # true for 0/000 after normalization
source: enum/string            # pdf_text, ocr, filename, manual_override, etc.
confidence: float
label/context: optional string
candidates: optional list
was_overridden: bool
```

The shared detector should provide:

- Candidate extraction from text.
- Candidate ranking.
- Normalization preserving raw display form.
- Resolution state: resolved, missing, ambiguous, or conflict.
- Human-readable diagnostics for GUI, website, CLI, and logs.

The shared answer-key resolver should accept the form metadata and return:

- Selected source/row/column.
- Normalized answer map.
- Match status and confidence.
- Warnings/conflicts.
- Whether user confirmation is required.

## Processing flow

### 1. PDF acquisition and classification

For every PDF-to-questions flow:

1. Identify the selected source PDF, including cleaned/converted PDF paths where applicable.
2. Extract enough content to detect metadata:
   - Digital PDF: local text extraction first.
   - Scanned PDF: OCR/vision extraction or AI-provided document context.
3. Run the shared form detector against the relevant PDF content.
4. Use filename/folder evidence only as fallback/supporting evidence.
5. Produce a resolved form metadata object or an explicit unresolved state.

### 2. Before answer-key lookup

1. If there is exactly one high-confidence form candidate, use it automatically.
2. If there are several close candidates, show all candidates and require confirmation.
3. If no candidate exists, ask for a form value in interactive flows.
4. In non-interactive CLI mode, fail with an actionable error unless an explicit form override/flag was supplied.
5. Do not silently use `default_form` as a substitute for a missing detected form in answer-key mode.

### 3. Answer-key resolution

1. Normalize the resolved form for lookup while retaining its raw display form.
2. Resolve the answer-key row/column using the shared resolver.
3. Validate that the selected key has usable question answers.
4. Display the chosen form, normalized identity, source, answer-key source, and match confidence.
5. If the PDF form conflicts with the answer-key metadata, prefer the PDF-derived lookup and show a warning; permit an explicit warned override.
6. If Form 0 is resolved, bypass answer solving and apply the zero-test contract.

### 4. Questions Markdown generation

All generation paths must include the canonical visible metadata line before question sections. Prompts must tell AI systems to preserve it and not invent or alter it without evidence.

A generated file should resemble:

```markdown
# Quiz Questions

Form number: 063

## Question 1
Question text
- Option A
- Option B
- Option C
- Option D

Answer: A
```

For Form 0, the output must additionally preserve the runtime shuffle contract, either as a supported visible metadata line or as the normalized question data written by the builder. The parser/exporter must retain `shuffleOptions: true` where the existing format supports that field.

The Markdown parser must:

- Ignore the metadata line when constructing question text.
- Read the metadata when present.
- Continue reading legacy files without metadata.
- Avoid treating the form line as a question or option.

### 5. Prompt generation

All prompt families must receive consistent form context:

- Root website Gemini/external LLM prompts.
- Python `generate_prompts.py` local prompts.
- Python web prompts.
- CLI-generated prompts.
- Super Batch generation prompts.
- Web AI Batch prompts.
- LLM runbook/in-app prompt instructions.
- Proofreading and enhanced/image-safe prompts.

Prompts should include both:

- Raw/display form value, e.g. `063`.
- Normalized lookup value, e.g. `63`.
- Source and confidence.
- Whether it is Form 0.
- Whether a manual override was applied.
- The selected answer-key status when available.

Required prompt rules:

- Do not ask AI to solve answers when a confirmed official answer key exists.
- Do not ask AI to solve answers for Form 0.
- For Form 0, explicitly state that all correct source answers are option 1 and that displayed answer choices must be shuffled by the shared runtime with correct-index remapping.
- Preserve the metadata line in `questions.md`.
- If metadata is unresolved, tell the AI not to guess and require the application/user resolution path instead.
- Keep raw Markdown output requirements compatible with current parsers: no JSON-only replacement, code fences, or explanatory prose in final Markdown output.

## Surface-by-surface scope

### Root website builder

Affected areas include the PDF extraction/upload flow, answer-key controls, form input UI, `generator.js`, `question-parser.js`, `quiz-core.js`, and related prompt/service code.

Expected behavior:

- Detect form metadata from the uploaded/processed PDF before answer-key merge.
- Populate the visible form control automatically.
- Show source/confidence and allow a warned manual override.
- Use the detected/confirmed form in CSV/XLS/XLSX parsing and merge.
- Include metadata in generated questions data/Markdown.
- Ensure Form 0 sets the shared shuffle behavior.

### Root website player and exported player

Affected areas include `app.js`, `quiz_player.html`, export helpers, and shared `quiz-core.js` behavior.

Expected behavior:

- Preserve form metadata through export.
- Apply Form 0 shuffling through shared runtime logic.
- Remap `correctIndex` after shuffle.
- Keep saved answer state, review mode, score calculation, and missed-question practice correct after shuffling.
- Avoid changing official answer-key tests that intentionally disable shuffling.

### Python web application

Affected areas include `quiz-builder-app/web/app.js`, web parsing/answer merging, and its generated/loaded `questions.md` flow.

Expected behavior:

- Detect and display form metadata during extraction and answer-key matching.
- Revalidate metadata at build/merge time.
- Ask interactively in the website when missing or ambiguous.
- Keep Form 0 runtime behavior consistent with the root player.

### Desktop GUI

Affected areas include the Extract tab, Web AI Batch dialog, Super Batch dialogs/engine, answer matrix/merge controls, and export/build actions.

Expected behavior:

- Replace the default manual-first form field with detected form display/status.
- Keep an editable override control with warning text.
- Show detection source, raw and normalized values, confidence, and unresolved candidates.
- Ask for confirmation for missing/ambiguous/conflicting cases.
- Pass resolved form metadata to regular extraction, prompt generation, answer merging, Web AI Batch, Super Batch, standalone export, and hub generation.
- Super Batch review rows must show detected form metadata and answer-key selection status before generation.
- Digital and scanned branches must both use the same resolver.
- Form 0 must be explicit in the decision table and prompt, not inferred only from the current default config.

### CLI and Python scripts

Affected areas include `commands.py`, `prompts.py`, `super_batch.py`, `batch.py`, `workspace.py`, `generate_prompts.py`, answer extraction scripts, merge scripts, and validation/build commands.

Expected behavior:

- Expose automatic detection as the default behavior.
- Retain an explicit form override argument for non-interactive use.
- Fail clearly when answer-key resolution requires user input but no override is supplied.
- Ensure Super Batch currently passing a hard-coded `"0"` does not bypass PDF detection.
- Ensure `WebAIBatchDialog` does not always use `config.default_form`.
- Keep answer-key normalization deterministic and reusable.

## Configuration changes

Avoid adding configuration where detection should be automatic. Existing `default_form` may remain for backwards compatibility and explicit fallback/override scenarios, but it must not override a resolved PDF form.

Potential configuration additions, only if consistent with existing conventions:

- Detection confidence threshold.
- Whether filename fallback is allowed in a specific non-interactive mode.
- Whether to require confirmation below a configured confidence.

Defaults should favor safety: unresolved or conflicting answer-key selection requires confirmation rather than silent selection.

## Error and edge-case behavior

Handle at least the following:

1. `מבחן מס' 063` → raw `063`, normalized `63`.
2. `מבחן מס' 000` → raw `000`, normalized `0`, Form 0 true.
3. `Form 0`, `שאלון 0`, and `000` → same lookup identity, with raw source retained.
4. Leading-zero key value `063` and numeric key value `63` → equivalent lookup.
5. No labeled form in PDF → ask in GUI/website; actionable failure in non-interactive CLI.
6. Multiple labeled forms in one PDF → rank; ask when not clearly resolved.
7. A page number that resembles a form number → do not select without form-label evidence.
8. Form number only in filename → use as fallback with lower confidence and visible provenance.
9. PDF form conflicts with key filename or key row → prefer PDF for lookup, show warning, allow warned override.
10. Multiple matching answer-key rows/columns → do not silently select.
11. Missing selected answer-key form → report available forms and ask for override/alternate key.
12. Form 0 with no answer key → assign first option and enable runtime shuffling.
13. Confirmed official answer key → merge answers and disable shuffling according to current semantics.
14. Existing legacy `questions.md` without metadata → load normally; add metadata on rebuild only.
15. Existing legacy JSON → remain readable and receive automatic form resolution when rebuilt/merged.
16. Malformed metadata line → ignore safely, report diagnostic, and rerun detection rather than crashing.
17. OCR produces conflicting representations such as `O63`/`063` → normalize only when confidence supports it; otherwise ask.
18. Hebrew/English RTL punctuation and apostrophe variants → normalize for matching but retain evidence text.

## Testing plan

Use the repository’s existing test assets under `tests/`, especially:

- `tests/2022/מועד א.pdf`
- `tests/2022/מועד ב.pdf`
- `tests/2022/מועד א.xls`
- `tests/2022/מועד ב.xls`
- `tests/2019/מועד א 2019.pdf`
- `tests/2019/מועד א 2019.xlsx`
- `tests/2021/ליטורל מועד ב טופס 0.pdf`
- `tests/2021/מועד א ליטורל 2021.pdf`
- Existing year fixtures and answer-key files under the remaining `tests/<year>/` directories.

Add focused tests in existing suites rather than creating a parallel framework.

### Detector unit tests

- Hebrew labeled values with apostrophe, colon, spacing, and RTL variants.
- English labels and filename fallback.
- `0`, `00`, and `000` normalization to Form 0.
- `063` preservation and equivalence to `63`.
- One-or-more digit policy.
- Candidate confidence ranking.
- Multiple candidates and unresolved ambiguity.
- Page-number false positives.
- OCR punctuation/character noise.

### Answer-key unit/integration tests

- CSV selection using detected `063` against a `63` row.
- XLS/XLSX selection using the PDF-derived normalized value.
- Markdown/text and legacy JSON behavior.
- Hebrew letters, English letters, numeric, parenthesized, and bracket answer formats.
- Form 0 behavior with all answers mapped to internal index `0`.
- Missing form, duplicate form, and conflicting form diagnostics.
- Ensure the PDF-derived form is passed instead of `Config.default_form`.

### Markdown and prompt tests

- Generated metadata line is visible and parseable.
- Parser ignores metadata as a question and preserves legacy files.
- Prompt output contains raw and normalized form values, source/confidence, and Form 0 instructions.
- Local, web, Super Batch, Web AI Batch, and proofreading prompt variants share the same rules.
- AI output containing a metadata line still parses correctly.

### GUI tests

Use the existing PySide6 offscreen test conventions in `quiz-builder-app/tests_py` to cover:

- Automatic form population/status in the Extract tab.
- Manual override warning.
- Missing/ambiguous candidate confirmation dialog.
- Conflict warning and PDF-preferred lookup.
- Super Batch review metadata and answer-key match.
- Web AI Batch prompt generation with detected form.
- Form 0 decision and displayed shuffle setting.

### Website/runtime tests

Extend the existing Node and browser suites:

- Root `quiz-core.js` form normalization and answer extraction.
- Root generator auto-detection/merge flow.
- Python web app metadata parsing and merge flow where testable.
- Form 0 choice shuffling and correct-index remapping.
- Official answer-key merge remains non-shuffled.
- Exported standalone player preserves correctness after shuffle.
- Saved answers/review/results remain correct after shuffled rendering.

### End-to-end verification

At minimum, exercise:

1. A PDF with an ordinary nonzero form and matching tabular answer key.
2. A PDF containing `מבחן מס' 063` with a key row/column represented as `63`.
3. A Form 0/`000` PDF with no key, verifying all source answers are option 1 and runtime choices shuffle.
4. A scanned PDF where OCR is needed.
5. A missing/ambiguous form requiring interactive confirmation.
6. A conflicting key case where the PDF form is used by default and the override warning appears.
7. The same representative scenarios in root website, Python web app, GUI, and CLI/prompt paths where practical.

Existing relevant test files include:

- `test-suite/run_tests.js`
- `test-suite/browser/quiz-flow.spec.js`
- `quiz-builder-app/tests_py/test_merge_answers.py`
- `quiz-builder-app/tests_py/test_web_batch.py`
- `quiz-builder-app/tests_py/test_super_batch.py`
- `quiz-builder-app/tests_py/test_super_batch_engine.py`
- `quiz-builder-app/tests_py/test_gui_offscreen.py`
- `quiz-builder-app/tests_py/test_markdown_questions.py`
- `quiz-builder-app/tests_py/test_parse_questions.py`
- `quiz-builder-app/tests_py/test_quizbuilder_commands.py`
- `quiz-builder-app/tests_py/test_hub_exporter.py`
- `test-suite/run_local_tests.py`

Dependency-sensitive tests should skip cleanly when PySide6, PDF libraries, Excel readers, or browser tooling are unavailable, consistent with existing project conventions.

## Acceptance criteria

- The application detects a PDF form number from labeled PDF content without requiring manual typing in the normal path.
- `מבחן מס' 063` is detected as raw `063` and matched numerically to form `63`.
- `000`, `00`, `0`, `Form 0`, and equivalent recognized values produce the Form 0 behavior while preserving the source display value.
- The detected PDF form drives answer-key row/column selection for CSV, XLS, XLSX, Markdown/text, and compatible JSON sources.
- No detected form or unresolved multiple candidates never silently selects an answer-key form.
- PDF-vs-key conflicts use the PDF value by default, show a warning, and allow an explicit warned override.
- Newly generated `questions.md` files contain the canonical visible form metadata line before questions.
- Legacy question files remain readable and are not auto-rewritten until rebuild.
- All prompt families receive raw form, normalized form, provenance/confidence, and Form 0 instructions.
- No prompt asks AI to solve answers for Form 0 or for a confirmed official answer key.
- Form 0 uses `correctIndex: 0` plus shared runtime shuffling/remapping across website, GUI exports, and standalone player.
- Root website, Python web application, GUI, CLI, Super Batch, Web AI Batch, answer merging, and export flows use the same resolution logic.
- Existing tests continue to pass, and new detector/answer-key/prompt/UI/runtime coverage exercises the supplied `tests/` fixtures.
- This specification is implemented without changing the established output artifact from `questions.md`.

## Implementation sequencing recommendation

1. Add shared form metadata normalization, candidate detection, ranking, and resolution states.
2. Consolidate answer-key form lookup around the shared normalized identity.
3. Update Markdown read/write compatibility and generated metadata.
4. Update Python CLI, regular GUI, Web AI Batch, and Super Batch flows.
5. Update root JavaScript core/generator/player/export paths.
6. Update Python web app and all prompt templates/runbooks.
7. Add unit, integration, GUI, browser, and fixture-backed tests.
8. Run Python and Node suites, then browser tests where available, and resolve cross-surface regressions.
