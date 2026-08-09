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
   - `options`: Array of all choice strings (questions can have 4, 5, 6 or more options; strip prefixes like 'א.', 'ב.', '1.', '2.').
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
   - Ensure questions end with proper Hebrew punctuation (e.g., '?').

2. OPTIONS CLEANUP:
   - Ensure each question has a clean `options` array containing all choices (e.g. 4, 5, 6+ choices).
   - Remove redundant option labels (e.g., strip 'א.', 'ב.', 'ג.', 'ד.' or '1.', '2.' from the start of option strings).

3. SCHEMA PRESERVATION:
   - Do NOT alter `correctIndex` values (if already present).
   - Do NOT alter or remove `pageImage` paths (e.g. `"pages_output/page_X.png"`).
   - Do NOT change the order or number of questions.

---------------------------------------------------------------------------
OUTPUT & DELIVERABLE REQUIREMENTS:
---------------------------------------------------------------------------
1. Provide your response either as a downloadable `questions.json` file OR in a single clean code block ready for one-click copy-pasting.
2. Return ONLY complete, valid JSON without introductory commentary or explanations.
"""
    else:
        web_prompt = f"""I am uploading the exam document for Hebrew test "{test_name}".

Please extract all multiple-choice questions into a clean Markdown file (`questions.md`) for an interactive Hebrew quiz system.

===========================================================================
REQUIRED MARKDOWN FORMAT (questions.md):
===========================================================================
### שאלה 1: [נוסח השאלה המלא בעברית] (עמוד 1)
- א. [אפשרות 1]
- ב. [אפשרות 2]
- ג. [אפשרות 3]
- ד. [אפשרות 4]

### שאלה 2: [נוסח השאלה השנייה בעברית] (עמוד 2)
- א. [אפשרות 1]
- ב. [אפשרות 2]
- ג. [אפשרות 3]
- ד. [אפשרות 4]

===========================================================================
STRICT EXTRACTION & PROOFREADING RULES:
===========================================================================
1. HEBREW READING ORDER & ACRONYMS: Extract text in natural Hebrew reading order. Do NOT reverse words, letters, or numbers. Preserve scientific terms and acronyms (e.g. "ATP", "DNA", "pH", "GSI", "DVM", "CO2") exactly as written.
2. OPTIONS FORMATTING: Each option MUST start on a new line with standard bullet format: - א., - ב., - ג., - ד., - ה., etc. Extract all options for each question (questions may have 4, 5, 6 or more choices).
3. PAGE NUMBER TRACKING: Always end each question header with the exact 1-based PDF source page number in parentheses: (עמוד X), e.g. (עמוד 1), (עמוד 5). This is CRITICAL for matching questions referencing graphs, diagrams, figures, or tables.
4. DELIVERABLE FORMAT (CODE BOX & FILE DOWNLOAD): Provide your entire response inside a single, copyable Markdown code block (wrapped in ```markdown ... ```) OR as a downloadable `questions.md` file. Do NOT include conversational explanations, intros, or commentary outside the code box.
"""

    # 3. Enhanced prompts for image-based options (schema-compatible fallback)
    if is_proofread:
        local_prompt_enhanced = f"""[TASK: HEBREW EXAM QUESTION PROOFREADING & FORMATTING - IMAGE-OPTION SAFE MODE]

Context:
Automated extraction produced `{test_dir}/questions.json` for test "{test_name}".
This exam may include options that are images/graphs/tables/diagrams.

Important schema constraint:
- Keep the existing schema only: `question`, `options`, `correctIndex`, optional `pageImage`.
- Do NOT introduce unsupported fields such as optionImages or nested option objects.

Your Instructions:
1. Open and read `{test_dir}/questions.json`.
2. Fix Hebrew order/punctuation/parentheses issues.
3. Preserve option placeholders for visual choices, for example:
   - "ראה דיאגרמה א"
   - "ראה גרף ב"
   - "ראה טבלה ג"
4. Do NOT replace placeholders with invented visual descriptions.
5. Preserve existing `correctIndex` and `pageImage` values.
6. Overwrite `{test_dir}/questions.json` with valid JSON only.
"""

        web_prompt_enhanced = f"""I am attaching an auto-extracted questions.json for Hebrew test "{test_name}".

Please proofread it while preserving compatibility with this exact schema:
- question (string)
- options (string array)
- correctIndex (number or null)
- pageImage (optional string)

Rules for visual/image options:
1. Keep placeholder-style options such as "ראה דיאגרמה א" / "ראה גרף ב".
2. Do NOT add unsupported fields (no optionImages, no nested option objects).
3. Keep `pageImage` paths unchanged for visual questions.
4. Return only valid JSON with no commentary.
"""
    else:
        local_prompt_enhanced = f"""[TASK: HEBREW MULTIPLE-CHOICE EXTRACTION - IMAGE-OPTION SAFE MODE]

Context:
You are processing test "{test_name}" (Form {form_number}). Source page renders are in `{test_dir}/pages_output/`.

Critical schema constraint:
- Output must stay compatible with this schema only:
  `question` (string), `options` (string[]), `correctIndex` (null), optional `pageImage` (string).
- No per-option image fields are allowed.

Extraction Rules:
1. Extract every multiple-choice question in order.
2. Keep natural Hebrew reading order.
3. For options:
   - Text option: keep the text.
   - Image-only option: use placeholder text like "ראה דיאגרמה א", "ראה גרף ב", "ראה טבלה ג".
   - Mixed text+image option: keep text and append short reference like "(ראה גרף בעמוד זה)".
4. Set `correctIndex` to null.
5. Set `pageImage` to "pages_output/page_X.png" for any question with visual content in question or options.
6. Save valid JSON to `{test_dir}/questions.json`.
"""

        web_prompt_enhanced = f"""I am uploading a Hebrew exam for test "{test_name}".

Please extract all multiple-choice questions into questions.md (or directly JSON) with image-option safe handling.

Rules:
1. Keep Hebrew in natural reading order.
2. For image-based options, use placeholders:
   - "ראה דיאגרמה א" / "ראה גרף ב" / "ראה טבלה ג"
3. Keep source page marker `(עמוד X)` per question.
4. Do not invent image descriptions.
5. If outputting JSON, use only these fields:
   - question, options, correctIndex (null), optional pageImage.
6. Return only the requested content (no extra commentary).
"""

    if target in ["local", "all"]:
        local_path = os.path.join(test_dir, "prompt_local_agent.txt")
        with open(local_path, "w", encoding="utf-8") as f:
            f.write(local_prompt)
        print(f"  [OK] Created local agent prompt: {local_path}")

        local_enhanced_path = os.path.join(test_dir, "prompt_local_agent_enhanced.txt")
        with open(local_enhanced_path, "w", encoding="utf-8") as f:
            f.write(local_prompt_enhanced)
        print(f"  [OK] Created local agent enhanced prompt: {local_enhanced_path}")

    if target in ["web", "all"]:
        web_path = os.path.join(test_dir, "prompt_web_ai.txt")
        with open(web_path, "w", encoding="utf-8") as f:
            f.write(web_prompt)
        print(f"  [OK] Created web AI prompt: {web_path}")

        web_enhanced_path = os.path.join(test_dir, "prompt_web_ai_enhanced.txt")
        with open(web_enhanced_path, "w", encoding="utf-8") as f:
            f.write(web_prompt_enhanced)
        print(f"  [OK] Created web AI enhanced prompt: {web_enhanced_path}")


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
