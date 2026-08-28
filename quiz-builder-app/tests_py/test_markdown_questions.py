from quizbuilder.markdown import dump_questions, load_questions
from quizbuilder.validation import load_questions as validate_load


def test_markdown_round_trip(tmp_path):
    questions = [{"question": "What?", "options": ["One", "Two"], "correctIndex": 1}]
    path = tmp_path / "questions.md"
    path.write_text(dump_questions(questions), encoding="utf-8")
    assert load_questions(path) == questions
    assert validate_load(path) == questions


def test_markdown_hebrew_format(tmp_path):
    md_content = """# מבחן לדוגמה

## שאלה 1: מהו ההסבר?
- א. תשובה א
- ב. תשובה ב

תשובה: ב

## שאלה 2
1. אופציה 1
2. אופציה 2

Answer: 1
"""
    path = tmp_path / "questions.md"
    path.write_text(md_content, encoding="utf-8")
    loaded = load_questions(path)
    assert len(loaded) == 2
    assert loaded[0]["question"] == "מהו ההסבר?"
    assert loaded[0]["options"] == ["תשובה א", "תשובה ב"]
    assert loaded[0]["correctIndex"] == 1
    assert loaded[1]["options"] == ["אופציה 1", "אופציה 2"]
    assert loaded[1]["correctIndex"] == 0


def test_markdown_explanation_parsing_and_dumping(tmp_path):
    questions = [
        {
            "question": "מה התוצאה של 2+2?",
            "options": ["3", "4", "5"],
            "correctIndex": 1,
            "explanation": "כי 2 ועוד 2 שווה 4 על פי חשבון בסיסי.",
        }
    ]
    path = tmp_path / "questions_with_exp.md"
    dumped = dump_questions(questions)
    assert "Explanation: כי 2 ועוד 2 שווה 4" in dumped
    path.write_text(dumped, encoding="utf-8")
    loaded = load_questions(path)
    assert loaded == questions


def test_markdown_many_options(tmp_path):
    md_content = """## Question 1: Multiple choices
- א. אפשרות א
- ב. אפשרות ב
- ג. אפשרות ג
- ד. אפשרות ד
- ה. אפשרות ה
- ו. אפשרות ו

תשובה: ה

## Question 2: English letters
- A. Choice 1
- B. Choice 2
- C. Choice 3
- D. Choice 4
- E. Choice 5
- F. Choice 6
- G. Choice 7

Answer: F
"""
    path = tmp_path / "questions_6_opts.md"
    path.write_text(md_content, encoding="utf-8")
    loaded = load_questions(path)
    assert len(loaded) == 2
    assert len(loaded[0]["options"]) == 6
    assert loaded[0]["correctIndex"] == 4  # 'ה' -> 4
    assert len(loaded[1]["options"]) == 7
    assert loaded[1]["correctIndex"] == 5  # 'F' -> 5
