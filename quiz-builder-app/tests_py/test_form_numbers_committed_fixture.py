from pathlib import Path

from quizbuilder.form_numbers import resolve_form_number


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "form_numbers"


def test_comprehensive_confusing_fixture_prefers_labeled_form():
    text = (FIXTURE_DIR / "comprehensive.txt").read_text(encoding="utf-8")
    result = resolve_form_number(text, "exam_form_000.pdf")
    assert result.status == "resolved"
    assert result.raw_value == "063"
    assert result.normalized_value == "63"
    assert result.candidate.source == "pdf-content"


def test_form_zero_fixture_is_detected_from_filename_when_content_is_unhelpful():
    text = (FIXTURE_DIR / "form_zero.txt").read_text(encoding="utf-8")
    result = resolve_form_number(text, "biology טופס 000.pdf")
    assert result.status == "resolved"
    assert result.is_form_zero
    assert result.normalized_value == "0"


def test_ambiguous_fixture_requires_resolution():
    text = (FIXTURE_DIR / "ambiguous.txt").read_text(encoding="utf-8")
    result = resolve_form_number(text, "exam.pdf")
    assert result.status == "ambiguous"
    assert result.candidate is None
