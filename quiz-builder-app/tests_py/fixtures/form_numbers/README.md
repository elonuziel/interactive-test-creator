# Form-number fixtures

These CI-safe text fixtures model text extracted from deliberately confusing PDFs:

- `comprehensive.txt`: exam code, labeled form `063`, page-number noise, and unrelated numbers.
- `form_zero.txt`: no content form label; the filename supplies `000`.
- `ambiguous.txt`: two equally strong labeled form candidates.

The production detector consumes extracted PDF text, so these fixtures test the deterministic metadata layer without requiring a PDF/OCR runtime in CI.

For local real-PDF validation, use the ignored repository corpus under `tests/`. A binary PDF should only be added after legal/licensing review and should contain no personal data.
