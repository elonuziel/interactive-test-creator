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
