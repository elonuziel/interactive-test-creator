import os
from pathlib import Path
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from quizbuilder.config import Config
from quizbuilder.gui.app import MainWindow
from quizbuilder.gui.question_editor import QuestionEditorWidget
from quizbuilder.models import Workspace


@pytest.fixture(scope="module")
def application():
    return QApplication.instance() or QApplication([])


def test_question_editor_round_trips_question(application):
    editor = QuestionEditorWidget()
    source = {"question": "מה נשמע?", "options": ["טוב", "מצוין"], "correctIndex": 1}

    editor.set_question(source)
    result = {}
    editor.collect(result)

    assert result["question"] == source["question"]
    assert result["options"] == source["options"]
    assert result["correctIndex"] == source["correctIndex"]
    editor.deleteLater()


def test_main_window_populates_real_tests_folder(application):
    root = Path(__file__).resolve().parents[2] / "tests"
    window = MainWindow(Config.defaults(root=root))

    assert window.exam_list.count() == 35
    assert window.ai_provider_combo.findText("Web: Freebuff Chat") >= 0
    window.close()


def test_main_window_tracks_editor_changes(application, tmp_path):
    workspace_path = tmp_path / "exam"
    workspace_path.mkdir()
    workspace = Workspace("exam", workspace_path)
    window = MainWindow(Config.defaults(root=tmp_path))
    window.state["workspace"] = workspace
    window.state["questions"] = [{"question": "Old", "options": ["A", "B"], "correctIndex": 0}]
    window.state["index"] = 0
    window.question_editor.set_question(window.state["questions"][0])
    window.state["dirty"] = False

    window.question_editor.text_edit.setPlainText("New")

    assert window.state["dirty"] is True
    window.state["dirty"] = False
    window.close()
