from pathlib import Path
import threading

import pytest

from quizbuilder.super_batch import (
    AnswerKeyCandidate,
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


def test_scanned_cli_markdown_is_validated_and_saved(tmp_path, monkeypatch):
    current = item(tmp_path)
    monkeypatch.setattr("quizbuilder.super_batch.send_to_provider", lambda *args, **kwargs: "## Question 1\n\nQ?\n\n- A\n- B\n\nAnswer: A\n")
    result = process_item(current, Provider(), "fake", ai_mode="two_phase")
    assert result.success
    assert result.output.name == "questions.md"


def test_existing_output_requires_overwrite(tmp_path):
    current = item(tmp_path)
    (current.overview.workspace / "questions.md").write_text("old", encoding="utf-8")
    current.overwrite = False
    result = process_item(current, Provider(), "fake")
    assert not result.success
    assert "already exists" in result.error


def test_cancelled_plan_does_not_process(tmp_path, monkeypatch):
    current = item(tmp_path)
    event = threading.Event()
    event.set()
    result = process_plan(SuperBatchPlan(tmp_path, (current,)), Provider(), "fake", cancel_event=event)
    assert not result[0].success
    assert result[0].error == "Cancelled"
