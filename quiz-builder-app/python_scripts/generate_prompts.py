import os
import sys
import argparse


# Shared guideline blocks to ensure consistency across all prompts
HEBREW_PROOFREAD_GUIDELINES = """1. HEBREW TEXT ACCURACY:
   - Fix reversed Hebrew words or letters (e.g. "םימ" -> "מים").
   - Fix inverted parentheses, brackets, or mixed English/Hebrew terms (e.g. "(DNA) לשרשרת" -> "לשרשרת (DNA)").
   - Ensure questions end with proper Hebrew punctuation (e.g. '?').

2. OPTIONS CLEANUP:
   - Ensure each question has a clean options list containing all choices (4, 5, 6+ choices).
   - Clean up any stray sub-bullet numbering or leftover prefixes (e.g. remove 'א.', 'ב.', '1.' from option strings).

3. STRUCTURE PRESERVATION:
   - Preserve question order and all options per question.
   - Deliverable: Return only raw Markdown for `questions.md` (no JSON, no explanations, no code fences)."""

HEBREW_EXTRACTION_RULES = """1. FORM NUMBER IDENTIFICATION: Inspect the exam header and first page to detect the exam form number (e.g. "מבחן מס' 063", "שאלון 063", "טופס 000", "Form 063"). Include the detected form number as the very first line of questions.md: <!-- Form: [NUMBER_OR_0] --> (e.g. <!-- Form: 063 -->).
2. HEBREW READING ORDER & ACRONYMS: Extract text in natural Hebrew reading order. Do NOT reverse words, letters, or numbers. Preserve scientific terms and acronyms (e.g. "ATP", "DNA", "pH", "GSI", "DVM", "CO2") exactly as written.
3. OPTIONS FORMATTING: Each option MUST start on a new line with standard bullet format: - א., - ב., - ג., - ד., - ה., etc. Extract all options for each question.
4. PAGE NUMBER TRACKING: Always end each question header with the exact 1-based PDF source page number in parentheses: (עמוד X), e.g. (עמוד 1), (עמוד 5). This is CRITICAL for matching visual questions with diagrams/tables.
5. DELIVERABLE FORMAT: Return only raw Markdown body for `questions.md` (no JSON, no explanations, no code fences)."""

IMAGE_OPTION_RULES = """Rules for visual/image options:
1. For image-based or diagram options, keep placeholder text such as "ראה דיאגרמה א" / "ראה גרף ב" / "ראה טבלה ג".
2. Do NOT invent visual descriptions.
3. Include (עמוד X) with the 1-based source page number in every question header."""


def generate_prompts(test_dir, test_name, form_number, has_answers, target="all"):
    os.makedirs(test_dir, exist_ok=True)
    questions_md_path = os.path.join(test_dir, "questions.md")
    is_proofread = os.path.exists(questions_md_path)

    # 1. Local Agent Prompts
    if is_proofread:
        local_prompt = f"""[TASK: HEBREW EXAM QUESTION PROOFREADING & FORMATTING]

Context:
Automated text extraction generated `{test_dir}/questions.md` from a digital PDF for test "{test_name}". Hebrew PDF text extraction often suffers from reversed word order, backwards punctuation, and mixed language glitches.

Your Instructions:
1. Open and read `{test_dir}/questions.md`.
{HEBREW_PROOFREAD_GUIDELINES}
2. Use this exact format per question:
   - `### שאלה N: [נוסח השאלה] (עמוד X)`
   - `- א. ...`, `- ב. ...`, `- ג. ...`, `- ד. ...`
3. Save output as `{test_dir}/questions.md`.
"""
        local_prompt_enhanced = f"""[TASK: HEBREW EXAM QUESTION PROOFREADING & FORMATTING - IMAGE-OPTION SAFE MODE]

Context:
Automated extraction produced `{test_dir}/questions.md` for test "{test_name}".
This exam may include options that are images/graphs/tables/diagrams.

Your Instructions:
1. Open and read `{test_dir}/questions.md`.
{HEBREW_PROOFREAD_GUIDELINES}
{IMAGE_OPTION_RULES}
2. Save output as `{test_dir}/questions.md`.
"""
    else:
        local_prompt = f"""[TASK: HEBREW MULTIPLE-CHOICE EXAM EXTRACTION]

Context:
You are processing test "{test_name}" (Form {form_number}; use this exact value for answer-key lookup). If Form 0/000 is indicated, every correct answer is option 1 and the shared runtime must shuffle displayed options. Rendered page images are saved in `{test_dir}/pages_output/` (e.g. `page_1.png`, `page_2.png`). Raw extracted text (if available) is in `{test_dir}/raw_text.md`.

Your Instructions:
1. Inspect all rendered page images in `{test_dir}/pages_output/` sequentially.
2. Extract EVERY multiple-choice question in the exam.
3. For each question:
   - Format question header exactly as: `### שאלה N: [נוסח השאלה] (עמוד X)`.
   - List options as bullets: `- א. ...`, `- ב. ...`, `- ג. ...`, `- ד. ...`.
4. Save output as `{test_dir}/questions.md` only (not JSON).

Required Markdown Example:
### שאלה 1: מהו התפקיד העיקרי של המיטוכונדריה בתא? (עמוד 3)
- א. ייצור אנרגיה (ATP)
- ב. סינתזת חלבונים
- ג. אחסון החומר התורשתי
- ד. פירוק רעלים בתא

Answer: A
"""
        local_prompt_enhanced = f"""[TASK: HEBREW MULTIPLE-CHOICE EXTRACTION - IMAGE-OPTION SAFE MODE]

Context:
You are processing test "{test_name}" (Form {form_number}; use this exact value for answer-key lookup). If Form 0/000 is indicated, every correct answer is option 1 and the shared runtime must shuffle displayed options. Source page renders are in `{test_dir}/pages_output/`.

Extraction Rules:
1. Extract every multiple-choice question in order.
{HEBREW_EXTRACTION_RULES}
{IMAGE_OPTION_RULES}
2. Save output to `{test_dir}/questions.md`.
"""

    # 2. Web AI Prompts
    if is_proofread:
        web_prompt = f"""I am attaching the auto-extracted `questions.md` file for the Hebrew exam "{test_name}".

Please perform a thorough AI proofreading pass according to these guidelines:

{HEBREW_PROOFREAD_GUIDELINES}

OUTPUT FORMAT:
- `### שאלה N: [נוסח השאלה] (עמוד X)`
- `- א. ...`, `- ב. ...`, `- ג. ...`, `- ד. ...`
- `Answer: A` (or B / C / D / א / ב / ג / ד if answer is known)
"""
        web_prompt_enhanced = f"""I am attaching an auto-extracted questions source for Hebrew test "{test_name}".

Please proofread and return ONLY raw Markdown content for `questions.md`.

{HEBREW_PROOFREAD_GUIDELINES}

{IMAGE_OPTION_RULES}
"""
    else:
        web_prompt = f"""I am uploading the exam document for Hebrew test "{test_name}" (Form {form_number}; use this value for answer-key lookup).

Please extract all multiple-choice questions into a clean Markdown file (`questions.md`) for an interactive Hebrew quiz system.

REQUIRED MARKDOWN FORMAT (questions.md):
### שאלה 1: [נוסח השאלה המלא בעברית] (עמוד 1)
- א. [אפשרות 1]
- ב. [אפשרות 2]
- ג. [אפשרות 3]
- ד. [אפשרות 4]

Answer: A

STRICT EXTRACTION & PROOFREADING RULES:
{HEBREW_EXTRACTION_RULES}
"""
        web_prompt_enhanced = f"""I am uploading a Hebrew exam for test "{test_name}" (Form {form_number}; use this value for answer-key lookup).

Please extract all multiple-choice questions and return ONLY raw Markdown content for `questions.md`.

STRICT RULES:
{HEBREW_EXTRACTION_RULES}

{IMAGE_OPTION_RULES}
"""

    # Save target files
    targets = {
        "local": [
            ("prompt_local_agent.txt", local_prompt),
            ("prompt_local_agent_enhanced.txt", local_prompt_enhanced),
        ],
        "web": [
            ("prompt_web_ai.txt", web_prompt),
            ("prompt_web_ai_enhanced.txt", web_prompt_enhanced),
        ],
    }

    selected = ["local", "web"] if target == "all" else [target]
    for cat in selected:
        for filename, content in targets.get(cat, []):
            dest = os.path.join(test_dir, filename)
            with open(dest, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"  [OK] Created {cat} prompt: {dest}")


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
