# Deep Review Walkthrough

## What Was Fixed (Critical & Medium Bugs)

### 1. 🐛 Escape Key Memory Leak in Lightbox (`generator.js` ~L221)
**Severity:** Medium — Memory leak / behavioral bug  
**Problem:** Every time the user clicked to zoom an image, a new `keydown` listener was registered on `document`. Over time (many zoom opens), dozens of handlers would pile up. The `removeEventListener` was inside a named function (`onKey`) but it only removed that *specific* reference — subsequent calls created new ones that were never cleaned up.  
**Fix:** The handler is now stored on `overlay._keyHandler` and registered **once** when the overlay is first created. It stays alive permanently (only 1 handler ever exists) and checks `overlay.style.display !== 'none'` before acting.

---

### 2. 🐛 Hi-Res Lightbox Zoom Failed When Sidebar Wasn't Opened (`generator.js` ~L1975)
**Severity:** Medium — Feature silently broken  
**Problem:** `showImageZoom()` attempts to re-render proof pages at 2.5× scale using `state.pdfBytes`. However, `state.pdfBytes` is only populated by `loadPdfSidebar()`, which runs when the user uploads a PDF. If the user goes straight to parsing (skipping the sidebar step, or if the sidebar loaded but `state.pdfBytes` was already consumed), hi-res re-render silently failed and the low-res thumbnail remained.  
**Fix:** `runParse()` now immediately captures the PDF buffer into `state.pdfBytes` after reading it, before any other processing. This guarantees hi-res zoom always works as long as a PDF is loaded.

---

### 3. 🐛 Question/Diagram Images Rendered at Low Scale (`generator.js` ~L2080, ~L2599)
**Severity:** Medium — Image quality issue  
**Problem:** Two code paths rendered page images for questions at `scale: 1.3`:
- The `_needsPageRender` inline block in `runParse()` (questions referencing diagrams/charts)
- The `autoAttachDiagramPageImages()` function  

Meanwhile, `renderPageImageData()` was bumped to `scale: 2.5` in the previous session. This inconsistency meant manually triggered diagram images were sharper than auto-detected ones.  
**Fix:** Both paths now delegate to `renderPageImageData(page, 2.5)` — the same shared function — ensuring consistent 2.5× quality everywhere.

---

### 4. 🐛 Dead `---PAGE_BOUNDARY---` Split in `callGeminiOcr` (`generator.js` ~L899)
**Severity:** Medium — Incorrect logic (dead code with potential data corruption)  
**Problem:** `callGeminiOcr` sets `responseMimeType: "application/json"` and asks Gemini to produce a JSON array. Gemini therefore **never** emits the `---PAGE_BOUNDARY---` delimiter. The split logic always produced a 1-element array (the entire JSON blob), and the `while` loop silently padded it with empty strings up to `imageDatas.length`. In chunked mode with multiple pages per chunk, this meant extra empty strings were pushed into the pages array, diluting the question extraction.  
**Fix:** Return `[text]` directly — one element per API call (which may cover multiple pages). The downstream `extractTextViaGemini` correctly joins all chunks, and `parseQuestionsFromText` handles JSON-first parsing.

---

### 5. 🐛 Results Screen `score-text` Never Updated (`app.js` ~L629)
**Severity:** Minor-Medium — Stale UI text  
**Problem:** The `<p id="score-text">` element in `quiz_player.html` defaults to `"ענית נכונה על 0 מתוך 0 שאלות."` and was never updated by `renderResults()`. The score circle and percentage animated correctly, but the text line was always wrong.  
**Fix:** `renderResults()` now sets `scoreText.textContent` before the animation begins.

---

## Additional Bugs Found / Minor Suggestions

| # | Location | Severity | Description |
|---|----------|----------|-------------|
| 1 | `generator.js` ~L1690 | Minor UX | Changing the "עמוד מקור" (source page) number input calls `renderPreview()` which destroys and re-creates the entire DOM. This loses keyboard focus, is slow for large question lists, and can confuse the user. **Suggestion:** update only `state.questions[index].sourcePage` and the proof image element in-place, without a full re-render. |
| 2 | `generator.js` ~L504 | Minor | `groupPdfTextItemsToLines` groups text items within `≤2` PDF units of the same y-position. For certain fonts or rotated text, this threshold can split a single rendered line into two groups, causing garbled extracted text. **Suggestion:** increase tolerance to `≤5` or make it scale-relative. |
| 3 | `generator.js` ~L1475 | Minor | `openCropModal` computes `totalPages` as `state.pdfPagesState?.length || state.proofPageImages?.length || 30`. The `|| 30` fallback silently adds non-existent pages to the dropdown. **Suggestion:** only populate the dropdown from confirmed sources, or hide the dropdown when PDF state is unavailable. |
| 4 | `app.js` ~L97 | Minor | `getStorageKey()` hashes only `questions[0].question + questions.length`. Two different quizzes with the same question count and identical first question text will share the same localStorage key and corrupt each other's saved progress. **Suggestion:** include `questions[questions.length - 1].question` or a few random question samples in the hash seed. |
| 5 | `generator.js` ~L2759 | Minor | `elements.htmlFile.addEventListener` extracts embedded questions with `.match(/window\.__INLINE_QUESTIONS__\s*=\s*(\[[\s\S]*?\])\s*;/)`. The greedy `[\s\S]*?` is lazy-non-greedy but still scans the entire file. For large HTML files with many images embedded as base64, this regex can be very slow (hundreds of milliseconds). **Suggestion:** use `indexOf` + `JSON.parse` with bracket counting for robustness and speed. |
| 6 | `generator.js` ~L1952 | Minor | `createStandaloneQuizHtml` patches `app.js` with a raw `replace()` of `<script src="app.js"></script>`. If `app.js` source itself contains that exact string (unlikely but possible in edge cases), the replace would double-inject. **Suggestion:** use a unique placeholder comment in `quiz_player.html` instead of matching the script tag. |
| 7 | `app.js` ~L596 | Minor | `renderResults` computes `incorrectCount = total - correctCount` but this includes unanswered questions. The badge on "נסה שוב שאלות שגויות" says `incorrectCount` but the button retries both wrong AND unanswered — so the badge number matches what the button does, but the label is potentially confusing. **Suggestion:** rename the variable to `wrongOrUnansweredCount` to match button behavior. |
| 8 | `index.html` ~L25 | Minor | PDF.js is loaded both as a local ES module AND a CDN `<script>` tag in sequence. If the ES module succeeds, the CDN script still downloads and runs (setting `window['pdfjs-dist/build/pdf']`). This wastes ~500KB of bandwidth. **Suggestion:** add `nomodule` or a conditional load to skip the CDN if the local module loaded first. |
