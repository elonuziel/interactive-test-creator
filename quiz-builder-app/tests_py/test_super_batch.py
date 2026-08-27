from pathlib import Path

from quizbuilder.super_batch import (
    build_plan,
    default_decision,
    extract_exam_metadata,
    generation_prompt,
    normalize_answer_key,
    strict_questions,
    zero_test_questions,
)


def test_super_batch_discovers_recursive_pdfs_and_keys(tmp_path):
    folder = tmp_path / "nested" / "exam_2024_a"
    folder.mkdir(parents=True)
    pdf = folder / "test_12345_2024_a.pdf"
    pdf.write_bytes(b"%PDF")
    (folder / "answers.md").write_text("1: A\n2: B\n", encoding="utf-8")

    plan = build_plan(tmp_path)

    assert len(plan.items) == 1
    assert plan.items[0].overview.pdf == pdf
    assert plan.items[0].answer_keys[0].path.name == "answers.md"
    assert plan.items[0].answer_keys[0].answers == {1: "A", 2: "B"}


def test_super_batch_isolates_multi_pdf_folder(tmp_path):
    folder = tmp_path / "multi_exams"
    folder.mkdir()
    pdf_a = folder / "biology_moed_a.pdf"
    pdf_b = folder / "biology_moed_b.pdf"
    pdf_a.write_bytes(b"%PDF")
    pdf_b.write_bytes(b"%PDF")

    plan = build_plan(tmp_path)

    assert len(plan.items) == 2
    # Verify both get isolated workspaces under .quizbuilder so their questions.md won't collide
    workspaces = {item.overview.workspace for item in plan.items}
    assert len(workspaces) == 2
    assert all(".quizbuilder" in str(w) for w in workspaces)


def test_metadata_and_zero_test_behavior():
    metadata = extract_exam_metadata("Exam number: 12345\n2024", "biology_2024_a.pdf")
    assert metadata["test_number"] == "12345"
    assert metadata["year"] == "2024"
    assert metadata["variant"] == "a"

    source = [{"question": "Q", "options": ["A", "B"], "correctIndex": 1}]
    assert zero_test_questions(source)[0]["correctIndex"] == 0


def test_normalize_answer_key_formats(tmp_path):
    # JSON format
    json_file = tmp_path / "answers.json"
    json_file.write_text('{"1": "A", "2": 2, "3": "C"}', encoding="utf-8")
    assert normalize_answer_key(json_file) == {1: "A", 2: "B", 3: "C"}

    # Bracket format from Form 0 CSV/text
    csv_file = tmp_path / "answers_form0.txt"
    csv_file.write_text("Header\n[1] {1}\n[2] {3}\n[3] {4}\n", encoding="utf-8")
    assert normalize_answer_key(csv_file) == {1: "A", 2: "C", 3: "D"}


def test_strict_questions_rejects_invalid_file(tmp_path):
    path = tmp_path / "questions.md"
    path.write_text("## Question 1\nQ\n- A\n", encoding="utf-8")
    try:
        strict_questions(path)
    except ValueError as exc:
        assert "at least two" in str(exc)
    else:
        raise AssertionError("Expected strict validation failure")


def test_strict_questions_supports_generate_only(tmp_path):
    path = tmp_path / "questions.md"
    path.write_text("## Question 1\nQ?\n- Option A\n- Option B\n\n## Question 2\nQ2?\n- Opt 1\n- Opt 2\nAnswer: B\n", encoding="utf-8")
    questions = strict_questions(path, allow_unanswered=True)
    assert len(questions) == 2


def test_generation_prompt_includes_file_paths(tmp_path):
    folder = tmp_path / "exam"
    folder.mkdir()
    pdf = folder / "exam.pdf"
    pdf.write_bytes(b"%PDF")
    plan = build_plan(tmp_path)
    item = plan.items[0]
    item.decision = "zero_test"
    prompt = generation_prompt(item, "overview", "two_phase")
    assert "questions.md" in prompt
    assert "zero_test" in prompt
    assert str(pdf.resolve()) in prompt
    assert str(item.overview.workspace.resolve()) in prompt


def test_auto_match_and_selection_of_correct_answer_key(tmp_path):
    folder = tmp_path / "exam_project"
    folder.mkdir()
    pdf_a = folder / "biology_2024_moed_a.pdf"
    pdf_a.write_bytes(b"%PDF")
    key_a = folder / "answers_moed_a.csv"
    key_a.write_text("1,A\n2,B\n", encoding="utf-8")
    key_b = folder / "answers_moed_b.csv"
    key_b.write_text("1,C\n2,D\n", encoding="utf-8")

    plan = build_plan(tmp_path)
    assert len(plan.items) == 1
    # Both keys from the folder are available in the dropdown
    assert default_decision(plan.items[0]) == "use_answer_key"
