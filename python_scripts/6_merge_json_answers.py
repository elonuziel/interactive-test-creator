import json
import argparse
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def main():
    parser = argparse.ArgumentParser(description="Merge questions.json with an answers.json file mapping.")
    parser.add_argument("questions_file", help="Path to questions.json or test directory")
    parser.add_argument("answers_file", nargs="?", help="Path to answers.json (optional if directory is given)", default=None)
    parser.add_argument("-o", "--output", help="Output JSON file", default=None)
    
    args = parser.parse_args()

    p1 = Path(args.questions_file)
    if p1.is_dir():
        q_path = p1 / "questions.json"
        a_path = p1 / "answers.json"
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
        with open(q_path, 'r', encoding='utf-8') as f:
            questions = json.load(f)
            
        with open(a_path, 'r', encoding='utf-8') as f:
            answers = json.load(f)
            
    except Exception as e:
        print(f"Error reading files: {e}")
        return 1
        
    updated = 0
    for i, q in enumerate(questions):
        question_num = str(i + 1)
        if question_num in answers and answers[question_num] is not None:
            # Assuming answers.json uses 1-based indexing for answers (e.g. 1-4)
            # The HTML app uses 0-based indexing for the correct option
            ans_idx = answers[question_num] - 1
            q['correctIndex'] = ans_idx
            updated += 1
            
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(questions, f, ensure_ascii=False, indent=2)
        
    print(f"Successfully updated correctIndex for {updated}/{len(questions)} questions in {out_path}")
    return 0

if __name__ == '__main__':
    main()
