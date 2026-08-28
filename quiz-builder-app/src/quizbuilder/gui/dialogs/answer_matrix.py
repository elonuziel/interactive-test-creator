from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class AnswerMatrixDialog(QDialog):
    """Rapid visual grid for inspecting and changing correct answers for all questions in an exam."""

    def __init__(
        self,
        parent: QWidget | None,
        questions: list[dict[str, Any]],
        exam_name: str = "Exam",
        on_save: Callable[[], bool] | None = None,
        on_dirty: Callable[[], None] | None = None,
    ):
        super().__init__(parent)
        self.questions = questions
        self.exam_name = exam_name
        self.on_save = on_save
        self.on_dirty = on_dirty
        self.dirty = False

        self.setWindowTitle(f"Quick Answer Matrix — {self.exam_name}")
        self.resize(750, 520)

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel("<b>Rapid Answer Key Review:</b> Click any choice to update that question's correct answer instantly.")
        )

        HEBREW_LETTERS = ["א", "ב", "ג", "ד", "ה", "ו", "ז", "ח", "ט", "י"]
        LATIN_LETTERS = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]

        max_options = max(4, min(10, max((len(q.get("options", [])) for q in questions), default=4)))
        headers = ["#", "Question Preview"] + [
            f"{HEBREW_LETTERS[i]} ({LATIN_LETTERS[i]})" for i in range(max_options)
        ]

        table = QTableWidget(len(questions), len(headers), self)
        table.setHorizontalHeaderLabels(headers)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for col in range(2, len(headers)):
            table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)

        for row_idx, q in enumerate(questions):
            num_item = QTableWidgetItem(str(row_idx + 1))
            num_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(row_idx, 0, num_item)

            q_text = (q.get("question", "") or "").strip()
            preview_item = QTableWidgetItem(q_text[:75] + ("..." if len(q_text) > 75 else ""))
            table.setItem(row_idx, 1, preview_item)

            curr_ans = q.get("correctIndex", 0)
            q_options_count = len(q.get("options", [])) or 4

            def make_toggle(r: int, o: int):
                def _handler(checked: bool):
                    if checked:
                        self.questions[r]["correctIndex"] = o
                        self.dirty = True
                        if self.on_dirty:
                            self.on_dirty()
                return _handler

            for opt_idx in range(max_options):
                if opt_idx < q_options_count:
                    radio = QRadioButton(HEBREW_LETTERS[opt_idx])
                    if opt_idx == curr_ans:
                        radio.setChecked(True)
                    radio.toggled.connect(make_toggle(row_idx, opt_idx))
                    table.setCellWidget(row_idx, 2 + opt_idx, radio)
                else:
                    placeholder = QTableWidgetItem("—")
                    placeholder.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
                    table.setItem(row_idx, 2 + opt_idx, placeholder)

        layout.addWidget(table)

        btn_box = QHBoxLayout()
        if self.on_save:
            btn_save = QPushButton("💾 Save questions.md")
            btn_save.clicked.connect(self._handle_save)
            btn_box.addWidget(btn_save)

        btn_done = QPushButton("Done")
        btn_done.clicked.connect(self.accept)
        btn_box.addStretch()
        btn_box.addWidget(btn_done)
        layout.addLayout(btn_box)

    def _handle_save(self) -> None:
        if self.on_save:
            self.on_save()
        self.accept()

