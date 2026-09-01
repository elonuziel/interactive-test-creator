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
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ...exporter import (
    build_all_standalone_quizzes,
    build_central_hub,
    build_run_standalone_quiz,
)
from ...runs import QuizRun, RunError, assemble_run, write_run_questions
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

        # ── LEFT panel: Choose exams to include ─────────────────────────
        selection_group = QGroupBox("Choose exams to include")
        selection_layout = QVBoxLayout(selection_group)
        self.play_list = QListWidget()
        self.play_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        play_sel_row = QHBoxLayout()
        self.select_all_button = QPushButton("Select all")
        self.select_all_button.setObjectName("secondary")
        self.select_all_button.setToolTip("Check all exams to include in the quiz")
        self.clear_all_button = QPushButton("Deselect all")
        self.clear_all_button.setObjectName("secondary")
        self.clear_all_button.setToolTip("Uncheck all exams")
        play_sel_row.addWidget(self.select_all_button)
        play_sel_row.addWidget(self.clear_all_button)

        self.mix_checkbox = QCheckBox("🔀 Mix and shuffle questions")
        self.mix_checkbox.setToolTip("Combine the checked exams into one shuffled quiz.")

        self.pool_size_widget = QWidget()
        pool_size_row = QHBoxLayout(self.pool_size_widget)
        pool_size_row.setContentsMargins(0, 0, 0, 0)
        pool_size_row.addWidget(QLabel("Question pool size:"))
        self.pool_size_spin = QSpinBox()
        self.pool_size_spin.setRange(1, 1000)
        self.pool_size_spin.setValue(30)
        self.pool_size_spin.setToolTip("Number of questions drawn in mixed mode (default 30)")
        pool_size_row.addWidget(self.pool_size_spin)
        self.all_pool_check = QCheckBox("All")
        self.all_pool_check.setToolTip("Include all available questions without limit")
        pool_size_row.addWidget(self.all_pool_check)
        pool_size_row.addStretch()
        self.pool_size_widget.setVisible(False)  # hidden until mix mode is on

        selection_layout.addWidget(self.play_list, 1)
        selection_layout.addLayout(play_sel_row)
        selection_layout.addWidget(self.mix_checkbox)
        selection_layout.addWidget(self.pool_size_widget)
        self.export_splitter.addWidget(selection_group)

        # ── RIGHT panel ──────────────────────────────────────────────────
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setSpacing(10)

        # Summary
        self.summary = QLabel("No exams selected. Check one or more exams to continue.")
        self.summary.setObjectName("sectionHint")
        self.summary.setWordWrap(True)
        right_layout.addWidget(self.summary)

        # — Group 1: Build HTML files —
        build_group = QGroupBox("🏗 Build HTML files")
        build_layout = QVBoxLayout(build_group)
        build_hint = QLabel("Compile standalone, 100% self-contained HTML quiz files that can be shared or opened offline.")
        build_hint.setWordWrap(True)
        build_layout.addWidget(build_hint)

        self.build_hub_button = QPushButton("🌐 Build Shareable Master Quiz (quiz_hub.html)")
        self.build_hub_button.setObjectName("primary")
        self.build_hub_button.setToolTip(
            "Compile master quiz hub (quiz_hub.html) embedding all exams, exam picker, mixed practice, and progress tracking."
        )

        self.export_hub_as_button = QPushButton("💾 Export Master Quiz As…")
        self.export_hub_as_button.setObjectName("secondary")
        self.export_hub_as_button.setToolTip(
            "Choose a custom filename or destination folder (e.g. shareable_quiz.html) to export the master all-in-one quiz."
        )

        self.build_all_button = QPushButton("⚡ Build All Standalone HTMLs")
        self.build_all_button.setObjectName("secondary")
        self.build_all_button.setToolTip(
            "Compile standalone quiz.html inside each ready exam folder."
        )

        # Alias for backward compatibility
        self.build_shareable_button = self.build_hub_button

        build_layout.addWidget(self.build_hub_button)
        build_layout.addWidget(self.export_hub_as_button)
        build_layout.addWidget(self.build_all_button)
        right_layout.addWidget(build_group)
        # — Group 2: Play or export this session —
        play_group = QGroupBox("▶ Play or export")
        play_layout = QVBoxLayout(play_group)
        play_hint = QLabel("Generate a temporary quiz for the selected exams and open it in the browser, or save it as an HTML file.")
        play_hint.setObjectName("sectionHint")
        play_hint.setWordWrap(True)
        play_layout.addWidget(play_hint)

        self.play_button = QPushButton("▶  Play selected quiz in browser")
        self.play_button.setObjectName("primary")
        self.export_button = QPushButton("💾 Export as HTML…")
        self.open_runs_button = QPushButton("📁 Open saved quizzes folder")
        self.open_runs_button.setObjectName("secondary")
        play_layout.addWidget(self.play_button)
        play_layout.addWidget(self.export_button)
        play_layout.addWidget(self.open_runs_button)
        right_layout.addWidget(play_group)

        right_layout.addStretch()
        self.export_splitter.addWidget(right_widget)

        self.export_splitter.setStretchFactor(0, 4)
        self.export_splitter.setStretchFactor(1, 6)
        tab_layout.addWidget(self.export_splitter)

    def _connect_signals(self) -> None:
        self.play_list.customContextMenuRequested.connect(self._show_play_list_context_menu)
        self.select_all_button.clicked.connect(self.select_all_play_exams)
        self.clear_all_button.clicked.connect(self.clear_all_play_exams)
        self.play_list.itemChanged.connect(lambda: self.update_summary())
        self.mix_checkbox.toggled.connect(self._on_mix_toggled)
        self.all_pool_check.toggled.connect(lambda checked: self.pool_size_spin.setEnabled(not checked))
        self.build_hub_button.clicked.connect(self.build_central_hub_action)
        self.export_hub_as_button.clicked.connect(lambda: self.build_shareable_quiz_action(target_filename="shareable_quiz.html", ask_path=True))
        self.play_button.clicked.connect(self.prepare_and_play_quiz)
        self.open_runs_button.clicked.connect(self.open_runs_folder)

    def _on_mix_toggled(self, checked: bool) -> None:
        """Show pool size controls only when mix mode is active."""
        self.pool_size_widget.setVisible(checked)
        self.update_summary()

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

    def build_central_hub_action(self) -> None:
        self.build_shareable_quiz_action(target_filename="quiz_hub.html", ask_path=False)

    def build_shareable_quiz_action(
        self,
        target_filename: str = "quiz_hub.html",
        ask_path: bool = False,
    ) -> None:
        root = self.main_window.state.get("root")
        if not root:
            QMessageBox.warning(self, "No exam folder", "Choose an exam folder first.")
            return

        selected = self.checked_play_workspaces()
        if not selected:
            # Fallback to all ready workspaces under root (using build_plan for complete multi-PDF coverage)
            try:
                from ...super_batch import build_plan
                from ...models import Workspace
                plan = build_plan(root)
                selected = [
                    Workspace(
                        name=item.overview.name,
                        path=item.overview.workspace,
                        source_pdf=item.overview.pdf,
                    )
                    for item in plan.items
                    if (item.overview.workspace / "questions.md").is_file()
                    or (item.overview.workspace / "questions.json").is_file()
                ]
            except Exception:
                selected = []

            if not selected:
                from ...workspace import discover_batch
                candidates = discover_batch(root)
                selected = [c.workspace for c in candidates if c.workspace.questions_path.is_file()]

        if not selected:
            QMessageBox.warning(
                self,
                "No questions found",
                "No workspaces containing questions.md were found to build the master quiz.",
            )
            return

        out_path = root / target_filename
        if ask_path:
            filename, _ = QFileDialog.getSaveFileName(
                self,
                "Export Shareable Master Quiz",
                str(out_path),
                "HTML files (*.html)",
            )
            if not filename:
                return
            out_path = Path(filename)

        buttons_to_toggle = [
            getattr(self, "build_hub_button", None),
            getattr(self, "export_hub_as_button", None),
        ]
        for btn in buttons_to_toggle:
            if btn:
                btn.setEnabled(False)

        self.main_window._set_status(
            f"Building Shareable Master Quiz ({out_path.name}) from {len(selected)} exams...",
            "busy",
        )

        title = self.main_window.state.get("hub_title") or f"מרכז מבחנים אינטראקטיבי - {root.name}"

        def build():
            hub_path = build_central_hub(root, selected, output=out_path, title=title)
            return hub_path

        worker = Worker(build)

        def done(hub_path: Path):
            for btn in buttons_to_toggle:
                if btn:
                    btn.setEnabled(True)
            self.main_window._set_status(f"{hub_path.name} built successfully", "ready")

            box = QMessageBox(self)
            box.setWindowTitle("Shareable Quiz Ready")
            box.setIcon(QMessageBox.Icon.Information)
            box.setText(
                f"Shareable Master Quiz generated successfully!\n"
                f"Embedded {len(selected)} exam(s) into a single, 100% self-contained file.\n\n"
                f"Location:\n{hub_path}"
            )
            open_btn = box.addButton("🌐 Open Quiz in Browser", QMessageBox.ButtonRole.ActionRole)
            folder_btn = box.addButton("📁 Open Folder", QMessageBox.ButtonRole.ActionRole)
            box.addButton(QMessageBox.StandardButton.Ok)
            box.exec()

            if box.clickedButton() == open_btn:
                webbrowser.open(hub_path.as_uri())
            elif box.clickedButton() == folder_btn:
                webbrowser.open(hub_path.parent.as_uri())

        def failed(error):
            for btn in buttons_to_toggle:
                if btn:
                    btn.setEnabled(True)
            self.main_window._set_status("Could not build Shareable Quiz", "error")
            QMessageBox.critical(
                self,
                "Could not build Shareable Quiz",
                f"{error}\n\nMake sure at least one exam folder contains a valid questions.md file.",
            )

        worker.signals.finished.connect(done)
        worker.signals.failed.connect(failed)
        self.main_window.start_worker(worker)

    def build_all_standalone_action(self) -> None:
        root = self.main_window.state.get("root")
        if not root:
            QMessageBox.warning(self, "No exam folder", "Choose an exam folder first.")
            return

        selected = self.checked_play_workspaces()
        if not selected:
            from ...workspace import discover_batch
            candidates = discover_batch(root)
            selected = [c.workspace for c in candidates if c.workspace.questions_path.is_file()]

        if not selected:
            QMessageBox.warning(self, "No questions found", "No workspaces containing questions.md were found.")
            return
        self.main_window._set_status(f"Compiling standalone quiz.html for {len(selected)} exams...", "busy")

        def build():
            scripts_dir = self.config.scripts_root
            generated = build_all_standalone_quizzes(selected, scripts_dir=scripts_dir)
            return generated

        worker = Worker(build)

        def done(generated: list[Path]):
            self.build_all_button.setEnabled(True)
            self.main_window._set_status(f"Generated {len(generated)} standalone quiz.html files", "ready")
            QMessageBox.information(
                self,
                "Batch Standalone HTMLs Ready",
                f"Successfully compiled {len(generated)} standalone quiz.html files inside each exam workspace!",
            )

        def failed(error):
            self.build_all_button.setEnabled(True)
            self.main_window._set_status("Batch standalone build failed", "error")
            QMessageBox.critical(self, "Batch Build Error", str(error))

        worker.signals.finished.connect(done)
        worker.signals.failed.connect(failed)
        self.main_window.start_worker(worker)

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
            limit = None if self.all_pool_check.isChecked() else self.pool_size_spin.value()
            run = assemble_run(selected, mix=mix_mode, limit=limit, shuffle=True)
            write_run_questions(run, output.with_suffix(".json"))
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
            box.addButton(QMessageBox.StandardButton.Ok)
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


