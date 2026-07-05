# Interactive Hebrew Quiz Generator

> **Try it live:** [elonuziel.github.io/html-test-creator/quiz_generator.html](https://elonuziel.github.io/html-test-creator/quiz_generator.html)

Turn scanned Hebrew exam PDFs into interactive, self-grading quizzes — in your browser. Upload a PDF, let Gemini OCR extract the questions, attach an answer key, and export a standalone HTML quiz.

## 🎯 Quiz Generator

**`quiz_generator.html`** + **`generator.js`** — the builder UI.

### Workflow
1. Upload a **PDF** (digital or scanned)
2. (Optional) Upload an **answer key** — CSV, XLS, or XLSX — with a form number
3. Enter a **Gemini API key** (free from [Google AI Studio](https://aistudio.google.com/apikey))
4. Click **הפעל ניתוח** — Gemini extracts and parses all questions
5. Edit questions, answers, and correct choices in the preview
6. Click **הורד מבחן עצמאי** to download, or **פתור מבחן כעת** to take it immediately

### Generator Features
- **OCR engines** — Gemini chunked (default, best for Hebrew) or Gemini native PDF
- **Answer key formats** — CSV, XLS, XLSX with automatic form-number matching
- **Proof mode** — view the original PDF page alongside each question
- **Add/remove answers** — adjust option counts per question in the editor
- **Image detection** — charts, graphs, tables auto-attach page images for cropping
- **Re-edit existing quizzes** — upload a previously downloaded quiz HTML to continue editing
- **File clear buttons** — remove uploaded files without refreshing

### API Keys
| Type | Prefix | How to get |
|---|---|---|
| Gemini (free) | `AIza...` | [Google AI Studio](https://aistudio.google.com/apikey) |
| Gemini (Cloud) | `AQ...` | [Google Cloud Console](https://console.cloud.google.com/apis/credentials) |

Free tier tip: the generator sends all pages in one request to stay within rate limits.

## 📝 Quiz Taker

**`index.html`** + **`app.js`** + **`style.css`** — the standalone quiz player.

### Features
- **RTL Hebrew** — full right-to-left support
- **Keyboard navigation** — `1`–`9` to select, `←` `→` to navigate, `Esc` to close zoom
- **Immediate feedback** — optional toggle to check answers as you go
- **Progress tracking** — progress bar + question jump bar
- **Auto-save & resume** — localStorage persistence
- **Review mode** — after submitting, click any question to jump back and review, or use the **חזרה לשאלות** button
- **Image zoom & crop** — zoom into attached images, crop to focus on specific areas
- **Dark/light theme** — toggle in the header
- **Answer shuffle** — options randomized per session

## 🗂️ Project Structure

```
quiz_generator.html   — Builder UI
generator.js          — PDF extraction, OCR, parsing, export logic
index.html            — Quiz taker shell
app.js                — Quiz player logic (navigation, scoring, review)
style.css             — Shared styles (RTL, dark mode, responsive)
vendor/pdfjs/         — PDF.js for in-browser PDF rendering
tests/                — Sample exam PDFs and answer keys
```

## 📄 License

MIT — see [LICENSE](LICENSE).
