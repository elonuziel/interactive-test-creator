from pathlib import Path

import pytest

from quizbuilder.form_numbers import resolve_form_number


@pytest.mark.parametrize(
    ("relative_pdf", "expected"),
    [
        ("2021/ליטורל מועד ב טופס 0.pdf", "0"),
        ("2008/2013/מבחן ליטורל 2013 מועד א כל התשובות א (1).pdf", "2013"),
    ],
)
def test_real_fixture_filename_form_detection(relative_pdf, expected):
    pdf = Path(__file__).parents[2] / "tests" / relative_pdf
    if not pdf.is_file():
        pytest.skip("Local fixture corpus is not checked into CI")
    result = resolve_form_number("", pdf.name)
    assert result.status == "resolved"
    assert result.normalized_value == expected


def test_real_fixture_pdf_content_ignores_exam_code_as_form():
    fitz = pytest.importorskip("fitz")
    pdf = Path(__file__).parents[2] / "tests" / "2021" / "מועד א ליטורל 2021.pdf"
    if not pdf.is_file():
        pytest.skip("Local fixture corpus is not checked into CI")
    with fitz.open(pdf) as document:
        text = "\n".join(page.get_text() for page in document)
    result = resolve_form_number(text, pdf.name)
    assert all(candidate.source != "pdf-content" or "קוד מבחן" not in candidate.context for candidate in result.candidates)
