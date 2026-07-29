# LLM Runbook: Extracting Hebrew Exams into Interactive HTML Quizzes

This document is the definitive guide for an AI Agent (like yourself!) processing an exam folder.

**CRITICAL UPDATE: You do NOT need to run any Python scripts.**
The `start.bat` wizard handles **all** pre-processing (detecting PDF types, rendering PDF pages to images, extracting answer keys from CSV) and **all** post-processing (merging answers, QA checks, building the standalone HTML file).

Your **ONLY** job is to read the rendered images and extract the questions into `questions.json`.

---

## Your Task: Create `questions.json`

When you are invoked by `start.bat`, you will be placed inside a test directory (e.g. `tests/2022_moed_b/`).
You will see a folder named `pages_output/` containing images of the exam pages (e.g., `page_1.png`, `page_2.png`).

You must read these images using your Vision capabilities, extract the multiple-choice questions, and output exactly one file: `questions.json`.

### `questions.json` Schema Reference
Each question object in the JSON array must follow this exact structure:
```json
[
  {
    "question": "הטקסט המלא של השאלה בעברית...",
    "options": ["תשובה א", "תשובה ב", "תשובה ג", "תשובה ד"],
    "correctIndex": 0,
    "pageImage": "pages_output/page_3.png"
  }
]
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `question` | string | **Yes** | Full question text in Hebrew in natural logical reading order. |
| `options` | string[] | **Yes** | Answer options (usually 4). Extract them exactly as they appear. |
| `correctIndex` | number | **Yes** | 0-based index of the correct option. Just put `0` as a placeholder (start.bat will merge the real answers later from the answer key!). |
| `pageImage` | string | No | Relative path to the full-page scan where this question appears (e.g., `"pages_output/page_3.png"`). Set ONLY for questions with diagrams/images/tables. Omit for text-only questions. |

---

## 💡 The Fast Image Reference Rule

Do **NOT** waste time trying to manually crop sub-images of diagrams, graphs, or tables, and do **NOT** write custom python scripts to crop them.

The interactive web app has a built-in Cropper feature! 
For **questions that reference or contain a diagram, graph, image, or table** (e.g., questions with keywords like `לפניכם`, `גרף`, `תרשים`, `תמונה`, `איור`, `טבלה`), set the `"pageImage"` field to point to the full page scan (e.g. `"pages_output/page_X.png"`). 
Do **NOT** set `"pageImage"` for text-only questions.

**Example:**
If Question 15 mentions a graph and appears on `pages_output/page_5.png`, set `"pageImage": "pages_output/page_5.png"`. If Question 16 is text-only, omit `"pageImage"`.

---

## Agent Proofreading Protocol

Before saving the final `questions.json`, perform a proofreading audit using your native LLM capabilities against this checklist:
1. **Audit Hebrew Word Order:** Ensure phrases are in correct logical order. Do not output reversed text.
2. **Audit Mixed Language Terms:** Correct reversed parentheses or English terms inside Hebrew text.
3. **Verify Option Boundaries:** Ensure each question has clean, non-truncated option strings.
4. **Preserve Schema:** Ensure every question has `"question"`, `"options"`, `"correctIndex": 0`, and optional `"pageImage"` (only for questions with diagrams/images/tables).

---

## Workflow Summary

1. Read images from `pages_output/`.
2. Extract text and options.
3. Apply the Fast Image Reference Rule (set `"pageImage"`).
4. Proofread.
5. Save `questions.json`.
6. Terminate. (Do not run any python scripts — `start.bat` is waiting for `questions.json` to appear and will take over immediately!)