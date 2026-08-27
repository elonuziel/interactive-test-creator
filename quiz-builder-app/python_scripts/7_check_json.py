import sys
import json
import argparse

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="QA check for the final questions.json file.")
    parser.add_argument("json_file", help="Path to the questions.json file or test directory")
    parser.add_argument("--expected-options", type=int, default=None,
                        help="Expected number of options per question (default: 4). "
                             "Questions with a different count will show a WARNING rather than an ERROR.")
    
    args = parser.parse_args()
    expected_opts = args.expected_options if args.expected_options is not None else 4

    p = Path(args.json_file)
    if p.is_dir():
        target_file = p / "questions.json"
    else:
        target_file = p

    if not target_file.exists():
        print(f"Questions file not found: {target_file}")
        return

    try:
        with open(target_file, 'r', encoding='utf-8') as f:
            qs = json.load(f)
    except Exception as e:
        print(f"Error reading JSON: {e}")
        return

    print(f"Total questions: {len(qs)}\n")
    errors = []
    warnings = []
    
    # ── Auto-clean pageImage from purely text-only questions ──────────────────
    import re
    IMAGE_KEYWORDS_RE = re.compile(
        r'לפניכם|גרף|תרשים|תמונה|איור|מפה|ציור|דיאגרמה|צילום|טבלה|בטבלה|תרשים|scheme', re.IGNORECASE
    )
    cleaned_count = 0
    for q in qs:
        question_text = q.get('question', '')
        options_text = ' '.join(str(o) for o in q.get('options', []) if o)
        has_visual_text = bool(IMAGE_KEYWORDS_RE.search(question_text)) or bool(IMAGE_KEYWORDS_RE.search(options_text))
        if 'pageImage' in q:
            if not q.get('image') and not has_visual_text:
                del q['pageImage']
                cleaned_count += 1

    if cleaned_count > 0:
        with open(target_file, 'w', encoding='utf-8') as f:
            json.dump(qs, f, ensure_ascii=False, indent=2)
        print(f"Cleaned pageImage field from {cleaned_count} text-only question(s).\n")

    for i, q in enumerate(qs):
        issues = []
        warns = []
        if not q.get('question'):
            issues.append("EMPTY question text")
            
        options = q.get('options', [])
        if len(options) < 2:
            issues.append(f"Option count: {len(options)} (fewer than minimum 2 options)")
        elif len(options) != expected_opts:
            warns.append(f"Option count: {len(options)} (expected {expected_opts})")
            
        for j, opt in enumerate(options):
            if not opt:
                issues.append(f"Empty option {j}")

        options_text = ' '.join(str(o) for o in options if o)
        if IMAGE_KEYWORDS_RE.search(options_text) and not q.get('pageImage') and not q.get('image'):
            warns.append("Visual option keywords detected but no pageImage/image field found")
                
        # correctIndex out of range causes a silent app bug
        ci = q.get('correctIndex', 0)
        if ci >= len(options):
            issues.append(f"correctIndex {ci} out of range (only {len(options)} options)")
        elif ci < 0:
            issues.append(f"correctIndex {ci} is negative")

        # Detect duplicate option text within a question
        seen_texts = {}
        for j, opt in enumerate(options):
            if opt and opt in seen_texts:
                warns.append(f"Duplicate option text: option {seen_texts[opt]} and option {j} both say \"{opt}\"")
            elif opt:
                seen_texts[opt] = j
            
        if issues:
            errors.append((i + 1, issues))
        if warns:
            warnings.append((i + 1, warns))

    if errors:
        print(f"{len(errors)} question(s) have ERRORS:\n")
        for qnum, issues in errors:
            print(f"  Q{qnum}: {', '.join(issues)}")
    else:
        print("No errors found.")

    if warnings:
        print(f"\n{len(warnings)} question(s) have WARNINGS:\n")
        for qnum, warns in warnings:
            print(f"  Q{qnum}: {', '.join(warns)}")
        print("\n  Warnings are expected for exams with combination answers or non-standard option counts.")
    else:
        print("No warnings.")

    if not errors and not warnings:
        print("All questions look good!")

if __name__ == "__main__":
    main()