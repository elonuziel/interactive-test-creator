# Super Batch Option Specification

## Status
Draft product/technical specification. No implementation is included in this document.

## Goal
Add a **Super Batch** workflow in the GUI that processes many exam PDFs and their answer keys in one operation. It must work only with detected local CLI AI providers, automatically create a `questions.md` file for every eligible exam, and intelligently distinguish digital PDFs from scanned PDFs.

The workflow should provide a quick overview of each PDF and its matching answer key, infer the exam/test number and variant, match the correct answer key, and generate validated Markdown output for all selected exams.

## User-facing entry point

- Add a dedicated **Super Batch** action in the GUI.
- It must use the same underlying service/controller as any future CLI entry point, but the current requested entry point is the GUI.
- The user selects a root projects folder.
- Discovery is recursive through nested folders.
- Existing workspace/folder names are retained; no automatic renaming is required.
- The UI should clearly state that Super Batch supports local CLI AI providers only.
- The provider selector should include all detected local CLI providers already supported by the application, including Freebuff, agy, Claude, ChatGPT, Gemini, Ollama, and llm where available.
- Web-only providers must not be selectable for this operation.

## Discovery and input model

Super Batch recursively scans the selected root for exam projects and source files.

Recognized source inputs:

- PDF exam files.
- Existing answer-key sources supported by the application: CSV, XLS, XLSX, and Markdown answer keys.
- Legacy JSON answer keys may remain readable for compatibility, but Markdown should be the preferred editable/default format.

The implementation should reuse existing discovery and answer-key matching logic where possible, while extending it to support a batch plan containing multiple PDFs and candidate answer keys.

For folders containing multiple PDFs, each PDF should be treated as a distinct candidate/workspace according to existing project-slug behavior, unless an existing workspace mapping is already present.

## Processing phases

### Phase 1: Inspect and classify PDFs

For every discovered PDF:

1. Detect whether it is digital/text-based or scanned/image-based using the existing PDF classification flow.
2. For digital PDFs:
   - Extract text locally.
   - Use the existing configured page-discard/cleaning rules where regular mode does so.
   - Do not invoke AI merely to perform the zero-test/default-answer behavior described below.
3. For scanned PDFs:
   - Render page images/thumbnails and use OCR/vision-capable local CLI AI processing to understand the document.
   - The AI should receive extracted context and representative page thumbnails by default. The payload strategy may be configurable later, but the initial implementation should avoid requiring the provider to read an arbitrary local file path.
4. Build a compact quick overview containing at least:
   - Detected test/exam number.
   - Year/date when available.
   - Variant/form, including Moed A/B where available.
   - PDF classification.
   - Page count and basic source information.
   - Confidence and unresolved fields.

### Phase 2: Identify and match answer keys

- Parse answer-key files locally into normalized question-number-to-answer mappings whenever possible.
- Match keys using the detected test number and variant, plus existing filename/Moed matching rules.
- The AI may help identify metadata from scanned content, but local deterministic parsing and matching should be preferred for answer-key files.
- Present a review table before generation begins.
- The table should show, for each candidate:
  - Exam/workspace name.
  - PDF path.
  - Digital/scanned classification.
  - Detected test number/year/variant.
  - Proposed answer key.
  - Match confidence/status.
  - Any warnings.
- Clear matches may be bulk-confirmed.
- Unresolved or ambiguous cases should open focused confirmation dialogs after the table review.
- Do not silently select among multiple plausible answer keys.
- The user must be able to exclude individual items from the run.

### Phase 3: Decide how answers are produced

#### Digital PDFs

For digital PDFs, Super Batch should avoid AI for the special “zero test” behavior:

- Treat the generated digital-PDF test as a zero test where every correct answer is initially the first option.
- Do not ask AI to determine those correct answers.
- The final quiz/player may still scramble displayed answer choices using existing runtime behavior; the source correct index must be adjusted consistently by existing quiz logic.
- If an answer key is available and the user explicitly chooses to use it, the normal answer-key merge path may override the zero-test defaults. The UI must make this choice explicit rather than silently ignoring a supplied key.

#### Scanned PDFs

For scanned PDFs, the user must choose one of the following per item when no reliable answer key is available:

1. Generate questions only, with unresolved answer metadata according to the final Markdown schema.
2. Treat it as a zero test, assigning the first option as correct without asking AI to solve the exam.
3. Provide/use dedicated instructions for this exam, supplied by the user in the GUI and included in the AI prompt.

If a matching answer key is confirmed, use it as the source of correct answers rather than asking the AI to solve questions.

The exact no-key Markdown representation must be standardized during implementation. It must remain strictly parseable and pass the selected validation mode. Prefer an explicit unresolved representation over silently inventing a correct answer.

## AI invocation strategy

- Support two modes:
  - **Two-phase mode (default):** overview/metadata and context first, then focused question generation.
  - **Single-invocation mode (configurable):** provide the overview, answer mapping, PDF context, and instructions in one generation request.
- The provider command must be invoked through the existing provider/prompt abstraction, not via GUI-specific subprocess code.
- Accept either of these provider behaviors:
  - The CLI returns Markdown/content through its captured output.
  - The CLI writes the requested workspace file directly.
- In both cases, locate the resulting Markdown, normalize it, validate it strictly, and only then commit it as `questions.md`.
- Reject JSON-only output for the final user-editable artifact, though legacy/internal JSON compatibility may remain elsewhere in the application.
- Prompts must require raw Markdown in the canonical format and must not permit surrounding code fences or explanatory prose.
- Include the normalized answer mapping, detected metadata, and any user-provided dedicated instructions in the generation prompt.

## PDF cleaning

- Expose the existing configured discard-pages behavior in Super Batch.
- PDF page cleanup applies only to digital PDFs as requested.
- The operation must not silently discard pages from scanned PDFs.
- The UI should display the configured rule and allow the user to confirm or adjust it before starting.
- Reuse the regular-mode output conventions for cleaned/merged PDFs where cleanup is enabled.

## Concurrency and controls

- Use configurable worker concurrency for independent workspaces.
- Provide a conservative default (recommended: 2 workers), with the setting exposed in the Super Batch options.
- Respect provider/rate-limit constraints as much as possible.
- Include Start, Pause/Cancel, and final completion controls.
- Cancellation must prevent new jobs from starting and allow active subprocesses to terminate cleanly where supported.
- A failed item must not abort unrelated items.

## Progress and reporting

Show a live per-item log while processing. Each item should report:

- Current phase: discovery, classification, extraction/OCR, overview, matching, awaiting confirmation, generation, validation, saved, skipped, or failed.
- Workspace/PDF name.
- Detected metadata.
- Selected answer key and match status.
- Output path.
- Error and recovery guidance when applicable.

The user specifically requested live per-item progress. A persistent report file is not required for the initial feature because the requested artifact output is `questions.md` only, but the internal result model should be structured enough to support a report later.

## Existing files and overwrite policy

- If a workspace already contains `questions.md`, ask before replacing it.
- The review UI should make overwrite decisions visible per workspace.
- Do not overwrite confirmed existing files without an explicit user decision.
- Use atomic writes and preferably create a backup before replacement.
- Legacy `questions.json` files remain readable, but new Super Batch output is always `questions.md`.

## Output artifacts

Primary output:

- One validated `questions.md` per successfully processed exam workspace.

The initial user-facing workflow should avoid leaving a large set of intermediate artifacts. Temporary extraction text, thumbnails, prompts, and normalized answer data may be stored in a temporary/cache location and cleaned after successful completion.

The implementation must not expose JSON as the default output. Internal structured data may use JSON only where required by existing runtime/exporter interfaces.

## Strict validation

Before saving any generated output:

- Parse the returned Markdown with the shared Markdown parser.
- Require valid question headings and question text.
- Require a valid options list for every question.
- Require consistent numbering/order.
- Require valid answer metadata when an answer key or zero-test mode was selected.
- Require answer-key coverage when the user selected answer-key mode.
- Reject malformed, empty, truncated, or prose-wrapped AI output.
- Display validation errors with actionable recovery options: retry, edit instructions, exclude item, or save for manual repair if that mode is explicitly supported.

## Error handling

Errors should be isolated per item and shown with recovery guidance, including:

- Missing or unreadable PDF.
- No detected local CLI providers.
- Provider missing, unauthenticated, timeout, non-zero exit, or malformed output.
- OCR/thumbnail extraction failure.
- Missing answer key.
- Ambiguous answer-key match.
- Existing `questions.md` overwrite conflict.
- Markdown validation failure.
- Cancellation.

The error model should preserve provider stderr/exit status for diagnostics without exposing unnecessary implementation details in the primary dialog.

## GUI usability requirements

- Add an explanatory intro/help panel describing:
  - Recursive scanning.
  - Digital vs scanned handling.
  - Answer-key matching.
  - Why scanned exams may require a decision.
  - The fact that output is `questions.md`.
- Include an in-app canonical Markdown example/help link or dialog.
- Make provider, worker count, two-phase/single-call mode, page-cleaning option, and no-key handling visible before start.
- Show a review table before irreversible generation/overwrite decisions.
- Use accessible labels, tooltips, keyboard navigation, and clear disabled states.
- Keep the existing light/dark theme support.

## Configuration candidates

Add configuration fields only where they fit existing conventions:

- `super_batch_workers` (default 2).
- `super_batch_ai_mode` (`two_phase` default or `single_invocation`).
- `super_batch_discard_pages` / reuse existing discard-pages setting.
- Default no-key policy for scanned PDFs, while still requiring per-item confirmation where ambiguity exists.
- Provider allowlist is not required initially because the user selected all detected local CLIs.

## Testing requirements

Add focused tests for:

1. Recursive discovery of PDFs and candidate answer keys.
2. Test number/year/variant extraction from representative filenames and extracted metadata.
3. Deterministic answer-key normalization and matching.
4. Ambiguous/missing-key review states.
5. Digital-PDF zero-test behavior without AI invocation.
6. Scanned-PDF branching for generate-only, zero-test, and dedicated instructions.
7. Canonical prompt construction for both two-phase and single-invocation modes.
8. Acceptance of provider-returned Markdown and provider-written `questions.md`.
9. Strict validation and rejection of malformed output.
10. Existing `questions.md` overwrite confirmation and atomic replacement.
11. Per-item failure isolation and cancellation.
12. Configurable concurrency.
13. GUI offscreen tests for opening Super Batch, review table, option controls, progress updates, and confirmation dialogs.
14. Regression coverage for legacy JSON reading.

Tests that require PySide6, PDF libraries, or provider binaries should be skipped cleanly when dependencies are unavailable and exercised in CI where those dependencies are installed.

## Acceptance criteria

- A user can select a root folder in the GUI and recursively discover multiple PDF exams.
- Only detected local CLI AI providers are available for Super Batch.
- Each PDF receives a digital/scanned classification and a quick overview with test number and variant where detectable.
- Candidate answer keys are normalized and matched using metadata and existing variant logic.
- The user reviews all proposed matches and resolves ambiguous cases before generation.
- Digital PDFs can produce a zero test without an AI call for answer solving.
- Scanned PDFs provide explicit per-item choices for missing keys: generate-only, zero test, or dedicated instructions.
- The selected workflow generates a strictly valid `questions.md` for every successful item.
- Existing `questions.md` files are never overwritten without explicit confirmation.
- One failed item does not prevent other items from completing.
- Progress is visible live per item.
- Output writes are atomic.
- Existing legacy JSON workspaces remain readable.
- The GUI remains usable in both light and dark themes.
- The feature is covered by unit/integration tests and documented in the README/in-app help.
