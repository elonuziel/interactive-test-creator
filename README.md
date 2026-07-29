# 📝 Interactive Hebrew Quiz Generator & Player

> **Try it live:** [elonuziel.github.io/interactive-test-creator/quiz_generator.html](https://elonuziel.github.io/interactive-test-creator/quiz_generator.html)

Turn scanned or digital Hebrew exam PDFs into fully interactive, self-grading digital quizzes right in your browser — zero backend required. Upload a PDF, extract questions with Gemini OCR, attach an answer key, proofread side-by-side, and export a standalone, portable HTML quiz file.

---

## 🎯 Quiz Generator (`quiz_generator.html`)

**`quiz_generator.html`** + **`generator.js`** — The in-browser builder & OCR engine.

### Workflow
1. **Upload PDF**: Select a digital or scanned exam PDF.
2. **Attach Answer Key** *(Optional)*: Upload a CSV, XLS, or XLSX answer key and select your form number.
3. **Configure Gemini OCR**: Enter a free API key from [Google AI Studio](https://aistudio.google.com/apikey) or a Cloud API key.
4. **Run Analysis**: Click **הפעל ניתוח** to automatically extract questions, options, and diagrams.
5. **Edit & Proofread**: Adjust text, options, answer keys, or compare side-by-side with original PDF page snapshots in **Proof Mode**.
6. **Export & Take**: Click **הורד מבחן עצמאי** to download a single-file HTML quiz, or **פתור מבחן כעת** to start immediately.

### Key Generator Features
- **OCR Engines**: Gemini Page Chunking (optimized for Hebrew layout) & Gemini Native PDF.
- **Answer Key Matching**: Parses CSV, XLS, and XLSX files, matching question keys automatically by form number.
- **Proof Mode**: Visual side-by-side comparison of original PDF pages against generated question cards.
- **Image Detection**: Auto-detects charts, diagrams, tables, and attaches page images for built-in cropping.
- **Re-edit Quiz HTML**: Upload previously exported quiz HTML files to resume editing.
- **File Management**: Independent file clear buttons to change inputs without page refreshes.

---

## 📝 Quiz Taker (`index.html`)

**`index.html`** + **`app.js`** + **`style.css`** — The standalone, RTL-native quiz player.

### Player Features
- **Native RTL Hebrew**: Purpose-built right-to-left UI with modern Rubik typography.
- **Keyboard Navigation**:
  - `1`–`9`: Select answer choices.
  - `←` / `→`: Navigate between questions.
  - `Esc`: Close image zoom overlay.
- **Immediate Feedback**: Optional toggle to check answers instantaneously.
- **Progress Jump Bar**: Jump to any question and see real-time answered/correct status.
- **Auto-Save & Resume**: Per-quiz `LocalStorage` persistence to resume uncompleted sessions.
- **Answer Shuffling**: Randomized options per session for exams without explicit answer keys.
- **Image Cropper & Fullscreen Zoom**: Crop embedded graphs or tables directly in the quiz card.
- **Results Dashboard & Review**: Score calculation with filters for **All**, **Wrong Only**, or **Unanswered** questions.
- **Dark & Light Themes**: Seamless theme switching with system preference support.

---

## 📁 Repository Structure

```
interactive-test-creator/
├── index.html            # Quiz Player Shell (GitHub Pages Root)
├── app.js                # Quiz Engine & Navigation
├── quiz_generator.html   # Web Quiz Builder Interface
├── generator.js          # OCR, Gemini API, & PDF Parser Engine
├── style.css             # Unified RTL & Theme System
├── favicon.svg           # Application SVG Favicon
├── vendor/               # Third-party dependencies (PDF.js)
├── .github/workflows/    # GitHub Pages deployment workflow
├── cli-legacy/           # Legacy Python scripts & batch wizard
├── deal-with-later/      # Preserved research guides, scripts & proposals
└── tests/                # Sample test PDFs & answer key fixtures
```

---

## 🔑 Gemini API Keys

| Type | Prefix | How to Get |
|---|---|---|
| Gemini Free Tier | `AIza...` | [Google AI Studio](https://aistudio.google.com/apikey) |
| Gemini Cloud | `AQ...` | [Google Cloud Console](https://console.cloud.google.com/apis/credentials) |

---

## 📄 License

MIT — see [LICENSE](LICENSE).
