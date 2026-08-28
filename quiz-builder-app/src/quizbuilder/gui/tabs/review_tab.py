"""Review tab component for QuizBuilder GUI: question list, filtering, reordering, and editing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ...markdown import dump_questions, write_questions
from ...validation import ValidationError, load_questions
from ..dialogs import AnswerMatrixDialog
from ..question_editor import QuestionEditorWidget

if TYPE_CHECKING:
    from ..app import MainWindow


class ReviewTabWidget(QWidget):
    """Tab 2: Question list navigation, editing, reordering, and saving."""

    def __init__(self, main_window: MainWindow, parent: QWidget | None = None):
        super().__init__(parent)
        self.main_window = main_window
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        tab_layout = QVBoxLayout(self)
        tab_layout.setContentsMargins(0, 0, 0, 0)

        self.review_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.review_splitter.setChildrenCollapsible(False)

        # Left panel: Questions in this exam
        list_group = QGroupBox("Questions in this exam")
        list_layout = QVBoxLayout(list_group)
        self.question_status = QLabel("No exam selected")
        self.question_status.setStyleSheet("font-weight: bold;")

        filter_row = QHBoxLayout()
        self.question_filter_edit = QLineEdit()
        self.question_filter_edit.setPlaceholderText("Filter questions...")
        self.filter_incomplete_checkbox = QCheckBox("⚠️ Incomplete only")
        self.filter_incomplete_checkbox.setToolTip("Show only questions missing options, text, or a valid answer.")
        filter_row.addWidget(self.question_filter_edit, 1)
        filter_row.addWidget(self.filter_incomplete_checkbox)

        self.question_list = QListWidget()
        self.question_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.question_list.setDefaultDropAction(Qt.DropAction.MoveAction)

        reorder_row = QHBoxLayout()
        self.move_up_button = QPushButton("⬆️ Up")
        self.move_up_button.setToolTip("Move selected question up (Alt+↑) — or drag to reorder")
        self.move_down_button = QPushButton("⬇️ Down")
        self.move_down_button.setToolTip("Move selected question down (Alt+↓) — or drag to reorder")
        self.duplicate_button = QPushButton("📋 Duplicate")
        self.duplicate_button.setToolTip("Duplicate selected question (Ctrl+D)")
        reorder_row.addWidget(self.move_up_button)
        reorder_row.addWidget(self.move_down_button)
        reorder_row.addWidget(self.duplicate_button)

        action_row = QHBoxLayout()
        self.add_question_button = QPushButton("➕ Add")
        self.delete_question_button = QPushButton("🗑️ Delete")
        self.matrix_button = QPushButton("🔢 Answer Matrix")
        self.matrix_button.setToolTip("Open quick grid to view and edit all answers at once")
        action_row.addWidget(self.add_question_button)
        action_row.addWidget(self.delete_question_button)
        action_row.addWidget(self.matrix_button)

        self.open_questions_button = QPushButton("Open questions file...")
        self.open_questions_button.setToolTip("Load questions from any questions.md or questions.json file")

        list_layout.addWidget(self.question_status)
        list_layout.addLayout(filter_row)
        list_layout.addWidget(self.question_list, 1)
        list_layout.addLayout(reorder_row)
        list_layout.addLayout(action_row)
        list_layout.addWidget(self.open_questions_button)
        self.review_splitter.addWidget(list_group)

        # Right panel: Review and edit questions
        edit_group = QGroupBox("Review and edit questions")
        edit_layout = QVBoxLayout(edit_group)
        self.question_editor = QuestionEditorWidget()
        self.save_button = QPushButton("Save questions.md")
        self.save_button.setObjectName("primary")
        self.save_as_button = QPushButton("Save as...")
        self.save_as_button.setToolTip("Save questions to a custom .md or .json file")
        self.help_button = QPushButton("Markdown format help")
        self.help_button.setToolTip("Show the questions.md format used by this project.")
        self.save_button.setToolTip("Save the current questions to questions.md. Shortcut: Ctrl+S")
        self.next_export_button = QPushButton("Next: play or export")
        edit_layout.addWidget(self.question_editor, 1)
        edit_actions = QHBoxLayout()
        edit_actions.addWidget(self.save_button)
        edit_actions.addWidget(self.save_as_button)
        edit_actions.addWidget(self.help_button)
        edit_actions.addStretch()
        edit_actions.addWidget(self.next_export_button)
        edit_layout.addLayout(edit_actions)
        self.review_splitter.addWidget(edit_group)

        self.review_splitter.setStretchFactor(0, 4)
        self.review_splitter.setStretchFactor(1, 6)
        tab_layout.addWidget(self.review_splitter)

    def _connect_signals(self) -> None:
        self.question_filter_edit.textChanged.connect(self.refresh_question_list)
        self.filter_incomplete_checkbox.toggled.connect(self.refresh_question_list)
        self.question_list.currentRowChanged.connect(self.show_question)
        self.question_list.model().rowsMoved.connect(lambda *_: self._on_questions_reordered())
        self.help_button.clicked.connect(self.show_markdown_help)
        self.question_editor.changed.connect(self.mark_dirty)
        self.question_editor.crop_requested.connect(self.main_window.open_image_cropper)
        self.move_up_button.clicked.connect(self.move_question_up)
        self.move_down_button.clicked.connect(self.move_question_down)
        self.duplicate_button.clicked.connect(self.duplicate_question)
        self.add_question_button.clicked.connect(self.add_question)
        self.delete_question_button.clicked.connect(self.delete_question)
        self.matrix_button.clicked.connect(self.open_answer_matrix)
        self.open_questions_button.clicked.connect(self.import_custom_questions_file)
        self.save_button.clicked.connect(self.save_test)
        self.save_as_button.clicked.connect(self.save_questions_as)
        self.next_export_button.clicked.connect(lambda: (self.save_active_question(), self.main_window.tabs.setCurrentIndex(2)))

        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self.save_test)
        QShortcut(QKeySequence("Ctrl+D"), self).activated.connect(self.duplicate_question)
        QShortcut(QKeySequence("Alt+Up"), self).activated.connect(self.move_question_up)
        QShortcut(QKeySequence("Alt+Down"), self).activated.connect(self.move_question_down)
        QShortcut(QKeySequence("Delete"), self.question_list).activated.connect(self.delete_question)

    def _on_questions_reordered(self) -> None:
        """Sync state["questions"] after a drag-drop reorder in the question list."""
        questions = self.main_window.state["questions"]
        if not questions:
            return
        new_order: list = []
        seen: set[int] = set()
        for i in range(self.question_list.count()):
            item = self.question_list.item(i)
            if item is None:
                continue
            old_idx = item.data(Qt.ItemDataRole.UserRole)
            if old_idx is not None and 0 <= old_idx < len(questions) and old_idx not in seen:
                seen.add(old_idx)
                new_order.append(questions[old_idx])
        if len(new_order) == len(questions):
            self.save_active_question()
            self.main_window.state["questions"] = new_order
            self.main_window.state["dirty"] = True
            current_row = self.question_list.currentRow()
            self.refresh_question_list()
            if 0 <= current_row < self.question_list.count():
                self.question_list.setCurrentRow(current_row)

    def _update_drag_drop_mode(self) -> None:
        """Enable drag-drop reorder only when no filter is active."""
        has_filter = bool(self.question_filter_edit.text()) or self.filter_incomplete_checkbox.isChecked()
        mode = (
            QListWidget.DragDropMode.NoDragDrop
            if has_filter
            else QListWidget.DragDropMode.InternalMove
        )
        self.question_list.setDragDropMode(mode)

    def show_markdown_help(self) -> None:
        QMessageBox.information(
            self,
            "questions.md format",
            "Each question uses this format:\n\n## Question 1\n\nQuestion text\n\n- First choice\n- Second choice\n- Third choice\n- Fourth choice\n\nAnswer: A\n\nUse pageImage: path/to/page.png on its own line when a question references a diagram or table.",
        )

    def is_question_incomplete(self, q: dict) -> bool:
        if not q.get("question", "").strip():
            return True
        opts = [opt.strip() for opt in q.get("options", []) if opt.strip()]
        if len(opts) < 2:
            return True
        idx = q.get("correctIndex")
        if idx is None or idx < 0 or idx >= len(opts):
            return True
        return False

    def refresh_question_list(self) -> None:
        questions = self.main_window.state["questions"]
        filter_text = self.question_filter_edit.text().strip().casefold()
        only_incomplete = self.filter_incomplete_checkbox.isChecked()

        self._update_drag_drop_mode()
        self.question_list.blockSignals(True)
        self.question_list.clear()

        incomplete_count = 0
        visible_indices = []

        for index, item in enumerate(questions):
            is_inc = self.is_question_incomplete(item)
            if is_inc:
                incomplete_count += 1

            if only_incomplete and not is_inc:
                continue

            text = item.get("question", "").strip() or f"Question {index + 1}"
            first_line = text.split("\n", 1)[0][:60]

            if filter_text and filter_text not in text.casefold():
                continue

            icon_badge = "⚠️ " if is_inc else ""
            list_item = QListWidgetItem(f"{icon_badge}{index + 1}. {first_line}")
            list_item.setData(Qt.ItemDataRole.UserRole, index)
            self.question_list.addItem(list_item)
            visible_indices.append(index)

        self.question_list.blockSignals(False)

        # Update status header
        workspace = self.main_window.state["workspace"]
        if workspace:
            status_text = f"{workspace.name}: {len(questions)} question(s)"
            if incomplete_count > 0:
                status_text += f" | <span style='color: #f59e0b;'>⚠️ {incomplete_count} incomplete</span>"
            else:
                status_text += " | <span style='color: #10b981;'>✓ All complete</span>"
            self.question_status.setText(status_text)
        else:
            self.question_status.setText("No exam selected")

        # Reselect current question if visible
        current_idx = self.main_window.state["index"]
        if current_idx in visible_indices:
            row = visible_indices.index(current_idx)
            self.question_list.setCurrentRow(row)
        elif self.question_list.count() > 0:
            self.question_list.setCurrentRow(0)
        else:
            self.show_question(-1)

    def show_question(self, row: int) -> None:
        if self.main_window.state["loading"]:
            return

        self.save_active_question()

        if row < 0 or row >= self.question_list.count():
            self.main_window.state["index"] = -1
            self.question_editor.clear()
            self.question_editor.setEnabled(False)
            return

        real_index = self.question_list.item(row).data(Qt.ItemDataRole.UserRole)
        self.main_window.state["index"] = real_index
        question = self.main_window.state["questions"][real_index]

        self.main_window.state["loading"] = True
        self.question_editor.setEnabled(True)
        self.question_editor.set_question(question)
        self.main_window.state["loading"] = False

    def save_active_question(self) -> None:
        index = self.main_window.state["index"]
        if 0 <= index < len(self.main_window.state["questions"]):
            self.question_editor.collect(self.main_window.state["questions"][index])

    def mark_dirty(self) -> None:
        if not self.main_window.state["loading"]:
            self.main_window.state["dirty"] = True
            self.main_window._update_tab_labels()

    def add_question(self) -> None:
        self.save_active_question()
        new_q = {
            "question": "",
            "options": ["", "", "", ""],
            "correctIndex": 0,
            "pageImage": "",
        }
        self.main_window.state["questions"].append(new_q)
        self.main_window.state["dirty"] = True
        self.main_window.state["index"] = len(self.main_window.state["questions"]) - 1
        self.refresh_question_list()
        self.question_list.setCurrentRow(self.question_list.count() - 1)
        self.question_editor.text_edit.setFocus()

    def duplicate_question(self) -> None:
        index = self.main_window.state["index"]
        if index < 0 or index >= len(self.main_window.state["questions"]):
            return
        self.save_active_question()
        source = self.main_window.state["questions"][index]
        dup = {
            "question": source.get("question", ""),
            "options": list(source.get("options", ["", "", "", ""])),
            "correctIndex": source.get("correctIndex", 0),
            "pageImage": source.get("pageImage", ""),
        }
        self.main_window.state["questions"].insert(index + 1, dup)
        self.main_window.state["dirty"] = True
        self.main_window.state["index"] = index + 1
        self.refresh_question_list()

    def delete_question(self) -> None:
        index = self.main_window.state["index"]
        if index < 0 or index >= len(self.main_window.state["questions"]):
            return
        confirm = QMessageBox.question(
            self,
            "Delete Question",
            f"Are you sure you want to delete Question {index + 1}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.main_window.state["questions"].pop(index)
            self.main_window.state["dirty"] = True
            if not self.main_window.state["questions"]:
                self.main_window.state["index"] = -1
            elif index >= len(self.main_window.state["questions"]):
                self.main_window.state["index"] = len(self.main_window.state["questions"]) - 1
            self.refresh_question_list()

    def move_question_up(self) -> None:
        index = self.main_window.state["index"]
        if index <= 0 or index >= len(self.main_window.state["questions"]):
            return
        self.save_active_question()
        q = self.main_window.state["questions"].pop(index)
        self.main_window.state["questions"].insert(index - 1, q)
        self.main_window.state["dirty"] = True
        self.main_window.state["index"] = index - 1
        self.refresh_question_list()

    def move_question_down(self) -> None:
        index = self.main_window.state["index"]
        if index < 0 or index >= len(self.main_window.state["questions"]) - 1:
            return
        self.save_active_question()
        q = self.main_window.state["questions"].pop(index)
        self.main_window.state["questions"].insert(index + 1, q)
        self.main_window.state["dirty"] = True
        self.main_window.state["index"] = index + 1
        self.refresh_question_list()

    def open_answer_matrix(self) -> None:
        self.save_active_question()
        questions = self.main_window.state["questions"]
        if not questions:
            QMessageBox.information(self, "Answer Matrix", "No questions available in this exam.")
            return
        dialog = AnswerMatrixDialog(questions, parent=self)
        if dialog.exec() == AnswerMatrixDialog.DialogCode.Accepted:
            self.main_window.state["dirty"] = True
            self.refresh_question_list()
            current_idx = self.main_window.state["index"]
            if 0 <= current_idx < len(questions):
                self.question_editor.set_question(questions[current_idx])

    def import_custom_questions_file(self) -> None:
        workspace = self.main_window.state["workspace"]
        start_dir = str(workspace.path) if workspace else (str(self.main_window.state["root"]) if self.main_window.state["root"] else "")
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Import Questions File",
            start_dir,
            "Question Files (*.md *.json);;Markdown Files (*.md);;JSON Files (*.json);;All Files (*)",
        )
        if filename:
            file_path = Path(filename)
            try:
                if file_path.suffix.lower() == ".json":
                    data = json.loads(file_path.read_text(encoding="utf-8"))
                    questions = data if isinstance(data, list) else data.get("questions", [])
                else:
                    questions = load_questions(file_path)
                if not questions:
                    QMessageBox.warning(self, "Empty File", f"No questions found in {file_path.name}.")
                    return
                self.save_active_question()
                self.main_window.state["questions"] = questions
                self.main_window.state["dirty"] = True
                self.main_window.state["index"] = 0
                self.refresh_question_list()
                self.main_window._set_status(f"Imported {len(questions)} question(s) from {file_path.name}", "success")
                QMessageBox.information(self, "Questions Imported", f"Successfully loaded {len(questions)} question(s) from:\n\n{file_path.name}\n\nClick 'Save questions.md' to store them in your active exam folder.")
            except Exception as e:
                QMessageBox.critical(self, "Import Error", f"Could not load questions from {file_path.name}:\n\n{e}")

    def save_questions_as(self) -> None:
        self.save_active_question()
        questions = self.main_window.state["questions"]
        if not questions:
            QMessageBox.warning(self, "No questions", "There are no questions to save.")
            return
        workspace = self.main_window.state["workspace"]
        default_name = f"{workspace.name}_questions.md" if workspace else "questions.md"
        start_dir = str(workspace.path / default_name) if workspace else default_name
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save Questions As",
            start_dir,
            "Markdown Files (*.md);;JSON Files (*.json);;All Files (*)",
        )
        if filename:
            file_path = Path(filename)
            try:
                if file_path.suffix.lower() == ".json":
                    file_path.write_text(json.dumps(questions, ensure_ascii=False, indent=2), encoding="utf-8")
                else:
                    write_questions(file_path, dump_questions(questions))
                self.main_window._set_status(f"Questions saved to {file_path.name}", "success")
                QMessageBox.information(self, "Saved", f"Successfully saved {len(questions)} question(s) to:\n\n{file_path.name}")
            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"Could not save questions to {file_path.name}:\n\n{e}")

    def save_test(self) -> None:
        workspace = self.main_window.state["workspace"]
        if not workspace:
            QMessageBox.warning(self, "No exam selected", "Select an exam before saving.")
            return
        self.save_active_question()
        questions = self.main_window.state["questions"]
        try:
            write_questions(workspace.questions_path, dump_questions(questions))
            self.main_window.state["dirty"] = False
            self.main_window._update_tab_labels()
            self.main_window._set_status(f"Saved {len(questions)} question(s) to {workspace.name}/questions.md", "success")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Could not save questions.md:\n\n{e}")
