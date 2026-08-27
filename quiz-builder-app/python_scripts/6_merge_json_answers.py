import argparse
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from quizbuilder.markdown import dump_questions, load_questions as load_markdown_questions  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Merge a questions.md file with an answers.json mapping.")
    parser.add_argument("questions_file", help="Path to questions.md/questions.json or test directory")
    parser.add_argument("answers_file", nargs="?", help="Path to answers.json", default=None)
    parser.add_argument("-o", "--output", help="Output question file", default=None)
    args = parser.parse_args()

    p1 = Path(args.questions_file)
    if p1.is_dir():
        q_path = p1 / ("questions.md" if (p1 / "questions.md").exists() else "questions.json")
        a_path = Path(args.answers_file) if args.answers_file else p1 / "answers.json"
        out_path = Path(args.output) if args.output else q_path
    else:
        q_path = p1
        a_path = Path(args.answers_file) if args.answers_file else p1.parent / "answers.json"
        out_path = Path(args.output) if args.output else q_path
    if not q_path.exists():
        print(f"Questions file not found: {q_path}")
        return 1
    if not a_path.exists():
        print(f"Answers file not found: {a_path}")
        return 1
    try:
        questions = (load_markdown_questions(q_path) if q_path.suffix.lower() == '.md'
                     else json.loads(q_path.read_text(encoding='utf-8')))
        answers = json.loads(a_path.read_text(encoding='utf-8'))
    except Exception as exc:
        print(f"Error reading files: {exc}")
        return 1
    updated = 0
    for i, question in enumerate(questions):
        value = answers.get(str(i + 1))
        if value is not None:
            question['correctIndex'] = int(value) - 1
            updated += 1
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.suffix.lower() == '.md':
        out_path.write_text(dump_questions(questions), encoding='utf-8')
    else:
        out_path.write_text(json.dumps(questions, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Successfully updated correctIndex for {updated}/{len(questions)} questions in {out_path}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
