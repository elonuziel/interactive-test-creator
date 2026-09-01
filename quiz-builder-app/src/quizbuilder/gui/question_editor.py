"""RTL question editor form used on the quiz builder's review tab."""

from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

HEBREW_LETTERS = ["א.", "ב.", "ג.", "ד.", "ה.", "ו.", "ז.", "ח."]


class QuestionEditorWidget(QWidget):
    """Form for editing one question: text, dynamic options (2-8), correct answer.

    Emits ``changed`` whenever the user modifies any field so the owning
    window can track unsaved changes.
    """

    changed = Signal()
    crop_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_image: str | None = None
        self._workspace_path: Path | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        layout.addWidget(QLabel("Question text:"))
        self.text_edit = QPlainTextEdit()
        self.text_edit.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.text_edit.setPlaceholderText("הקלד את נוסח השאלה בעברית...")
        self.text_edit.setMinimumHeight(65)
        self.text_edit.setMaximumHeight(260)
        layout.addWidget(self.text_edit)

        # Image / Graph display & action controls
        self.image_container = QWidget()
        img_layout = QVBoxLayout(self.image_container)
        img_layout.setContentsMargins(0, 0, 0, 0)
        img_layout.setSpacing(4)

        self.image_info_label = QLabel("")
        self.image_info_label.setObjectName("image_info")
        self.image_info_label.setStyleSheet("color: #38bdf8; font-weight: bold;")
        self.image_info_label.setVisible(False)

        self.image_preview = QLabel("")
        self.image_preview.setMaximumHeight(160)
        self.image_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_preview.setStyleSheet("border: 1px dashed #334155; border-radius: 6px; padding: 4px; background: rgba(0,0,0,0.1);")
        self.image_preview.setVisible(False)

        img_btn_row = QHBoxLayout()
        self.browse_image_btn = QPushButton("🖼️ Attach Image...")
        self.browse_image_btn.setToolTip("Attach a custom diagram, graph, or cropped image to this question.")
        self.browse_image_btn.clicked.connect(self._choose_image_file)

        self.crop_image_btn = QPushButton("✂️ Crop Page in Browser")
        self.crop_image_btn.setToolTip("Open the web cropper to crop a diagram or math formula from the PDF pages.")
        self.crop_image_btn.clicked.connect(self.crop_requested.emit)

        self.remove_image_btn = QPushButton("✖️ Remove")
        self.remove_image_btn.setToolTip("Remove the attached image reference from this question.")
        self.remove_image_btn.clicked.connect(self._remove_image)
        self.remove_image_btn.setVisible(False)

        img_btn_row.addWidget(self.browse_image_btn)
        img_btn_row.addWidget(self.crop_image_btn)
        img_btn_row.addWidget(self.remove_image_btn)
        img_btn_row.addStretch()

        img_layout.addWidget(self.image_info_label)
        img_layout.addWidget(self.image_preview)
        img_layout.addLayout(img_btn_row)
        layout.addWidget(self.image_container)

        layout.addWidget(QLabel("Answer choices — select the correct one:"))

        self.option_edits: list[QLineEdit] = []
        self.option_radios: list[QRadioButton] = []
        self.option_rows: list[QWidget] = []
        self.radio_group = QButtonGroup(self)

        self.options_layout = QVBoxLayout()
        self.options_layout.setSpacing(4)

        for idx, letter in enumerate(HEBREW_LETTERS):
            row_widget = QWidget()
            row = QHBoxLayout(row_widget)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(6)

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
            self.options_layout.addWidget(row_widget)
            self.option_rows.append(row_widget)

            # Default: show first 4 options, hide 5-8 until needed
            if idx >= 4:
                row_widget.setVisible(False)

        layout.addLayout(self.options_layout)

        # Dynamic add/remove option buttons
        opt_mgmt_row = QHBoxLayout()
        self.add_option_btn = QPushButton("➕ Add Option")
        self.add_option_btn.setToolTip("Add another choice row (e.g. ה, ו, ז, ח)")
        self.add_option_btn.clicked.connect(self._add_option_row)

        self.remove_option_btn = QPushButton("➖ Remove Option")
        self.remove_option_btn.setToolTip("Remove the last choice row (minimum 2)")
        self.remove_option_btn.clicked.connect(self._remove_option_row)

        opt_mgmt_row.addWidget(self.add_option_btn)
        opt_mgmt_row.addWidget(self.remove_option_btn)
        opt_mgmt_row.addStretch()
        layout.addLayout(opt_mgmt_row)

        layout.addWidget(QLabel("Explanation (optional):"))
        self.explanation_edit = QPlainTextEdit()
        self.explanation_edit.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self.explanation_edit.setPlaceholderText("הקלד הסבר או נימוק לתשובה הנכונה (יוצג לתלמיד במשוב)...")
        self.explanation_edit.setMinimumHeight(45)
        self.explanation_edit.setMaximumHeight(120)
        layout.addWidget(self.explanation_edit)

        layout.addStretch()

        self.text_edit.textChanged.connect(self.changed)
        self.explanation_edit.textChanged.connect(self.changed)
        for edit in self.option_edits:
            edit.textChanged.connect(self.changed)
        for radio in self.option_radios:
            radio.toggled.connect(lambda checked: self.changed.emit() if checked else None)

    def _add_option_row(self) -> None:
        """Reveal the next hidden option row (up to 8 options)."""
        for i, row in enumerate(self.option_rows):
            if row.isHidden():
                row.setVisible(True)
                self.option_edits[i].setFocus()
                self.changed.emit()
                break

    def _remove_option_row(self) -> None:
        """Hide the last visible option row (minimum 2 options kept)."""
        visible_indices = [i for i, row in enumerate(self.option_rows) if not row.isHidden()]
        if len(visible_indices) > 2:
            last_idx = visible_indices[-1]
            self.option_rows[last_idx].setVisible(False)
            self.option_edits[last_idx].clear()
            if self.option_radios[last_idx].isChecked():
                self.option_radios[0].setChecked(True)
            self.changed.emit()

    def set_question(self, question: dict | None, workspace_path: Path | None = None) -> None:
        """Populate the fields from a question dict, or clear when None."""
        self._workspace_path = workspace_path
        if question is None:
            self.clear()
            return

        self.text_edit.setPlainText(question.get("question", ""))
        self.explanation_edit.setPlainText(question.get("explanation", ""))
        options = question.get("options", [])
        visible_count = max(4, min(len(self.option_rows), len(options)))

        for i, row in enumerate(self.option_rows):
            row.setVisible(i < visible_count)
            self.option_edits[i].setText(options[i] if i < len(options) else "")

        answer_index = question.get("correctIndex", 0)
        if isinstance(answer_index, int) and 0 <= answer_index < visible_count:
            self.option_radios[answer_index].setChecked(True)
        elif self.option_radios:
            self.option_radios[0].setChecked(True)

        self._current_image = question.get("image") or question.get("pageImage")
        self._render_image_preview()

    def _render_image_preview(self) -> None:
        if self._current_image and self._workspace_path:
            img_file = Path(self._current_image)
            if not img_file.is_absolute():
                img_file = self._workspace_path / self._current_image
            if img_file.is_file():
                pix = QPixmap(str(img_file))
                if not pix.isNull():
                    scaled = pix.scaled(320, 160, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    self.image_preview.setPixmap(scaled)
                    self.image_preview.setVisible(True)
                    self.image_info_label.setText(f"📊 Attached Graph/Diagram: {self._current_image}")
                    self.image_info_label.setVisible(True)
                    self.remove_image_btn.setVisible(True)
                    return
        if self._current_image:
            self.image_info_label.setText(f"⚠️ Image path (not found on disk): {self._current_image}")
            self.image_info_label.setVisible(True)
            self.image_preview.clear()
            self.image_preview.setVisible(False)
            self.remove_image_btn.setVisible(True)
        else:
            self.image_preview.clear()
            self.image_preview.setVisible(False)
            self.image_info_label.setVisible(False)
            self.remove_image_btn.setVisible(False)

    def _choose_image_file(self) -> None:
        start_dir = str(self._workspace_path) if self._workspace_path else ""
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Attach Image / Diagram to Question",
            start_dir,
            "Image Files (*.png *.jpg *.jpeg *.webp *.svg)",
        )
        if filename:
            chosen_path = Path(filename)
            if self._workspace_path:
                try:
                    rel = chosen_path.relative_to(self._workspace_path)
                    self._current_image = str(rel).replace("\\", "/")
                except ValueError:
                    self._current_image = str(chosen_path)
            else:
                self._current_image = str(chosen_path)
            self._render_image_preview()
            self.changed.emit()

    def _remove_image(self) -> None:
        self._current_image = None
        self._render_image_preview()
        self.changed.emit()

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

        if self._current_image:
            question["image"] = self._current_image
        else:
            question.pop("image", None)
            question.pop("pageImage", None)

        exp = self.explanation_edit.toPlainText().strip()
        if exp:
            question["explanation"] = exp
        else:
            question.pop("explanation", None)

    def clear(self) -> None:
        self.text_edit.clear()
        self.explanation_edit.clear()
        for i, row in enumerate(self.option_rows):
            row.setVisible(i < 4)
        for field in self.option_edits:
            field.clear()
        if self.option_radios:
            self.option_radios[0].setChecked(True)
        self._current_image = None
        self.image_preview.clear()
        self.image_preview.setVisible(False)
        self.image_info_label.setVisible(False)
        self.remove_image_btn.setVisible(False)
