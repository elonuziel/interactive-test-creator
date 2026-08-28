from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)


class WelcomeDialog(QDialog):
    """First-time onboarding dialog showing the 3 core steps of the application."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Welcome to Interactive Quiz Builder")
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(20, 20, 20, 20)

        title = QLabel("🎓 Interactive Quiz Builder")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        subtitle = QLabel("Create interactive quizzes from exam PDFs in three simple steps.")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("font-size: 13px; color: #64748b;")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        steps = [
            (
                "📁",
                "Step 1 — Choose Folder",
                "Click <b>Choose exam folder…</b> to select the parent folder that contains your exam sub-folders. Each sub-folder should have a PDF and optionally an answer key.",
            ),
            (
                "⚙️",
                "Step 2 — Extract &amp; Review",
                "Extract questions automatically from digital PDFs, or use the <b>AI prompt</b> for scanned exams. Review and fix questions on the <b>Review questions</b> tab.",
            ),
            (
                "▶️",
                "Step 3 — Play or Export",
                "Go to <b>Play or export</b>, tick the exams you want, then click <b>Play quiz in browser</b> or export a standalone HTML file to share with students.",
            ),
        ]
        for icon, heading, body in steps:
            step_row = QHBoxLayout()
            step_row.setSpacing(12)
            icon_lbl = QLabel(icon)
            icon_lbl.setStyleSheet("font-size: 28px;")
            icon_lbl.setFixedWidth(44)
            icon_lbl.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

            text_col = QVBoxLayout()
            text_col.setSpacing(2)
            h_lbl = QLabel(heading)
            h_lbl.setStyleSheet("font-weight: 700; font-size: 13px;")
            b_lbl = QLabel(body)
            b_lbl.setWordWrap(True)
            b_lbl.setStyleSheet("color: #64748b;")
            text_col.addWidget(h_lbl)
            text_col.addWidget(b_lbl)

            step_row.addWidget(icon_lbl)
            step_row.addLayout(text_col, 1)
            layout.addLayout(step_row)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Get Started →")
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

