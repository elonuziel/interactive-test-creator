"""RTL question editor form used on the quiz builder's review tab."""

from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
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

        # Image / Graph display
        self.image_info_label = QLabel("")
        self.image_info_label.setObjectName("image_info")
        self.image_info_label.setStyleSheet("color: #38bdf8; font-weight: bold; margin-top: 4px;")
        self.image_info_label.setVisible(False)
        self.image_preview = QLabel("")
        self.image_preview.setMaximumHeight(160)
        self.image_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_preview.setStyleSheet("border: 1px dashed #334155; border-radius: 6px; padding: 4px; background: rgba(0,0,0,0.1);")
        self.image_preview.setVisible(False)
        layout.addWidget(self.image_info_label)
        layout.addWidget(self.image_preview)

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
            badge.setObjectName("badge")

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

    def set_question(self, question: dict | None, workspace_path: Path | None = None) -> None:
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

        # Show image preview if attached
        img_rel = question.get("image") or question.get("pageImage")
        if img_rel and workspace_path:
            img_file = Path(img_rel)
            if not img_file.is_absolute():
                img_file = workspace_path / img_rel
            if img_file.is_file():
                pix = QPixmap(str(img_file))
                if not pix.isNull():
                    scaled = pix.scaled(320, 160, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    self.image_preview.setPixmap(scaled)
                    self.image_preview.setVisible(True)
                    self.image_info_label.setText(f"📊 Attached Graph/Diagram: {img_rel}")
                    self.image_info_label.setVisible(True)
                    return
        self.image_preview.clear()
        self.image_preview.setVisible(False)
        self.image_info_label.setVisible(False)

    def collect(self, question: dict) -> None:
        """Write the current field values back into a question dict."""
        question["question"] = self.text_edit.toPlainText().strip()
        non_empty_options = [field.text().strip() for field in self.option_edits if field.text().strip()]
        question["options"] = non_empty_options
        checked_id = self.radio_group.checkedId()
        if 0 <= checked_id < len(self.option_edits):
            checked_text = self.option_edits[checked_id].text().strip()
            if checked_text in non_empty_options:
                question["correctIndex"] = non_empty_options.index(checked_text)
            else:
                question["correctIndex"] = min(max(0, checked_id), max(0, len(non_empty_options) - 1))
        else:
            question["correctIndex"] = 0

    def clear(self) -> None:
        self.text_edit.clear()
        for field in self.option_edits:
            field.clear()
        if self.option_radios:
            self.option_radios[0].setChecked(True)
        self.image_preview.clear()
        self.image_preview.setVisible(False)
        self.image_info_label.setVisible(False)
