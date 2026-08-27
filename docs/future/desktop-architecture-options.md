# Future Desktop Architecture Options

Status: deferred. The active desktop implementation is Python + PySide6 + PyInstaller.

## Current Decision

Keep the current PySide6 application as the production path for now.

It already matches the repository's strongest dependencies:

- PyMuPDF for PDF inspection, extraction, and rendering.
- pandas/openpyxl for CSV/XLS/XLSX answer keys.
- Existing Python parser, validation, batch, provider, and export services.
- PyInstaller for standalone Windows and Linux bundles.

The user experience is a normal desktop application. Python is bundled inside the application, so end users do not need to install Python.

## Deferred Option: Tauri + Python Services

A future rewrite could use a Tauri frontend with a modern web UI and retain Python for document processing:

```text
Tauri desktop UI
        |
Local typed bridge or localhost service
        |
Python application services
        |
PyMuPDF, spreadsheet processing, parsing, validation, export
```

This should be a new frontend, not an immediate rewrite of the working PySide6 application.

### Advantages

- Modern frontend UI stack.
- Smaller runtime than Electron.
- Stronger frontend layout and interaction tooling.
- Rust can provide secure filesystem/process boundaries.
- Good long-term option if the application becomes a polished commercial product.

### Costs

- Rust and Cargo become required build tools.
- A stable local API must be designed first.
- Python process lifecycle, errors, cancellation, and packaging need a bridge.
- Windows and Linux builds need separate integration testing.
- The question editor, PDF preview, batch queue, provider launcher, and export flows must be rebuilt.
- Packaging becomes a Tauri bundle containing both the web frontend and Python runtime/services.

## Trigger Conditions

Reconsider Tauri when one or more of these are true:

- The PySide6 UI cannot meet required interaction or visual quality.
- Frontend development becomes the dominant part of the product.
- There is a need for a browser-like plugin/component ecosystem.
- The application needs a shared web UI and desktop UI.
- The team is prepared to maintain Rust, TypeScript, and Python together.
- Clean-machine installers and signing are already part of the release process.

## Migration Requirements

Before starting a Tauri rewrite:

1. Extract all business logic from Qt callbacks into Python application services.
2. Define typed request/response contracts for projects, batch jobs, questions, validation, generation, and export.
3. Add a local service or subprocess protocol with structured JSON messages.
4. Add cancellation, progress, and error events to that protocol.
5. Add contract tests independent of either frontend.
6. Keep the standalone HTML quiz export format unchanged.
7. Run PySide6 and Tauri frontends against the same fixtures until the replacement is complete.
8. Build Python service/runtime artifacts for Windows and Linux before integrating them into Tauri.

## Other Alternatives

### Electron

Useful if the product becomes primarily a web application, but it is larger and would still need the Python processing backend. Not preferred for this project.

### Flutter

Can provide a polished cross-platform UI, but would require a Dart-to-Python bridge and a second UI ecosystem. Not preferred unless mobile support becomes important.

### C++/Qt

Strong native performance and packaging, but it would require rewriting the Python document pipeline. Not justified by the current requirements.

## Recommended Sequence

1. Validate the PySide6 GUI against the real `tests/מבחנים` corpus.
2. Finish Windows packaging and clean-machine installation.
3. Stabilize Python service contracts and fixture coverage.
4. Revisit Tauri only as a parallel frontend experiment.
5. Replace PySide6 only after the Tauri frontend matches the existing workflow and release artifacts.
