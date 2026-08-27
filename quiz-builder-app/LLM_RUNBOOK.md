# LLM Runbook: Extracting Hebrew Exams into Interactive HTML Quizzes

This document is the definitive guide for an AI Agent (like yourself!) processing an exam folder.

**CRITICAL UPDATE: You do NOT need to run any Python scripts.**
The `start.bat` / `start.sh` wizard and `quizbuilder` CLI handle **all** pre-processing (detecting PDF types, rendering PDF pages to images, extracting answer keys from CSV) and **all** post-processing (merging answers, QA checks, building the standalone HTML file).

Your **ONLY** job is to read the rendered images and extract the questions into `questions.md`.

---

## Your Task: Create `questions.md`

When you are invoked by the CLI / wizard, you will be placed inside a test directory (e.g. `tests/2022_moed_b/`).
You will see a folder named `pages_output/` containing images of the exam pages (e.g., `page_1.png`, `page_2.png`).

You must read these images using your Vision capabilities, extract the multiple-choice questions, and output exactly one file: `questions.md`.

### `questions.md` Schema Reference
Each question object in the JSON array must follow this exact structure:
```markdown
# Quiz Questions

## Question 1

הטקסט המלא של השאלה בעברית...

pageImage: pages_output/page_3.png

- תשובה א
- תשובה ב
- תשובה ג
- תשובה ד

Answer: A
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `question` | text | **Yes** | Full question text in Hebrew in natural logical reading order. |
| options | bullets | **Yes** | Answer options, usually four or more. |
| `Answer` | A, B, C... | No | Correct option; use `A` as a placeholder when answer keys are merged later. |
| `pageImage` | path | No | Relative path to the full-page scan for diagrams/images/tables. |

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

Before saving the final `questions.md`, perform a proofreading audit using your native LLM capabilities against this checklist:
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
5. Save `questions.md`.
6. Terminate. (Do not run any python scripts — `start.bat` is waiting for `questions.md` to appear and will take over immediately!)