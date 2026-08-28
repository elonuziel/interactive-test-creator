from __future__ import annotations

import os
from pathlib import Path

import pytest

from quizbuilder.prompts import extract_markdown_from_response


def test_extract_markdown_from_code_blocks():
    raw_with_fences = """Here is the extracted quiz:
```markdown
## Question 1
Sample question?
- A
- B
Answer: A
```
Hope this helps!"""
    assert extract_markdown_from_response(raw_with_fences) == "## Question 1\nSample question?\n- A\n- B\nAnswer: A"

    raw_plain = "## Question 1\nSample question?\n- A\n- B\nAnswer: A"
    assert extract_markdown_from_response(raw_plain) == raw_plain


@pytest.fixture(scope="module")
def application():
    pyside6 = pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_copy_file_to_clipboard(application, tmp_path):
    from quizbuilder.gui.web_batch_dialog import copy_file_to_clipboard
    test_file = tmp_path / "sample.pdf"
    test_file.write_bytes(b"%PDF-1.4 test")

    assert copy_file_to_clipboard(test_file) is True
    # Non-existent file
    assert copy_file_to_clipboard(tmp_path / "non_existent.pdf") is False


def test_reveal_in_file_manager(application, tmp_path):
    from quizbuilder.gui.web_batch_dialog import reveal_in_file_manager
    test_file = tmp_path / "sample.pdf"
    test_file.write_bytes(b"%PDF-1.4 test")
    # Should not raise exception
    reveal_in_file_manager(test_file)


def test_draggable_pdf_widget(application, tmp_path):
    from quizbuilder.gui.web_batch_dialog import DraggablePdfWidget
    widget = DraggablePdfWidget()
    assert widget.pdf_path is None
    assert not widget.isEnabled()

    pdf_file = tmp_path / "exam.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 content")
    widget.set_pdf(pdf_file)

    assert widget.pdf_path == pdf_file
    assert widget.isEnabled()
    assert pdf_file.name in widget.name_label.text()


def test_web_batch_dialog_queue_and_save(application, tmp_path):
    from quizbuilder.config import Config
    from quizbuilder.gui.web_batch_dialog import WebAIBatchDialog
    from quizbuilder.markdown import load_questions
    from quizbuilder.workspace import Workspace

    # Setup 2 test exam folders
    exam1 = tmp_path / "exam_chem_1"
    exam1.mkdir()
    pdf1 = exam1 / "chemistry.pdf"
    pdf1.write_bytes(b"%PDF-1.4 chem")

    exam2 = tmp_path / "exam_bio_2"
    exam2.mkdir()
    pdf2 = exam2 / "biology.pdf"
    pdf2.write_bytes(b"%PDF-1.4 bio")
    (exam2 / "answers.csv").write_text("1,A\n2,B\n", encoding="utf-8")

    ws1 = Workspace("exam_chem_1", exam1)
    ws2 = Workspace("exam_bio_2", exam2)

    config = Config.defaults(root=tmp_path)
    dialog = WebAIBatchDialog(parent=None, workspaces=[ws1, ws2], config=config, dark_mode=False)

    assert len(dialog.items) == 2
    assert dialog.current_index == 0
    assert dialog.items[0].pdf_path == pdf1
    assert dialog.items[1].pdf_path == pdf2
    assert dialog.queue_list.count() == 2

    # Paste markdown response for exam 1
    ai_markdown = """```markdown
## Question 1
What is water?
- Liquid
- Gas
- Solid
- Plasma
Answer: A

## Question 2
What is sodium?
- Element
- Molecule
- Planet
- Star
Answer: A
```"""

    dialog.response_edit.setPlainText(ai_markdown)
    dialog.save_and_next()

    # Verify questions.md was saved for exam 1
    assert (exam1 / "questions.md").exists()
    qs1 = load_questions(exam1 / "questions.md")
    assert len(qs1) == 2
    assert dialog.items[0].status == "saved"
    assert dialog.items[0].questions_count == 2

    # Dialog should have auto-advanced to exam 2
    assert dialog.current_index == 1

    # Skip exam 2
    dialog.skip_current()
    assert dialog.items[1].status == "skipped"

    dialog.close()


def test_main_window_has_web_batch_button(application, tmp_path):
    from quizbuilder.config import Config
    from quizbuilder.gui.app import MainWindow
    window = MainWindow(Config.defaults(root=tmp_path))
    assert hasattr(window, "web_batch_button")
    assert "Web AI Batch" in window.web_batch_button.text()
    window.close()
