"""Tests for DOCX batch conversion helpers in quizbuilder.documents."""

from pathlib import Path
import sys

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quizbuilder.documents import convert_docx_batch, detect_docx_converter, find_soffice
import quizbuilder.documents as docs_module


def test_convert_docx_batch_skips_existing_pdf_without_overwrite(tmp_path):
    docx = tmp_path / "exam.docx"
    docx.write_text("fake", encoding="utf-8")
    existing_pdf = tmp_path / "exam.pdf"
    existing_pdf.write_text("pdf", encoding="utf-8")

    summary = convert_docx_batch(
        ["exam.docx"],
        str(tmp_path),
        backend_name="soffice",
        backend_value="soffice",
        overwrite_existing=False,
    )

    assert not summary["converted"]
    assert summary["skipped"] == [("exam.docx", "matching PDF already exists")]
    assert not summary["failed"]


def test_convert_docx_batch_overwrite_uses_backend(tmp_path, monkeypatch):
    docx = tmp_path / "exam.docx"
    docx.write_text("fake", encoding="utf-8")
    existing_pdf = tmp_path / "exam.pdf"
    existing_pdf.write_text("old", encoding="utf-8")

    called = {"count": 0}

    def fake_soffice(_soffice_path, _docx_path, _output_dir):
        called["count"] += 1
        (tmp_path / "exam.pdf").write_text("new", encoding="utf-8")
        return True, "ok"

    monkeypatch.setattr(docs_module, "convert_docx_to_pdf_with_soffice", fake_soffice)

    summary = convert_docx_batch(
        ["exam.docx"],
        str(tmp_path),
        backend_name="soffice",
        backend_value="soffice",
        overwrite_existing=True,
    )

    assert called["count"] == 1
    assert summary["converted"] == [("exam.docx", "exam.pdf")]
    assert not summary["skipped"]
    assert not summary["failed"]


def test_detect_docx_converter_returns_none_when_soffice_absent(monkeypatch):
    monkeypatch.setattr(docs_module, "find_soffice", lambda: None)
    backend_name, backend_value = detect_docx_converter()
    assert backend_name is None
    assert backend_value is None
