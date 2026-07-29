import os
import sys

def generate_prompts(test_dir, test_name, form_number, has_answers):
    # Ensure test directory exists
    os.makedirs(test_dir, exist_ok=True)
    
    # Check if questions.json already exists (meaning it was auto-extracted from a digital PDF)
    questions_json_path = os.path.join(test_dir, "questions.json")
    is_proofread = os.path.exists(questions_json_path)

    if is_proofread:
        local_prompt = (
            f"Read {test_dir}/questions.json and perform an AI proofreading pass. "
            f"Fix any reversed Hebrew words, incorrect word order, or mixed Hebrew/English parentheses. "
            f"Preserve the JSON schema exactly. Overwrite {test_dir}/questions.json with the fixed version. "
            f"Do not run any other scripts."
        )
        web_prompt = f"""I have auto-extracted questions from a digital PDF for test "{test_name}", but the Hebrew extraction might have some reversed words or formatting quirks.

Please review the attached `questions.json` and perform an AI proofreading pass:
1. Fix any reversed Hebrew words or incorrect word order.
2. Correct mixed language terms (e.g., reversed parentheses with English words).
3. Ensure options are not truncated.
4. Output the fixed JSON using the exact same schema. Do NOT change `correctIndex` or `pageImage` values.

Return ONLY the corrected JSON array ready to save as {test_dir}/questions.json.
"""
    else:
        # 1. Local Agent Prompt (Extraction)
        local_prompt = (
            f"Read the rendered pages in {test_dir}/pages_output/ and extract all multiple-choice "
            f"questions into {test_dir}/questions.json. For each question, extract the full text and all options. "
            f"Set 'pageImage' to point to its source page (e.g. pages_output/page_3.png) ONLY if the question "
            f"references or contains a diagram, graph, image, or table. Omit 'pageImage' for text-only questions. "
            f"Do not worry about extracting answers or running other scripts (start.bat handles that)."
        )

        # 2. Web AI Prompt (Extraction)
        web_prompt = f"""I am uploading the rendered pages for test "{test_name}".
{"Form Number for answer key: " + form_number + "." if has_answers else ""}

Please extract all multiple-choice questions into a structured questions.json format for a Hebrew quiz app.

Requirements:
1. Extract every question with its full text in correct Hebrew reading order (do not reverse words or punctuation).
2. Extract all options (usually 4 options: א, ב, ג, ד) for each question.
3. Determine correctIndex (0-based integer) matching Form {form_number} from the answer key (if uploaded).
4. Set "pageImage": "pages_output/page_X.png" ONLY if the question references or contains a diagram, graph, image, or table. Omit "pageImage" for text-only questions.
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
    "correctIndex": 0,
    "pageImage": "pages_output/page_3.png"
  }}
]

Output the complete JSON ready to save as {test_dir}/questions.json.
"""

    local_path = os.path.join(test_dir, "prompt_local_agent.txt")
    with open(local_path, "w", encoding="utf-8") as f:
        f.write(local_prompt)

    web_path = os.path.join(test_dir, "prompt_web_ai.txt")
    with open(web_path, "w", encoding="utf-8") as f:
        f.write(web_prompt)

    print(f"OK - Created prompt files in {test_dir}/")

if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("Usage: python generate_prompts.py <test_dir> <test_name> <form_number> <has_answers(1/0)>")
        sys.exit(1)
        
    test_dir_arg = sys.argv[1]
    test_name_arg = sys.argv[2]
    form_number_arg = sys.argv[3]
    has_answers_arg = sys.argv[4] == "1"
    
    generate_prompts(test_dir_arg, test_name_arg, form_number_arg, has_answers_arg)
