from pathlib import Path
import threading

import pytest

from quizbuilder.documents import preferred_pdf
from quizbuilder.super_batch import (
    AnswerKeyCandidate,
    _context_for_pdf,
    ExamOverview,
    SuperBatchItem,
    SuperBatchPlan,
    process_item,
    process_plan,
)


class Provider:
    id = "fake"
    label = "Fake CLI"
    kind = "local"


def item(tmp_path, digital=False, decision="generate_only"):
    folder = tmp_path / "exam"
    folder.mkdir(exist_ok=True)
    pdf = folder / "exam.pdf"
    pdf.write_bytes(b"%PDF")
    overview = ExamOverview(pdf, folder, "exam", digital, test_number="123")
    return SuperBatchItem(overview, decision=decision, overwrite=True)


def test_preferred_pdf_uses_clean_variant(tmp_path):
    original = tmp_path / "exam.pdf"
    cleaned = tmp_path / "exam_clean.pdf"
    original.write_bytes(b"original")
    cleaned.write_bytes(b"cleaned")
    assert preferred_pdf(original) == cleaned


def test_preferred_pdf_uses_workspace_clean_variant(tmp_path):
    original = tmp_path / "source" / "biology_a.pdf"
    original.parent.mkdir()
    original.write_bytes(b"original")
    workspace = tmp_path / "workspaces" / ".quizbuilder" / "biology_a_sub"
    workspace.mkdir(parents=True)
    cleaned = workspace / "biology_a_clean.pdf"
    cleaned.write_bytes(b"cleaned in workspace")
    assert preferred_pdf(original, workspace) == cleaned


def test_scanned_cli_markdown_is_validated_and_saved(tmp_path, monkeypatch):
    current = item(tmp_path)
    monkeypatch.setattr("quizbuilder.super_batch.send_to_provider", lambda *args, **kwargs: "## Question 1\n\nQ?\n\n- A\n- B\n\nAnswer: A\n")
    result = process_item(current, Provider(), "fake", ai_mode="two_phase")
    assert result.success
    assert current.status == "saved"
    assert result.output.name == "questions.md"


def test_existing_output_requires_overwrite(tmp_path):
    current = item(tmp_path)
    (current.overview.workspace / "questions.md").write_text("old", encoding="utf-8")
    current.overwrite = False
    result = process_item(current, Provider(), "fake")
    assert not result.success
    assert "already exists" in result.error


def test_context_mode_path_is_explicit(tmp_path):
    pdf = tmp_path / "scan.pdf"
    pdf.write_bytes(b"%PDF")
    context = _context_for_pdf(pdf, False, "path")
    assert str(pdf.resolve()) in context
    assert "PDF file path" in context


def test_context_mode_extracted_uses_local_text(tmp_path, monkeypatch):
    pdf = tmp_path / "scan.pdf"
    pdf.write_bytes(b"%PDF")

    class Page:
        def get_text(self):
            return "OCR text"

    class Document(list):
        pass

    mock_fitz = type("Fitz", (), {"open": lambda self, path: Document([Page()])})()
    monkeypatch.setitem(__import__("sys").modules, "fitz", mock_fitz)
    monkeypatch.setitem(__import__("sys").modules, "pymupdf", mock_fitz)
    context = _context_for_pdf(pdf, False, "extracted")
    assert "OCR text" in context


def test_cancelled_plan_does_not_process(tmp_path, monkeypatch):
    current = item(tmp_path)
    event = threading.Event()
    event.set()
    result = process_plan(SuperBatchPlan(tmp_path, (current,)), Provider(), "fake", cancel_event=event)
    assert not result[0].success
    assert result[0].error == "Cancelled"
