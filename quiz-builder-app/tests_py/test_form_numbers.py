from quizbuilder.form_numbers import detect_form_candidates, normalize_form_number, resolve_form_number
from quizbuilder.markdown import dump_questions, load_questions


def test_normalize_preserves_zero_identity():
    assert normalize_form_number("063") == "63"
    assert normalize_form_number("000") == "0"


def test_detects_hebrew_labeled_form_and_preserves_raw_value():
    resolved = resolve_form_number("כותרת: מבחן מס' 063\nעמוד 3 מתוך 10", "exam.pdf")
    assert resolved.status == "resolved"
    assert resolved.raw_value == "063"
    assert resolved.normalized_value == "63"
    assert not resolved.is_form_zero


def test_form_zero_is_explicit():
    resolved = resolve_form_number("ליטורל טופס 0", "ליטורל מועד ב טופס 0.pdf")
    assert resolved.status == "resolved"
    assert resolved.is_form_zero
    assert resolved.normalized_value == "0"


def test_ambiguous_candidates_are_not_silently_selected():
    resolved = resolve_form_number("מבחן מס' 63\nשאלון 64", "exam.pdf")
    assert resolved.status == "ambiguous"
    assert resolved.candidate is None


def test_markdown_form_metadata_is_ignored_by_question_parser():
    resolution = resolve_form_number("מבחן מס' 063")
    text = dump_questions([
        {"question": "Q1", "options": ["A", "B"], "correctIndex": 0}
    ], resolution)
    path = __import__("pathlib").Path("/tmp/form-metadata-test.md")
    path.write_text(text, encoding="utf-8")
    try:
        questions = load_questions(path)
        assert len(questions) == 1
        assert questions[0]["question"] == "Q1"
    finally:
        path.unlink(missing_ok=True)
