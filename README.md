# 📝 Interactive Hebrew Quiz Generator & Player

> **Try it live:** [elonuziel.github.io/interactive-test-creator](https://elonuziel.github.io/interactive-test-creator/)

Turn scanned or digital Hebrew exam PDFs into fully interactive, self-grading digital quizzes right in your browser — zero backend required. Upload a PDF, extract questions with Gemini OCR, attach an answer key, proofread side-by-side, and export a standalone, portable HTML quiz file.

---

## 🎯 Quiz Generator (`index.html`)

**`index.html`** + **`generator.js`** — the main builder & creator UI (GitHub Pages root landing page).

### Workflow
1. **Upload PDF or questions.json**: Select a digital/scanned exam PDF, or upload a `questions.json` file.
2. **Attach Answer Key** *(Optional)*: Upload a CSV, XLS, or XLSX answer key and select your form number.
3. **Clean PDF & Select Pages**: Discard blank or cover pages using standard presets ("ניקוי סטנדרטי", "הסר ריקים") and download a clean PDF.
4. **Configure Gemini OCR or External LLM**: Use a free Gemini API key, or copy the extraction prompt to ChatGPT/Claude.
5. **Edit & Proofread**: Adjust text, options, answer keys, or compare side-by-side with original PDF page snapshots in **Proof Mode**.
6. **Export & Take**: Click **הורד מבחן עצמאי** to download a single-file HTML quiz, or **פתור מבחן כעת** to start immediately.

---

## 📝 Quiz Taker (`quiz_player.html`)

**`quiz_player.html`** + **`app.js`** + **`style.css`** — The standalone, RTL-native quiz player.

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
├── index.html            # Web Quiz Builder Interface (GitHub Pages Root)
├── generator.js          # OCR, Gemini API, & PDF Parser Engine
├── quiz_player.html      # Standalone Quiz Player Shell
├── app.js                # Quiz Engine & Navigation
├── style.css             # Unified RTL & Theme System
├── favicon.svg           # Application SVG Favicon
├── vendor/               # Third-party dependencies (PDF.js)
├── .github/workflows/    # GitHub Pages deployment workflow
├── cli-legacy/           # Legacy Python scripts & batch wizard
├── deal-with-later/      # Preserved research guides, scripts & proposals

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
