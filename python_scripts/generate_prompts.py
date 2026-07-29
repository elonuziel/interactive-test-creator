import sys
import os

def generate_prompts(test_dir, test_name, form_number="1", has_answers=True):
    os.makedirs(test_dir, exist_ok=True)
    
    # 1. Local Agent Prompt (for agy, gemini, claude, Cursor, VS Code, Antigravity)
    if has_answers:
        local_prompt = f"Read LLM_RUNBOOK.md and follow it to process the test in {test_dir}/ -- extract questions from the PDF, parse them into questions.json, and merge the answer key (Form Number: {form_number}). Work through all steps."
    else:
        local_prompt = f"Read LLM_RUNBOOK.md and follow it to process the test in {test_dir}/ -- extract questions from the PDF and parse them into questions.json. Work through all steps."

    local_path = os.path.join(test_dir, "prompt_local_agent.txt")
    with open(local_path, "w", encoding="utf-8") as f:
        f.write(local_prompt)

    # 2. Web AI Prompt (for ChatGPT, Claude.ai, Gemini Web, Google AI Studio)
    if has_answers:
        web_prompt = f"""I am uploading an exam PDF file and answer key (CSV/Excel) for test "{test_name}".
Form Number for answer key: {form_number}.

Please extract all multiple-choice questions into a structured questions.json format for a Hebrew quiz app.

Requirements:
1. Extract every question with its full text in correct Hebrew reading order (do not reverse words or punctuation).
2. Extract all options (usually 4 options: א, ב, ג, ד) for each question.
3. Determine correctIndex (0-based integer: Option 1 = 0, Option 2 = 1, Option 3 = 2, Option 4 = 3) matching Form {form_number} from the answer key.
4. If a question references a diagram or image, include an "image": "images/qX.png" field.
5. Return ONLY a valid JSON array matching this exact schema:

[
  {{
    "question": "שאלה בעברית...",
    "options": [
      "תשובה 1",
      "תשובה 2",
      "תשובה 3",
      "תשובה 4"
    ],
    "correctIndex": 0
  }}
]

Output the complete JSON ready to save as {test_dir}/questions.json.
"""
    else:
        web_prompt = f"""I am uploading an exam PDF file for test "{test_name}".

Please extract all multiple-choice questions into a structured questions.json format for a Hebrew quiz app.

Requirements:
1. Extract every question with its full text in correct Hebrew reading order (do not reverse words or punctuation).
2. Extract all options (usually 4 options: א, ב, ג, ד) for each question.
3. If an answer key or master key is embedded in the PDF (e.g. Option 1 / א is correct), set correctIndex (0-based: Option 1 = 0, Option 2 = 1, Option 3 = 2, Option 4 = 3). Otherwise set correctIndex to 0.
4. If a question references a diagram or image, include an "image": "images/qX.png" field.
5. Return ONLY a valid JSON array matching this exact schema:

[
  {{
    "question": "שאלה בעברית...",
    "options": [
      "תשובה 1",
      "תשובה 2",
      "תשובה 3",
      "תשובה 4"
    ],
    "correctIndex": 0
  }}
]

Output the complete JSON ready to save as {test_dir}/questions.json.
"""

    web_path = os.path.join(test_dir, "prompt_web_ai.txt")
    with open(web_path, "w", encoding="utf-8") as f:
        f.write(web_prompt)

    print(f"OK - Created prompt files in {test_dir}/")

if __name__ == "__main__":
    test_dir = sys.argv[1] if len(sys.argv) > 1 else "tests/test_1"
    test_name = sys.argv[2] if len(sys.argv) > 2 else os.path.basename(test_dir.rstrip("/\\"))
    form_number = sys.argv[3] if len(sys.argv) > 3 else "1"
    has_answers = sys.argv[4].lower() in ["1", "true", "yes"] if len(sys.argv) > 4 else True
    generate_prompts(test_dir, test_name, form_number, has_answers)
