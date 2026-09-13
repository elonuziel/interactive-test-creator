"""Regression tests for GUI fixes and dynamic delegation in Round 3:
- discover_batch export and imports
- LITE_STYLESHEET typography rule
- Question editor relative image preview resolution
- MainWindow session restore with invalid paths
- MainWindow dynamic __getattr__ and __dir__ delegation
"""
from __future__ import annotations

import base64
from pathlib import Path
import pytest

from quizbuilder import batch
from quizbuilder import workspace
from quizbuilder.gui import styles


# Valid 1x1 PNG byte sequence
VALID_1X1_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


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
    sample_img.write_bytes(VALID_1X1_PNG)

    editor = QuestionEditorWidget()
    question = {
        "question": "שאלה עם גרף?",
        "options": ["א", "ב"],
        "correctIndex": 0,
        "image": "images/diagram.png",
    }

    editor.set_question(question, workspace_path=tmp_path)
    assert not editor.image_preview.isHidden()
    assert editor.image_preview.pixmap() is not None and not editor.image_preview.pixmap().isNull()
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


def test_main_window_dynamic_delegation(tmp_path):
    """Verify __getattr__ and __dir__ delegate seamlessly to all 3 tabs."""
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    from quizbuilder.config import Config
    from quizbuilder.gui.app import MainWindow

    _app = QApplication.instance() or QApplication([])

    window = MainWindow(Config.defaults(root=tmp_path))

    # Attributes on extract_tab
    assert hasattr(window, "exam_list")
    assert window.exam_list is window.extract_tab.exam_list
    assert hasattr(window, "select_all_extract_exams")
    assert callable(window.select_all_extract_exams)

    # Attributes on review_tab
    assert hasattr(window, "question_editor")
    assert window.question_editor is window.review_tab.question_editor
    assert hasattr(window, "refresh_question_list")
    assert callable(window.refresh_question_list)

    # Attributes on export_tab
    assert hasattr(window, "play_list")
    assert window.play_list is window.export_tab.play_list
    assert hasattr(window, "select_all_play_exams")
    assert callable(window.select_all_play_exams)

    # Unknown attribute raises AttributeError
    with pytest.raises(AttributeError):
        _ = window.non_existent_attribute_12345

    # dir(window) includes tab attributes
    dir_attrs = dir(window)
    assert "exam_list" in dir_attrs
    assert "question_editor" in dir_attrs
    assert "play_list" in dir_attrs

    window.close()
    window.deleteLater()
