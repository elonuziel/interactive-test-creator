import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from quizbuilder.markdown import load_questions as load_markdown_questions, dump_questions  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="QA check for the questions.md file.")
    parser.add_argument("questions_file", help="Path to questions.md/questions.json or test directory")
    parser.add_argument("--expected-options", type=int, default=4)
    args = parser.parse_args()
    target = Path(args.questions_file)
    if target.is_dir():
        target = target / ("questions.md" if (target / "questions.md").is_file() else "questions.json")
    if not target.exists():
        print(f"Questions file not found: {target}")
        return 1
    try:
        questions = load_markdown_questions(target) if target.suffix.lower() == '.md' else __import__('json').loads(target.read_text(encoding='utf-8'))
    except Exception as exc:
        print(f"Error reading questions: {exc}")
        return 1
    errors, warnings = [], []
    for i, question in enumerate(questions, 1):
        issues, warns = [], []
        text = question.get('question', '')
        options = question.get('options', [])
        if not text.strip(): issues.append('EMPTY question text')
        if len(options) < 2: issues.append(f'Option count: {len(options)} (fewer than minimum 2 options)')
        elif len(options) != args.expected_options: warns.append(f'Option count: {len(options)} (expected {args.expected_options})')
        if any(not option for option in options): issues.append('Empty option')
        correct = question.get('correctIndex', 0)
        if correct < 0: issues.append(f'correctIndex {correct} is negative')
        elif correct >= len(options): issues.append(f'correctIndex {correct} out of range')
        if len(set(options)) != len(options): warns.append('Duplicate option text')
        if issues: errors.append((i, issues))
        if warns: warnings.append((i, warns))
    print(f"Total questions: {len(questions)}\n")
    for i, issues in errors: print(f"  Q{i}: {', '.join(issues)}")
    if errors: print(f"{len(errors)} question(s) have ERRORS.")
    else: print('No errors found.')
    for i, warns in warnings: print(f"  Q{i}: {', '.join(warns)}")
    if warnings: print(f"{len(warnings)} question(s) have WARNINGS.")
    else: print('No warnings.')
    if not errors and not warnings: print('All questions look good!')
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
