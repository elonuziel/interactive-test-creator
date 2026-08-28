"""Export tab component for QuizBuilder GUI: playlist selection, mixed quizzes, browser playback & HTML export."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any
import webbrowser

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ...exporter import build_run_standalone_quiz
from ...runs import RunError, assemble_run, write_run_questions
from ...validation import ValidationError, load_questions
from ..workers import Worker

if TYPE_CHECKING:
    from ..app import MainWindow


class ExportTabWidget(QWidget):
    """Tab 3: Playlist selection, quiz player & standalone HTML exporter."""

    def __init__(self, main_window: MainWindow, parent: QWidget | None = None):
        super().__init__(parent)
        self.main_window = main_window
        self.config = main_window.config
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        tab_layout = QVBoxLayout(self)
        tab_layout.setContentsMargins(0, 0, 0, 0)

        self.export_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.export_splitter.setChildrenCollapsible(False)

        # Left panel: Choose exams to include
        selection_group = QGroupBox("Choose exams to include")
        selection_layout = QVBoxLayout(selection_group)
        self.play_list = QListWidget()
        self.play_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        play_sel_row = QHBoxLayout()
        self.select_all_button = QPushButton("Select all")
        self.select_all_button.setToolTip("Check all exams to include in the quiz")
        self.clear_all_button = QPushButton("Deselect all")
        self.clear_all_button.setToolTip("Uncheck all exams")
        play_sel_row.addWidget(self.select_all_button)
        play_sel_row.addWidget(self.clear_all_button)

        self.mix_checkbox = QCheckBox("Mix and shuffle questions (mixed mode)")
        self.mix_checkbox.setToolTip("Combine the checked exams into one shuffled quiz.")
        selection_layout.addWidget(self.play_list, 1)
        selection_layout.addLayout(play_sel_row)
        selection_layout.addWidget(self.mix_checkbox)
        self.export_splitter.addWidget(selection_group)

        # Right panel: Play or export your quiz
        action_group = QGroupBox("Play or export your quiz")
        action_layout = QVBoxLayout(action_group)
        self.summary = QLabel("No exams selected. Check one or more exams to continue.")
        self.summary.setWordWrap(True)
        self.play_button = QPushButton("Play quiz in browser")
        self.play_button.setObjectName("primary")
        self.export_button = QPushButton("Export quiz as HTML...")
        self.open_runs_button = QPushButton("Open saved quizzes folder")
        action_layout.addWidget(self.summary)
        action_layout.addWidget(self.play_button)
        action_layout.addWidget(self.export_button)
        action_layout.addWidget(self.open_runs_button)
        action_layout.addStretch()
        self.export_splitter.addWidget(action_group)

        self.export_splitter.setStretchFactor(0, 4)
        self.export_splitter.setStretchFactor(1, 6)
        tab_layout.addWidget(self.export_splitter)

    def _connect_signals(self) -> None:
        self.play_list.customContextMenuRequested.connect(self._show_play_list_context_menu)
        self.select_all_button.clicked.connect(self.select_all_play_exams)
        self.clear_all_button.clicked.connect(self.clear_all_play_exams)
        self.play_list.itemChanged.connect(lambda: self.update_summary())
        self.mix_checkbox.toggled.connect(lambda: self.update_summary())
        self.play_button.clicked.connect(self.prepare_and_play_quiz)
        self.export_button.clicked.connect(self.export_quiz)
        self.open_runs_button.clicked.connect(self.open_runs_folder)

    def _show_play_list_context_menu(self, pos: QPoint) -> None:
        menu = QMenu(self)
        sel_all = menu.addAction("Select all")
        sel_all.triggered.connect(self.select_all_play_exams)
        desel_all = menu.addAction("Deselect all")
        desel_all.triggered.connect(self.clear_all_play_exams)
        invert = menu.addAction("Invert selection")
        invert.triggered.connect(self.invert_play_exams_selection)
        menu.exec(self.play_list.mapToGlobal(pos))

    def select_all_play_exams(self) -> None:
        """Check all exams in the play/export exam list."""
        for index in range(self.play_list.count()):
            self.play_list.item(index).setCheckState(Qt.CheckState.Checked)
        self.update_summary()

    def clear_all_play_exams(self) -> None:
        """Uncheck all exams in the play/export exam list."""
        for index in range(self.play_list.count()):
            self.play_list.item(index).setCheckState(Qt.CheckState.Unchecked)
        self.update_summary()

    def invert_play_exams_selection(self) -> None:
        """Invert checked state for all exams in the play/export exam list."""
        for index in range(self.play_list.count()):
            item = self.play_list.item(index)
            new_state = (
                Qt.CheckState.Unchecked
                if item.checkState() == Qt.CheckState.Checked
                else Qt.CheckState.Checked
            )
            item.setCheckState(new_state)
        self.update_summary()

    def select_all_exams(self) -> None:
        self.select_all_play_exams()

    def clear_all_exams(self) -> None:
        self.clear_all_play_exams()

    def checked_play_workspaces(self) -> list:
        selected = [
            self.play_list.item(index).data(Qt.ItemDataRole.UserRole)
            for index in range(self.play_list.count())
            if self.play_list.item(index).checkState() == Qt.CheckState.Checked
        ]
        return selected or ([self.main_window.state["workspace"]] if self.main_window.state["workspace"] else [])

    def update_summary(self) -> None:
        selected = self.checked_play_workspaces()
        total = 0
        for workspace in selected:
            try:
                total += len(load_questions(workspace.questions_path))
            except (OSError, ValidationError):
                pass
        self.summary.setText(f"{len(selected)} exam(s), {total} question(s) ready\n{'Mixed mode' if self.mix_checkbox.isChecked() else 'Standard mode'}")
        self.main_window._update_tab_labels()

    def prepare_and_play_quiz(self) -> None:
        self._build_quiz(None)

    def export_quiz(self) -> None:
        selected = self.checked_play_workspaces()
        if not selected:
            QMessageBox.warning(self, "No exams selected", "Select at least one exam.")
            return
        default = f"{selected[0].name}.html"
        filename, _ = QFileDialog.getSaveFileName(self, "Export quiz as HTML", default, "HTML files (*.html)")
        if filename:
            self._build_quiz(Path(filename))

    def _build_quiz(self, custom_path: Path | None) -> None:
        selected = self.checked_play_workspaces()
        if not selected:
            QMessageBox.warning(self, "No exams selected", "Select at least one exam to play or export.")
            return

        if not self.main_window.state["root"]:
            QMessageBox.warning(self, "No exam folder", "Exam folder root is missing.")
            return

        self.play_button.setEnabled(False)
        self.export_button.setEnabled(False)

        def build():
            mix_mode = self.mix_checkbox.isChecked()
            output = self.main_window.state["root"] / "runs" / ("mixed_quiz.html" if mix_mode else f"{selected[0].name}.html")
            run = assemble_run(self.main_window.state["root"], selected, mix=mix_mode)
            write_run_questions(run)
            html = custom_path or output.with_suffix(".html")
            build_run_standalone_quiz(run, html)
            opened = bool(not custom_path and webbrowser.open(html.as_uri()))
            return run, html, opened

        worker = Worker(build)

        def done(result):
            run, html, opened = result
            self.play_button.setEnabled(True)
            self.export_button.setEnabled(True)

            box = QMessageBox(self)
            box.setWindowTitle("Quiz Ready")
            box.setIcon(QMessageBox.Icon.Information)
            box.setText(f"Successfully generated quiz with {len(run.questions)} question(s)!\n\nSaved to:\n{html}")
            open_btn = box.addButton("🌐 Open in Browser", QMessageBox.ButtonRole.ActionRole)
            folder_btn = box.addButton("📁 Open Folder", QMessageBox.ButtonRole.ActionRole)
            ok_btn = box.addButton(QMessageBox.StandardButton.Ok)
            box.exec()

            if box.clickedButton() == open_btn:
                webbrowser.open(html.as_uri())
            elif box.clickedButton() == folder_btn:
                webbrowser.open(html.parent.as_uri())

        def failed(error):
            self.play_button.setEnabled(True)
            self.export_button.setEnabled(True)
            QMessageBox.critical(self, "Could not build quiz", f"{error}\n\nMake sure the selected exams contain valid questions.md files.")

        worker.signals.finished.connect(done)
        worker.signals.failed.connect(failed)
        self.main_window.start_worker(worker)

    def open_image_cropper(self) -> None:
        # Look for local web player or standalone html to crop from
        web_index = self.config.scripts_root.parent / "web" / "index.html"
        if not web_index.is_file():
            web_index = Path(__file__).resolve().parents[3] / "web" / "index.html"
        if web_index.is_file():
            webbrowser.open(web_index.as_uri())
        else:
            QMessageBox.information(
                self,
                "Image Cropper",
                "To crop an image from a PDF page, open your exported HTML quiz or web player in the browser and use the 'Crop Image' tool below any diagram.",
            )

    def open_runs_folder(self) -> None:
        if not self.main_window.state["root"]:
            QMessageBox.warning(self, "No exam folder", "Choose an exam folder first.")
            return
        runs = self.main_window.state["root"] / "runs"
        runs.mkdir(parents=True, exist_ok=True)
        webbrowser.open(runs.as_uri())

