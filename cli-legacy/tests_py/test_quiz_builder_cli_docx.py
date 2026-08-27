"""Tests for DOCX intake and conversion flow in quizbuilder."""

from pathlib import Path
import sys

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quizbuilder.config import Config
from quizbuilder.documents import convert_docx_batch, detect_docx_converter, find_soffice
from quizbuilder.models import Workspace
from quizbuilder.wizard import run_workspace
import quizbuilder.documents as docs_module
import quizbuilder.wizard as wizard_module


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


def test_process_workspace_fallback_when_no_converter_and_no_pdf(tmp_path, monkeypatch):
    test_dir = tmp_path / "workspace"
    test_dir.mkdir()
    (test_dir / "only.docx").write_text("docx", encoding="utf-8")

    monkeypatch.setattr(docs_module, "find_soffice", lambda: None)
    monkeypatch.setattr(wizard_module, "open_path", lambda _p: None)

    workspace = Workspace("workspace", test_dir)
    config = Config.defaults(root=tmp_path)

    # Should not raise; safely prints fallback prompt and returns
    run_workspace(config, workspace)


def test_process_workspace_converts_docx_when_soffice_available(tmp_path, monkeypatch):
    test_dir = tmp_path / "workspace"
    test_dir.mkdir()
    (test_dir / "exam.docx").write_text("docx", encoding="utf-8")

    def fake_convert(source, out_dir):
        pdf = Path(out_dir) / f"{Path(source).stem}.pdf"
        pdf.write_text("fake pdf", encoding="utf-8")
        return pdf

    monkeypatch.setattr(wizard_module, "convert_docx_with_soffice", fake_convert)
    monkeypatch.setattr(wizard_module, "classify_pdf", lambda _p: False)
    monkeypatch.setattr(wizard_module, "open_path", lambda _p: None)
    monkeypatch.setattr(wizard_module.PipelineRunner, "render_pages", lambda *args, **kwargs: None)
    monkeypatch.setattr("builtins.input", lambda _p="": "s")

    workspace = Workspace("workspace", test_dir)
    config = Config.defaults(root=tmp_path)

    run_workspace(config, workspace)
    assert (test_dir / "exam.pdf").exists()
