import os
import sys
import argparse

def generate_prompts(test_dir, test_name, form_number, has_answers, target="all"):
    # Ensure test directory exists
    os.makedirs(test_dir, exist_ok=True)
    
    # Check if questions.json already exists (meaning it was auto-extracted from a digital PDF)
    questions_json_path = os.path.join(test_dir, "questions.json")
    is_proofread = os.path.exists(questions_json_path)

    # 1. Local Agent Prompts (Extraction vs Proofread)
    if is_proofread:
        local_prompt = f"""[TASK: HEBREW EXAM QUESTION PROOFREADING & FORMATTING]

Context:
Automated text extraction generated `{test_dir}/questions.json` from a digital PDF for test "{test_name}". Hebrew PDF text extraction often suffers from reversed word order, backwards punctuation, and mixed language glitches.

Your Instructions:
1. Open and read `{test_dir}/questions.json`.
2. Inspect every question text and option string carefully for Hebrew formatting glitches:
   - Fix reversed Hebrew words or letters (e.g., "םימ" -> "מים").
   - Correct reversed parentheses and quotes when mixing English & Hebrew (e.g., "(DNA) לשרשרת" -> "לשרשרת (DNA)").
   - Ensure proper Hebrew question marks ('?') are at the end of questions.
   - Clean up any stray sub-bullet numbering or leftover prefixes (e.g., remove 'א.', 'ב.', '1.' from option strings).
3. Do NOT modify the overall structure, question count, or existing `correctIndex` / `pageImage` values.
4. Overwrite `{test_dir}/questions.json` with the proofread, valid JSON.

JSON Schema to maintain:
[
  {{
    "question": "נוסח השאלה בעברית תקינה...",
    "options": [
      "אפשרות ראשונה",
      "אפשרות שנייה",
      "אפשרות שלישית",
      "אפשרות רביעית"
    ],
    "correctIndex": 0,
    "pageImage": "pages_output/page_2.png"
  }}
]
"""
    else:
        local_prompt = f"""[TASK: HEBREW MULTIPLE-CHOICE EXAM EXTRACTION]

Context:
You are processing test "{test_name}" (Form {form_number}). Rendered page images are saved in `{test_dir}/pages_output/` (e.g., `page_1.png`, `page_2.png`). Raw extracted text (if available) is in `{test_dir}/raw_text.md`.

Your Instructions:
1. Inspect all rendered page images in `{test_dir}/pages_output/` sequentially.
2. Extract EVERY multiple-choice question in the exam.
3. For each question:
   - `question`: Full question statement in correct Hebrew reading order (left-to-right sentences, right-to-left Hebrew words).
   - `options`: Array of all 4 choice strings (strip prefixes like 'א.', 'ב.', '1.', '2.').
   - `correctIndex`: Set to `null` (answer key will be merged automatically by quiz_builder).
   - `pageImage`: Set to `"pages_output/page_X.png"` (where X is the 1-based page number) ONLY IF the question contains or references a diagram, figure, chart, table, image, or mathematical formula. Omit `pageImage` if the question is purely text.
4. Save the complete output as valid JSON directly to `{test_dir}/questions.json`.

Target JSON Schema:
[
  {{
    "question": "מהו התפקיד העיקרי של המיטוכונדריה בתא?",
    "options": [
      "ייצור אנרגיה (ATP)",
      "סינתזת חלבונים",
      "אחסון החומר התורשתי",
      "פירוק רעלים בתא"
    ],
    "correctIndex": null,
    "pageImage": "pages_output/page_3.png"
  }}
]
"""

    # 2. Web AI Prompts (Extraction vs Proofread)
    if is_proofread:
        web_prompt = f"""I am attaching the auto-extracted `questions.json` file for the Hebrew exam "{test_name}".

Because this file was generated automatically from a PDF, it may contain reversed Hebrew words, inverted parentheses, or minor formatting errors.

Please perform a thorough AI proofreading pass according to these guidelines:

1. HEBREW TEXT ACCURACY:
   - Fix any reversed Hebrew words or backward reading order.
   - Fix inverted parentheses, brackets, or mixed English/Hebrew terms (e.g., "pH 7-ב" or "חלבונים (Proteins)").
   - Ensure questions end with proper Hebrew punctuation.

2. OPTIONS CLEANUP:
   - Ensure each question has a clean `options` array containing all 4 choices.
   - Remove redundant option labels (e.g., strip 'א.', 'ב.', 'ג.', 'ד.' or '1.', '2.' from the start of option strings).

3. SCHEMA PRESERVATION:
   - Do NOT alter `correctIndex` values (if already present).
   - Do NOT alter or remove `pageImage` paths (e.g. `"pages_output/page_X.png"`).
   - Do NOT change the order or number of questions.

OUTPUT REQUIREMENTS:
Return ONLY the final, complete, valid JSON array. Do not include markdown code block ticks (```json), intro text, or explanation commentary.
"""
    else:
        web_prompt = f"""I am uploading the exam document for Hebrew test "{test_name}".

Please extract all multiple-choice questions into a clean `questions.json` array for an interactive quiz app.

---------------------------------------------------------------------------
EXTRACTION RULES:
---------------------------------------------------------------------------
1. HEBREW TEXT ORDER:
   - Extract text in natural, correct Hebrew reading order.
   - Do NOT reverse word order or letters.
   - Ensure mixed Hebrew and English/scientific terms (e.g. "ATP", "DNA", "pH") read correctly.

2. OPTIONS FORMATTING:
   - Extract all 4 choices into the `options` array.
   - Remove option letter prefixes (e.g. convert "א. תגובה מהירה" to "תגובה מהירה").

3. DIAGRAM & IMAGE REFERENCES (`pageImage`):
   - If a question includes or references a visual element (diagram, chart, graph, illustration, or complex chemical formula), set `"pageImage": "pages_output/page_X.png"` where X is the page number (e.g., `"pages_output/page_4.png"`).
   - If the question is purely text-based, DO NOT include the `pageImage` key.

4. ANSWER KEY (`correctIndex`):
   - Set `"correctIndex": null` for all questions (the answer key will be merged automatically).

---------------------------------------------------------------------------
REQUIRED JSON SCHEMA:
---------------------------------------------------------------------------
[
  {{
    "question": "שאלה לדוגמה בעברית...",
    "options": [
      "תשובה ראשונה",
      "תשובה שנייה",
      "תשובה שלישית",
      "תשובה רביעית"
    ],
    "correctIndex": null,
    "pageImage": "pages_output/page_2.png"
  }}
]

OUTPUT REQUIREMENT:
Return ONLY the raw JSON array. Do NOT wrap in markdown blocks, and do NOT add intro/outro commentary.
"""

    if target in ["local", "all"]:
        local_path = os.path.join(test_dir, "prompt_local_agent.txt")
        with open(local_path, "w", encoding="utf-8") as f:
            f.write(local_prompt)
        print(f"  [OK] Created local agent prompt: {local_path}")

    if target in ["web", "all"]:
        web_path = os.path.join(test_dir, "prompt_web_ai.txt")
        with open(web_path, "w", encoding="utf-8") as f:
            f.write(web_prompt)
        print(f"  [OK] Created web AI prompt: {web_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate on-demand prompts for local and web AI assistants.")
    parser.add_argument("test_dir", help="Target test directory")
    parser.add_argument("test_name", help="Test workspace name")
    parser.add_argument("form_number", help="Form number")
    parser.add_argument("has_answers", help="Has answers (1/0)")
    parser.add_argument("target", nargs="?", default="all", help="Target prompt to generate (local, web, all)")

    args = parser.parse_args()
    has_ans = args.has_answers in ["1", "true", "True"]
    generate_prompts(args.test_dir, args.test_name, args.form_number, has_ans, args.target)
