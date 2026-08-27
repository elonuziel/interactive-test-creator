from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import webbrowser
import threading

from PySide6.QtCore import QSettings, QThreadPool, Qt, QTimer
from PySide6.QtGui import QGuiApplication, QImage, QKeySequence, QPixmap, QShortcut, QAction
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHeaderView,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QProgressBar,
    QSpinBox,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..batch import discover_batch
from ..commands import generate_workspace_prompt, process_workspace, process_workspaces
from ..super_batch import build_plan, classify_plan_item, default_decision, process_plan
from ..config import Config
from ..documents import classify_pdf, clean_pdf, convert_docx_with_soffice, describe_page_cleaning, DocumentError
from ..exporter import build_run_standalone_quiz, build_standalone_quiz
from ..markdown import dump_questions, write_questions
from ..preview import render_pdf_page
from ..providers import WEB_PROVIDERS, detect_providers, open_web_provider
from ..prompts import extract_markdown_from_response, send_to_provider
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
        self.super_batch_button = QPushButton("Super Batch (local AI)")
        self.super_batch_button.setToolTip("Review and generate questions.md for multiple exams using a detected local CLI AI.")
        left.addWidget(self.exam_search)
        left.addWidget(self.exam_list, 1)
        left.addWidget(self.batch_button)
        left.addWidget(self.super_batch_button)
        layout.addWidget(self.exam_group, 4)

        self.extract_group = QGroupBox("2. Prepare questions (saved as questions.md)")
        right = QVBoxLayout(self.extract_group)
        self.current_exam_title = QLabel("Choose an exam from the list")
        self.pdf_combo = QComboBox()
        self.pdf_combo.addItem("No exam file selected", None)
        self.browse_pdf_button = QPushButton("Choose file...")
        self.browse_pdf_button.setToolTip("Select a custom PDF or Word (DOCX) exam file")
        pdf_row = QHBoxLayout()
        pdf_row.addWidget(QLabel("Exam file:"))
        pdf_row.addWidget(self.pdf_combo, 1)
        pdf_row.addWidget(self.browse_pdf_button)
        self.detection_title = QLabel("PDF type: waiting for an exam")
        self.detection_description = QLabel("Choose an exam to check whether its text can be extracted automatically.")
        self.detection_description.setWordWrap(True)
        self.extract_button = QPushButton("Extract questions from PDF")
        self.ai_hint = QLabel("Digital PDFs can be extracted automatically. Scanned PDFs need an AI prompt. Results are saved as questions.md.")
        self.ai_hint.setWordWrap(True)
        self.ai_provider_combo = QComboBox()
        local_items = detect_providers(self.config.provider.freebuff_commands)
        for provider, command in local_items:
            self.ai_provider_combo.addItem(f"Local: {provider.label} ({command})", (provider, command))
        for provider in WEB_PROVIDERS:
            self.ai_provider_combo.addItem(f"Web: {provider.label}", (provider, None))
        self.launch_ai_button = QPushButton("Create AI prompt")
        self._on_ai_provider_changed()
        self.launch_ai_button.setToolTip("Create a prompt for extracting questions into questions.md.")
        self.answer_combo = QComboBox()
        self.answer_combo.addItem("No answer key", None)
        self.browse_answer_button = QPushButton("Choose file...")
        self.browse_answer_button.setToolTip("Select a custom CSV or Excel (XLS/XLSX) answer key")
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

        # Clean PDF section for scanned exams
        self.clean_group = QGroupBox("Clean PDF (Discard blank & cover pages)")
        clean_layout = QVBoxLayout(self.clean_group)
        self.clean_hint = QLabel("Discard blank/cover pages for clean AI prompts & accurate OCR.")
        self.clean_hint.setWordWrap(True)
        clean_layout.addWidget(self.clean_hint)

        preset_row = QHBoxLayout()
        self.preset_std_button = QPushButton("🧹 Standard clean (std)")
        self.preset_std_button.setToolTip("Discards cover pages 1-4 and even pages (6, 8, 10...)")
        self.preset_even_button = QPushButton("📄 Even pages")
        self.preset_odd_button = QPushButton("📄 Odd pages")
        self.preset_clear_button = QPushButton("☐ Reset")
        preset_row.addWidget(self.preset_std_button)
        preset_row.addWidget(self.preset_even_button)
        preset_row.addWidget(self.preset_odd_button)
        preset_row.addWidget(self.preset_clear_button)
        clean_layout.addLayout(preset_row)

        range_row = QHBoxLayout()
        range_row.addWidget(QLabel("Discard pages:"))
        self.discard_range_edit = QLineEdit("std")
        self.discard_range_edit.setPlaceholderText("e.g. std, 1-4, 6, 8")
        range_row.addWidget(self.discard_range_edit, 1)
        self.clean_pdf_button = QPushButton("🧹 Create clean PDF")
        self.clean_pdf_button.setToolTip("Creates <name>_clean.pdf without discarded pages")
        range_row.addWidget(self.clean_pdf_button)
        clean_layout.addLayout(range_row)

        self.clean_summary_label = QLabel("Select an exam to calculate kept pages.")
        self.clean_summary_label.setStyleSheet("color: var(--muted-color); font-size: 11px;")
        clean_layout.addWidget(self.clean_summary_label)
        right.addWidget(self.clean_group)
        answer_row = QHBoxLayout()
        answer_row.addWidget(QLabel("Answer key (optional):"))
        answer_row.addWidget(self.answer_combo, 1)
        answer_row.addWidget(self.browse_answer_button)
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
        self.open_questions_button = QPushButton("Open questions file...")
        self.open_questions_button.setToolTip("Load questions from any questions.md or questions.json file")
        list_layout.addWidget(self.question_status)
        list_layout.addWidget(self.question_list, 1)
        list_layout.addWidget(self.add_question_button)
        list_layout.addWidget(self.delete_question_button)
        list_layout.addWidget(self.open_questions_button)
        layout.addWidget(list_group, 4)
        edit_group = QGroupBox("Review and edit questions")
        edit_layout = QVBoxLayout(edit_group)
        self.question_editor = QuestionEditorWidget()
        self.save_button = QPushButton("Save questions.md")
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
        self.pdf_combo.currentIndexChanged.connect(self._on_pdf_selection_changed)
        self.browse_pdf_button.clicked.connect(self.choose_custom_exam_file)
        self.browse_answer_button.clicked.connect(self.choose_custom_answer_key)
        self.preset_std_button.clicked.connect(lambda: self.set_discard_preset("std"))
        self.preset_even_button.clicked.connect(lambda: self.set_discard_preset("even"))
        self.preset_odd_button.clicked.connect(lambda: self.set_discard_preset("odd"))
        self.preset_clear_button.clicked.connect(lambda: self.set_discard_preset(""))
        self.discard_range_edit.textChanged.connect(lambda: self.update_clean_summary())
        self.clean_pdf_button.clicked.connect(self.run_clean_pdf)
        self.open_questions_button.clicked.connect(self.import_custom_questions_file)
        self.save_as_button.clicked.connect(self.save_questions_as)
        self.extract_button.clicked.connect(self.process_selected_exam)
        self.batch_button.clicked.connect(self.process_batch_checked)
        self.super_batch_button.clicked.connect(self.open_super_batch)
        self.ai_provider_combo.currentIndexChanged.connect(self._on_ai_provider_changed)
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
        return Config(root, self.config.scripts_root, self.config.default_form, self.config.default_discard_pages, self.config.auto_build, self.config.super_batch_workers, self.config.super_batch_ai_mode, self.config.provider)

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
        for doc in sorted(list(workspace.path.glob("*.pdf")) + list(workspace.path.glob("*.docx")), key=lambda item: item.name.casefold()):
            if self.pdf_combo.findData(doc) < 0:
                self.pdf_combo.addItem(doc.name, doc)
        if not self.pdf_combo.count():
            self.pdf_combo.addItem("No exam file selected", None)
        self.answer_combo.clear()
        self.answer_combo.addItem("No answer key", None)
        for answer in sources.answer_keys:
            self.answer_combo.addItem(answer.name, answer)
        for ans in sorted(list(workspace.path.glob("*.csv")) + list(workspace.path.glob("*.xlsx")) + list(workspace.path.glob("*.xls")), key=lambda item: item.name.casefold()):
            if self.answer_combo.findData(ans) < 0:
                self.answer_combo.addItem(ans.name, ans)
        self.state["loading"] = False
        self._load_questions(workspace)
        pdf = self.pdf_combo.currentData()
        if pdf and Path(pdf).is_file():
            self.check_pdf_classification(Path(pdf))
            self.preview_first_page(Path(pdf))
        else:
            self.detection_title.setText("No exam file found")
            self.detection_description.setText("Add a PDF to this folder, or click Choose file... to select an exam.")
        self.state["dirty"] = False
        self.setWindowTitle("Interactive Quiz Builder")
        self.update_summary()

    def choose_custom_exam_file(self) -> None:
        workspace = self.state["workspace"]
        start_dir = str(workspace.path) if workspace else (str(self.state["root"]) if self.state["root"] else "")
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Choose Exam File (PDF or Word DOCX)",
            start_dir,
            "Exam Files (*.pdf *.docx);;PDF Files (*.pdf);;Word Documents (*.docx);;All Files (*)",
        )
        if filename:
            path = Path(filename)
            if path.suffix.lower() == ".docx":
                try:
                    pdf_path = convert_docx_with_soffice(path, path.parent)
                    path = pdf_path
                except Exception as exc:
                    QMessageBox.warning(self, "DOCX Conversion", f"Could not convert DOCX to PDF automatically: {exc}\n\nPlease convert to PDF manually.")
            label = f"{path.name} ({path.parent.name})" if workspace and path.parent != workspace.path else path.name
            idx = self.pdf_combo.findData(path)
            if idx < 0:
                self.pdf_combo.addItem(label, path)
                idx = self.pdf_combo.count() - 1
            self.pdf_combo.setCurrentIndex(idx)
            self._on_pdf_selection_changed()

    def choose_custom_answer_key(self) -> None:
        workspace = self.state["workspace"]
        start_dir = str(workspace.path) if workspace else (str(self.state["root"]) if self.state["root"] else "")
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Choose Answer Key (CSV, Excel, Markdown, or JSON)",
            start_dir,
            "Answer Key Files (*.csv *.xlsx *.xls *.json *.md);;CSV Files (*.csv);;Excel Files (*.xlsx *.xls);;Markdown / JSON Answers (*.md *.json);;All Files (*)",
        )
        if filename:
            path = Path(filename)
            label = f"{path.name} ({path.parent.name})" if workspace and path.parent != workspace.path else path.name
            idx = self.answer_combo.findData(path)
            if idx < 0:
                self.answer_combo.addItem(label, path)
                idx = self.answer_combo.count() - 1
            self.answer_combo.setCurrentIndex(idx)

    def import_custom_questions_file(self) -> None:
        if not self.confirm_discard_changes():
            return
        workspace = self.state["workspace"]
        start_dir = str(workspace.path) if workspace else (str(self.state["root"]) if self.state["root"] else "")
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Open Questions File (Markdown or JSON)",
            start_dir,
            "Question Files (*.md *.json);;Markdown Files (*.md);;JSON Files (*.json);;All Files (*)",
        )
        if filename:
            path = Path(filename)
            try:
                self.state["questions"] = load_questions(path)
                self.state["dirty"] = True
                self.refresh_question_list()
                if self.state["questions"]:
                    self.question_list.setCurrentRow(0)
                else:
                    self.question_editor.clear()
                self.status_label.setText(f"Loaded {len(self.state['questions'])} question(s) from {path.name}.")
                self.update_summary()
            except Exception as exc:
                QMessageBox.critical(self, "Could not load questions", f"Error reading {path.name}:\n{exc}")

    def save_questions_as(self) -> None:
        self.save_active_question()
        workspace = self.state["workspace"]
        default_name = "questions.md" if not workspace else f"{workspace.name}_questions.md"
        start_dir = str(workspace.path / default_name) if workspace else default_name
        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Save Questions As",
            start_dir,
            "Markdown Files (*.md);;JSON Files (*.json);;All Files (*)",
        )
        if filename:
            path = Path(filename)
            try:
                if path.suffix.lower() == ".json":
                    path.write_text(json.dumps(self.state["questions"], ensure_ascii=False, indent=2), encoding="utf-8")
                else:
                    dump_questions(self.state["questions"], path)
                self.status_label.setText(f"Saved {len(self.state['questions'])} question(s) to {path.name}.")
            except Exception as exc:
                QMessageBox.critical(self, "Could not save questions", f"Error saving {path.name}:\n{exc}")

    def _on_pdf_selection_changed(self) -> None:
        if self.state["loading"]:
            return
        pdf = self.pdf_combo.currentData()
        if pdf and Path(pdf).is_file():
            self.check_pdf_classification(Path(pdf))
            self.preview_first_page(Path(pdf))
            self.update_clean_summary()
        else:
            self.detection_title.setText("No exam file selected")
            self.detection_description.setText("Select a PDF or DOCX exam file to analyze.")
            self.preview.setText("No exam preview available")
            self.clean_summary_label.setText("Select an exam to calculate kept pages.")

    def set_discard_preset(self, preset: str) -> None:
        self.discard_range_edit.setText(preset)
        self.update_clean_summary()

    def update_clean_summary(self) -> None:
        pdf = self.pdf_combo.currentData()
        if not pdf or not Path(pdf).is_file() or Path(pdf).suffix.lower() != ".pdf":
            self.clean_summary_label.setText("Select a PDF exam to calculate kept pages.")
            return
        info = describe_page_cleaning(Path(pdf), self.discard_range_edit.text().strip())
        if info["total"] == 0:
            self.clean_summary_label.setText("Could not inspect PDF page count.")
        else:
            self.clean_summary_label.setText(
                f"Total {info['total']} page(s) → Keeping {info['kept_count']} page(s) ({info['discarded_count']} discarded)"
            )

    def run_clean_pdf(self) -> None:
        workspace = self.state["workspace"]
        if not workspace:
            QMessageBox.warning(self, "No exam selected", "Choose an exam from the list first.")
            return
        pdf = self.pdf_combo.currentData()
        if not pdf or not Path(pdf).is_file():
            QMessageBox.warning(self, "No PDF selected", "Choose a valid PDF file to clean.")
            return
        source_pdf = Path(pdf)
        clean_name = f"{source_pdf.stem}_clean.pdf" if not source_pdf.stem.endswith("_clean") else source_pdf.name
        clean_path = workspace.path / clean_name
        discard_spec = self.discard_range_edit.text().strip() or "std"

        self.clean_pdf_button.setEnabled(False)
        self.status_label.setText("Cleaning PDF and generating clean pages...")

        def execute():
            total, kept = clean_pdf(source_pdf, clean_path, discard_spec)
            return total, kept, clean_path

        worker = Worker(execute)

        def done(result):
            total, kept, output_path = result
            self.clean_pdf_button.setEnabled(True)
            idx = self.pdf_combo.findData(output_path)
            if idx < 0:
                self.pdf_combo.addItem(output_path.name, output_path)
                idx = self.pdf_combo.count() - 1
            self.pdf_combo.setCurrentIndex(idx)
            self.status_label.setText(f"Cleaned PDF saved: kept {kept} of {total} pages in {output_path.name}.")
            QMessageBox.information(
                self,
                "Clean PDF Created",
                f"Successfully created clean PDF with {kept} of {total} pages kept:\n\n{output_path}\n\nIt is now selected as the active exam file.",
            )

        def failed(error):
            self.clean_pdf_button.setEnabled(True)
            QMessageBox.critical(self, "Could not clean PDF", f"{error}\n\nCheck the discard page range.")

        worker.signals.finished.connect(done)
        worker.signals.failed.connect(failed)
        self.start_worker(worker)

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
        workspace = self.state["workspace"]
        workspace_path = workspace.path if workspace else None
        q = self.state["questions"][index] if 0 <= index < len(self.state["questions"]) else None
        self.question_editor.set_question(q, workspace_path=workspace_path)

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

    def open_super_batch(self) -> None:
        if not self.state["root"]:
            QMessageBox.warning(self, "No exam folder", "Choose an exam folder before starting Super Batch.")
            return
        local = [self.ai_provider_combo.itemData(i) for i in range(self.ai_provider_combo.count()) if self.ai_provider_combo.itemData(i) and self.ai_provider_combo.itemData(i)[0].kind in {"local", "freebuff"}]
        if not local:
            QMessageBox.warning(self, "No local CLI AI found", "Super Batch requires a detected local CLI AI provider. Install or configure one, then reload providers.")
            return
        try:
            plan = build_plan(self.state["root"])
            for item in plan.items:
                classify_plan_item(item)
                if item.decision is None:
                    item.decision = default_decision(item)
            if not plan.items:
                QMessageBox.information(self, "Super Batch", "No PDF exams were found recursively.")
                return

            dialog = QDialog(self)
            dialog.setWindowTitle("Review Super Batch Exams")
            dialog.resize(1050, 680)
            layout = QVBoxLayout(dialog)

            layout.addWidget(QLabel("Review discovered exams below. Configure settings, uncheck unwanted items, and click <b>Start Super Batch</b>."))

            form = QFormLayout()
            provider_combo = QComboBox()
            for provider_option, command_option in local:
                provider_combo.addItem(f"{provider_option.label} ({command_option})", (provider_option, command_option))
            form.addRow("Local CLI AI:", provider_combo)

            workers = QSpinBox()
            workers.setRange(1, 16)
            workers.setValue(max(1, self.config.super_batch_workers))
            form.addRow("Parallel workers:", workers)

            mode = QComboBox()
            mode.addItem("Two phases (overview + questions)", "two_phase")
            mode.addItem("Single invocation (all-in-one)", "single_invocation")
            mode.setCurrentIndex(0 if self.config.super_batch_ai_mode == "two_phase" else 1)
            form.addRow("AI mode:", mode)

            discard_rule = self.discard_range_edit.text().strip() or self.config.default_discard_pages or "std"
            clean = QCheckBox(f"Apply digital PDF page cleaning (rule: '{discard_rule}')")
            clean.setChecked(True)
            clean.setToolTip(f"Cleans digital PDFs using the '{discard_rule}' rule before question extraction.")
            form.addRow("PDF cleanup:", clean)

            context_mode = QComboBox()
            context_mode.addItem("AI OCR from PDF path (recommended)", "path")
            context_mode.addItem("AI OCR with local text hint", "extracted")
            context_mode.setCurrentIndex(0)
            context_mode.setToolTip("Scanned PDFs always go through the AI for OCR. Choose whether to provide the PDF path alone or add locally extracted text as a hint.")
            form.addRow("Scanned PDF context:", context_mode)
            layout.addLayout(form)

            # Bulk Actions Toolbar
            btn_bar = QHBoxLayout()
            btn_select_all = QPushButton("Select All")
            btn_deselect_all = QPushButton("Deselect All")
            btn_set_zero_test = QPushButton("Set Digital to Zero-Test")
            btn_auto_match = QPushButton("Auto-Match Keys")
            btn_bar.addWidget(btn_select_all)
            btn_bar.addWidget(btn_deselect_all)
            btn_bar.addWidget(btn_set_zero_test)
            btn_bar.addWidget(btn_auto_match)
            btn_bar.addStretch()
            layout.addLayout(btn_bar)

            # Review Table
            table = QTableWidget(len(plan.items), 8, dialog)
            table.setHorizontalHeaderLabels([
                "Include", "Exam Name", "Type", "Metadata", "Answer Key", "Decision", "Overwrite?", "Dedicated Instructions"
            ])
            table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
            table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
            table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
            table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
            table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)

            rows_data = []
            for row_idx, item in enumerate(plan.items):
                # 0: Include checkbox
                include_box = QCheckBox()
                include_box.setChecked(True)
                include_widget = QWidget()
                include_layout = QHBoxLayout(include_widget)
                include_layout.addWidget(include_box)
                include_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                include_layout.setContentsMargins(0, 0, 0, 0)
                table.setCellWidget(row_idx, 0, include_widget)

                # 1: Exam Name
                name_item = QTableWidgetItem(item.overview.name)
                name_item.setToolTip(f"PDF: {item.overview.pdf}\nWorkspace: {item.overview.workspace}")
                table.setItem(row_idx, 1, name_item)

                # 2: Type
                type_str = "📄 Digital" if item.overview.is_digital else "📷 Scanned"
                type_item = QTableWidgetItem(type_str)
                table.setItem(row_idx, 2, type_item)

                # 3: Metadata
                info_parts = []
                if item.overview.test_number:
                    info_parts.append(f"Test {item.overview.test_number}")
                if item.overview.year:
                    info_parts.append(item.overview.year)
                if item.overview.variant:
                    info_parts.append(f"Moed {item.overview.variant.upper()}")
                table.setItem(row_idx, 3, QTableWidgetItem(" | ".join(info_parts) or "-"))

                # 4: Answer Key
                key_combo = QComboBox()
                key_combo.addItem("No answer key", None)
                for candidate in item.answer_keys:
                    label = candidate.path.name
                    if candidate.answers:
                        label += f" ({len(candidate.answers)} ans)"
                    key_combo.addItem(label, candidate.path)

                # Auto-select the matched answer key in the dropdown
                if item.selected_answer_key:
                    for i in range(key_combo.count()):
                        if key_combo.itemData(i) == item.selected_answer_key:
                            key_combo.setCurrentIndex(i)
                            break
                elif item.answer_keys and item.answer_keys[0].score >= 0:
                    key_combo.setCurrentIndex(1)
                    item.selected_answer_key = item.answer_keys[0].path
                table.setCellWidget(row_idx, 4, key_combo)

                # 5: Decision
                decision_combo = QComboBox()
                decision_combo.addItem("Use answer key", "use_answer_key")
                decision_combo.addItem("Generate only (unanswered)", "generate_only")
                decision_combo.addItem("Zero test (all A)", "zero_test")
                if key_combo.currentIndex() > 0 or item.selected_answer_key:
                    decision_combo.setCurrentIndex(0)
                elif item.overview.is_digital:
                    decision_combo.setCurrentIndex(2)
                else:
                    decision_combo.setCurrentIndex(1)
                table.setCellWidget(row_idx, 5, decision_combo)

                # Connect key_combo changes to automatically update decision
                def on_key_changed(idx: int, d_combo=decision_combo, itm=item):
                    if idx > 0:
                        d_combo.setCurrentIndex(0)  # Use answer key
                    else:
                        d_combo.setCurrentIndex(2 if itm.overview.is_digital else 1)
                key_combo.currentIndexChanged.connect(on_key_changed)

                # 6: Overwrite
                exists = (item.overview.workspace / "questions.md").exists()
                overwrite_box = QCheckBox("⚠️ Exists" if exists else "New")
                overwrite_box.setChecked(not exists)
                if exists:
                    overwrite_box.setToolTip(f"questions.md already exists in {item.overview.workspace}. Check to overwrite.")
                overwrite_widget = QWidget()
                overwrite_layout = QHBoxLayout(overwrite_widget)
                overwrite_layout.addWidget(overwrite_box)
                overwrite_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                overwrite_layout.setContentsMargins(0, 0, 0, 0)
                table.setCellWidget(row_idx, 6, overwrite_widget)

                # 7: Instructions
                instructions = QLineEdit()
                instructions.setPlaceholderText("Optional dedicated prompt instructions...")
                table.setCellWidget(row_idx, 7, instructions)

                rows_data.append((item, include_box, key_combo, decision_combo, overwrite_box, instructions))

            # Connect bulk actions
            def select_all(checked: bool):
                for _, inc, _, _, _, _ in rows_data:
                    inc.setChecked(checked)

            def set_all_zero_test():
                for itm, _, k_combo, dec, _, _ in rows_data:
                    if itm.overview.is_digital:
                        k_combo.setCurrentIndex(0)
                        dec.setCurrentIndex(2)

            def auto_match_all():
                for itm, _, k_combo, dec_combo, _, _ in rows_data:
                    if itm.answer_keys and itm.answer_keys[0].score >= 0:
                        k_combo.setCurrentIndex(1)
                        dec_combo.setCurrentIndex(0)

            btn_select_all.clicked.connect(lambda: select_all(True))
            btn_deselect_all.clicked.connect(lambda: select_all(False))
            btn_set_zero_test.clicked.connect(set_all_zero_test)
            btn_auto_match.clicked.connect(auto_match_all)

            layout.addWidget(table)

            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
            buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Start Super Batch")
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)

            if dialog.exec() != QDialog.DialogCode.Accepted:
                return

            selected_items = []
            for item, include_box, key_combo, decision_combo, overwrite_box, instructions in rows_data:
                if not include_box.isChecked():
                    continue
                item.selected_answer_key = key_combo.currentData()
                item.decision = decision_combo.currentData()
                item.overwrite = overwrite_box.isChecked()
                item.dedicated_instructions = instructions.text().strip()
                if item.decision == "use_answer_key" and not item.selected_answer_key and not item.overview.is_digital:
                    item.decision = "generate_only"
                selected_items.append(item)

            if not selected_items:
                QMessageBox.information(self, "Super Batch", "No exams were selected to process.")
                return

            exec_plan = SuperBatchPlan(plan.root, tuple(selected_items))
            self.super_batch_button.setEnabled(False)
            self.status_label.setText(f"Super Batch starting: {len(exec_plan.items)} exam(s)...")
            provider, command = provider_combo.currentData()
            cancel_event = threading.Event()

            # Live Progress Dialog
            progress_dialog = QDialog(self)
            progress_dialog.setWindowTitle("Super Batch in Progress")
            progress_dialog.resize(800, 500)
            progress_dialog.setModal(True)
            p_layout = QVBoxLayout(progress_dialog)

            header_label = QLabel(f"<b>Running Super Batch:</b> {len(exec_plan.items)} exam(s) with {provider.label}")
            p_layout.addWidget(header_label)

            p_bar = QProgressBar()
            p_bar.setRange(0, len(exec_plan.items))
            p_bar.setValue(0)
            p_bar.setFormat("%v / %m exams completed (%p%)")
            p_layout.addWidget(p_bar)

            p_table = QTableWidget(len(exec_plan.items), 4, progress_dialog)
            p_table.setHorizontalHeaderLabels(["Exam", "Type", "Status", "Details"])
            p_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            p_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            p_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            p_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

            item_row_map = {}
            for r_idx, itm in enumerate(exec_plan.items):
                item_row_map[id(itm)] = r_idx
                p_table.setItem(r_idx, 0, QTableWidgetItem(itm.overview.name))
                p_table.setItem(r_idx, 1, QTableWidgetItem("Digital" if itm.overview.is_digital else "Scanned"))
                p_table.setItem(r_idx, 2, QTableWidgetItem("⏳ Pending"))
                p_table.setItem(r_idx, 3, QTableWidgetItem(""))
            p_layout.addWidget(p_table)

            cancel_btn = QPushButton("Cancel Super Batch")
            p_layout.addWidget(cancel_btn)
            cancel_btn.clicked.connect(lambda: (cancel_event.set(), cancel_btn.setEnabled(False), cancel_btn.setText("Cancelling… waiting for active jobs to terminate")))

            completed_count = [0]

            def on_progress(updated_item: SuperBatchItem):
                def update_ui():
                    r_idx = item_row_map.get(id(updated_item))
                    if r_idx is not None:
                        status_icons = {
                            "pending": "⏳ Pending",
                            "classifying": "🔍 Classifying",
                            "extracting": "⚙️ Extracting",
                            "generating": "🤖 Generating",
                            "saved": "✅ Saved",
                            "failed": "❌ Failed",
                            "cancelled": "🚫 Cancelled",
                        }
                        status_text = status_icons.get(updated_item.status, updated_item.status)
                        p_table.setItem(r_idx, 2, QTableWidgetItem(status_text))
                        detail = updated_item.error or (f"Saved questions.md in {updated_item.overview.workspace.name}" if updated_item.status == "saved" else "")
                        p_table.setItem(r_idx, 3, QTableWidgetItem(detail))
                        if updated_item.status in {"saved", "failed", "cancelled"}:
                            completed_count[0] += 1
                            p_bar.setValue(completed_count[0])
                        self.status_label.setText(f"Super Batch: {updated_item.overview.name} — {updated_item.status}")

                QTimer.singleShot(0, update_ui)

            def execute():
                return process_plan(
                    exec_plan,
                    provider,
                    command,
                    workers=workers.value(),
                    ai_mode=mode.currentData(),
                    context_mode=context_mode.currentData(),
                    discard_pages=discard_rule if clean.isChecked() else "",
                    clean_digital=clean.isChecked(),
                    cancel_event=cancel_event,
                    progress=on_progress,
                )

            worker = Worker(execute)
            worker.signals.finished.connect(lambda results: (progress_dialog.accept(), self._finish_super_batch(results)))
            worker.signals.failed.connect(lambda err: (progress_dialog.accept(), self.super_batch_button.setEnabled(True), QMessageBox.critical(self, "Super Batch Failed", str(err))))
            self.start_worker(worker)
            progress_dialog.exec()

        except Exception as exc:
            self.super_batch_button.setEnabled(True)
            QMessageBox.critical(self, "Could not prepare Super Batch", str(exc))

    def _finish_super_batch(self, results) -> None:
        self.super_batch_button.setEnabled(True)
        succeeded = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        self.status_label.setText(f"Super Batch complete: {len(succeeded)}/{len(results)} succeeded.")

        # Summary Dialog
        summary_dialog = QDialog(self)
        summary_dialog.setWindowTitle("Super Batch Results")
        summary_dialog.resize(750, 480)
        s_layout = QVBoxLayout(summary_dialog)

        headline = QLabel(f"<h3>Super Batch Complete</h3><p><b>{len(succeeded)}</b> succeeded, <b>{len(failed)}</b> failed out of <b>{len(results)}</b> total exams.</p>")
        s_layout.addWidget(headline)

        res_table = QTableWidget(len(results), 3, summary_dialog)
        res_table.setHorizontalHeaderLabels(["Exam", "Result", "Output / Error Details"])
        res_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        res_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        res_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        for idx, res in enumerate(results):
            res_table.setItem(idx, 0, QTableWidgetItem(res.item.overview.name))
            res_table.setItem(idx, 1, QTableWidgetItem("✅ Succeeded" if res.success else "❌ Failed"))
            detail_text = str(res.output) if res.success else str(res.error)
            res_table.setItem(idx, 2, QTableWidgetItem(detail_text))
        s_layout.addWidget(res_table)

        btn_box = QHBoxLayout()
        if succeeded:
            build_html_btn = QPushButton("⚡ Build HTML Quizzes for Successful Items")
            btn_box.addWidget(build_html_btn)

            def build_htmls():
                build_html_btn.setEnabled(False)
                build_html_btn.setText("Building HTML quizzes...")
                built_count = 0
                errors = []
                for res in succeeded:
                    try:
                        build_standalone_quiz(res.item.overview.workspace, self.config.scripts_root)
                        built_count += 1
                    except Exception as e:
                        errors.append(f"{res.item.overview.name}: {e}")
                build_html_btn.setText(f"Built {built_count} HTML Quiz(zes)")
                if errors:
                    QMessageBox.warning(summary_dialog, "HTML Quiz Build Warning", f"Built {built_count} quizzes, but encountered errors:\n" + "\n".join(errors))
                else:
                    QMessageBox.information(summary_dialog, "HTML Quizzes Built", f"Successfully built {built_count} standalone HTML quiz(zes)!")

            build_html_btn.clicked.connect(build_htmls)

        close_btn = QPushButton("Done")
        close_btn.clicked.connect(summary_dialog.accept)
        btn_box.addStretch()
        btn_box.addWidget(close_btn)
        s_layout.addLayout(btn_box)

        summary_dialog.exec()
        self.populate_tests()

    def _on_ai_provider_changed(self) -> None:
        data = self.ai_provider_combo.currentData()
        if not data:
            return
        provider, command = data
        if provider.kind == "web":
            self.launch_ai_button.setText(f"🌐 Open {provider.label}")
            self.launch_ai_button.setToolTip(f"Generate prompt and open {provider.label} in browser (prompt is automatically copied to clipboard).")
        else:
            self.launch_ai_button.setText(f"⚡ Generate with {provider.label}")
            self.launch_ai_button.setToolTip(f"Directly pipe prompt into {provider.label} ({command}) and save questions.md in exam folder.")

    def launch_ai(self) -> None:
        workspace = self.state["workspace"]
        if not workspace:
            QMessageBox.warning(self, "No exam selected", "Choose an exam first.")
            return
        data = self.ai_provider_combo.currentData()
        if not data:
            QMessageBox.warning(self, "No provider selected", "Choose an AI provider first.")
            return
        provider, command = data

        self.launch_ai_button.setEnabled(False)
        is_web = provider.kind == "web"
        if is_web:
            self.status_label.setText(f"Generating prompt for {provider.label}...")
        else:
            self.status_label.setText(f"Running {provider.label} to generate questions directly into {workspace.name}...")

        def launch():
            prompt = generate_workspace_prompt(
                self.config_for_root(self.state["root"]),
                workspace.path,
                "web" if is_web else "local",
            )
            if is_web:
                if self.config.provider.open_browser and not open_web_provider(provider):
                    raise RuntimeError(f"Could not open {provider.label} in the browser.")
                return "web", prompt, None
            else:
                stdout = send_to_provider(provider, command, prompt, cwd=workspace.path)
                questions_file = workspace.path / "questions.md"
                if stdout:
                    extracted = extract_markdown_from_response(stdout)
                    if not questions_file.exists() or any(k in extracted for k in ("## Question", "### שאלה", "## שאלה")):
                        questions_file.write_text(extracted, encoding="utf-8")
                return "local", prompt, questions_file

        def done(result):
            kind, prompt, questions_file = result
            self.launch_ai_button.setEnabled(True)
            if kind == "web":
                try:
                    prompt_text = prompt.read_text(encoding="utf-8")
                    QApplication.clipboard().setText(prompt_text)
                except Exception:
                    pass
                self.status_label.setText(f"Prompt copied to clipboard. Opened {provider.label} in browser.")
                QMessageBox.information(
                    self,
                    "AI Prompt Ready",
                    f"Prompt generated and copied to your clipboard!\n\nSaved at:\n{prompt}\n\nPaste it into {provider.label} and save the result as questions.md in the exam folder.",
                )
            else:
                self._load_questions(workspace)
                self.update_summary()
                q_count = len(self.state["questions"])
                if q_count > 0:
                    self.status_label.setText(f"Generated {q_count} question(s) with {provider.label} in questions.md.")
                    self.tabs.setCurrentIndex(1)
                    QMessageBox.information(
                        self,
                        "Questions Created Directly",
                        f"Successfully generated {q_count} question(s) with {provider.label} directly in:\n\n{questions_file}\n\nThey are now loaded and ready for review in Tab 2.",
                    )
                else:
                    self.status_label.setText(f"{provider.label} finished, but no questions were parsed into questions.md.")
                    QMessageBox.warning(
                        self,
                        "No Questions Parsed",
                        f"{provider.label} completed execution, but no questions could be parsed into questions.md.\n\nPrompt used:\n{prompt}",
                    )

        def failed(error):
            self.launch_ai_button.setEnabled(True)
            self.status_label.setText(f"Failed to execute {provider.label}.")
            QMessageBox.critical(self, "AI Provider Execution Failed", f"Error running {provider.label}:\n\n{error}")

        worker = Worker(launch)
        worker.signals.finished.connect(done)
        worker.signals.failed.connect(failed)
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
