import os
from pathlib import Path
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from quizbuilder.config import Config
from quizbuilder.gui.dialogs import (
    AnswerMatrixDialog,
    CliAgentGuideDialog,
    SuperBatchDialog,
    SuperBatchSummaryDialog,
    WelcomeDialog,
)
from quizbuilder.super_batch import SuperBatchResult, SuperBatchItem
from quizbuilder.workspace import ExamOverview


@pytest.fixture(scope="module")
def application():
    return QApplication.instance() or QApplication([])


def test_welcome_dialog(application):
    dialog = WelcomeDialog()
    assert dialog.windowTitle() == "Welcome to Interactive Quiz Builder"
    dialog.close()


def test_cli_guide_dialog(application):
    reloaded = [0]

    def on_reload():
        reloaded[0] += 1
        return 2

    dialog = CliAgentGuideDialog(on_reload_providers=on_reload)
    assert "CLI AI Agents" in dialog.windowTitle()
    dialog._handle_reload()
    assert reloaded[0] == 1
    dialog.close()


def test_answer_matrix_dialog(application):
    questions = [
        {"question": "מה צבע השמיים?", "options": ["כחול", "ירוק", "אדום", "צהוב"], "correctIndex": 0},
        {"question": "מה שטח ישראל?", "options": ["1000", "22000", "50000", "100000"], "correctIndex": 1},
    ]
    saved = [False]
    dirty = [False]

    def on_save():
        saved[0] = True
        return True

    def on_dirty():
        dirty[0] = True

    dialog = AnswerMatrixDialog(
        None,
        questions=questions,
        exam_name="Sample Exam",
        on_save=on_save,
        on_dirty=on_dirty,
    )
    assert dialog.windowTitle() == "Quick Answer Matrix — Sample Exam"
    dialog._handle_save()
    assert saved[0] is True
    dialog.close()


def test_super_batch_summary_dialog(application, tmp_path):
    overview = ExamOverview(
        workspace=tmp_path / "exam1",
        pdf=tmp_path / "exam1" / "exam.pdf",
        name="exam1",
        is_digital=True,
    )
    item = SuperBatchItem(overview=overview, status="saved")
    results = [SuperBatchResult(item=item, success=True, output="Saved")]

    retried = []
    dialog = SuperBatchSummaryDialog(
        None,
        results=results,
        config=Config.defaults(root=tmp_path),
        on_retry_failed=lambda items: retried.extend(items),
    )
    assert dialog.windowTitle() == "Super Batch Results"
    dialog.close()

