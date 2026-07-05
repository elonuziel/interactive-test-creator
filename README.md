# Interactive Hebrew Quiz Generator

> **React entry:** [index.html](index.html) | **Legacy builder:** [quiz_generator.html](quiz_generator.html) | **Legacy quiz taker:** [quiz_taker.html](quiz_taker.html)

Turn scanned Hebrew exam PDFs into interactive, self-grading quizzes. The repo now has a React-first root entry so it can be uploaded to Google AI Studio Build Mode, while the existing static builder and quiz player remain available as legacy pages.

## React / AI Studio entry

**`index.html`** + **`src/main.jsx`** + **`src/App.jsx`** + **`src/styles.css`** — the React shell for AI Studio.

### What this root app does
- Presents the repo as a React-based build target for AI Studio.
- Links to the existing builder and quiz player pages.
- Keeps the migration path open for moving Gemini calls to AI Studio server-side code later.
- Exposes route entry points: `/` (home), `/builder` (native React builder shell with runtime health), `/player` (legacy taker embedded).
- React `/builder` pre-fills legacy builder settings (`formNumber`, `llmPolicy`, `ocrEngine`) when launching `quiz_generator.html`.
- React `/builder` now supports local digital-PDF parsing directly in React (question extraction + optional CSV answer merge), with legacy fallback for scanned/LLM flows.

## Legacy pages kept in place

**`quiz_generator.html`** + **`generator.js`** — the original builder UI.

**`quiz_taker.html`** + **`app.js`** + **`style.css`** — the standalone quiz player.

### Generator features
- OCR engines — Gemini chunked or Gemini native PDF
- Answer key formats — CSV, XLS, XLSX with automatic form-number matching
- Proof mode — view the original PDF page alongside each question
- Add/remove answers — adjust option counts per question in the editor
- Image detection — charts, graphs, tables auto-attach page images for cropping
- Re-edit existing quizzes — upload a previously downloaded quiz HTML to continue editing
- File clear buttons — remove uploaded files without refreshing
- Keyless Gemini UX — no user API key input in the UI; requests go through server proxy

## AI Studio notes

- Google AI Studio Build mode generates web apps with React by default and a Node.js server runtime for secrets.
- Gemini requests now go through `/api/gemini/generate-content` in `server.js`, using `GEMINI_API_KEY` or `GOOGLE_API_KEY` from runtime environment variables.
- The browser no longer asks users to paste API keys or passcodes.
- This repo is structured so AI Studio can import the React shell while preserving the current HTML workflow.

## Runtime secrets

- Configure one of these server-side environment variables:
- `GEMINI_API_KEY`
- `GOOGLE_API_KEY`
- Do not place API keys in client-side code or user-facing forms.
- Runtime health check endpoint: `GET /api/gemini/health`
: Returns non-secret configuration status (`configured: true|false`) so UI/deploy checks can fail fast with clear messaging.

## Project Structure

```
index.html          — React root entry
src/                — React shell for AI Studio
quiz_generator.html — Builder UI
generator.js        — PDF extraction, OCR, parsing, export logic
quiz_taker.html     — Quiz player shell
app.js              — Quiz player logic
style.css           — Shared styles for legacy pages
vendor/pdfjs/       — PDF.js for in-browser PDF rendering
tests/              — Sample exam PDFs and answer keys
```

## Run locally

```bash
npm install
npm run dev
```

In a second terminal (for Gemini proxy):

```bash
GEMINI_API_KEY=your_key_here npm run dev:server
```

Then open `http://localhost:5173`.

## Build

```bash
npm run build
```

## License

MIT — see [LICENSE](LICENSE).
