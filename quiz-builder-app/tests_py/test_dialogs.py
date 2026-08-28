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
from quizbuilder.super_batch import SuperBatchResult, SuperBatchItem, ExamOverview


@pytest.fixture(scope="module")
def application():
    return QApplication.instance() or QApplication([])


def test_welcome_dialog(application):
    dialog = WelcomeDialog()
    assert dialog.windowTitle() == "Welcome to Interactive Quiz Builder"
    dialog.close()
    dialog.deleteLater()


def test_cli_guide_dialog(application, monkeypatch):
    reloaded = [0]

    def on_reload():
        reloaded[0] += 1
        return 2

    dialog = CliAgentGuideDialog(on_reload_providers=on_reload)
    assert "CLI AI Agents" in dialog.windowTitle()
    dialog._handle_reload()
    assert reloaded[0] == 1
    dialog.close()
    dialog.deleteLater()


def test_answer_matrix_dialog(application):
    questions = [
        {"question": "מה צבע השמיים?", "options": ["כחול", "ירוק", "אדום", "צהוב", "סגול", "כתום"], "correctIndex": 4},
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
    dialog.deleteLater()


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
    dialog.deleteLater()


def test_super_batch_dialog_skip_and_select_all(application, tmp_path):
    exam1 = tmp_path / "exam1"
    exam1.mkdir()
    (exam1 / "exam.pdf").write_bytes(b"%PDF")
    exam2 = tmp_path / "exam2"
    exam2.mkdir()
    (exam2 / "exam.pdf").write_bytes(b"%PDF")

    overview1 = ExamOverview(workspace=exam1, pdf=exam1 / "exam.pdf", name="exam1", is_digital=True)
    overview2 = ExamOverview(workspace=exam2, pdf=exam2 / "exam.pdf", name="exam2", is_digital=False)

    item1 = SuperBatchItem(overview=overview1)
    item2 = SuperBatchItem(overview=overview2)

    from quizbuilder.providers import Provider
    providers = [(Provider("fake", "Fake Provider", "local"), "fake-cli")]

    dialog = SuperBatchDialog(
        None,
        root=tmp_path,
        config=Config.defaults(root=tmp_path),
        local_providers=providers,
        custom_items=[item1, item2],
    )
    assert dialog.table.rowCount() == 2
    assert len(dialog.get_selected_items()) == 2
    assert "Selected: 2 / 2" in dialog.selected_count_label.text()

    # Toggle first item off
    dialog.rows_data[0]["include_box"].setChecked(False)
    assert len(dialog.get_selected_items()) == 1
    assert dialog.rows_data[0]["decision_combo"].currentData() == "skip"
    assert "1 / 2" in dialog.selected_count_label.text()

    # Change second item to skip via decision dropdown
    dialog.rows_data[1]["decision_combo"].setCurrentIndex(3)
    assert len(dialog.get_selected_items()) == 0
    assert not dialog.rows_data[1]["include_box"].isChecked()
    assert "0 / 2" in dialog.selected_count_label.text()

    # Use Select All
    for it in dialog.rows_data:
        it["include_box"].setChecked(True)
    assert len(dialog.get_selected_items()) == 2

    dialog.close()
    dialog.deleteLater()


