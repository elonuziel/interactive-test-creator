from quizbuilder.form_numbers import detect_form_candidates, resolve_form_number


def test_supported_label_variants():
    samples = [
        "מבחן מס' 063",
        "מבחן מס 063",
        "מבחן מספר: 063",
        "מספר מבחן 063",
        "שאלון 063",
        "טופס 063",
        "Form 063",
        "Test No. 063",
        "Exam number: 063",
    ]
    for sample in samples:
        result = resolve_form_number(sample)
        assert result.status == "resolved", sample
        assert result.raw_value == "063", sample
        assert result.normalized_value == "63", sample


def test_content_beats_filename_fallback():
    result = resolve_form_number("מבחן מס' 063", "טופס 0.pdf")
    assert result.status == "resolved"
    assert result.raw_value == "063"
    assert result.candidate.source == "pdf-content"


def test_exam_code_is_not_treated_as_form():
    candidates = detect_form_candidates("קוד מבחן 123456\nמבחן מס' 063")
    assert [(item.raw_value, item.source) for item in candidates] == [("063", "pdf-content")]


def test_form_zero_variants_are_equivalent():
    for value in ("0", "00", "000"):
        result = resolve_form_number(f"טופס {value}")
        assert result.status == "resolved"
        assert result.is_form_zero
        assert result.normalized_value == "0"
