from quizbuilder.markdown import dump_questions, load_questions
from quizbuilder.validation import load_questions as validate_load


def test_markdown_round_trip(tmp_path):
    questions = [{"question": "What?", "options": ["One", "Two"], "correctIndex": 1}]
    path = tmp_path / "questions.md"
    path.write_text(dump_questions(questions), encoding="utf-8")
    assert load_questions(path) == questions
    assert validate_load(path) == questions
