# cli-legacy Full-Project Refactor Specification

## Status

Planned breaking refactor. This specification records the requested direction before implementation.

## Goals

Refactor the complete `cli-legacy/` project into a clearer, more maintainable, reliable, and easier-to-use application. The refactor may introduce breaking internal and user-facing changes where they materially improve the design.

The result should:

- Replace the monolithic interactive wizard with a cleaner command-oriented CLI while retaining a guided mode for users who want it.
- Support moderate non-interactive automation through flags and configuration.
- Use a simple data-driven registry for AI providers and launch targets.
- Establish explicit module boundaries and reusable interfaces.
- Refactor the Python pipeline, web player, and standalone exporter together.
- Add modern Python packaging with `pyproject.toml`.
- Add TOML configuration for paths, defaults, and provider behavior.
- Fail clearly at startup when required dependencies are unavailable.
- Improve tests, documentation, and migration guidance.

## Compatibility decision

This is a breaking cleanup. Existing internal interfaces, menu wording, module names, and numbered script names may change. All repository references and documentation must be updated consistently.

Where practical, short compatibility wrappers may remain temporarily, but they are not a requirement if they complicate the new architecture.

## Current-state findings

The current project contains:

- `quiz_builder_cli.py`, a large all-in-one Python wizard containing platform handling, dependency checks, workspace management, DOCX conversion, PDF processing orchestration, AI detection, prompt helpers, cleanup, post-processing, and browser launching.
- Numbered scripts under `python_scripts/` for PDF detection, extraction, rendering, answer extraction/merging, parsing, validation, manifest generation, and HTML building.
- Separate shell launchers under `start.bat`, `start.sh`, and `servers/`.
- A browser-based quiz player under `web/` with JavaScript, CSS, HTML, image cropping, persistence, review, and theme behavior.
- A standalone HTML exporter that bundles assets and data.
- Python tests under `tests_py/` with optional runtime dependencies such as PyMuPDF.
- Existing Freebuff detection added to the CLI for `freebuff` and `freebuff-cli`, currently wired directly into the monolithic wizard.

## Target architecture

### 1. Python package layout

Create a proper package, for example:

```text
cli-legacy/
├── pyproject.toml
├── README.md
├── start.bat
├── start.sh
├── src/
│   └── quizbuilder/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py
│       ├── config.py
│       ├── errors.py
│       ├── models.py
│       ├── paths.py
│       ├── dependencies.py
│       ├── workspace.py
│       ├── providers.py
│       ├── prompts.py
│       ├── pipeline.py
│       ├── documents.py
│       ├── postprocess.py
│       ├── exporter.py
│       └── platform.py
├── scripts/
│   └── ... optional compatibility entrypoints ...
├── web/
├── tests/
└── legacy/                  # only if temporary wrappers are retained
```

Names may be adjusted during implementation, but each module must have one primary responsibility.

### 2. CLI commands

Replace the current menu-first flow with explicit commands. The exact command names may be finalized during implementation, but the minimum capability set is:

- `init` — create or inspect a workspace.
- `detect` — inspect PDF type and available dependencies.
- `extract` — extract digital PDF text/images or render scanned pages.
- `prompt` — generate local/web/Freebuff prompts.
- `process` — run the end-to-end pipeline for a workspace.
- `validate` — validate questions JSON.
- `build` — generate a standalone HTML quiz.
- `serve` — run the local web player.
- `clean` — remove generated scratch artifacts safely.
- `wizard` — optional guided wrapper around the explicit commands.

Commands should expose useful non-interactive options such as workspace path, input files, form number, output path, page filtering, provider, and whether to build/open the result.

### 3. Configuration

Use TOML configuration, loaded from predictable locations:

1. Explicit `--config` path.
2. Workspace-local config.
3. User config directory where appropriate.
4. Built-in defaults.

Configuration should cover:

- Workspace/test root.
- Default form number.
- Default page-discard policy.
- Output directories and filenames.
- Dependency policy.
- Preferred AI provider.
- Provider command names and browser URLs.
- Whether browser opening is enabled by default.
- Whether standalone builds are automatic.

Never store API keys or secrets in committed TOML files. Environment variables or interactive secret input may be documented separately.

### 4. Models and errors

Introduce typed, explicit data structures for:

- Workspace metadata.
- Source document selection.
- PDF analysis results.
- Extraction results.
- Prompt provider definitions.
- Pipeline results and generated artifacts.
- Validation summaries.

Create domain-specific exceptions with user-safe messages and optional diagnostic details. Avoid broad silent exception handling except around optional integrations where a fallback is intentional.

### 5. Dependency policy

Use `pyproject.toml` as the source of truth. Define runtime and development/test dependencies, with sensible optional groups if needed.

The application should perform a strict startup check for required dependencies before commands that need them. The error must identify:

- Missing package.
- A copyable install command.
- The command or feature affected.
- Whether a lighter command remains available.

Avoid importing heavyweight optional libraries at module import time when doing so prevents help/version commands from running. Dependency validation should be explicit and command-aware even though the selected policy is strict for execution.

### 6. Provider registry

Replace hardcoded provider branches with a small registry/data model. Each provider should define:

- Stable provider ID.
- Display name.
- Detection function or executable names.
- Provider type: local command, browser URL, or other supported type.
- Prompt handoff strategy.
- Launch strategy.
- Whether it is available on the current platform.

Required providers:

- Local CLI agents currently supported by the project (`agy`, `gemini`, `claude`, as applicable).
- Freebuff command aliases: `freebuff` and `freebuff-cli`.
- Existing browser destinations: ChatGPT, Gemini Web, Claude Web, and Google AI Studio.

Freebuff behavior:

- Detect the first available local command on `PATH`.
- Offer Freebuff only when detected in the provider list.
- Generate the local prompt file before launch.
- Pipe prompt contents to the detected command via standard input.
- Launch and wait for the user to return/confirm completion.
- Do not invent a URL or automatic clipboard transfer for the CLI path.

### 7. Pipeline service

Create an orchestration service that composes document detection, conversion, rendering, extraction, prompt generation, answer merging, validation, manifest generation, cleanup, and export.

The orchestrator must:

- Avoid embedding user prompts and filesystem operations throughout the CLI layer.
- Return structured results rather than relying on global state.
- Support both interactive and non-interactive callers.
- Preserve intermediate artifacts until the configured cleanup stage.
- Make failures identify the exact stage and workspace.
- Avoid destructive cleanup unless explicitly requested or confirmed in interactive mode.

### 8. Document and workspace services

Separate:

- Path resolution and application-root detection.
- Workspace creation/listing/selection.
- PDF/DOCX discovery.
- DOCX-to-PDF converter detection.
- Platform-specific file opening.
- PDF type analysis and page handling.

The workspace service should not print directly. Presentation belongs in the CLI layer.

### 9. Prompt service

Centralize prompt generation and output paths. Prompt generation should support:

- Local agent prompts.
- Web AI prompts.
- Freebuff prompt launch.
- Printing prompts to the terminal.

Prompt files must be clearly classified as generated artifacts and excluded from accidental question-file autodetection.

### 10. Web player and exporter

Refactor `web/` alongside the Python code without changing the core user capabilities:

- RTL Hebrew quiz presentation.
- Immediate feedback setting.
- Welcome-screen immediate-feedback control.
- Question navigation and keyboard support.
- Review filters and persistence.
- Image cropper and zoom.
- Theme switching.
- Standalone HTML output.

Separate web concerns where appropriate:

- State/persistence.
- Rendering.
- navigation/input handling.
- review/results.
- theme.
- cropper/zoom.

The exporter should consume a clear template/assets/data interface rather than duplicating asset discovery logic. Ensure standalone builds continue to work without a server.

### 11. Shell launchers

Keep platform launchers simple:

- `start.sh` resolves its own directory, selects `python3` then `python`, and executes the package entrypoint while forwarding arguments.
- `start.bat` selects the packaged executable or Python environment and executes the same CLI entrypoint.
- `servers/run_server.sh` and `.bat` should delegate to the new `serve` command or remain thin wrappers.

Avoid business logic in shell scripts.

### 12. Numbered script migration

Numbered scripts may be renamed freely. If removed, update:

- Python imports and subprocess calls.
- Shell launchers.
- Build configuration.
- Tests.
- README and runbooks.
- Any generated or embedded references.

Prefer a small number of stable public commands over requiring users to understand pipeline script numbering.

## Testing strategy

Add or reorganize tests at these levels:

1. Unit tests for config loading, path resolution, dependency checks, provider detection, prompt routing, PDF classification, and validation.
2. Service tests for pipeline orchestration with mocked external tools.
3. CLI tests for command parsing, non-interactive behavior, and actionable errors.
4. Existing parser/merger/QA regression tests.
5. Web tests for the player, welcome-screen feedback toggle, prompt controls where applicable, exporter output, and standalone loading.
6. Shell syntax checks for launchers.

Tests must not launch real external AI providers or depend on network availability. Use injected runners, fake executables, temporary directories, and browser interception.

## Documentation requirements

Update `cli-legacy/README.md` to include:

- Installation using `pyproject.toml`.
- Virtual environment setup.
- Commands and examples.
- Guided wizard usage.
- Linux/macOS and Windows launchers.
- Configuration file locations and example TOML.
- Provider detection and Freebuff usage.
- Dependency troubleshooting, including PyMuPDF/`fitz`.
- Migration notes from the old wizard and numbered scripts.
- Development and test commands.

Keep `LLM_RUNBOOK.md` aligned with the new prompt/artifact paths and workflow.

## Migration order

1. Add package skeleton, models, errors, config, paths, and dependency handling.
2. Extract pure utilities and workspace/document services from the monolith.
3. Implement provider registry, including Freebuff, behind testable interfaces.
4. Implement pipeline orchestration and adapt existing numbered functionality.
5. Add command-oriented CLI and retain a temporary wizard wrapper if useful.
6. Update launchers and packaging.
7. Refactor web player/exporter and update browser tests.
8. Remove obsolete code, duplicate logic, and stale documentation.
9. Run complete tests, syntax checks, build checks, and manual smoke tests.

## Acceptance criteria

- [ ] `cli-legacy` has a clear package/module structure with single-responsibility modules.
- [ ] The main CLI file is no longer a monolithic implementation of all concerns.
- [ ] Explicit commands support the major workflow stages.
- [ ] A guided wizard remains available if needed for usability.
- [ ] Non-interactive flags support common automation scenarios.
- [ ] `pyproject.toml` defines installation and development/test dependencies.
- [ ] TOML configuration is documented and tested.
- [ ] Missing required dependencies produce actionable startup errors.
- [ ] Provider detection is data-driven and testable.
- [ ] Freebuff and `freebuff-cli` detection and stdin prompt handoff work as specified.
- [ ] Existing local/web AI provider options remain available as appropriate.
- [ ] PDF, DOCX, answer-key, parsing, validation, cleanup, and export behavior is covered by regression tests.
- [ ] The web player retains existing functionality, including the welcome-screen immediate-feedback toggle.
- [ ] Standalone HTML export remains functional.
- [ ] `start.sh`, `start.bat`, and server launchers are thin and validated.
- [ ] Documentation and migration notes are complete.
- [ ] Full test and lint/type/syntax validation passes in a properly provisioned environment.

## Explicit non-goals

- No automatic prompt transfer into hosted Freebuff Chat unless separately requested.
- No committed API keys or secrets.
- No production deployment or remote repository changes as part of the refactor.
