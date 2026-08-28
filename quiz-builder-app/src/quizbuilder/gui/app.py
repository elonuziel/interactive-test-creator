from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import webbrowser
import threading

from PySide6.QtCore import QSettings, QThreadPool, Qt, QTimer
from PySide6.QtGui import QCursor, QGuiApplication, QImage, QKeySequence, QPixmap, QShortcut, QAction
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
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
    QMenu,
    QProgressBar,
    QRadioButton,
    QSpinBox,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..batch import discover_batch
from ..commands import generate_workspace_prompt, process_workspace, process_workspaces
from ..super_batch import SuperBatchPlan, SuperBatchItem, build_plan, classify_plan_item, default_decision, process_plan
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
from .dialogs import (
    AnswerMatrixDialog,
    CliAgentGuideDialog,
    SuperBatchDialog,
    SuperBatchProgressDialog,
    SuperBatchSummaryDialog,
    WelcomeDialog,
)
from .question_editor import QuestionEditorWidget
from .styles import DARK_STYLESHEET, LITE_STYLESHEET
from .web_batch_dialog import WebAIBatchDialog
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
        self.setMinimumSize(780, 520)
        self.resize(1120, 780)
        self.dark_mode = self.settings.value("dark_mode", False, type=bool)
        self.setStyleSheet(DARK_STYLESHEET if self.dark_mode else LITE_STYLESHEET)
        self._build_ui()
        self._show_welcome_if_needed()
        self._connect_signals()
        self._restore_session()

    def start_worker(self, worker: Worker) -> None:
        self._active_workers.add(worker)
        self._set_worker_busy(True)

        def _remove(result_or_err=None) -> None:
            self._active_workers.discard(worker)
            self._set_worker_busy(bool(self._active_workers))

        worker.signals.finished.connect(_remove)
        worker.signals.failed.connect(_remove)
        self.thread_pool.start(worker)

    def toggle_theme(self) -> None:
        self.dark_mode = not self.dark_mode
        self.settings.setValue("dark_mode", self.dark_mode)
        self.setStyleSheet(DARK_STYLESHEET if self.dark_mode else LITE_STYLESHEET)
        self.theme_button.setText("☀️ Light" if self.dark_mode else "🌙 Dark")

    # ------------------------------------------------------------------ helpers

    def _set_status(self, text: str, kind: str = "info") -> None:
        """Update the status bar with optional color feedback."""
        colors: dict[str, str] = {
            "success": "color: #22c55e; font-weight: 500;",
            "error":   "color: #ef4444; font-weight: 500;",
            "busy":    "color: #f59e0b;",
            "info":    "",
        }
        self.status_label.setStyleSheet(colors.get(kind, ""))
        self.status_label.setText(text)

    def _set_worker_busy(self, busy: bool) -> None:
        """Show or hide the indeterminate progress bar in the status bar."""
        if hasattr(self, "status_progress"):
            self.status_progress.setVisible(busy)

    def _update_tab_labels(self) -> None:
        """Refresh tab title badges with live counts."""
        q_total = len(self.state.get("questions", []))
        ready = sum(
            1
            for i in range(self.play_list.count())
            if self.play_list.item(i).checkState() == Qt.CheckState.Checked
        )
        self.tabs.setTabText(1, f"Review questions ({q_total})" if q_total else "Review questions")
        self.tabs.setTabText(2, f"Play or export ({ready} ready)" if ready else "Play or export")

    def _recent_folders(self) -> list[str]:
        return self.settings.value("recent_folders", [], type=list) or []

    def _add_recent_folder(self, path: Path) -> None:
        existing = self._recent_folders()
        entry = str(path)
        if entry in existing:
            existing.remove(entry)
        existing.insert(0, entry)
        self.settings.setValue("recent_folders", existing[:5])

    def _show_recent_menu(self) -> None:
        menu = QMenu(self)
        recents = self._recent_folders()
        if not recents:
            menu.addAction("No recent folders").setEnabled(False)
        else:
            for path_str in recents:
                action = menu.addAction(Path(path_str).name)
                action.setToolTip(path_str)
                action.setData(path_str)
        chosen = menu.exec(QCursor.pos())
        if chosen and chosen.data():
            if not self.confirm_discard_changes():
                return
            self.state["root"] = Path(chosen.data())
            self.settings.setValue("last_exam_folder", chosen.data())
            self.populate_tests()

    def _on_questions_reordered(self) -> None:
        """Sync state["questions"] after a drag-drop reorder in the question list."""
        questions = self.state["questions"]
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
            self.state["questions"] = new_order
            self.state["dirty"] = True
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

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(14, 12, 14, 12)
        root_layout.setSpacing(10)

        top_bar = QFrame()
        top_bar.setObjectName("topBar")
        top_layout = QHBoxLayout(top_bar)
        self.root_label = QLabel("Exam folder: (not selected)")
        self.root_label.setToolTip("Choose the parent folder containing your exam folders.")
        self.choose_root_btn = QPushButton("Choose exam folder…")
        self.choose_root_btn.setToolTip("Select the parent folder that contains your exam projects.")
        self.recent_btn = QPushButton("▼ Recent")
        self.recent_btn.setToolTip("Open a recently used exam folder.")
        self.recent_btn.setMaximumWidth(82)
        self.refresh_root_btn = QPushButton("⟳ Reload")
        self.refresh_root_btn.setToolTip("Scan the selected folder again for exam projects.")
        self.theme_button = QPushButton("☀️ Light" if self.dark_mode else "🌙 Dark")
        self.theme_button.setToolTip("Toggle between dark and light theme.")
        self.theme_button.setMaximumWidth(88)
        self.theme_button.clicked.connect(self.toggle_theme)
        top_layout.addWidget(self.root_label, 1)
        top_layout.addWidget(self.choose_root_btn)
        top_layout.addWidget(self.recent_btn)
        top_layout.addWidget(self.refresh_root_btn)
        top_layout.addWidget(self.theme_button)
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
        self.status_progress = QProgressBar()
        self.status_progress.setRange(0, 0)  # indeterminate
        self.status_progress.setMaximumWidth(130)
        self.status_progress.setMaximumHeight(14)
        self.status_progress.setTextVisible(False)
        self.status_progress.setVisible(False)
        status_layout.addWidget(self.status_label, 1)
        status_layout.addWidget(self.status_progress)
        root_layout.addWidget(status_bar)

    def _build_extract_tab(self) -> None:
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        
        self.extract_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.extract_splitter.setChildrenCollapsible(False)

        self.exam_group = QGroupBox("1. Choose an exam")
        left = QVBoxLayout(self.exam_group)
        self.exam_search = QLineEdit()
        self.exam_search.setPlaceholderText("Search exams...")
        self.exam_list = QListWidget()
        self.batch_button = QPushButton("Process selected exams")
        
        super_batch_row = QHBoxLayout()
        self.super_batch_button = QPushButton("Super Batch (local AI)")
        self.super_batch_button.setToolTip("Review and generate questions.md for multiple exams automatically using a detected local CLI AI.")
        self.super_batch_info_btn = QPushButton("ℹ️")
        self.super_batch_info_btn.setMaximumWidth(32)
        self.super_batch_info_btn.setToolTip("Why use a local CLI AI agent? Click to learn the advantages and see how to install one.")
        self.super_batch_info_btn.clicked.connect(self.show_cli_agent_guide)
        super_batch_row.addWidget(self.super_batch_button, 1)
        super_batch_row.addWidget(self.super_batch_info_btn)

        left.addWidget(self.exam_search)
        left.addWidget(self.exam_list, 1)
        left.addWidget(self.batch_button)

        self.web_batch_button = QPushButton("🌐 Web AI Batch")
        self.web_batch_button.setToolTip("Step-by-step batch assistant for ChatGPT, Claude, Gemini Web, and Google AI Studio (1 PDF at a time with auto prompt copying and answer merging).")
        left.addWidget(self.web_batch_button)
        left.addLayout(super_batch_row)
        self.extract_splitter.addWidget(self.exam_group)

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
        self.extract_button.setObjectName("primary")
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
        
        self.ai_info_btn = QPushButton("ℹ️")
        self.ai_info_btn.setMaximumWidth(32)
        self.ai_info_btn.setToolTip("What is a CLI AI agent? Click to learn the advantages and how to install one.")
        self.ai_info_btn.clicked.connect(self.show_cli_agent_guide)

        self.answer_combo = QComboBox()
        self.answer_combo.addItem("No answer key", None)
        self.browse_answer_button = QPushButton("Choose file...")
        self.browse_answer_button.setToolTip("Select a custom CSV or Excel (XLS/XLSX) answer key")
        self.form_edit = QLineEdit(self.config.default_form)
        self.form_edit.setMaximumWidth(70)
        self.preview = QLabel("No exam preview available")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(200, 150)
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
        ai_row.addWidget(self.ai_info_btn)
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

        extract_scroll = QScrollArea()
        extract_scroll.setWidgetResizable(True)
        extract_scroll.setFrameShape(QFrame.Shape.NoFrame)
        extract_scroll.setWidget(self.extract_group)
        self.extract_splitter.addWidget(extract_scroll)

        self.extract_splitter.setStretchFactor(0, 4)
        self.extract_splitter.setStretchFactor(1, 6)
        tab_layout.addWidget(self.extract_splitter)
        self.tabs.addTab(tab, "Choose & extract")

    def _build_review_tab(self) -> None:
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        
        self.review_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.review_splitter.setChildrenCollapsible(False)

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
        self.tabs.addTab(tab, "Review questions")

    def _build_export_tab(self) -> None:
        tab = QWidget()
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        
        self.export_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.export_splitter.setChildrenCollapsible(False)

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
        self.export_splitter.addWidget(selection_group)

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
        self.tabs.addTab(tab, "Play or export")

    def _connect_signals(self) -> None:
        self.choose_root_btn.clicked.connect(self.choose_folder)
        self.refresh_root_btn.clicked.connect(self.reload_folder)
        self.recent_btn.clicked.connect(self._show_recent_menu)
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
        self.web_batch_button.clicked.connect(self.open_web_batch_wizard)
        self.super_batch_button.clicked.connect(self.open_super_batch)
        self.ai_provider_combo.currentIndexChanged.connect(self._on_ai_provider_changed)
        self.launch_ai_button.clicked.connect(self.launch_ai)
        self.preview_button.clicked.connect(self.preview_first_page)
        self.next_review_button.clicked.connect(lambda: self.tabs.setCurrentIndex(1))
        self.question_filter_edit.textChanged.connect(self.refresh_question_list)
        self.filter_incomplete_checkbox.toggled.connect(self.refresh_question_list)
        self.question_list.currentRowChanged.connect(self.show_question)
        self.question_list.model().rowsMoved.connect(lambda *_: self._on_questions_reordered())
        self.help_button.clicked.connect(self.show_markdown_help)
        self.question_editor.changed.connect(self.mark_dirty)
        self.question_editor.crop_requested.connect(self.open_image_cropper)
        self.move_up_button.clicked.connect(self.move_question_up)
        self.move_down_button.clicked.connect(self.move_question_down)
        self.duplicate_button.clicked.connect(self.duplicate_question)
        self.add_question_button.clicked.connect(self.add_question)
        self.delete_question_button.clicked.connect(self.delete_question)
        self.matrix_button.clicked.connect(self.open_answer_matrix)
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
        QShortcut(QKeySequence("Ctrl+D"), self).activated.connect(self.duplicate_question)
        QShortcut(QKeySequence("Alt+Up"), self).activated.connect(self.move_question_up)
        QShortcut(QKeySequence("Alt+Down"), self).activated.connect(self.move_question_down)
        QShortcut(QKeySequence("Delete"), self.question_list).activated.connect(self.delete_question)

    def show_markdown_help(self) -> None:
        QMessageBox.information(self, "questions.md format", "Each question uses this format:\n\n## Question 1\n\nQuestion text\n\n- First choice\n- Second choice\n- Third choice\n- Fourth choice\n\nAnswer: A\n\nUse pageImage: path/to/page.png on its own line when a question references a diagram or table.")

    def _show_welcome_if_needed(self) -> None:
        if self.settings.value("welcome_shown", False, type=bool):
            return
        if os.environ.get("QT_QPA_PLATFORM") == "offscreen" or QGuiApplication.platformName() == "offscreen":
            return
        dialog = WelcomeDialog(self)
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
        for name, splitter in (
            ("extract_splitter", getattr(self, "extract_splitter", None)),
            ("review_splitter", getattr(self, "review_splitter", None)),
            ("export_splitter", getattr(self, "export_splitter", None)),
        ):
            if splitter is not None:
                state = self.settings.value(name)
                if state:
                    splitter.restoreState(state)

    def closeEvent(self, event) -> None:
        if not self.confirm_discard_changes():
            event.ignore()
            return
        self.settings.setValue("window_geometry", self.saveGeometry())
        for name, splitter in (
            ("extract_splitter", getattr(self, "extract_splitter", None)),
            ("review_splitter", getattr(self, "review_splitter", None)),
            ("export_splitter", getattr(self, "export_splitter", None)),
        ):
            if splitter is not None:
                self.settings.setValue(name, splitter.saveState())
        event.accept()

    def config_for_root(self, root: Path) -> Config:
        return Config(root, self.config.scripts_root, self.config.default_form, self.config.default_discard_pages, self.config.auto_build, self.config.super_batch_workers, self.config.super_batch_ai_mode, self.config.provider)

    def mark_dirty(self) -> None:
        if self.state["workspace"] is not None:
            self.state["dirty"] = True
            ws_name = self.state["workspace"].name
            self.setWindowTitle(f"Interactive Quiz Builder — {ws_name} *")

    def save_active_question(self) -> None:
        if self.state["index"] >= 0:
            self.question_editor.collect(self.state["questions"][self.state["index"]])

    def save_test(self, show_message=True) -> bool:
        if not self.state["workspace"]:
            if show_message:
                QMessageBox.warning(self, "No exam selected", "Choose an exam first.")
            return False
        was_dirty = self.state["dirty"]
        self.save_active_question()
        try:
            write_questions(self.state["workspace"].path / "questions.md", self.state["questions"])
        except OSError as exc:
            LOGGER.exception("Could not save questions.md")
            self._set_status(f"Could not save questions.md: {exc}", "error")
            if show_message:
                QMessageBox.critical(self, "Could not save", f"{exc}\n\nCheck that the exam folder is writable and try again.")
            return False
        self.state["dirty"] = False
        ws_name = self.state["workspace"].name if self.state["workspace"] else ""
        self.setWindowTitle(f"Interactive Quiz Builder — {ws_name}" if ws_name else "Interactive Quiz Builder")
        self.refresh_question_list()
        self.update_summary()
        self._set_status("Changes saved.", "success")
        if show_message and was_dirty:
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
            self._add_recent_folder(self.state["root"])
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
        self.setWindowTitle(f"Interactive Quiz Builder — {workspace.name}")
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
        self.question_list.blockSignals(True)
        self.question_list.clear()
        filter_text = self.question_filter_edit.text().strip().lower()
        incomplete_only = self.filter_incomplete_checkbox.isChecked()

        valid = 0
        total = len(self.state["questions"])

        for index, question in enumerate(self.state["questions"]):
            text = (question.get("question", "") or "").strip()
            options = question.get("options", [])
            has_ans = isinstance(question.get("correctIndex"), int) and 0 <= question.get("correctIndex", -1) < len(options)
            ready = bool(text and len(options) >= 2 and has_ans)
            if ready:
                valid += 1

            if incomplete_only and ready:
                continue
            if filter_text and filter_text not in text.lower():
                continue

            prefix = "✅" if ready else "⚠️"
            display_text = f"{prefix} {index + 1}. {text[:55] + '...' if len(text) > 55 else (text or 'Empty question')}"
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, index)
            self.question_list.addItem(item)

        self.question_list.blockSignals(False)

        if total == 0:
            self.question_status.setText("No questions in this exam")
            self.question_status.setStyleSheet("color: var(--muted-color); font-weight: bold;")
        elif valid == total:
            self.question_status.setText(f"📊 {total} Questions — All {valid} Complete ✅")
            self.question_status.setStyleSheet("color: #4ade80; font-weight: bold;")
        else:
            self.question_status.setText(f"📊 {total} Questions (✅ {valid} Complete | ⚠️ {total - valid} Incomplete)")
            self.question_status.setStyleSheet("color: #facc15; font-weight: bold;")

        self._update_tab_labels()
        self._update_drag_drop_mode()

    def show_question(self, row: int) -> None:
        self.save_active_question()
        item = self.question_list.item(row) if row >= 0 else None
        real_index = item.data(Qt.ItemDataRole.UserRole) if item is not None else row
        if real_index is None:
            real_index = row
        self.state["index"] = real_index
        workspace = self.state["workspace"]
        workspace_path = workspace.path if workspace else None
        q = self.state["questions"][real_index] if 0 <= real_index < len(self.state["questions"]) else None
        self.question_editor.set_question(q, workspace_path=workspace_path)

    def _select_question_by_real_index(self, target_index: int) -> None:
        for row in range(self.question_list.count()):
            item = self.question_list.item(row)
            if item and item.data(Qt.ItemDataRole.UserRole) == target_index:
                self.question_list.setCurrentRow(row)
                return

    def add_question(self) -> None:
        self.save_active_question()
        self.state["questions"].append({"question": "", "options": ["", "", "", ""], "correctIndex": 0})
        self.state["dirty"] = True
        self.refresh_question_list()
        self._select_question_by_real_index(len(self.state["questions"]) - 1)

    def delete_question(self) -> None:
        index = self.state["index"]
        if index < 0 or QMessageBox.question(self, "Delete question", "Delete the selected question?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        self.save_active_question()
        self.state["questions"].pop(index)
        self.state["dirty"] = True
        self.refresh_question_list()
        next_index = min(index, len(self.state["questions"]) - 1)
        self._select_question_by_real_index(next_index)

    def move_question_up(self) -> None:
        idx = self.state["index"]
        if idx <= 0 or idx >= len(self.state["questions"]):
            return
        self.save_active_question()
        self.state["questions"][idx - 1], self.state["questions"][idx] = (
            self.state["questions"][idx],
            self.state["questions"][idx - 1],
        )
        self.state["index"] = idx - 1
        self.state["dirty"] = True
        self.refresh_question_list()
        self._select_question_by_real_index(idx - 1)

    def move_question_down(self) -> None:
        idx = self.state["index"]
        if idx < 0 or idx >= len(self.state["questions"]) - 1:
            return
        self.save_active_question()
        self.state["questions"][idx + 1], self.state["questions"][idx] = (
            self.state["questions"][idx],
            self.state["questions"][idx + 1],
        )
        self.state["index"] = idx + 1
        self.state["dirty"] = True
        self.refresh_question_list()
        self._select_question_by_real_index(idx + 1)

    def duplicate_question(self) -> None:
        idx = self.state["index"]
        if idx < 0 or idx >= len(self.state["questions"]):
            return
        self.save_active_question()
        import copy
        dup = copy.deepcopy(self.state["questions"][idx])
        self.state["questions"].insert(idx + 1, dup)
        self.state["index"] = idx + 1
        self.state["dirty"] = True
        self.refresh_question_list()
        self._select_question_by_real_index(idx + 1)

    def open_answer_matrix(self) -> None:
        self.save_active_question()
        questions = self.state["questions"]
        if not questions:
            QMessageBox.information(self, "Answer Matrix", "No questions available in this exam.")
            return

        exam_name = self.state["workspace"].name if self.state["workspace"] else "Exam"
        dialog = AnswerMatrixDialog(
            self,
            questions=questions,
            exam_name=exam_name,
            on_save=self.save_test,
            on_dirty=self.mark_dirty,
        )
        dialog.exec()
        if dialog.dirty:
            self.mark_dirty()
        self.refresh_question_list()
        if 0 <= self.state["index"] < len(questions):
            self.show_question(self.state["index"])

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
        self.status_label.setText(f"Extracting questions from {workspace.name}…")

        def execute():
            return process_workspace(
                self.config_for_root(self.state["root"]),
                workspace.path,
                self.answer_combo.currentData(),
                self.form_edit.text().strip() or "0",
                self.pdf_combo.currentData(),
            )

        def done(_result) -> None:
            self.extract_button.setEnabled(True)
            self.load_workspace(workspace)
            if self.state.get("questions"):
                self._set_status(f"Extracted {len(self.state['questions'])} question(s). Opening Review tab…", "success")
                QTimer.singleShot(400, lambda: self.tabs.setCurrentIndex(1))
            else:
                self._set_status("Extraction complete — no questions found. Try an AI prompt.", "info")

        def failed(error) -> None:
            self.extract_button.setEnabled(True)
            QMessageBox.critical(self, "Extraction failed", f"{error}\n\nCheck that the PDF is readable and that the selected exam folder is writable.")

        worker = Worker(execute)
        worker.signals.finished.connect(done)
        worker.signals.failed.connect(failed)
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

    def open_web_batch_wizard(self, custom_workspaces: list | None = None) -> None:
        if not self.state["root"]:
            QMessageBox.warning(self, "No exam folder", "Choose an exam folder before starting Web AI Batch.")
            return

        if custom_workspaces is not None:
            workspaces = custom_workspaces
        else:
            selected = [
                self.exam_list.item(index).data(Qt.ItemDataRole.UserRole)
                for index in range(self.exam_list.count())
                if self.exam_list.item(index).checkState() == Qt.CheckState.Checked
            ]
            if not selected:
                if self.state["workspace"]:
                    selected = [self.state["workspace"]]
                else:
                    selected = [
                        self.exam_list.item(index).data(Qt.ItemDataRole.UserRole)
                        for index in range(self.exam_list.count())
                        if self.exam_list.item(index).data(Qt.ItemDataRole.UserRole) is not None
                    ]

        if not selected:
            QMessageBox.information(self, "Web AI Batch", "No exams available to process.")
            return

        dialog = WebAIBatchDialog(
            self,
            workspaces=selected,
            config=self.config_for_root(self.state["root"]),
            dark_mode=self.dark_mode,
        )
        dialog.exec()
        self.populate_tests()
        if self.state["workspace"]:
            self.load_workspace(self.state["workspace"])

    def open_super_batch(self, custom_items: list[SuperBatchItem] | None = None) -> None:
        if not self.state["root"]:
            QMessageBox.warning(self, "No exam folder", "Choose an exam folder before starting Super Batch.")
            return
        local = [
            self.ai_provider_combo.itemData(i)
            for i in range(self.ai_provider_combo.count())
            if self.ai_provider_combo.itemData(i) and self.ai_provider_combo.itemData(i)[0].kind in {"local", "freebuff"}
        ]
        if not local:
            QMessageBox.warning(self, "No local CLI AI found", "Super Batch requires a detected local CLI AI provider. Install or configure one, then reload providers.")
            return
        try:
            discard_rule = self.discard_range_edit.text().strip() or self.config.default_discard_pages or "std"
            dialog = SuperBatchDialog(
                self,
                root=self.state["root"],
                config=self.config_for_root(self.state["root"]),
                local_providers=local,
                custom_items=custom_items,
                discard_rule=discard_rule,
            )
            if not dialog.plan.items:
                QMessageBox.information(self, "Super Batch", "No PDF exams were found recursively.")
                return

            if dialog.exec() != QDialog.DialogCode.Accepted:
                return

            selected_items = dialog.get_selected_items()
            if not selected_items:
                QMessageBox.information(self, "Super Batch", "No exams were selected to process.")
                return

            exec_plan = SuperBatchPlan(dialog.plan.root, tuple(selected_items))
            params = dialog.get_execution_params()
            provider = params["provider"]
            command = params["command"]

            self.super_batch_button.setEnabled(False)
            self.status_label.setText(f"Super Batch starting: {len(exec_plan.items)} exam(s)...")
            cancel_event = threading.Event()

            progress_dialog = SuperBatchProgressDialog(self, exec_plan, provider.label, cancel_event)

            def on_progress(updated_item: SuperBatchItem):
                QTimer.singleShot(0, lambda: progress_dialog.update_item_progress(updated_item))

            def execute():
                return process_plan(
                    exec_plan,
                    provider,
                    command,
                    workers=params["workers"],
                    ai_mode=params["ai_mode"],
                    context_mode=params["context_mode"],
                    discard_pages=params["discard_pages"],
                    clean_digital=params["clean_digital"],
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
        self.status_label.setText(f"Super Batch complete: {len(succeeded)}/{len(results)} succeeded.")

        summary_dialog = SuperBatchSummaryDialog(
            self,
            results=results,
            config=self.config_for_root(self.state["root"]),
            on_retry_failed=lambda failed_items: self.open_super_batch(custom_items=failed_items),
        )
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

    def reload_ai_providers(self) -> None:
        current_data = self.ai_provider_combo.currentData()
        self.ai_provider_combo.clear()
        local_items = detect_providers(self.config.provider.freebuff_commands)
        for provider, command in local_items:
            self.ai_provider_combo.addItem(f"Local: {provider.label} ({command})", (provider, command))
        for provider in WEB_PROVIDERS:
            self.ai_provider_combo.addItem(f"Web: {provider.label}", (provider, None))
        if current_data:
            for i in range(self.ai_provider_combo.count()):
                if self.ai_provider_combo.itemData(i) == current_data:
                    self.ai_provider_combo.setCurrentIndex(i)
                    break
        self._on_ai_provider_changed()

    def show_cli_agent_guide(self) -> None:
        def on_reload() -> int:
            self.reload_ai_providers()
            return sum(
                1 for i in range(self.ai_provider_combo.count())
                if "Local:" in self.ai_provider_combo.itemText(i)
            )

        dialog = CliAgentGuideDialog(self, on_reload_providers=on_reload)
        dialog.exec()

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
        self._update_tab_labels()

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
        self.start_worker(worker)

    def open_image_cropper(self) -> None:
        workspace = self.state["workspace"]
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
