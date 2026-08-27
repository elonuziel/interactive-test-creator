from quizbuilder.markdown import validate_image_references
from quizbuilder.validation import ValidationError, load_questions


def test_image_reference_validation_accepts_existing_and_data_urls(tmp_path):
    image = tmp_path / "pages_output" / "page_1.png"
    image.parent.mkdir()
    image.write_bytes(b"png")
    questions = [
        {"question": "Q", "options": ["A", "B"], "correctIndex": 0, "pageImage": "pages_output/page_1.png"},
        {"question": "Q2", "options": ["A", "B"], "correctIndex": 0, "image": "data:image/png;base64,abc"},
    ]
    assert validate_image_references(questions, tmp_path) == []


def test_question_loading_rejects_missing_local_image(tmp_path):
def test_question_loading_allows_missing_image_by_default(tmp_path):
    path = tmp_path / "questions.md"
    path.write_text("## Question 1\n\nQ\n\npageImage: pages_output/missing.png\n\n- A\n- B\n\nAnswer: A\n", encoding="utf-8")
    # Default load_questions must not crash so the GUI editor can load the file
    loaded = load_questions(path)
    assert len(loaded) == 1
    assert loaded[0]["pageImage"] == "pages_output/missing.png"


def test_question_loading_rejects_missing_local_image_when_opted_in(tmp_path):
    path = tmp_path / "questions.md"
    path.write_text("## Question 1\n\nQ\n\npageImage: pages_output/missing.png\n\n- A\n- B\n\nAnswer: A\n", encoding="utf-8")
    try:
        load_questions(path)
        load_questions(path, check_images=True)
    except ValidationError as exc:
        assert "Missing image references" in str(exc)
    else:
        raise AssertionError("Expected missing image validation failure")
        raise AssertionError("Expected missing image validation failure when check_images=True")
