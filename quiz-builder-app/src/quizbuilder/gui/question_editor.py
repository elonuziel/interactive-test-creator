"""RTL question editor form used on the quiz builder's review tab."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

HEBREW_LETTERS = ["א.", "ב.", "ג.", "ד."]


class QuestionEditorWidget(QWidget):
    """Form for editing one question: text, four options, correct answer.

    Emits ``changed`` whenever the user modifies any field so the owning
    window can track unsaved changes.
    """

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        intro = QLabel("Edit the question and answer choices below. Changes are marked unsaved until you save questions.md.")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        layout.addWidget(QLabel("Question text (נוסח השאלה):"))
        self.text_edit = QPlainTextEdit()
        self.text_edit.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.text_edit.setPlaceholderText("הקלד את נוסח השאלה בעברית...")
        self.text_edit.setMaximumHeight(110)
        layout.addWidget(self.text_edit)

        layout.addWidget(QLabel("Answer choices — select the correct answer (בחר את התשובה הנכונה):"))

        self.option_edits: list[QLineEdit] = []
        self.option_radios: list[QRadioButton] = []
        self.radio_group = QButtonGroup(self)

        for idx, letter in enumerate(HEBREW_LETTERS):
            row = QHBoxLayout()
            radio = QRadioButton()
            self.radio_group.addButton(radio, idx)
            if idx == 0:
                radio.setChecked(True)
            self.option_radios.append(radio)

            badge = QLabel(f"  {letter}  ")
            badge.setStyleSheet("background: #e2e8f0; font-weight: bold; border-radius: 4px; padding: 4px;")

            edit = QLineEdit()
            edit.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            edit.setPlaceholderText(f"אפשרות {letter}...")
            self.option_edits.append(edit)

            row.addWidget(radio)
            row.addWidget(badge)
            row.addWidget(edit, 1)
            layout.addLayout(row)

        layout.addStretch()

        self.text_edit.textChanged.connect(self.changed)
        for edit in self.option_edits:
            edit.textChanged.connect(self.changed)
        for radio in self.option_radios:
            radio.toggled.connect(lambda checked: self.changed.emit() if checked else None)

    def set_question(self, question: dict | None) -> None:
        """Populate the fields from a question dict, or clear when None."""
        if question is None:
            self.clear()
            return

        self.text_edit.setPlainText(question.get("question", ""))
        options = question.get("options", [])
        for i, field in enumerate(self.option_edits):
            field.setText(options[i] if i < len(options) else "")
        answer_index = question.get("correctIndex", 0)
        if isinstance(answer_index, int) and 0 <= answer_index < len(self.option_radios):
            self.option_radios[answer_index].setChecked(True)
        elif self.option_radios:
            self.option_radios[0].setChecked(True)

    def collect(self, question: dict) -> None:
        """Write the current field values back into a question dict."""
        question["question"] = self.text_edit.toPlainText().strip()
        question["options"] = [field.text().strip() for field in self.option_edits if field.text().strip()]
        checked_id = self.radio_group.checkedId()
        question["correctIndex"] = checked_id if checked_id >= 0 else 0

    def clear(self) -> None:
        self.text_edit.clear()
        for field in self.option_edits:
            field.clear()
        if self.option_radios:
            self.option_radios[0].setChecked(True)
