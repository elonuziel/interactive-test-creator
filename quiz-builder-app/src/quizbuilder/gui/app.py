from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import webbrowser

from PySide6.QtCore import QSettings, QThreadPool, Qt
from PySide6.QtGui import QGuiApplication, QImage, QKeySequence, QPixmap, QShortcut, QAction
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..batch import discover_batch
from ..commands import generate_workspace_prompt, process_workspace, process_workspaces
from ..config import Config
from ..documents import classify_pdf, DocumentError
from ..exporter import build_run_standalone_quiz
from ..markdown import write_questions
from ..preview import render_pdf_page
from ..providers import WEB_PROVIDERS, detect_providers, open_web_provider
from ..prompts import send_to_provider
from ..runs import RunError, assemble_run, write_run_questions
from ..validation import ValidationError, load_questions
from ..workspace import discover_sources
from .question_editor import QuestionEditorWidget
from .styles import DARK_STYLESHEET, LITE_STYLESHEET
from .workers import Worker

LOGGER = logging.getLogger(__name__)


class MainWindow(QWidget):
    def __init__(self, config: Config | None = None, parent=None):
        super().__init__(parent)
        self.config = config or Config.load()
        self.settings = QSettings("InteractiveQuizBuilder", "QuizBuilder")
        self.thread_pool = QThreadPool.globalInstance()
        self._active_workers: set[Worker] = set()
        self.state = {
            "root": None,
            "workspace": None,
            "questions": [],
            "index": -1,
            "dirty": False,
            "loading": False,
        }
        self.setWindowTitle("Interactive Quiz Builder")
        self.resize(1120, 780)
        self.dark_mode = self.settings.value("dark_mode", False, type=bool)
        self.setStyleSheet(DARK_STYLESHEET if self.dark_mode else LITE_STYLESHEET)
        self._build_ui()
        self._show_welcome_if_needed()
        self._connect_signals()
        self._add_theme_action()
        self._restore_session()

    def start_worker(self, worker: Worker) -> None:
        self._active_workers.add(worker)
        worker.signals.finished.connect(lambda _: self._active_workers.discard(worker))
        worker.signals.failed.connect(lambda _: self._active_workers.discard(worker))
        self.thread_pool.start(worker)

    def _add_theme_action(self) -> None:
        self.theme_button = QPushButton("Switch to light theme" if self.dark_mode else "Switch to dark theme")
        self.theme_button.clicked.connect(self.toggle_theme)
        self.layout().itemAt(0).widget().layout().addWidget(self.theme_button)

    def toggle_theme(self) -> None:
        self.dark_mode = not self.dark_mode
        self.settings.setValue("dark_mode", self.dark_mode)
        self.setStyleSheet(DARK_STYLESHEET if self.dark_mode else LITE_STYLESHEET)
        self.theme_button.setText("Switch to light theme" if self.dark_mode else "Switch to dark theme")

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(14, 12, 14, 12)
        root_layout.setSpacing(10)

        top_bar = QFrame()
        top_bar.setObjectName("topBar")
        top_layout = QHBoxLayout(top_bar)
        self.root_label = QLabel("Exam folder: (not selected)")
        self.root_label.setToolTip("Choose the parent folder containing your exam folders.")
        self.choose_root_btn = QPushButton("Choose exam folder...")
        self.choose_root_btn.setToolTip("Select the parent folder that contains your exam projects.")
        self.refresh_root_btn = QPushButton("Reload exams")
        self.refresh_root_btn.setToolTip("Scan the selected folder again for exam projects.")
        top_layout.addWidget(self.root_label, 1)
        top_layout.addWidget(self.choose_root_btn)
        top_layout.addWidget(self.refresh_root_btn)
        root_layout.addWidget(top_bar)

        self.tabs = QTabWidget()
        root_layout.addWidget(self.tabs, 1)
        self._build_extract_tab()
        self._build_review_tab()
        self._build_export_tab()

        status_bar = QFrame()
        status_bar.setObjectName("statusBar")
        status_layout = QHBoxLayout(status_bar)
        self.status_label = QLabel("Welcome! Choose an exam folder to begin. Each exam folder should contain a PDF and questions.md.")
        self.status_label.setWordWrap(True)
        status_layout.addWidget(self.status_label, 1)
        root_layout.addWidget(status_bar)

    def _build_extract_tab(self) -> None:
        tab = QWidget()
        layout = QHBoxLayout(tab)
        self.exam_group = QGroupBox("1. Choose an exam")
        left = QVBoxLayout(self.exam_group)
        self.exam_search = QLineEdit()
        self.exam_search.setPlaceholderText("Search exams...")
        self.exam_list = QListWidget()
        self.batch_button = QPushButton("Process selected exams")
        left.addWidget(self.exam_search)
        left.addWidget(self.exam_list, 1)
        left.addWidget(self.batch_button)
        layout.addWidget(self.exam_group, 4)

        self.extract_group = QGroupBox("2. Prepare questions (saved as questions.md)")
        right = QVBoxLayout(self.extract_group)
        self.current_exam_title = QLabel("Choose an exam from the list")
        self.pdf_combo = QComboBox()
        self.pdf_combo.addItem("No exam file selected", None)
        pdf_row = QHBoxLayout()
        pdf_row.addWidget(QLabel("Exam file:"))
        pdf_row.addWidget(self.pdf_combo, 1)
        self.detection_title = QLabel("PDF type: waiting for an exam")
        self.detection_description = QLabel("Choose an exam to check whether its text can be extracted automatically.")
        self.detection_description.setWordWrap(True)
        self.extract_button = QPushButton("Extract questions from PDF")
        self.ai_hint = QLabel("Digital PDFs can be extracted automatically. Scanned PDFs need an AI prompt. Results are saved as questions.md.")
        self.ai_hint.setWordWrap(True)
        self.ai_provider_combo = QComboBox()
        for provider in WEB_PROVIDERS:
            self.ai_provider_combo.addItem(f"Web: {provider.label}", (provider, None))
        for provider, command in detect_providers(self.config.provider.freebuff_commands):
            self.ai_provider_combo.addItem(f"Local: {provider.label} ({command})", (provider, command))
        self.launch_ai_button = QPushButton("Create AI prompt")
        self.launch_ai_button.setToolTip("Create a prompt for extracting questions into questions.md.")
        self.answer_combo = QComboBox()
        self.answer_combo.addItem("No answer key", None)
        self.form_edit = QLineEdit(self.config.default_form)
        self.form_edit.setMaximumWidth(70)
        self.preview = QLabel("No exam preview available")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(280, 240)
        self.preview_button = QPushButton("Preview first page")
        self.next_review_button = QPushButton("Next: review questions")
        right.addWidget(self.current_exam_title)
        right.addLayout(pdf_row)
        right.addWidget(self.detection_title)
        right.addWidget(self.detection_description)
        right.addWidget(self.extract_button)
        right.addWidget(self.ai_hint)
        ai_row = QHBoxLayout()
        ai_row.addWidget(self.ai_provider_combo, 2)
        ai_row.addWidget(self.launch_ai_button, 3)
        right.addLayout(ai_row)
        answer_row = QHBoxLayout()
        answer_row.addWidget(QLabel("Answer key (optional):"))
        answer_row.addWidget(self.answer_combo, 1)
        answer_row.addWidget(QLabel("Form number:"))
        answer_row.addWidget(self.form_edit)
        right.addLayout(answer_row)
        right.addWidget(self.preview, 1)
        actions = QHBoxLayout()
        actions.addWidget(self.preview_button)
        actions.addStretch()
        actions.addWidget(self.next_review_button)
        right.addLayout(actions)
        layout.addWidget(self.extract_group, 6)
        self.tabs.addTab(tab, "Choose & extract")

    def _build_review_tab(self) -> None:
        tab = QWidget()
        layout = QHBoxLayout(tab)
        list_group = QGroupBox("Questions in this exam")
        list_layout = QVBoxLayout(list_group)
        self.question_status = QLabel("No exam selected")
        self.question_list = QListWidget()
        self.add_question_button = QPushButton("Add question")
        self.delete_question_button = QPushButton("Delete")
        list_layout.addWidget(self.question_status)
        list_layout.addWidget(self.question_list, 1)
        list_layout.addWidget(self.add_question_button)
        list_layout.addWidget(self.delete_question_button)
        layout.addWidget(list_group, 4)
        edit_group = QGroupBox("Review and edit questions")
        edit_layout = QVBoxLayout(edit_group)
        self.question_editor = QuestionEditorWidget()
        self.save_button = QPushButton("Save questions.md")
        self.help_button = QPushButton("Markdown format help")
        self.help_button.setToolTip("Show the questions.md format used by this project.")
        self.save_button.setToolTip("Save the current questions to questions.md. Shortcut: Ctrl+S")
        self.next_export_button = QPushButton("Next: play or export")
        edit_layout.addWidget(self.question_editor, 1)
        edit_actions = QHBoxLayout()
        edit_actions.addWidget(self.save_button)
        edit_actions.addWidget(self.help_button)
        edit_actions.addStretch()
        edit_actions.addWidget(self.next_export_button)
        edit_layout.addLayout(edit_actions)
        layout.addWidget(edit_group, 6)
        self.tabs.addTab(tab, "Review questions")

    def _build_export_tab(self) -> None:
        tab = QWidget()
        layout = QHBoxLayout(tab)
        selection_group = QGroupBox("Choose exams to include")
        selection_layout = QVBoxLayout(selection_group)
        self.play_list = QListWidget()
        self.select_all_button = QPushButton("Select all")
        self.clear_all_button = QPushButton("Clear all")
        self.mix_checkbox = QCheckBox("Mix and shuffle questions (mixed mode)")
        self.mix_checkbox.setToolTip("Combine the checked exams into one shuffled quiz.")
        selection_layout.addWidget(self.play_list, 1)
        selection_layout.addWidget(self.select_all_button)
        selection_layout.addWidget(self.clear_all_button)
        selection_layout.addWidget(self.mix_checkbox)
        layout.addWidget(selection_group, 5)
        action_group = QGroupBox("Play or export your quiz")
        action_layout = QVBoxLayout(action_group)
        self.summary = QLabel("No exams selected. Check one or more exams to continue.")
        self.summary.setWordWrap(True)
        self.play_button = QPushButton("Play quiz in browser")
        self.export_button = QPushButton("Export quiz as HTML...")
        self.open_runs_button = QPushButton("Open saved quizzes folder")
        action_layout.addWidget(self.summary)
        action_layout.addWidget(self.play_button)
        action_layout.addWidget(self.export_button)
        action_layout.addWidget(self.open_runs_button)
        action_layout.addStretch()
        layout.addWidget(action_group, 5)
        self.tabs.addTab(tab, "Play or export")

    def _connect_signals(self) -> None:
        self.choose_root_btn.clicked.connect(self.choose_folder)
        self.refresh_root_btn.clicked.connect(self.reload_folder)
        self.exam_search.textChanged.connect(self.filter_exams)
        self.exam_list.currentItemChanged.connect(self.select_exam)
        self.pdf_combo.currentIndexChanged.connect(lambda: self.preview_first_page() if not self.state["loading"] else None)
        self.extract_button.clicked.connect(self.process_selected_exam)
        self.batch_button.clicked.connect(self.process_batch_checked)
        self.launch_ai_button.clicked.connect(self.launch_ai)
        self.preview_button.clicked.connect(self.preview_first_page)
        self.next_review_button.clicked.connect(lambda: self.tabs.setCurrentIndex(1))
        self.question_list.currentRowChanged.connect(self.show_question)
        self.help_button.clicked.connect(self.show_markdown_help)
        self.question_editor.changed.connect(self.mark_dirty)
        self.add_question_button.clicked.connect(self.add_question)
        self.delete_question_button.clicked.connect(self.delete_question)
        self.save_button.clicked.connect(self.save_test)
        self.next_export_button.clicked.connect(lambda: (self.save_active_question(), self.tabs.setCurrentIndex(2)))
        self.select_all_button.clicked.connect(self.select_all_exams)
        self.clear_all_button.clicked.connect(self.clear_all_exams)
        self.play_list.itemChanged.connect(lambda: self.update_summary())
        self.mix_checkbox.toggled.connect(lambda: self.update_summary())
        self.play_button.clicked.connect(self.prepare_and_play_quiz)
        self.export_button.clicked.connect(self.export_quiz)
        self.open_runs_button.clicked.connect(self.open_runs_folder)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(self.save_test)
        QShortcut(QKeySequence("Ctrl+F"), self).activated.connect(lambda: (self.exam_search.setFocus(), self.exam_search.selectAll()))

    def show_markdown_help(self) -> None:
        QMessageBox.information(self, "questions.md format", "Each question uses this format:\n\n## Question 1\n\nQuestion text\n\n- First choice\n- Second choice\n- Third choice\n- Fourth choice\n\nAnswer: A\n\nUse pageImage: path/to/page.png on its own line when a question references a diagram or table.")

    def _show_welcome_if_needed(self) -> None:
        if self.settings.value("welcome_shown", False, type=bool):
            return
        if os.environ.get("QT_QPA_PLATFORM") == "offscreen" or QGuiApplication.platformName() == "offscreen":
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Welcome to Quiz Builder")
        layout = QVBoxLayout(dialog)
        title = QLabel("Create an interactive quiz in a few steps")
        title.setStyleSheet("font-size: 18px; font-weight: 700;")
        layout.addWidget(title)
        instructions = QLabel(
            "1. Choose the folder containing your exam folders.\n"
            "2. Select an exam and extract questions or create an AI prompt.\n"
            "3. Review questions and save them as questions.md.\n"
            "4. Select an exam to play or export it as HTML.\n\n"
            "Each exam folder normally contains a PDF, questions.md, and optionally an answer key."
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        example = QPlainTextEdit("## Question 1\n\nWhat is the answer?\n\n- Choice A\n- Choice B\n\nAnswer: A")
        example.setReadOnly(True)
        example.setMaximumHeight(150)
        layout.addWidget(QLabel("Markdown example:"))
        layout.addWidget(example)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)
        dialog.exec()
        self.settings.setValue("welcome_shown", True)

    def _restore_session(self) -> None:
        saved = self.settings.value("last_exam_folder", "")
        configured = self.config.workspace_root
        self.state["root"] = configured if configured.is_dir() else Path(saved) if saved else configured
        self.populate_tests()
        geometry = self.settings.value("window_geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)

    def closeEvent(self, event) -> None:
        if not self.confirm_discard_changes():
            event.ignore()
            return
        self.settings.setValue("window_geometry", self.saveGeometry())
        event.accept()

    def config_for_root(self, root: Path) -> Config:
        return Config(root, self.config.scripts_root, self.config.default_form, self.config.default_discard_pages, self.config.auto_build, self.config.provider)

    def mark_dirty(self) -> None:
        if self.state["workspace"] is not None:
            self.state["dirty"] = True
            self.setWindowTitle("Interactive Quiz Builder *")

    def save_active_question(self) -> None:
        if self.state["index"] >= 0:
            self.question_editor.collect(self.state["questions"][self.state["index"]])

    def save_test(self, show_message=True) -> bool:
        if not self.state["workspace"]:
            if show_message:
                QMessageBox.warning(self, "No exam selected", "Choose an exam first.")
            return False
        self.save_active_question()
        try:
            write_questions(self.state["workspace"].path / "questions.md", self.state["questions"])
        except OSError as exc:
            LOGGER.exception("Could not save questions.md")
            self.status_label.setText(f"Could not save questions.md: {exc}")
            if show_message:
                QMessageBox.critical(self, "Could not save", f"{exc}\n\nCheck that the exam folder is writable and try again.")
            return False
        self.state["dirty"] = False
        self.setWindowTitle("Interactive Quiz Builder")
        self.refresh_question_list()
        self.update_summary()
        self.status_label.setText("Changes saved.")
        if show_message:
            QMessageBox.information(self, "Saved", "Your question changes were saved.")
        return True

    def confirm_discard_changes(self) -> bool:
        if not self.state["dirty"]:
            return True
        answer = QMessageBox.warning(self, "Unsaved changes", "Save your question changes before continuing?", QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel)
        if answer == QMessageBox.StandardButton.Save:
            return self.save_test(show_message=False)
        return answer == QMessageBox.StandardButton.Discard

    def populate_tests(self) -> None:
        if not self.state["root"]:
            return
        try:
            candidates = discover_batch(self.state["root"])
        except (FileNotFoundError, OSError) as exc:
            self.status_label.setText(str(exc))
            return
        self.state["batch_candidates"] = candidates
        self.exam_list.clear()
        self.play_list.clear()
        for candidate in candidates:
            label = candidate.workspace.name
            if candidate.issues:
                label += f" ({'; '.join(candidate.issues)})"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, candidate.workspace)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.exam_list.addItem(item)
            play_item = QListWidgetItem(label)
            play_item.setData(Qt.ItemDataRole.UserRole, candidate.workspace)
            play_item.setFlags(play_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            play_item.setCheckState(Qt.CheckState.Checked if candidate.ready_to_run else Qt.CheckState.Unchecked)
            self.play_list.addItem(play_item)
        self.root_label.setText(f"Exam folder: {self.state['root']}")
        self.status_label.setText(f"Found {len(candidates)} exam(s).")
        if candidates:
            self.exam_list.setCurrentRow(0)
        self.update_summary()

    def reload_folder(self) -> None:
        if self.confirm_discard_changes():
            self.populate_tests()

    def choose_folder(self) -> None:
        if not self.confirm_discard_changes():
            return
        chosen = QFileDialog.getExistingDirectory(self, "Choose exam folder")
        if chosen:
            self.state["root"] = Path(chosen)
            self.settings.setValue("last_exam_folder", str(self.state["root"]))
            self.populate_tests()

    def filter_exams(self, query: str) -> None:
        query = query.strip().casefold()
        for index in range(self.exam_list.count()):
            self.exam_list.item(index).setHidden(query not in self.exam_list.item(index).text().casefold())

    def select_exam(self, current, _previous=None) -> None:
        if current is not None:
            self.load_workspace(current.data(Qt.ItemDataRole.UserRole))

    def load_workspace(self, workspace) -> None:
        if workspace != self.state["workspace"] and not self.confirm_discard_changes():
            return
        self.state["workspace"] = workspace
        self.state["questions"] = []
        self.state["index"] = -1
        self.state["loading"] = True
        self.current_exam_title.setText(f"Exam: {workspace.name}")
        self.pdf_combo.clear()
        sources = discover_sources(workspace)
        if workspace.source_pdf:
            self.pdf_combo.addItem(workspace.source_pdf.name, workspace.source_pdf)
        elif sources.pdf:
            self.pdf_combo.addItem(sources.pdf.name, sources.pdf)
        for pdf in sorted(workspace.path.glob("*.pdf"), key=lambda item: item.name.casefold()):
            if self.pdf_combo.findData(pdf) < 0:
                self.pdf_combo.addItem(pdf.name, pdf)
        if not self.pdf_combo.count():
            self.pdf_combo.addItem("No exam file selected", None)
        self.answer_combo.clear()
        self.answer_combo.addItem("No answer key", None)
        for answer in sources.answer_keys:
            self.answer_combo.addItem(answer.name, answer)
        self.state["loading"] = False
        self._load_questions(workspace)
        pdf = self.pdf_combo.currentData()
        if pdf and Path(pdf).is_file():
            self.check_pdf_classification(Path(pdf))
            self.preview_first_page(Path(pdf))
        else:
            self.detection_title.setText("No exam file found")
            self.detection_description.setText("Add a PDF to this folder, then reload the exam list.")
        self.state["dirty"] = False
        self.setWindowTitle("Interactive Quiz Builder")
        self.update_summary()

    def _load_questions(self, workspace) -> None:
        try:
            self.state["questions"] = load_questions(workspace.questions_path)
        except (ValidationError, OSError) as exc:
            self.state["questions"] = []
            self.status_label.setText(f"Could not load questions.md: {exc}. Use Add question or run extraction.")
        self.refresh_question_list()
        if self.state["questions"]:
            self.question_list.setCurrentRow(0)
        else:
            self.question_editor.clear()

    def refresh_question_list(self) -> None:
        self.question_list.clear()
        valid = 0
        for index, question in enumerate(self.state["questions"]):
            text = (question.get("question", "") or "").strip()
            options = question.get("options", [])
            ready = bool(text and len(options) >= 2)
            valid += ready
            self.question_list.addItem(f"{'OK' if ready else 'Review'} {index + 1}. {text or 'Empty question'}")
        total = len(self.state["questions"])
        self.question_status.setText(f"{valid}/{total} questions ready" if total else "No questions in this exam")

    def show_question(self, index: int) -> None:
        self.save_active_question()
        self.state["index"] = index
        self.question_editor.set_question(self.state["questions"][index] if 0 <= index < len(self.state["questions"]) else None)

    def add_question(self) -> None:
        self.save_active_question()
        self.state["questions"].append({"question": "", "options": ["", "", "", ""], "correctIndex": 0})
        self.state["dirty"] = True
        self.refresh_question_list()
        self.question_list.setCurrentRow(len(self.state["questions"]) - 1)

    def delete_question(self) -> None:
        index = self.state["index"]
        if index < 0 or QMessageBox.question(self, "Delete question", "Delete the selected question?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        self.state["questions"].pop(index)
        self.state["dirty"] = True
        self.refresh_question_list()
        self.question_list.setCurrentRow(min(index, self.question_list.count() - 1))

    def check_pdf_classification(self, pdf: Path) -> None:
        try:
            is_digital = classify_pdf(pdf)
            if is_digital:
                self.detection_title.setText("Digital PDF detected")
                self.detection_description.setText("This PDF contains selectable text. Extract the questions automatically.")
                self.extract_button.setEnabled(True)
            else:
                self.detection_title.setText("Scanned PDF detected")
                self.detection_description.setText("Create an AI prompt below to extract questions from this image-based PDF.")
                self.extract_button.setEnabled(False)
        except Exception as exc:
            self.detection_title.setText("PDF analysis unavailable")
            self.detection_description.setText(f"{exc} You can still create an AI prompt or check the PDF manually.")
            self.extract_button.setEnabled(True)

    def preview_first_page(self, pdf: Path | None = None) -> None:
        target = pdf or self.pdf_combo.currentData()
        if not target:
            return
        self.preview.setText("Rendering preview...")
        worker = Worker(lambda: render_pdf_page(Path(target)))

        def done(data):
            pixmap = QPixmap.fromImage(QImage.fromData(data))
            self.preview.setPixmap(pixmap.scaled(self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            self.status_label.setText("Preview ready.")

        worker.signals.finished.connect(done)
        worker.signals.failed.connect(lambda error: self.preview.setText(f"Preview unavailable: {error}"))
        self.start_worker(worker)

    def process_selected_exam(self) -> None:
        workspace = self.state["workspace"]
        if not workspace:
            QMessageBox.warning(self, "No exam selected", "Choose an exam first.")
            return
        self.extract_button.setEnabled(False)
        worker = Worker(lambda: process_workspace(self.config_for_root(self.state["root"]), workspace.path, self.answer_combo.currentData(), self.form_edit.text().strip() or "0", self.pdf_combo.currentData()))
        worker.signals.finished.connect(lambda _result: (self.extract_button.setEnabled(True), self.load_workspace(workspace)))
        worker.signals.failed.connect(lambda error: (self.extract_button.setEnabled(True), QMessageBox.critical(self, "Extraction failed", f"{error}\n\nCheck that the PDF is readable and that the selected exam folder is writable.")))
        self.start_worker(worker)

    def process_batch_checked(self) -> None:
        selected = [self.exam_list.item(index).data(Qt.ItemDataRole.UserRole) for index in range(self.exam_list.count()) if self.exam_list.item(index).checkState() == Qt.CheckState.Checked]
        if not selected and self.state["workspace"]:
            selected = [self.state["workspace"]]
        if not selected or not self.state["root"]:
            QMessageBox.warning(self, "No exams selected", "Select at least one exam.")
            return
        worker = Worker(lambda: process_workspaces(self.config_for_root(self.state["root"]), selected))
        worker.signals.finished.connect(lambda _result: self.populate_tests())
        worker.signals.failed.connect(lambda error: QMessageBox.critical(self, "Batch processing failed", f"{error}\n\nCheck the PDFs and answer keys, then reload the exam list."))
        self.start_worker(worker)

    def launch_ai(self) -> None:
        workspace = self.state["workspace"]
        if not workspace:
            QMessageBox.warning(self, "No exam selected", "Choose an exam first.")
            return
        provider, command = self.ai_provider_combo.currentData()

        def launch():
            prompt = generate_workspace_prompt(self.config_for_root(self.state["root"]), workspace.path, "web" if provider.kind == "web" else "local")
            if provider.kind == "web":
                if self.config.provider.open_browser and not open_web_provider(provider):
                    raise RuntimeError(f"Could not open {provider.label} in the browser.")
            else:
                send_to_provider(provider, command, prompt)
            return prompt

        self.launch_ai_button.setEnabled(False)
        worker = Worker(launch)
        worker.signals.finished.connect(lambda prompt: (self.launch_ai_button.setEnabled(True), QMessageBox.information(self, "Prompt ready", f"Created prompt at:\n{prompt}")))
        worker.signals.failed.connect(lambda error: (self.launch_ai_button.setEnabled(True), QMessageBox.critical(self, "Could not launch AI provider", error)))
        self.start_worker(worker)

    def checked_play_workspaces(self) -> list:
        selected = [self.play_list.item(index).data(Qt.ItemDataRole.UserRole) for index in range(self.play_list.count()) if self.play_list.item(index).checkState() == Qt.CheckState.Checked]
        return selected or ([self.state["workspace"]] if self.state["workspace"] else [])

    def update_summary(self) -> None:
        selected = self.checked_play_workspaces()
        total = 0
        for workspace in selected:
            try:
                total += len(load_questions(workspace.questions_path))
            except (OSError, ValidationError):
                pass
        self.summary.setText(f"{len(selected)} exam(s), {total} question(s) ready\n{'Mixed mode' if self.mix_checkbox.isChecked() else 'Standard mode'}")

    def select_all_exams(self) -> None:
        for index in range(self.play_list.count()):
            self.play_list.item(index).setCheckState(Qt.CheckState.Checked)
        self.update_summary()

    def clear_all_exams(self) -> None:
        for index in range(self.play_list.count()):
            self.play_list.item(index).setCheckState(Qt.CheckState.Unchecked)
        self.update_summary()

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
            QMessageBox.warning(self, "No exams selected", "Select at least one exam.")
            return
        root = self.state["root"] or selected[0].path.parent
        self.play_button.setEnabled(False)
        self.export_button.setEnabled(False)

        def build():
            run = assemble_run(selected, mix=self.mix_checkbox.isChecked())
            output = root / "runs" / f"{run.name}.json"
            write_run_questions(run, output)
            html = custom_path or output.with_suffix(".html")
            build_run_standalone_quiz(run, html)
            opened = bool(not custom_path and webbrowser.open(html.as_uri()))
            return run, html, opened

        worker = Worker(build)

        def done(result):
            run, html, opened = result
            self.play_button.setEnabled(True)
            self.export_button.setEnabled(True)
            note = "" if opened or custom_path else " The browser could not be opened automatically."
            QMessageBox.information(self, "Quiz ready", f"Created {len(run.questions)} question(s).\nSaved to:\n{html}.{note}")

        def failed(error):
            self.play_button.setEnabled(True)
            self.export_button.setEnabled(True)
            QMessageBox.critical(self, "Could not build quiz", f"{error}\n\nMake sure the selected exams contain valid questions.md files.")

        worker.signals.finished.connect(done)
        worker.signals.failed.connect(failed)
        self.start_worker(worker)

    def open_runs_folder(self) -> None:
        if not self.state["root"]:
            QMessageBox.warning(self, "No exam folder", "Choose an exam folder first.")
            return
        runs = self.state["root"] / "runs"
        runs.mkdir(parents=True, exist_ok=True)
        webbrowser.open(runs.as_uri())


def main() -> int:
    application = QApplication.instance() or QApplication([])
    # MainWindow applies and persists the user's selected theme.
    window = MainWindow()
    window.show()
    return application.exec()


QuizBuilderWindow = MainWindow
