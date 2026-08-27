import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from quizbuilder.config import Config
from quizbuilder.gui.app import MainWindow


@pytest.fixture(scope="module")
def application():
    return QApplication.instance() or QApplication([])


def test_main_window_exposes_theme_toggle_and_markdown_help(application, tmp_path):
    window = MainWindow(Config.defaults(root=tmp_path))
    assert window.theme_button.text() in {"☀️ Light", "🌙 Dark", "Switch to dark theme", "Switch to light theme"}
    assert window.help_button.text() == "Markdown format help"
    before = window.dark_mode
    window.toggle_theme()
    assert window.dark_mode is not before
    window.close()
