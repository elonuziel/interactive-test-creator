# Interactive Hebrew Quiz Generator

> **React entry:** [index.html](index.html) | **Legacy builder:** [quiz_generator.html](quiz_generator.html) | **Legacy quiz taker:** [quiz_taker.html](quiz_taker.html)

Turn scanned Hebrew exam PDFs into interactive, self-grading quizzes. The repo now has a React-first root entry so it can be uploaded to Google AI Studio Build Mode, while the existing static builder and quiz player remain available as legacy pages.

## React / AI Studio entry

**`index.html`** + **`src/main.jsx`** + **`src/App.jsx`** + **`src/styles.css`** — the React shell for AI Studio.

### What this root app does
- Presents the repo as a React-based build target for AI Studio.
- Links to the existing builder and quiz player pages.
- Keeps the migration path open for moving Gemini calls to AI Studio server-side code later.

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

## AI Studio notes

- Google AI Studio Build mode generates web apps with React by default and a Node.js server runtime for secrets.
- The next migration step is to move Gemini calls to server-side code so the API key stays out of the browser.
- This repo is now structured so AI Studio can import the React shell while preserving the current HTML workflow.

## API Keys

| Type | Prefix | How to get |
|---|---|---|
| Gemini (free) | `AIza...` | [Google AI Studio](https://aistudio.google.com/apikey) |
| Gemini (Cloud) | `AQ...` | [Google Cloud Console](https://console.cloud.google.com/apis/credentials) |

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

## Build

```bash
npm run build
```

## License

MIT — see [LICENSE](LICENSE).
