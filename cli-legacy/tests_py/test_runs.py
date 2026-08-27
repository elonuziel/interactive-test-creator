import json

import pytest

from quizbuilder.models import Workspace
from quizbuilder.batch import discover_batch
from quizbuilder.exporter import build_run_standalone_quiz
from quizbuilder.preview import PreviewError, render_pdf_page
from quizbuilder.runs import RunError, assemble_run, write_run_questions


def make_workspace(root, name, questions):
    path = root / name
    path.mkdir()
    (path / "questions.json").write_text(
        json.dumps(questions, ensure_ascii=False), encoding="utf-8"
    )
    return Workspace(name, path)


def question(text):
    return {"question": text, "options": ["A", "B"], "correctIndex": 0}


def test_assemble_run_selects_one_test(tmp_path):
    workspace = make_workspace(tmp_path, "biology", [question("One")])

    run = assemble_run([workspace])

    assert run.name == "biology"
    assert run.sources == ("biology",)
    assert run.payload == [question("One")]


def test_assemble_run_mixes_selected_tests_without_mutating_sources(tmp_path):
    first = make_workspace(tmp_path, "biology", [question("One")])
    second = make_workspace(tmp_path, "history", [question("Two")])

    run = assemble_run([first, second], mix=True)
    run.questions[0].question["question"] = "Changed derived copy"

    assert run.name == "mixed_quiz"
    assert run.sources == ("biology", "history")
    assert json.loads((first.path / "questions.json").read_text()) == [question("One")]
    assert run.payload == [question("Changed derived copy"), question("Two")]


def test_assemble_run_requires_mixed_mode_for_multiple_tests(tmp_path):
    first = make_workspace(tmp_path, "one", [question("One")])
    second = make_workspace(tmp_path, "two", [question("Two")])

    with pytest.raises(RunError, match="mixed mode"):
        assemble_run([first, second])


def test_assemble_run_reports_missing_questions(tmp_path):
    workspace = Workspace("empty", tmp_path / "empty")
    workspace.path.mkdir()

    with pytest.raises(RunError, match="no questions.json"):
        assemble_run([workspace])


def test_write_run_questions_creates_derived_file(tmp_path):
    workspace = make_workspace(tmp_path, "biology", [question("One")])
    output = tmp_path / "runs" / "practice.json"

    written = write_run_questions(assemble_run([workspace]), output)

    assert written == output
    assert json.loads(output.read_text(encoding="utf-8")) == [question("One")]


def test_build_run_standalone_quiz_exports_mixed_questions(tmp_path):
    first = make_workspace(tmp_path, "biology", [question("One")])
    second = make_workspace(tmp_path, "history", [question("Two")])
    output = tmp_path / "runs" / "mixed.html"

    build_run_standalone_quiz(assemble_run([first, second], mix=True), output)

    html = output.read_text(encoding="utf-8")
    assert "One" in html
    assert "Two" in html


def test_discover_batch_reports_incomplete_and_ambiguous_projects(tmp_path):
    ready = make_workspace(tmp_path, "ready", [question("One")])
    (ready.path / "exam.pdf").touch()
    ambiguous = tmp_path / "ambiguous"
    ambiguous.mkdir()
    (ambiguous / "first.pdf").touch()
    (ambiguous / "second.pdf").touch()

    candidates = discover_batch(tmp_path)

    assert [candidate.workspace.name for candidate in candidates] == [
        "ambiguous - first", "ambiguous - second", "ready"
    ]
    assert candidates[0].ready_to_run is False
    assert "questions.json is missing" in candidates[0].issues[0]
    assert candidates[2].ready_to_run is True


def test_discover_batch_separates_multiple_exam_pdfs(tmp_path):
    year = tmp_path / "2010"
    year.mkdir()
    moed_a = year / "Moed A.pdf"
    moed_b = year / "Moed B.pdf"
    moed_a.touch()
    moed_b.touch()

    candidates = discover_batch(tmp_path)

    assert len(candidates) == 2
    assert candidates[0].workspace.path != candidates[1].workspace.path
    assert candidates[0].workspace.source_pdf == moed_a
    assert candidates[1].workspace.source_pdf == moed_b


def test_render_pdf_page_returns_png_bytes(tmp_path):
    import fitz

    pdf = tmp_path / "source.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Preview")
    document.save(pdf)
    document.close()

    image = render_pdf_page(pdf)

    assert image.startswith(b"\x89PNG")


def test_render_pdf_page_rejects_invalid_page(tmp_path):
    import fitz

    pdf = tmp_path / "source.pdf"
    document = fitz.open()
    document.new_page()
    document.save(pdf)
    document.close()

    with pytest.raises(PreviewError, match="outside the document"):
        render_pdf_page(pdf, page_number=1)
