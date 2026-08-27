import os
from pathlib import Path
import fitz
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication

from quizbuilder.config import Config
from quizbuilder.documents import clean_pdf, describe_page_cleaning, parse_page_ranges, DocumentError
from quizbuilder.gui.app import MainWindow
from quizbuilder.models import Workspace


@pytest.fixture(scope="module")
def application():
    return QApplication.instance() or QApplication([])


def create_dummy_pdf(path: Path, num_pages: int = 10) -> Path:
    doc = fitz.open()
    for i in range(num_pages):
        page = doc.new_page()
        page.insert_text((50, 50), f"Page {i + 1} content with selectable text for testing.")
    doc.save(str(path))
    return path


def test_parse_page_ranges_std():
    discards = parse_page_ranges("std", total_pages=10)
    assert discards == {1, 2, 3, 4, 6, 8, 10}


def test_parse_page_ranges_even_and_odd():
    evens = parse_page_ranges("even", total_pages=6)
    assert evens == {2, 4, 6}

    odds = parse_page_ranges("odd", total_pages=6)
    assert odds == {1, 3, 5}


def test_parse_page_ranges_custom():
    custom = parse_page_ranges("1-3, 5, 8-9", total_pages=10)
    assert custom == {1, 2, 3, 5, 8, 9}


def test_describe_page_cleaning(tmp_path):
    pdf = create_dummy_pdf(tmp_path / "test.pdf", num_pages=12)
    info = describe_page_cleaning(pdf, "std")

    assert info["total"] == 12
    assert info["discarded_count"] == 8
    assert info["kept_count"] == 4


def test_clean_pdf_creates_output(tmp_path):
    pdf = create_dummy_pdf(tmp_path / "original.pdf", num_pages=8)
    clean_out = tmp_path / "original_clean.pdf"

    total, kept = clean_pdf(pdf, clean_out, "1-2, 4")
    assert total == 8
    assert kept == 5
    assert clean_out.is_file()

    doc = fitz.open(clean_out)
    assert len(doc) == 5
    assert "Page 3" in doc[0].get_text()


def test_clean_pdf_rejects_all_discarded(tmp_path):
    pdf = create_dummy_pdf(tmp_path / "original.pdf", num_pages=3)
    clean_out = tmp_path / "out.pdf"

    with pytest.raises(DocumentError, match="All pages would be discarded"):
        clean_pdf(pdf, clean_out, "1-3")


def test_gui_clean_panel_presets_and_execution(application, tmp_path):
    exam_dir = tmp_path / "exam_clean_test"
    exam_dir.mkdir()
    pdf = create_dummy_pdf(exam_dir / "exam.pdf", num_pages=8)

    window = MainWindow(Config.defaults(root=tmp_path))
    workspace = Workspace("exam_clean_test", exam_dir)
    window.load_workspace(workspace)

    assert hasattr(window, "clean_group")
    assert hasattr(window, "preset_std_button")
    assert hasattr(window, "clean_pdf_button")

    window.set_discard_preset("even")
    assert window.discard_range_edit.text() == "even"
    assert "Keeping 4 page(s)" in window.clean_summary_label.text()

    window.set_discard_preset("std")
    assert window.discard_range_edit.text() == "std"
    assert "6 discarded" in window.clean_summary_label.text()

    window.close()
