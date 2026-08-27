import os
import sys
import argparse


def generate_prompts(test_dir, test_name, form_number, has_answers, target="all"):
    # Ensure test directory exists
    os.makedirs(test_dir, exist_ok=True)

    # Check if the Markdown source already exists (meaning it is ready for proofreading).
    questions_md_path = os.path.join(test_dir, "questions.md")
    is_proofread = os.path.exists(questions_md_path)

    # 1. Local Agent Prompts (Extraction vs Proofread)
    if is_proofread:
        local_prompt = f"""[TASK: HEBREW EXAM QUESTION PROOFREADING & FORMATTING]

Context:
Automated text extraction generated `{test_dir}/questions.md` from a digital PDF for test "{test_name}". Hebrew PDF text extraction often suffers from reversed word order, backwards punctuation, and mixed language glitches.

Your Instructions:
1. Open and read `{test_dir}/questions.md`.
2. Inspect every question text and option string carefully for Hebrew formatting glitches:
   - Fix reversed Hebrew words or letters (e.g., "םימ" -> "מים").
   - Correct reversed parentheses and quotes when mixing English & Hebrew (e.g., "(DNA) לשרשרת" -> "לשרשרת (DNA)").
   - Ensure proper Hebrew question marks ('?') are at the end of questions.
   - Clean up any stray sub-bullet numbering or leftover prefixes (e.g., remove 'א.', 'ב.', '1.' from option strings).
3. Preserve question order and all options per question.
4. Return Markdown only in this format per question:
     - `### שאלה N: [נוסח השאלה] (עמוד X)`
     - `- א. ...`, `- ב. ...`, `- ג. ...`, `- ד. ...` (or more as needed)
5. Save output as `{test_dir}/questions.md`.
"""
    else:
        local_prompt = f"""[TASK: HEBREW MULTIPLE-CHOICE EXAM EXTRACTION]

Context:
You are processing test "{test_name}" (Form {form_number}). Rendered page images are saved in `{test_dir}/pages_output/` (e.g., `page_1.png`, `page_2.png`). Raw extracted text (if available) is in `{test_dir}/raw_text.md`.

Your Instructions:
1. Inspect all rendered page images in `{test_dir}/pages_output/` sequentially.
2. Extract EVERY multiple-choice question in the exam.
3. For each question:
   - Format question header exactly as: `### שאלה N: [נוסח השאלה] (עמוד X)`.
   - List options as bullets: `- א. ...`, `- ב. ...`, `- ג. ...`, `- ד. ...` (or more when needed).
   - Strip prefixes that are duplicated inside option text.
4. Save output as `{test_dir}/questions.md` only (not JSON).

Required Markdown Example:
### שאלה 1: מהו התפקיד העיקרי של המיטוכונדריה בתא? (עמוד 3)
- א. ייצור אנרגיה (ATP)
- ב. סינתזת חלבונים
- ג. אחסון החומר התורשתי
- ד. פירוק רעלים בתא
"""

    # 2. Web AI Prompts (Extraction vs Proofread)
    if is_proofread:
        web_prompt = f"""I am attaching the auto-extracted `questions.md` file for the Hebrew exam "{test_name}".

Because this file was generated automatically from a PDF, it may contain reversed Hebrew words, inverted parentheses, or minor formatting errors.

Please perform a thorough AI proofreading pass according to these guidelines:

1. HEBREW TEXT ACCURACY:
   - Fix any reversed Hebrew words or backward reading order.
   - Fix inverted parentheses, brackets, or mixed English/Hebrew terms (e.g., "pH 7-ב" or "חלבונים (Proteins)").
   - Ensure questions end with proper Hebrew punctuation (e.g., '?').

2. OPTIONS CLEANUP:
   - Ensure each question has a clean `options` array containing all choices (e.g. 4, 5, 6+ choices).
   - Remove redundant option labels (e.g., strip 'א.', 'ב.', 'ג.', 'ד.' or '1.', '2.' from the start of option strings).

3. STRUCTURE PRESERVATION:
    - Do NOT change the order or number of questions.
    - Preserve all options per question.

---------------------------------------------------------------------------
OUTPUT & DELIVERABLE REQUIREMENTS:
---------------------------------------------------------------------------
1. Return only raw Markdown content for `questions.md`.
2. Use this exact format per question:
    - `### שאלה N: [נוסח השאלה] (עמוד X)`
    - `- א. ...`, `- ב. ...`, `- ג. ...`, `- ד. ...`
3. Do not return JSON and do not include commentary or code fences.
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
4. DELIVERABLE FORMAT: Return only the raw Markdown body for `questions.md` (no JSON, no explanations, no surrounding markdown code fences).
"""

    # 3. Enhanced prompts for image-based options (schema-compatible fallback)
    if is_proofread:
        local_prompt_enhanced = f"""[TASK: HEBREW EXAM QUESTION PROOFREADING & FORMATTING - IMAGE-OPTION SAFE MODE]

Context:
Automated extraction produced `{test_dir}/questions.md` for test "{test_name}".
This exam may include options that are images/graphs/tables/diagrams.

Important schema constraint:
- Output Markdown only (for later parser conversion).
- Do NOT introduce unsupported JSON fields such as optionImages or nested option objects.

Your Instructions:
1. Open and read `{test_dir}/questions.md`.
2. Fix Hebrew order/punctuation/parentheses issues.
3. Preserve option placeholders for visual choices, for example:
   - "ראה דיאגרמה א"
   - "ראה גרף ב"
   - "ראה טבלה ג"
4. Do NOT replace placeholders with invented visual descriptions.
5. Return markdown in this structure per question:
    - `### שאלה N: [נוסח השאלה] (עמוד X)`
    - `- א. ...`, `- ב. ...`, `- ג. ...`, `- ד. ...`
6. Save output as `{test_dir}/questions.md` only.
"""

        web_prompt_enhanced = f"""I am attaching an auto-extracted questions source for Hebrew test "{test_name}".

    Please proofread and return ONLY raw Markdown content for `questions.md`.

    Rules for visual/image options:
    1. Keep placeholder-style options such as "ראה דיאגרמה א" / "ראה גרף ב".
    2. Do NOT invent image descriptions.
    3. Use this exact format per question:
       - `### שאלה N: [נוסח השאלה] (עמוד X)`
       - `- א. ...`, `- ב. ...`, `- ג. ...`, `- ד. ...`
    4. Do not return JSON, no code fences, and no commentary.
    """
    else:
        local_prompt_enhanced = f"""[TASK: HEBREW MULTIPLE-CHOICE EXTRACTION - IMAGE-OPTION SAFE MODE]

Context:
You are processing test "{test_name}" (Form {form_number}). Source page renders are in `{test_dir}/pages_output/`.

Critical schema constraint:
- Output must be valid Markdown that can be parsed by quiz_builder into JSON.
- No per-option image fields or JSON objects are allowed in the markdown output.

Extraction Rules:
1. Extract every multiple-choice question in order.
2. Keep natural Hebrew reading order.
3. For options:
   - Text option: keep the text.
   - Image-only option: use placeholder text like "ראה דיאגרמה א", "ראה גרף ב", "ראה טבלה ג".
   - Mixed text+image option: keep text and append short reference like "(ראה גרף בעמוד זה)".
4. Use this exact markdown shape per question:
  - Header: `### שאלה N: [טקסט השאלה] (עמוד X)`
  - Options: one per line as `- א. ...`, `- ב. ...`, etc.
5. Save output to `{test_dir}/questions.md`.
"""

        web_prompt_enhanced = f"""I am uploading a Hebrew exam for test "{test_name}".

Please extract all multiple-choice questions and return ONLY raw Markdown content for `questions.md`.

Rules:
1. Keep Hebrew in natural reading order.
2. For image-based options, use placeholders:
   - "ראה דיאגרמה א" / "ראה גרף ב" / "ראה טבלה ג"
3. Do not invent image descriptions.
4. Use this exact format for every question:
   - `### שאלה N: [נוסח השאלה] (עמוד X)`
   - `- א. [אפשרות]`
   - `- ב. [אפשרות]`
   - `- ג. [אפשרות]`
   - `- ד. [אפשרות]`
5. Include `(עמוד X)` with the 1-based source page number in every question header.
6. Return only the markdown body with no JSON, no commentary, and no surrounding code fences.
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
