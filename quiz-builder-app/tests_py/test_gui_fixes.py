"""Regression tests for GUI fixes in Round 3:
- discover_batch export and imports
- LITE_STYLESHEET typography rule
- Question editor relative image preview resolution
- MainWindow session restore with invalid paths
"""
from __future__ import annotations

from pathlib import Path
import pytest

from quizbuilder import batch
from quizbuilder import workspace
from quizbuilder.gui import styles


def test_batch_module_exports_discover_batch():
    """Verify discover_batch is exported from quizbuilder.batch and not workspace."""
    assert hasattr(batch, "discover_batch")
    assert not hasattr(workspace, "discover_batch")


def test_lite_stylesheet_has_qlabel_color():
    """Verify LITE_STYLESHEET contains explicit QLabel styling matching DARK_STYLESHEET."""
    assert "QLabel { color: #1e293b; }" in styles.LITE_STYLESHEET
    assert "QLabel { color: #e2e8f0; }" in styles.DARK_STYLESHEET


def test_question_editor_image_preview_with_workspace_path(tmp_path):
    """Verify that QuestionEditorWidget correctly resolves relative image paths when workspace_path is passed."""
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    from quizbuilder.gui.question_editor import QuestionEditorWidget

    _app = QApplication.instance() or QApplication([])

    img_dir = tmp_path / "images"
    img_dir.mkdir()
    sample_img = img_dir / "diagram.png"
    # Write a 1x1 transparent PNG
    sample_img.write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00"
        b"\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    editor = QuestionEditorWidget()
    question = {
        "question": "שאלה עם גרף?",
        "options": ["א", "ב"],
        "correctIndex": 0,
        "image": "images/diagram.png",
    }

    # Pass relative workspace_path
    editor.set_question(question, workspace_path=tmp_path)
    assert editor.image_preview.isVisible()
    assert "Attached Graph/Diagram" in editor.image_info_label.text()
    assert "not found on disk" not in editor.image_info_label.text()

    editor.deleteLater()


def test_main_window_restore_session_invalid_root(tmp_path):
    """Verify that non-existent workspace_root does not set a ghost state['root']."""
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    from quizbuilder.config import Config
    from quizbuilder.gui.app import MainWindow

    _app = QApplication.instance() or QApplication([])

    non_existent = tmp_path / "does_not_exist_folder"
    config = Config.defaults(root=non_existent)
    # Explicitly set non-existent workspace root
    config.workspace_root = non_existent

    window = MainWindow(config)
    # Root must be None, not non_existent
    assert window.state["root"] is None
    assert "No exam folder selected" in window.root_label.text()

    window.close()
    window.deleteLater()
