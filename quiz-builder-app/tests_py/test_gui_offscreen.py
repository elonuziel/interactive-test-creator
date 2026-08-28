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
    source = {"question": "מה נשמע?", "options": ["אחד", "שתיים", "שלוש", "ארבע", "חמש", "שש"], "correctIndex": 4}

    editor.set_question(source)
    result = {}
    editor.collect(result)

    assert result["question"] == source["question"]
    assert result["options"] == source["options"]
    assert result["correctIndex"] == 4

    # Test dynamic add & remove row
    editor._add_option_row()
    assert not editor.option_rows[6].isHidden()
    editor._remove_option_row()
    assert editor.option_rows[6].isHidden()

    editor.deleteLater()


def test_main_window_populates_real_tests_folder(application, tmp_path):
    for name in ["exam_2020_a", "exam_2021_b"]:
        exam_dir = tmp_path / name
        exam_dir.mkdir()
        (exam_dir / "questions.md").write_text("## Question 1\nTest?\n- A\n- B\n\nAnswer: A\n", encoding="utf-8")
        (exam_dir / f"{name}.pdf").write_bytes(b"%PDF-1.4\n")

    window = MainWindow(Config.defaults(root=tmp_path))

    assert window.exam_list.count() == 2
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


def test_main_window_custom_file_choosers(application, tmp_path):
    exam_dir = tmp_path / "exam_nested"
    exam_dir.mkdir()
    (exam_dir / "exam.pdf").write_bytes(b"%PDF-1.4\n")
    (exam_dir / "exam.docx").touch()
    (exam_dir / "keys.csv").write_text("1,A\n2,B\n", encoding="utf-8")
    (exam_dir / "questions.md").write_text("## Question 1\nQ?\n- A\n- B\n\nAnswer: A\n", encoding="utf-8")

    window = MainWindow(Config.defaults(root=tmp_path))
    assert hasattr(window, "browse_pdf_button")
    assert hasattr(window, "browse_answer_button")
    assert hasattr(window, "open_questions_button")
    assert hasattr(window, "save_as_button")

    workspace = Workspace("exam_nested", exam_dir)
    window.load_workspace(workspace)

    # Both PDF and DOCX should be listed in the exam file combo
    items = [window.pdf_combo.itemText(i) for i in range(window.pdf_combo.count())]
    assert any("exam.pdf" in item for item in items)
    assert any("exam.docx" in item for item in items)

    # CSV answer key should be listed in the answer key combo
    answers = [window.answer_combo.itemText(i) for i in range(window.answer_combo.count())]
    assert any("keys.csv" in ans for ans in answers)

    window.close()


def test_cli_agent_info_buttons_and_provider_reload(application, tmp_path):
    window = MainWindow(Config.defaults(root=tmp_path))
    assert hasattr(window, "super_batch_info_btn")
    assert hasattr(window, "ai_info_btn")
    assert "CLI AI agent" in window.super_batch_info_btn.toolTip()
    assert "CLI AI agent" in window.ai_info_btn.toolTip()

    initial_count = window.ai_provider_combo.count()
    assert initial_count > 0
    window.reload_ai_providers()
    assert window.ai_provider_combo.count() == initial_count
    window.close()


def test_question_reordering_and_duplication(application, tmp_path):
    window = MainWindow(Config.defaults(root=tmp_path))
    window.state["questions"] = [
        {"question": "Q1", "options": ["A", "B"], "correctIndex": 0},
        {"question": "Q2", "options": ["C", "D"], "correctIndex": 1},
        {"question": "Q3", "options": ["E", "F"], "correctIndex": 0},
    ]
    window.refresh_question_list()
    assert window.question_list.count() == 3

    # Duplicate Q2
    window.show_question(1)
    window.duplicate_question()
    assert len(window.state["questions"]) == 4
    assert window.state["questions"][2]["question"] == "Q2"

    # Move Q3 (now at index 3) up
    window.show_question(3)
    window.move_question_up()
    assert window.state["questions"][2]["question"] == "Q3"

    # Move Q1 down
    window.show_question(0)
    window.move_question_down()
    assert window.state["questions"][1]["question"] == "Q1"

    window.state["dirty"] = False
    window.close()


def test_question_filtering_and_status(application, tmp_path):
    window = MainWindow(Config.defaults(root=tmp_path))
    window.state["questions"] = [
        {"question": "Math calculus integral", "options": ["A", "B"], "correctIndex": 0},
        {"question": "Physics gravity force", "options": ["C", "D"], "correctIndex": 1},
        {"question": "", "options": ["E"], "correctIndex": 0},  # incomplete
    ]
    window.refresh_question_list()
    assert "2 Complete" in window.question_status.text()
    assert "1 Incomplete" in window.question_status.text()
    assert window.question_list.count() == 3

    # Filter by keyword
    window.question_filter_edit.setText("calculus")
    assert window.question_list.count() == 1
    assert "Math calculus" in window.question_list.item(0).text()

    # Filter by incomplete only
    window.question_filter_edit.clear()
    window.filter_incomplete_checkbox.setChecked(True)
    assert window.question_list.count() == 1
    assert "Empty question" in window.question_list.item(0).text()

    window.state["dirty"] = False
    window.close()


def test_main_window_has_matrix_button_and_explanation(application, tmp_path):
    window = MainWindow(Config.defaults(root=tmp_path))
    assert hasattr(window, "matrix_button")
    assert hasattr(window.question_editor, "explanation_edit")

    # Set question with explanation
    q = {
        "question": "Q with explanation",
        "options": ["A", "B"],
        "correctIndex": 0,
        "explanation": "Because of reason X",
    }
    window.question_editor.set_question(q)
    assert window.question_editor.explanation_edit.toPlainText() == "Because of reason X"

    collected = {}
    window.question_editor.collect(collected)
    assert collected["explanation"] == "Because of reason X"

    window.state["dirty"] = False
    window.close()

